"""Stdlib-only sandbox fixture. Not an architecture or robot control policy."""
import ast
import base64
import hashlib
import io
import json
import math
import re
import struct
import zipfile
import zlib


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_no_paths(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('path', 'relative_path', 'artifacts', 'evidence_root'):
                raise ValueError('Operator artifact reference crossed boundary')
            check_no_paths(item)
    elif isinstance(value, list):
        for item in value:
            check_no_paths(item)
    elif isinstance(value, str) and (re.match(r'^[A-Za-z]:[\\/]', value)
                                    or re.match(r'^/(mnt|home|Users|tmp|work|code)(/|$)', value)):
        raise ValueError('Operator filesystem path crossed boundary')


def decode_png(blob):
    if blob[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Bad PNG signature')
    cursor=8; compressed=[]; dimensions=None; ended=False
    while cursor < len(blob):
        if cursor+12 > len(blob):raise ValueError('Truncated PNG chunk')
        length=struct.unpack('!I',blob[cursor:cursor+4])[0]
        tag=blob[cursor+4:cursor+8]; body=blob[cursor+8:cursor+8+length]
        if cursor+12+length > len(blob):raise ValueError('Truncated PNG payload')
        crc=struct.unpack('!I',blob[cursor+8+length:cursor+12+length])[0]
        if zlib.crc32(tag+body) != crc:raise ValueError('PNG CRC mismatch')
        if tag==b'IHDR':
            width,height,bits,color,compression,filtering,interlace=struct.unpack('!2I5B',body)
            if not 0<width<=640 or not 0<height<=480 or (bits,color,compression,filtering,interlace)!=(8,2,0,0,0):
                raise ValueError('Unexpected native PNG format')
            dimensions=(width,height)
        elif tag==b'IDAT':compressed.append(body)
        elif tag==b'IEND':ended=True
        cursor+=12+length
    if dimensions is None or not ended:raise ValueError('Incomplete PNG')
    width,height=dimensions; expected=height*(width*3+1)
    inflater=zlib.decompressobj(); pixels=inflater.decompress(b''.join(compressed),expected+1)
    if len(pixels)!=expected or not inflater.eof:raise ValueError('PNG decoded size mismatch')
    rows=[]
    for y in range(height):
        start=y*(width*3+1)
        # The shared gateway emits PNG filter0; no other filter is inferred.
        if pixels[start]!=0:raise ValueError('Unexpected gateway PNG row filter')
        rows.append(pixels[start+1:start+1+width*3])
    data=b''.join(rows)
    return {'width_px':width,'height_px':height,'decoded_bytes':len(data),
            'decoded_sha256':digest(data),'minimum_channel':min(data),'maximum_channel':max(data)}


def decode_depth(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        if archive.namelist()!=['depth_m.npy']:raise ValueError('Unexpected NPZ entries')
        item=archive.getinfo('depth_m.npy')
        if item.file_size > 640*480*4+4096:raise ValueError('Oversized NPY')
        npy=archive.read(item)
    if npy[:6]!=b'\x93NUMPY':raise ValueError('Bad NPY signature')
    version=tuple(npy[6:8])
    if version==(1,0):offset=10;length=struct.unpack('<H',npy[8:10])[0]
    elif version in ((2,0),(3,0)):offset=12;length=struct.unpack('<I',npy[8:12])[0]
    else:raise ValueError('Unexpected NPY version')
    header=ast.literal_eval(npy[offset:offset+length].decode('utf-8'))
    if header.get('fortran_order') is not False or header.get('descr') not in ('<f4','=f4'):
        raise ValueError('Expected row-major float32 depth')
    shape=header.get('shape')
    if not isinstance(shape,tuple) or len(shape)!=2 or not 0<shape[0]<=480 or not 0<shape[1]<=640:
        raise ValueError('Bad depth dimensions')
    data=npy[offset+length:]
    if len(data)!=shape[0]*shape[1]*4:raise ValueError('Depth decoded size mismatch')
    minimum=math.inf; maximum=-math.inf
    for (value,) in struct.iter_unpack('<f',data):
        if not math.isfinite(value) or value<=0:raise ValueError('Nonpositive/nonfinite physical depth')
        minimum=min(minimum,value);maximum=max(maximum,value)
    return {'width_px':shape[1],'height_px':shape[0],'decoded_bytes':len(data),
            'decoded_sha256':digest(data),'minimum_depth_m':minimum,'maximum_depth_m':maximum}


def inspect_response(response):
    check_no_paths(response)
    if response.get('status')!='ok':raise ValueError('Raw response was not delivered: '+str(response.get('status')))
    camera=response['camera'];calibration=response['calibration']
    if camera not in ('overhead','oblique','wrist') or calibration.get('camera',camera)!=camera:
        raise ValueError('Camera identity mismatch')
    if not response['capture_id'].startswith(camera+'-'):raise ValueError('Capture identity mismatch')
    if abs(response['capture_sim_time_s']-response['capture_telemetry']['sim_time_s'])>1e-9:
        raise ValueError('Capture timestamp mismatch')
    intrinsics=calibration['intrinsics_px'];rotation=calibration['world_from_camera_rotation']
    position=calibration['camera_position_world_m']
    if len(intrinsics)!=3 or any(len(row)!=3 for row in intrinsics) or len(rotation)!=3 or any(len(row)!=3 for row in rotation) or len(position)!=3:
        raise ValueError('Malformed camera calibration')
    if not all(math.isfinite(v) for row in intrinsics+rotation+[position] for v in row):raise ValueError('Nonfinite camera calibration')
    if intrinsics[0][0]<=0 or intrinsics[1][1]<=0:raise ValueError('Nonpositive focal length')
    images={}
    if set(response['images'])!={'rgb','depth'}:raise ValueError('Both native modalities required')
    for name,value in response['images'].items():
        blob=base64.b64decode(value['data'],validate=True)
        if len(blob)!=value['bytes'] or digest(blob)!=value['sha256']:raise ValueError('Encoded artifact identity mismatch')
        if value['encoding']!=('png-base64' if name=='rgb' else 'npz-base64'):raise ValueError('Unknown encoding')
        decoded=(decode_png if name=='rgb' else decode_depth)(blob)
        if any(decoded[key]!=calibration[key] for key in ('width_px','height_px')):raise ValueError('Dimensions disagree with calibration')
        images[name]={**decoded,'encoded_sha256':value['sha256'],'encoded_bytes':len(blob)}
    return {'camera':camera,'request_id':response['request_id'],'capture_id':response['capture_id'],
            'capture_sequence':response['capture_sequence'],'capture_sim_time_s':response['capture_sim_time_s'],
            'calibration_sha256':digest(json.dumps(calibration,sort_keys=True,separators=(',',':'),allow_nan=False).encode()),
            'images':images,'operator_paths_absent':True,'decoded_in_stdlib_only_fixture':True}


class Candidate:
    def __init__(self,kind,episode_dir,persistent):
        self.events=[];self.received=[]
    def step(self,packet):
        camera=packet['camera']
        if camera not in ('overhead','oblique','wrist'):raise ValueError('Unsupported fixture camera')
        return {'type':'sensor_request','request_id':'fixture-'+camera,'camera':camera,'modalities':['rgb','depth']}
    def accept_model(self,response):raise ValueError('Fixture does not request models')
    def accept_feedback(self,feedback):raise ValueError('Fixture does not command robot actions')
    def accept_sensor(self,response):
        result=inspect_response(response);self.received.append(result['camera'])
        self.events.append({'event':'decoded_raw_camera','result':result})
    def drain_events(self):
        events=self.events;self.events=[];return events
