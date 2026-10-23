"""Small lossless PNG writer; no image manipulation dependency."""
import struct
import zlib
from pathlib import Path

def write_png(path,rgb):
    h,w,_=rgb.shape
    def chunk(tag,data):return struct.pack('!I',len(data))+tag+data+struct.pack('!I',zlib.crc32(tag+data))
    raw=b''.join(b'\0'+row.tobytes() for row in rgb)
    content=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
    Path(path).write_bytes(content)
