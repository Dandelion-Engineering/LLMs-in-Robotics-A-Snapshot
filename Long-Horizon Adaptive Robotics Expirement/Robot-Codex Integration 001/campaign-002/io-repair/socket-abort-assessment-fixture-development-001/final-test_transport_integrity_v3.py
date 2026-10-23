"""Receipt adversaries: no sockets, native processes, models or simulation."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import transport_integrity_v3 as subject
from test_client_quiescence import make_records as quiescence_records


def raw_json(value):
    return json.dumps(value, indent=2).encode() + b'\n'


def stream(raw):
    return {'bytes': len(raw), 'sha256': subject.digest(raw)}


def h2(upload, download, active=False):
    return {'schema': 'campaign002-passive-h2-3', 'error': None,
            'preface_complete': True, 'settings_complete': True, 'frames_complete': True,
            'headers_complete': True, 'frame_complete':{'upload':True,'download':True},
            'header_complete':{'upload':True,'download':True},'settings_by_direction':{'upload':True,'download':True},
            'upload_complete':True, 'open_streams': int(active), 'closed_streams': int(not active),
            'last_stream_id': 1, 'retiring': False, 'reset_streams': 0, 'active_stream_ids': [1] if active else [], 'reset_records': [], 'terminal_control_records': [],
            'goaway': {'upload': None, 'download': None}, 'frames': {'upload': 2, 'download': 2},
            'bytes': {'upload': len(upload), 'download': len(download)}, 'max_streams': 1024}


def probe_baseline():
    return (b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'+bytes.fromhex('000000040000000000')
            +bytes.fromhex('000000040100000000')+bytes.fromhex('000008060000000000')+b'C02V3H2!')


def probe_shutdown():
    return bytes.fromhex('0000080700000000000000000000000000')


def terminal_record():
    return {'direction':'upload', 'stream_id':1, 'error_code':8, 'frame':3, 'end_byte':55,
            'normal_close':{'opened_upload':{'frame':2,'end_byte':42},
                            'upload_closed':{'frame':2,'end_byte':42},
                            'download_closed':{'frame':2,'end_byte':18}},
            'opposite_observed_frames':3}


class Fixture:
    def __init__(self, root, count=2, *, fixed_probe=False, terminal_control=False):
        self.repo, self.stage = root / 'repo', root / 'stage'
        self.stage.mkdir(); (self.stage / 'client').mkdir()
        self.frozen = {'sources': {}}
        for name in tuple(dict.fromkeys(subject.SOURCE_NAMES + subject.client_quiescence.SOURCE_NAMES +
                                       (subject.PROBE_SOURCE_NAME, subject.PREFLIGHT_SOURCE_NAME, subject.BOUNDARY_SOURCE_NAME))):
            p = self.repo / name; p.parent.mkdir(parents=True, exist_ok=True)
            raw = ('fixture source ' + name).encode(); p.write_bytes(raw)
            self.frozen['sources'][name] = stream(raw)
        self.sources = {name: self.frozen['sources'][name] for name in subject.BRIDGE_SOURCE_NAMES}
        self.inside = {name: self.frozen['sources'][subject.CAMPAIGN + 'harness/' + name]
                       for name in ('codehost_inside_v3.py', 'codehost_mux_protocol.py')}
        self.owner = {'schema': 'campaign002-native-owner-1', 'owner_kind': 'model_client',
                      'pid': 123, 'process_creation_filetime': 789,
                      'queried_executable_path': 'C:\\native\\codex.exe',
                      'executable': {'path': 'C:\\native\\codex.exe', 'sha256': 'a'*64,
                                     'bytes': 99, 'file_identity': [1, 2, 99, 456]},
                      'wall_unix_s': 10., 'monotonic_s': 10.}
        self.owner_bound = self.bind('codehost-native-owner-v3.json', raw_json(self.owner))
        self.ready = {'schema': 'campaign002-codehost-owner-ready-3', 'child_pid': 42,
                      'max_connections': 16, 'max_frame_bytes': 65536,
                      'per_channel_queue_bytes': 1048576, 'aggregate_queue_bytes': 4194304,
                      'sources': self.inside}
        self.parent, self.namespace, self.channels = [], [], []
        self.p('open', sources=self.sources, max_connections=16, max_frame_bytes=65536,
               per_channel_queue_bytes=1048576, aggregate_queue_bytes=4194304,
               framing_headroom_bytes=655360,subprocess_reader_limit=32768,client_socket_read_ahead_bytes=0)
        self.p('namespace_started')
        self.n('open', sources=self.inside, max_records=16384, max_metadata_bytes=1048576)
        self.n('child_started', child_pid=42)
        self.n('ready', receipt=self.ready)
        self.frame('incoming', 9, 0, subject.canonical(self.ready))
        self.p('listening', shared_child_pid=42, endpoint=['127.0.0.1', 5000])
        self.p('owner_registered', owner=self.owner, receipt=self.owner_bound)
        for cid in range(1, count+1):
            auth = {'schema': 'campaign002-channel-owner-1', 'owner_pid': 123,
                    'process_creation_filetime': 789, 'queried_executable_path': self.owner['queried_executable_path'],
                    'executable_sha256': 'a'*64, 'executable_file_identity': [1,2,99,456],
                    'client': ['127.0.0.1', 6000+cid], 'server': ['127.0.0.1', 5000], 'tcp_state': 5,
                    'lookup_attempts': 1, 'lookup_elapsed_s': .001,
                    'wall_unix_s': 11., 'monotonic_s': 11.}
            self.p('channel_authenticated', channel_id=cid, authentication=auth, owner_receipt=self.owner_bound)
            self.frame('outgoing', 1, cid)
            self.n('channel_open', channel_id=cid, child_pid=42)
            self.frame('incoming', 2, cid)
            active = (cid != 2) if fixed_probe else cid == count
            flags = 5 if terminal_control and cid == 1 else 4 if active else 5
            settings = b'\0\0\0\4\0\0\0\0\0'
            header = b'\0\0\0\1' + bytes([flags]) + b'\0\0\0\1'
            upload = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n' + settings + header
            download = settings + header
            if terminal_control and cid == 1:
                download += bytes.fromhex('000008060100000000') + b'proof123'
            if fixed_probe:
                upload=probe_baseline()
                download=b'\0\0\0\4\0\0\0\0\0'+b'\0\0\0\4\1\0\0\0\0'+b'\0\0\x08\6\1\0\0\0\0C02V3H2!'
            if fixed_probe:
                for part in (upload[:33],upload[33:42],upload[42:]):self.frame('outgoing',3,cid,part)
            else:self.frame('outgoing',3,cid,upload)
            self.frame('incoming', 3, cid, download)
            if terminal_control and cid == 1:
                cancel = bytes.fromhex('00000403000000000100000008')
                self.frame('outgoing', 3, cid, cancel)
                upload += cancel
                if active:
                    next_stream = bytes.fromhex('000000010400000003')
                    self.frame('outgoing', 3, cid, next_stream)
                    self.frame('incoming', 3, cid, next_stream)
                    upload += next_stream; download += next_stream
            witness = h2(upload, download, active)
            if terminal_control and cid == 1:
                witness.update(frames={'upload':3+int(active), 'download':3+int(active)},
                               closed_streams=1, last_stream_id=3 if active else 1,
                               active_stream_ids=[3] if active else [])
                witness['terminal_control_records'] = [terminal_record()]
            if fixed_probe:
                witness.update(open_streams=0,closed_streams=0,active_stream_ids=[],last_stream_id=0,
                               frames={'upload':3,'download':3})
            terminal = {'schema': 'campaign002-codehost-channel-3', 'channel_id': cid,
                        'qualified': True, 'reason': 'owner_finish' if active else 'clean_idle_eof',
                        'upload': stream(upload), 'download': stream(download), 'h2': witness,
                        'finish_frontier': copy.deepcopy(witness) if active else None,
                        'upload_eof_h2': None, 'download_eof_h2': None, 'error_type': None}
            meters = {'client_read': stream(upload), 'upload': stream(upload),
                      'download': stream(download), 'client_written': stream(download)}
            self.channels.append({'channel_id': cid, 'authentication': auth, 'namespace_closed': terminal,
                                  'meters': meters, 'h2': witness, 'parent_eof': None,
                                  'finish_frontier': copy.deepcopy(witness)})
        idle_channels=[ch for ch in self.channels if ch['namespace_closed']['reason']=='clean_idle_eof']
        live_channels=[ch for ch in self.channels if ch['namespace_closed']['reason']=='owner_finish']
        for channel in idle_channels:
            self.eof_channel(channel, False); self.close_channel(channel)
        self.frontiers = [self.p('channel_finish_frontier', channel_id=channel['channel_id'],
                                  client_finishing=True, h2=channel['finish_frontier'], upload_read_pending=True)
                          for channel in self.channels]
        self.drain_begin = self.p('owner_drain_begin', bound_s=25)
        first_finish = self.frontiers[0] if self.frontiers else self.drain_begin
        self.marker = {'kind':'client_finishing_before_close','schema':'campaign002-client-finishing-1',
                       'wall_unix_s':first_finish['wall_unix_s']-.001,
                       'monotonic_s':first_finish['monotonic_s']-.001}
        self.drain_begin.update(start_monotonic_s=self.marker['monotonic_s'],
                                deadline_monotonic_s=self.marker['monotonic_s']+25)
        self.frame('outgoing',10,0)
        self.nsbegin = self.n('owner_drain_begin',channels=count,bound_s=25)
        self.nsbegin.update(start_monotonic_s=self.nsbegin['monotonic_s'],
                            deadline_monotonic_s=self.nsbegin['monotonic_s']+25)
        for channel in self.channels:
            closed = channel in idle_channels
            self.n('channel_finish_frontier',channel_id=channel['channel_id'],
                   h2=copy.deepcopy(channel['finish_frontier']),already_closed=closed)
            if not closed: channel['h2']['retiring'] = True
        self.frame('incoming',11,0)
        self.n('owner_drain_ack',channels=count)
        self.p('owner_drain_ack')
        if fixed_probe:
            channel=self.channels[0];tail=probe_shutdown()
            self.frame('outgoing',3,1,tail)
            for key in ('client_read','upload'):channel['meters'][key]=stream(probe_baseline()+tail)
            channel['namespace_closed']['upload']=stream(probe_baseline()+tail)
            channel['h2']['bytes']['upload']+=len(tail);channel['h2']['frames']['upload']+=1
            channel['h2']['goaway']['upload']=0
        for channel in live_channels:self.eof_channel(channel,True)
        for channel in self.channels:
            channel['seal_frontier'] = copy.deepcopy(channel['h2'])
            self.p('channel_seal_frontier',channel_id=channel['channel_id'],h2=channel['seal_frontier'])
        self.finishing = self.p('owner_finishing',client_finishing=True,
                                authenticated_channels=count,attempts=count,seal_qualified=True,seal_error_code=None)
        self.frame('outgoing',7,0)
        self.p('owner_input_closed',after_finish_drain=True)
        self.n('owner_finish',channels=count,seal_qualified=True,seal_error_code=None)
        for channel in live_channels:
            channel['namespace_closed']['seal_frontier'] = copy.deepcopy(channel['h2'])
            self.close_channel(channel)
        for name in ('stdout', 'stderr'):
            self.n('child_diagnostic', stream=name, bytes=0, sha256=subject.digest(b''), truncated=False)
        self.finished = self.n('closed', qualified=True, reason='owner_finish', child_pid=42,
            child_exit_before_cleanup=None, child_exit_code=-15, terminate_sent=True, kill_sent=False,
            diagnostic_streams_complete=True, error_type=None, sources=self.inside,
            owner_finish_received=True, stdin_eof=True, owner_input_wait_bound_s=.5,
            owner_drain_received=True,owner_drain_acknowledged=True,owner_drain_timeout_s=25,
            owner_drain_elapsed_s=.2,drain_qualified=True,drain_error_code=None,
            channel_count=count, channels_closed=count, queue_bytes_at_close=0, queue_high_water_bytes=100,
            queue_headroom_bytes=196608, per_channel_queue_maximum_bytes={str(n):100 for n in range(1,count+1)},
            frame_counts={d: sum(x['kind']=='frame' and x['direction']==d for x in self.namespace)
                          for d in ('incoming','outgoing')})
        self.terminal = self.p('namespace_finished', finished=self.finished)
        self.p('namespace_output_closed',after_finished=True)
        self.drain = {key:self.drain_begin[key] for key in ('start_monotonic_s','deadline_monotonic_s','bound_s')}
        self.drain.update(seal_qualified=True,seal_error_code=None,completed_monotonic_s=self.parent[-1]['monotonic_s'])
        self.p('owner_drain_completed',**self.drain)
        self.p('retirement_started')
        self.p('closed', qualified=True, failures=[], accepted=count, denied=0, attempts=count)
        self.receipt = {'schema': 'campaign002-codehost-owner-bridge-3', 'qualified': True,
                        'sources': self.sources, 'exit_code': 0, 'drain':self.drain, 'owner_receipt': self.owner_bound,
                        'owner': self.owner, 'ready': self.ready, 'finished': self.finished,
                        'attempts': count, 'accepted': count, 'denied': 0,
                        'queue_maximum_bytes': 100, 'queued_bytes_at_close': 0,
                        'framing_headroom_bytes':655360,'queue_with_headroom_maximum_bytes':655460,
                        'per_channel_queue_maximum_bytes':{str(n):100 for n in range(1,count+1)},
                        'per_channel_with_headroom_maximum_bytes':{str(n):655460 for n in range(1,count+1)},
                        'channels': self.channels, 'failures': [], 'namespace_records': self.namespace}
        self.retirement = {'qualified': True, 'normal_wait_timed_out': False,
                           'windows_wrapper_killed_after_linux_retired': False, 'windows_exit_code': 0,
                           'observations': [{'retired': True, 'namespace_evidence_available': True,
                             'outer_same_process': False, 'namespace_members': [], 'namespace_ids': [987]}]}
        owner_raw = raw_json(self.owner)
        self.client = [{'kind': 'native_process_owner_registered', 'receipt_bytes': len(owner_raw),
                        'receipt_sha256': subject.digest(owner_raw)},
                       {'kind':'request','method':'initialize','id':1}, self.marker,
                       {'kind': 'client_shutdown', 'exit_code': 0}]

    def bind(self, name, raw):
        (self.stage/name).write_bytes(raw)
        return {'path': Path(name).name, **stream(raw)}

    def p(self, kind, **fields):
        row = {'kind': kind, 'wall_unix_s': 100.+len(self.parent)*.01, 'monotonic_s': 200.+len(self.parent)*.01, **fields}
        self.parent.append(row); return row

    def n(self, kind, **fields):
        row = {'kind':kind, 'schema':subject.NAMESPACE_SCHEMA, 'sequence':len(self.namespace)+1,
               'wall_unix_s':500.+len(self.namespace)*.01, 'monotonic_s':800.+len(self.namespace)*.01, **fields}
        self.namespace.append(row); return row

    def frame(self, direction, kind, cid, payload=b''):
        fields = {'frame_type':kind, 'channel_id':cid, 'payload_bytes':len(payload),
                  'payload_sha256':subject.digest(payload)}
        self.p('frame', direction=direction, **fields)
        self.n('frame', direction={'incoming':'outgoing','outgoing':'incoming'}[direction], **fields)

    def eof_channel(self,channel,finishing):
        cid=channel['channel_id']; terminal=channel['namespace_closed']; witness=copy.deepcopy(channel['h2'])
        channel['parent_eof']=self.p('client_eof',channel_id=cid,client_finishing=finishing,h2=witness)
        self.frame('outgoing',4,cid)
        channel['upload_drained']=self.p('upload_drained',channel_id=cid,meters=copy.deepcopy(channel['meters']))
        self.n('channel_eof',channel_id=cid,direction='upload',owner_finishing=finishing,h2=witness)
        self.n('channel_upload_drained',channel_id=cid,owner_finishing=finishing,upload=terminal['upload'])
        self.n('channel_eof',channel_id=cid,direction='download',owner_finishing=finishing,h2=witness)
        terminal.update(upload_eof=True,upload_drained=True,download_eof=True,
                        upload_eof_h2=witness,download_eof_h2=witness,seal_frontier=None)

    def close_channel(self, channel):
        cid, closed = channel['channel_id'], channel['namespace_closed']
        self.n('channel_closed', channel_id=cid, receipt=closed)
        self.frame('incoming', 5, cid, subject.canonical(closed))
        self.p('channel_closed', channel_id=cid, namespace_closed=closed,
               meters=channel['meters'], h2=channel['h2'])

    def refresh_closed_frames(self):
        for rows in (self.parent,self.namespace):
            for row in rows:
                if row.get('kind')=='frame' and row.get('frame_type')==5:
                    terminal=self.channels[row['channel_id']-1]['namespace_closed'];payload=subject.canonical(terminal)
                    row.update(payload_bytes=len(payload),payload_sha256=subject.digest(payload))

    def seal(self):
        previous = None
        for i,row in enumerate(self.parent,1):
            row.pop('record_sha256',None)
            row.update(schema=subject.TRANSPORT_SCHEMA,sequence=i,previous_sha256=previous)
            row['record_sha256']=subject.digest(subject.canonical(row));previous=row['record_sha256']

    def write(self):
        self.seal()
        if self.owner['owner_kind']=='model_client' and not hasattr(self,'quiescence'):
            self.quiescence,self.client=quiescence_records(self.marker,
                mode='terminal' if self.channels else 'preflight',prefix=self.client[:-2])
            self.client[next(i for i,r in enumerate(self.client)
                             if r.get('kind')=='client_finishing_before_close')]=self.marker
        self.bind('client/native-owner.json',raw_json(self.owner))
        self.bind('client/events.jsonl',b''.join(subject.canonical(x)+b'\n' for x in self.client))
        self.bind('client/launch.json',raw_json({'binary':self.owner['executable']['path'],
              'binary_sha256':self.owner['executable']['sha256'],'bootstrap_requested':bool(self.channels),
              'config_overrides':{'thread_unload_delay_secs':0}}))
        self.bind('client/preflight.json',raw_json({'effective_config':{'thread_unload_delay_secs':0}}))
        result={'model_started':bool(self.channels),'success':True,
                'effective_config':{'thread_unload_delay_secs':0}}
        if self.owner['owner_kind']=='model_client':
            self.bind('client/native-quiescence.json',raw_json(self.quiescence))
            result['native_quiescence']=self.quiescence
        self.bind('client/result.json',raw_json(result))
        stderr=b''.join(b'RCI_CODEHOST_V3 '+subject.canonical(x)+b'\n' for x in self.namespace)
        item=self.bind('codehost-owner-stderr-v3.txt',stderr)
        self.receipt['stderr']={**item,'raw_bytes':len(stderr),'raw_sha256':subject.digest(stderr),
                                'truncated':False,'redacted':False}
        self.receipt['retirement']=self.bind('codehost-owner-retirement-v3.json',raw_json(self.retirement))
        self.terminal.update(payload_bytes=len(subject.canonical(self.finished)),
                             payload_sha256=subject.digest(subject.canonical(self.finished)))
        self.parent[-1]['receipt']=self.bind('codehost-owner-bridge-v3.json',raw_json(self.receipt))
        self.seal();self.bind('codehost-transport-v3.jsonl',b''.join(subject.canonical(x)+b'\n' for x in self.parent))


def diagnostic_fixture(root, case):
    f=Fixture(root,count=0 if case=='foreign_owner' else 1)
    f.owner['owner_kind']='transport_probe'
    f.owner_bound.update(f.bind('codehost-native-owner-v3.json',raw_json(f.owner)))
    owner_raw=raw_json(f.owner)
    f.client[0].update(receipt_bytes=len(owner_raw),receipt_sha256=subject.digest(owner_raw))
    f.receipt.update(qualified=False,failures=['channel_OwnerError' if case=='foreign_owner' else 'channel_ValueError'])
    f.parent[-1].update(qualified=False,failures=f.receipt['failures'])
    if case=='foreign_owner':
        client,server=['127.0.0.1',6001],['127.0.0.1',5000]
        f.receipt.update(denied=1,attempts=1,failures=['channel_OwnerError','drain_invalid']);f.parent[-1].update(denied=1,attempts=1,failures=f.receipt['failures'])
        f.finishing.update(seal_qualified=False,seal_error_code='drain_invalid')
        f.drain.update(seal_qualified=False,seal_error_code='drain_invalid')
        f.parent.insert(f.parent.index(f.finishing),{'kind':'failure','reason':'drain_invalid'})
        f.finishing['attempts']=1
        i=f.parent.index(f.finishing)
        f.parent[i:i]=[{'kind':'channel_denied','channel_id':1,'reason':'foreign_tcp_owner',
                       'client':client,'server':server}, {'kind':'failure','reason':'channel_OwnerError'}]
        sibling={key:copy.deepcopy(f.owner[key]) for key in
                 ('pid','process_creation_filetime','queried_executable_path','executable')}
        sibling.update(pid=124,process_creation_filetime=790)
        result={'ready_to_finish':True,'channels':[],'client':client,'server':server,
                'attempted_payload_bytes':0,'denial_eof_observed':True}
        injection={'sibling_process':sibling,'client':client,'server':server,
                   'attempted_payload_bytes':0,'denial_eof_observed':True}
    else:
        partial=b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'+b'\0\0\0\4\0\0\0\0\0'+b'\0\0\0\4\1\0\0\0\0'+b'\0\0\x08'
        download=b'\0\0\0\4\0\0\0\0\0'
        sibling=None;channel=f.channels[0]
        original=h2(partial,download)
        original.update(frames_complete=False,frame_complete={'upload':False,'download':True},
                        upload_complete=False,open_streams=0,active_stream_ids=[],closed_streams=0,last_stream_id=0,
                        frames={'upload':2,'download':1})
        final_h2=copy.deepcopy(original); final_h2['retiring']=True
        channel.update(h2=final_h2,finish_frontier=copy.deepcopy(original),seal_frontier=copy.deepcopy(final_h2))
        f.frontiers[0]['h2']=channel['finish_frontier']
        for name in ('client_read','upload'):channel['meters'][name]=stream(partial)
        for name in ('download','client_written'):channel['meters'][name]=stream(download)
        final=channel['namespace_closed'];final.update(qualified=False,reason='error',error_type='ValueError',
                 upload=stream(partial),download=stream(download),h2=copy.deepcopy(original),finish_frontier=None,
                 seal_frontier=None,upload_eof_h2=copy.deepcopy(original),download_eof_h2=copy.deepcopy(original))
        f.finished.update(qualified=False,reason='error',error_type='ValueError',owner_finish_received=False,
                          stdin_eof=False,owner_drain_received=False,owner_drain_acknowledged=False,
                          owner_drain_elapsed_s=None,drain_qualified=False,drain_error_code='owner_drain_unqualified')
        f.receipt['exit_code']=1;f.retirement['windows_exit_code']=1
        f.receipt['failures']=['channel_ValueError','namespace_finished_unqualified','drain_invalid','namespace_wrapper_nonzero','namespace_receipt_ValueError']
        f.parent[-1]['failures']=f.receipt['failures']
        eof=channel['parent_eof'];eof.update(client_finishing=False,h2=copy.deepcopy(original))
        channel['upload_drained']['meters']=copy.deepcopy(channel['meters'])
        f.finishing.update(seal_qualified=False,seal_error_code='drain_invalid')
        f.drain.update(seal_qualified=False,seal_error_code='drain_invalid')
        next(r for r in f.parent if r['kind']=='channel_seal_frontier')['h2']=channel['seal_frontier']
        def pframe(kind):return next(r for r in f.parent if r.get('kind')=='frame' and r['frame_type']==kind)
        prefix=[r for r in f.parent[:f.parent.index(f.frontiers[0])]
                if r['kind'] not in ('client_eof','upload_drained') and r.get('frame_type')!=4]
        f.parent[:]=prefix+[eof,{'kind':'failure','reason':'channel_ValueError'},pframe(4),channel['upload_drained'],
            f.frontiers[0],f.drain_begin,pframe(10),pframe(5),{'kind':'failure','reason':'namespace_finished_unqualified'},
            f.terminal,next(r for r in f.parent if r['kind']=='namespace_output_closed'),
            {'kind':'failure','reason':'drain_invalid'},next(r for r in f.parent if r['kind']=='channel_seal_frontier'),
            f.finishing,pframe(7),next(r for r in f.parent if r['kind']=='owner_input_closed'),
            next(r for r in f.parent if r['kind']=='owner_drain_completed'),
            next(r for r in f.parent if r['kind']=='retirement_started'),
            {'kind':'failure','reason':'namespace_wrapper_nonzero'},
            {'kind':'failure','reason':'namespace_receipt_ValueError'},f.parent[-1]]
        keep={'open','child_started','ready','channel_open','child_diagnostic','closed','channel_closed'}
        prefix=[r for r in f.namespace if r['kind'] in keep and r['kind'] not in ('channel_closed','child_diagnostic','closed')
                or r['kind']=='frame' and r['frame_type'] in (9,1,2,3)]
        half=next(r for r in f.namespace if r.get('frame_type')==4)
        neofs=[r for r in f.namespace if r['kind']=='channel_eof']
        for r in neofs:r.update(owner_finishing=False,h2=copy.deepcopy(original))
        nd=next(r for r in f.namespace if r['kind']=='channel_upload_drained');nd.update(owner_finishing=False,upload=stream(partial))
        f.namespace[:]=prefix+[half,neofs[0],{'kind':'failure','error_type':'ValueError'},nd,neofs[1]]+[
            r for r in f.namespace if r['kind'] in ('channel_closed','child_diagnostic','closed')
            or r.get('frame_type')==5]
        for rows in (f.parent,f.namespace):
            for row in rows:
                if row.get('kind')=='frame' and row['frame_type']==3:
                    up=row['direction']==('outgoing' if rows is f.parent else 'incoming')
                    raw=partial if up else download;row.update(payload_bytes=len(raw),payload_sha256=subject.digest(raw))
        f.refresh_closed_frames()
        for n,r in enumerate(f.namespace,1):r.update(schema=subject.NAMESPACE_SCHEMA,sequence=n,wall_unix_s=500+n*.01,monotonic_s=800+n*.01)
        f.finished['frame_counts']={d:sum(r.get('kind')=='frame' and r['direction']==d for r in f.namespace) for d in ('incoming','outgoing')}
        result={'ready_to_finish':True,'channels':[{'channel_id':1,'sent':stream(partial),'closed_before_finish':True}],
                'partial_header_bytes':3,'client_eof_before_owner_finish':True}
        injection={'channel_id':1,'fixed_upload_bytes':len(partial),'fixed_upload_sha256':subject.digest(partial),
                   'partial_header_bytes':3,'client_eof_before_owner_finish':True}
    for i,row in enumerate(f.parent):row.update(wall_unix_s=100.+i*.01,monotonic_s=200.+i*.01)
    first_finish = f.frontiers[0] if f.frontiers else f.drain_begin
    f.marker.update(wall_unix_s=first_finish['wall_unix_s']-.001,monotonic_s=first_finish['monotonic_s']-.001)
    f.drain_begin.update(start_monotonic_s=f.marker['monotonic_s'],deadline_monotonic_s=f.marker['monotonic_s']+25)
    f.drain.update(start_monotonic_s=f.marker['monotonic_s'],deadline_monotonic_s=f.marker['monotonic_s']+25,completed_monotonic_s=next(r['monotonic_s'] for r in f.parent if r['kind']=='owner_drain_completed'))
    next(r for r in f.parent if r['kind']=='owner_drain_completed').update(f.drain)
    f.client[-1]={'kind':'probe_client_closed','schema':'campaign002-h2-probe-client-1','closed':True,
                  'wall_unix_s':f.marker['wall_unix_s']+1,'monotonic_s':f.marker['monotonic_s']+1}
    identity={key:copy.deepcopy(f.owner[key]) for key in
              ('pid','process_creation_filetime','queried_executable_path','executable')}
    client_result={'schema':'campaign002-channel-client-3','case':case,'completed':True,'owner':identity,
                   'sibling':sibling,'result':result,'child_exit_codes':{'owner':0},'finish':f.marker,'model_calls':0}
    if sibling:client_result['child_exit_codes']['foreign']=0
    transcript=[]
    def event(role,kind,offset,**fields):
        evt={'kind':kind,'wall_unix_s':f.marker['wall_unix_s']+offset,
             'monotonic_s':f.marker['monotonic_s']+offset,**fields}
        transcript.append({'schema':'campaign002-channel-probe-transcript-3','role':role,
                           'event':evt,'received_wall_unix_s':evt['wall_unix_s']+.01})
    event('owner','client_ready',-5,pid=123)
    if sibling:event('foreign','client_ready',-4,pid=124)
    event('foreign' if sibling else 'owner','ready_to_finish',-1,result=result)
    transcript.append({'schema':'campaign002-channel-probe-transcript-3','role':'controller',
                       'event':f.marker,'received_wall_unix_s':f.marker['wall_unix_s']+.01})
    for role in client_result['child_exit_codes']:
        event(role,'client_finishing',.1);event(role,'client_closed',.2)
    f.seal();f.write()
    tr=f.bind('client-transcript.jsonl',b''.join(subject.canonical(x)+b'\n' for x in transcript))
    cr=f.bind('client-result.json',raw_json(client_result))
    declaration={'schema':'campaign002-transport-v3-case-1','case':case,'owner_kind':'transport_probe','model_calls':0,
                 'physical_simulation':False,'expected_failure':True,'injection':injection,
                 'client_transcript':tr,'client_result':cr}
    f.bind('diagnostic-case.json',raw_json(declaration))
    return f,declaration


def closed_pipe_fixture(root,error):
    f,declaration=diagnostic_fixture(root,'in_flight_eof')
    previous_marker=copy.deepcopy(f.marker)
    early=[r for r in f.parent if r.get('frame_type')==5 or r.get('reason')=='namespace_finished_unqualified'
           or r['kind'] in ('namespace_finished','namespace_output_closed')]
    for row in early:f.parent.remove(row)
    at=f.parent.index(f.frontiers[0]);f.parent[at:at]=early
    f.parent[:]=[r for r in f.parent if r.get('frame_type') not in (10,7)]
    failure={'kind':'failure','reason':'frame_write_'+error}
    f.parent.insert(f.parent.index(f.drain_begin)+1,failure)
    f.receipt['failures'].insert(2,failure['reason'])
    closed=next(r for r in f.parent if r['kind']=='owner_input_closed')
    f.parent.remove(closed);closed.update(after_finish_drain=False,failed_cleanup=True)
    f.parent.insert(next(i for i,r in enumerate(f.parent) if r['kind']=='retirement_started'),closed)
    channel=f.channels[0];channel['h2']['retiring']=False;channel['seal_frontier']['retiring']=False
    for n,row in enumerate(f.parent):row.update(wall_unix_s=100+n*.01,monotonic_s=200+n*.01)
    f.marker.update(wall_unix_s=f.frontiers[0]['wall_unix_s']-.001,monotonic_s=f.frontiers[0]['monotonic_s']-.001)
    f.drain_begin.update(start_monotonic_s=f.marker['monotonic_s'],deadline_monotonic_s=f.marker['monotonic_s']+25)
    f.drain.update(start_monotonic_s=f.marker['monotonic_s'],deadline_monotonic_s=f.marker['monotonic_s']+25,
                  completed_monotonic_s=next(r['monotonic_s'] for r in f.parent if r['kind']=='owner_drain_completed'))
    next(r for r in f.parent if r['kind']=='owner_drain_completed').update(f.drain)
    client=json.loads((f.stage/'client-result.json').read_text());client['finish']=f.marker
    transcript=[json.loads(line) for line in (f.stage/'client-transcript.jsonl').read_text().splitlines()]
    for row in transcript:
        for key in ('wall_unix_s','monotonic_s'):row['event'][key]+=f.marker[key]-previous_marker[key]
        row['received_wall_unix_s']+=f.marker['wall_unix_s']-previous_marker['wall_unix_s']
    next(r for r in transcript if r['role']=='controller')['event']=f.marker
    f.client[-1].update(wall_unix_s=f.marker['wall_unix_s']+1,monotonic_s=f.marker['monotonic_s']+1)
    declaration['client_result']=f.bind('client-result.json',raw_json(client))
    declaration['client_transcript']=f.bind('client-transcript.jsonl',b''.join(subject.canonical(r)+b'\n' for r in transcript))
    f.bind('diagnostic-case.json',raw_json(declaration));f.write()
    return f


def positive_probe_fixture(root,case):
    f=Fixture(root,count=1 if case=='boundary_single_channel' else 3,fixed_probe=case=='multi_channel')
    f.owner['owner_kind']='transport_probe'
    f.owner_bound.update(f.bind('codehost-native-owner-v3.json',raw_json(f.owner)))
    owner_raw=raw_json(f.owner)
    f.client[0].update(receipt_bytes=len(owner_raw),receipt_sha256=subject.digest(owner_raw))
    f.client[-1]={'kind':'probe_client_closed','schema':'campaign002-h2-probe-client-1','closed':True,
                 'wall_unix_s':f.marker['wall_unix_s']+1,'monotonic_s':f.marker['monotonic_s']+1}
    identity={key:copy.deepcopy(f.owner[key]) for key in
              ('pid','process_creation_filetime','queried_executable_path','executable')}
    result={'ready_to_finish':True,'channels':[{'channel_id':ch['channel_id'],
              'client':ch['authentication']['client'],'server':ch['authentication']['server'],
              'sent':ch['meters']['client_read']} for ch in f.channels]}
    value={'schema':'campaign002-channel-client-3','case':case,'completed':True,'owner':identity,
           'sibling':None,'result':result,'child_exit_codes':{'owner':0},'finish':f.marker,'model_calls':0}
    if case=='multi_channel':
        result['channels'][0]['sent']=stream(probe_baseline())
        result['channels'][0]['closed_before_finish']=False
        f.seal()
        acknowledgment=next(r for r in f.parent if r['kind']=='owner_drain_ack')
        prefix=b''.join(subject.canonical(r)+b'\n' for r in f.parent[:acknowledgment['sequence']])
        value['pending_read_shutdown']={'schema':'campaign002-pending-read-shutdown-1',
            'frontier':f.frontiers[0],'drain_begin':f.drain_begin,'acknowledgment':acknowledgment,
            'retained_ledger_prefix':{'path':'codehost-transport-v3.jsonl',**stream(prefix)},
            'grant_monotonic_s':acknowledgment['monotonic_s'],'control_sent_monotonic_s':acknowledgment['monotonic_s'],
            'deadline_monotonic_s':f.marker['monotonic_s']+25,
            'shutdown_bytes':17,'shutdown_sha256':subject.digest(probe_shutdown())}
    transcript=[]
    for kind,offset,fields in [('client_ready',-5,{'pid':123}),('ready_to_finish',-1,{'result':result}),
                             ('client_finishing',.1,{}),('client_closed',.2,{})]:
        event={'kind':kind,'wall_unix_s':f.marker['wall_unix_s']+offset,
               'monotonic_s':f.marker['monotonic_s']+offset,**fields}
        transcript.append({'schema':'campaign002-channel-probe-transcript-3','role':'owner',
                           'event':event,'received_wall_unix_s':event['wall_unix_s']+.01})
    transcript.insert(2,{'schema':'campaign002-channel-probe-transcript-3','role':'controller',
                        'event':f.marker,'received_wall_unix_s':f.marker['wall_unix_s']+.01})
    if case=='multi_channel':
        ack=value['pending_read_shutdown']['acknowledgment'];tail=next(r for r in f.parent if r.get('frame_type')==3 and r.get('channel_id')==1 and r['sequence']>ack['sequence'])
        finishing=next(r for r in transcript if r['event']['kind']=='client_finishing')['event']
        finishing.update(monotonic_s=ack['monotonic_s'],wall_unix_s=ack['wall_unix_s'])
        shutdown={'kind':'channel_shutdown_control','channel_id':1,'bytes':17,'sha256':subject.digest(probe_shutdown()),
                  'monotonic_s':tail['monotonic_s'],'wall_unix_s':tail['wall_unix_s']}
        at=next(n for n,r in enumerate(transcript) if r['event']['kind']=='client_closed')
        transcript.insert(at,{'schema':'campaign002-channel-probe-transcript-3','role':'owner','event':shutdown,'received_wall_unix_s':shutdown['wall_unix_s']+.001})
        transcript[-1]['event'].update(monotonic_s=tail['monotonic_s']+.1,wall_unix_s=tail['wall_unix_s']+.1)
    f.write();f.bind('client-result.json',raw_json(value))
    f.bind('client-transcript.jsonl',b''.join(subject.canonical(x)+b'\n' for x in transcript))
    return f


class TransportV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.f=Fixture(Path(self.temp.name))
        self.repo=patch.object(subject,'REPO',self.f.repo);self.repo.start();self.addCleanup(self.repo.stop)

    def verify(self,**kwargs):
        return subject.verify_transport_integrity(self.f.stage,self.f.frozen,**kwargs)

    def fails(self,phrase):
        self.f.write()
        with self.assertRaisesRegex(ValueError,phrase):self.verify()

    def test_two_channels_one_child_and_exact_bytes(self):
        self.f.write();value=self.verify()
        self.assertTrue(value['passed']);self.assertEqual(value['accepted_count'],2)
        self.assertEqual(value['namespace']['child_pid'],42)
        self.assertIn('client/native-owner.json',value['input_bindings'])
        self.assertTrue(value['client_quiescence']['passed'])
        self.assertIn('client/native-quiescence.json',value['input_bindings'])

    def test_actual_top_level_rejects_missing_quiescence_receipt(self):
        self.f.write();(self.f.stage/'client/native-quiescence.json').unlink()
        with self.assertRaisesRegex(ValueError,'Native quiescence: missing'):self.verify()

    def test_actual_top_level_rejects_false_cleanup_with_healthy_bridge(self):
        self.f.write();self.f.quiescence['handshake_qualified']=False;self.f.write()
        self.assertTrue(self.f.receipt['qualified'])
        with self.assertRaisesRegex(ValueError,'failed, forced'):self.verify()

    def test_actual_top_level_rejects_wrong_acknowledged_thread(self):
        self.f.write()
        event=next(e for e in self.f.quiescence['events'] if e['phase']=='thread_closed')
        event['thread_id']='foreign';self.f.quiescence['thread_closed']['thread_id']='foreign';self.f.write()
        with self.assertRaisesRegex(ValueError,'correlation differs'):self.verify()

    def test_actual_top_level_requires_zero_unload_evidence_without_replacing_shutdown(self):
        self.f.write()
        for name,field in (('launch.json','config_overrides'),('preflight.json','effective_config'),('result.json','effective_config')):
            p=self.f.stage/'client'/name;original=p.read_bytes()
            for value in (None,False,0.0,'0',60):
                with self.subTest(name=name,value=value):
                    changed=json.loads(original)
                    if value is None:changed[field].pop('thread_unload_delay_secs')
                    else:changed[field]['thread_unload_delay_secs']=value
                    p.write_bytes(raw_json(changed))
                    with self.assertRaisesRegex(ValueError,'unload scheduling'):self.verify()
            p.write_bytes(original)
        self.assertTrue(self.verify()['passed'])

    def test_actual_top_level_binds_cleanup_controller_source(self):
        self.f.write();name=subject.CAMPAIGN+'harness/native_quiescence.py'
        self.f.frozen['sources'][name]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'source differs'):self.verify()

    def test_fixture_covers_actual_source_emitted_parent_event_kinds(self):
        source = Path(subject.__file__).resolve().parents[1] / 'harness/codehost_bridge_v3.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        emitted = {node.args[0].value for node in ast.walk(tree)
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr == 'emit' and node.args
                   and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)}
        self.assertEqual(emitted, subject.PARENT_KINDS | {'failure', 'channel_denied', 'socket_failure'})
        self.assertNotIn('socket_failure', subject.PARENT_KINDS)
        self.assertEqual({row['kind'] for row in self.f.parent} | {'client_eof',
            'native_cleanup_begin','native_cleanup_ack','native_cleanup_channel'}, subject.PARENT_KINDS)

    def test_socket_failure_metadata_cannot_qualify_otherwise_valid_transport(self):
        self.f.write()
        self.assertTrue(self.verify()['passed'])
        self.f.parent.insert(2, {**self.f.parent[1], 'kind':'socket_failure',
            'diagnostic_schema':'campaign002-socket-failure-1', 'channel_id':1,
            'operation':'upload_read', 'exception_class':'ConnectionAbortedError',
            'errno':1236, 'winerror':1236})
        self.fails('Owner transport has failure')

    def test_socket_failure_metadata_is_not_an_accepted_expected_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,_=diagnostic_fixture(Path(tmp),'foreign_owner')
            f.parent.insert(2, {**f.parent[1], 'kind':'socket_failure',
                'diagnostic_schema':'campaign002-socket-failure-1', 'channel_id':1,
                'operation':'upload_read', 'exception_class':'ConnectionAbortedError',
                'errno':1236, 'winerror':1236})
            f.write()
            with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,'Unknown expected-failure'):
                subject.verify_expected_failure(f.stage,f.frozen,case='foreign_owner')

    def test_actual_begin_finishing_emits_one_original_frontier_and_gates_live_only(self):
        source = Path(subject.__file__).resolve().parents[1] / 'harness/codehost_bridge_v3.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        bridge = next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Bridge')
        methods = [node for node in bridge.body if isinstance(node,ast.FunctionDef)
                   and node.name in ('observe_finishing','begin_finish')]
        namespace={'require':subject.require,'time':SimpleNamespace(monotonic=lambda:0)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=methods,type_ignores=[])),str(source),'exec'),namespace)
        emitted=[]; gated=[]; channels={}
        for item in self.f.channels:
            snapshot=copy.deepcopy(item['finish_frontier']); cid=item['channel_id']
            channels[cid]=SimpleNamespace(id=cid,state='closed' if cid==1 else 'live',finish_frontier=None,upload_read_pending=True,
                h2=SimpleNamespace(summary=lambda snapshot=snapshot:copy.deepcopy(snapshot),
                                   validate_reset_scope=lambda:None,
                                   begin_retirement=lambda cid=cid:gated.append(cid)))
        fake=SimpleNamespace(channels=channels,finishing=False,server=None,process=None,
            fixture=SimpleNamespace(client_finishing=SimpleNamespace(is_set=lambda:True)),
            ledger=SimpleNamespace(emit=lambda kind,**fields:emitted.append({'kind':kind,**fields})),
            closing_marker=lambda:self.f.marker,fail=lambda error:self.fail(error))
        fake.begin_finish=lambda:namespace['begin_finish'](fake)
        namespace['observe_finishing'](fake);namespace['observe_finishing'](fake)
        self.assertEqual([x['kind'] for x in emitted],['channel_finish_frontier']*2+['owner_drain_begin'])
        self.assertEqual(gated,[2]);self.assertEqual(emitted[0]['h2'],self.f.channels[0]['h2'])
        self.assertEqual(fake.drain['deadline_monotonic_s'],self.f.marker['monotonic_s']+25)

    def test_missing_parent_frontier_rejected(self):
        self.f.parent.remove(self.f.frontiers[0]); self.fails('frontier identity')

    def test_duplicate_parent_frontier_rejected(self):
        self.f.parent.insert(self.f.parent.index(self.f.frontiers[0]), copy.deepcopy(self.f.frontiers[0]))
        self.fails('frontier identity')

    def test_foreign_or_boolean_frontier_channel_rejected(self):
        for cid in (3, True):
            with self.subTest(channel_id=cid):
                self.f.frontiers[0]['channel_id'] = cid; self.fails('frontier identity')

    def test_frontier_projection_cannot_be_changed_independently(self):
        self.f.channels[0]['finish_frontier'] = copy.deepcopy(self.f.channels[0]['finish_frontier'])
        self.f.channels[0]['finish_frontier']['frames']['upload'] += 1
        self.fails('frontier receipt projection')

    def test_frontier_phase_and_extra_fields_rejected(self):
        self.f.frontiers[0]['client_finishing'] = False; self.fails('frontier phase')
        self.f.frontiers[0]['client_finishing'] = True
        self.f.frontiers[0]['untrusted_extra'] = True; self.fails('frontier phase')

    def test_frontier_before_durable_marker_rejected(self):
        self.f.marker['wall_unix_s'] = self.f.frontiers[0]['wall_unix_s'] + .1
        self.fails('frontier phase|Early EOF')

    def test_frontier_after_owner_finishing_rejected_with_valid_ledger(self):
        row = self.f.frontiers[-1]; self.f.parent.remove(row)
        self.f.parent.insert(self.f.parent.index(self.f.finishing)+1, row)
        for index, event in enumerate(self.f.parent):
            event.update(wall_unix_s=100.+index, monotonic_s=200.+index)
        self.fails('frontier phase')

    def test_frontier_authentication_order_checked_independently(self):
        self.f.seal()
        auths = [row for row in self.f.parent if row['kind'] == 'channel_authenticated']
        auths[0]['sequence'] = self.f.frontiers[0]['sequence']
        with self.assertRaisesRegex(ValueError, 'frontier phase'):
            subject.parent_finish_frontiers(self.f.parent,
                {ch['channel_id']: ch for ch in self.f.channels}, auths, self.f.marker, self.f.finishing)

    def test_parent_reset_cannot_be_hidden_by_clean_namespace_frontier(self):
        self.f.channels[-1]['finish_frontier'].update(reset_streams=1,
            reset_records=[{'direction': 'upload', 'stream_id': 1, 'error_code': 8}])
        self.fails('Earlier HTTP2 reset')

    def test_parent_frontier_error_or_malformed_counter_rejected(self):
        value = self.f.channels[-1]['finish_frontier']
        value['error'] = 'bad_frame'; self.fails('HTTP2 witness schema')
        value['error'] = None; value['bytes']['download'] = True
        self.fails('directional counter')

    def test_parent_frontier_byte_prefix_tamper_rejected(self):
        self.f.channels[-1]['finish_frontier']['bytes']['download'] -= 1
        self.fails('directional DATA prefix')

    def test_parent_frontier_reversed_counter_rejected(self):
        self.f.channels[-1]['finish_frontier']['frames']['download'] += 1
        self.fails('reversed after owner FINISH')

    def test_idle_closed_parent_frontier_must_equal_final(self):
        self.f.channels[0]['finish_frontier']['closed_streams'] = 0
        self.fails('Already closed idle')

    def test_different_parent_and_namespace_frontiers_follow_actual_data_prefix(self):
        # Current DATA receipt may be emitted before feed_h2 notices the owner
        # flag. Split the actual frame boundaries; the parent snapshot then
        # excludes only this last received payload, while the namespace has it.
        cid = self.f.channels[-1]['channel_id']
        settings = b'\0\0\0\4\0\0\0\0\0'
        header = b'\0\0\0\1\4\0\0\0\1'
        for rows, direction in ((self.f.parent, 'incoming'), (self.f.namespace, 'outgoing')):
            event = next(row for row in rows if row['kind'] == 'frame' and row['frame_type'] == 3
                         and row['channel_id'] == cid and row['direction'] == direction)
            event.update(payload_bytes=len(settings), payload_sha256=subject.digest(settings))
            extra = copy.deepcopy(event); extra.update(payload_bytes=len(header), payload_sha256=subject.digest(header))
            rows.insert(rows.index(event)+1, extra)
        # Move the incoming second chunk just before the frontier batch, the
        # precise interleaving allowed by receive_frames -> feed_h2.
        event = next(row for row in self.f.parent if row['kind'] == 'frame'
                     and row.get('payload_sha256') == subject.digest(header) and row['direction'] == 'incoming')
        self.f.parent.remove(event); self.f.parent.insert(self.f.parent.index(self.f.frontiers[0]), event)
        event = next(row for row in self.f.namespace if row['kind'] == 'frame'
                     and row.get('payload_sha256') == subject.digest(header) and row['direction'] == 'outgoing')
        self.f.namespace.remove(event)
        boundary = next(index for index, row in enumerate(self.f.namespace)
                        if row['kind'] == 'frame' and row['frame_type'] == 10)
        self.f.namespace.insert(boundary, event)
        for index, row in enumerate(self.f.parent):
            row.update(wall_unix_s=100.+index*.01, monotonic_s=200.+index*.01)
        for index, row in enumerate(self.f.namespace, 1):
            row.update(sequence=index, wall_unix_s=500.+index*.01, monotonic_s=800.+index*.01)
        self.f.marker.update(wall_unix_s=self.f.frontiers[0]['wall_unix_s']-.1,
                             monotonic_s=self.f.frontiers[0]['monotonic_s']-.1)
        self.f.drain_begin.update(start_monotonic_s=self.f.marker['monotonic_s'],deadline_monotonic_s=self.f.marker['monotonic_s']+25)
        self.f.drain.update(start_monotonic_s=self.f.marker['monotonic_s'],deadline_monotonic_s=self.f.marker['monotonic_s']+25,
                            completed_monotonic_s=next(x['monotonic_s'] for x in self.f.parent if x['kind']=='namespace_output_closed'))
        next(x for x in self.f.parent if x['kind']=='owner_drain_completed').update(self.f.drain)
        front = self.f.channels[-1]['finish_frontier']
        front['bytes']['download'] = len(settings); front['frames']['download'] = 1
        self.f.finished['frame_counts'] = {direction: sum(row['kind'] == 'frame'
            and row['direction'] == direction for row in self.f.namespace) for direction in ('incoming','outgoing')}
        self.f.write(); self.assertTrue(self.verify()['passed'])

    def test_cancel_must_be_permitted_by_both_endpoint_frontiers(self):
        channel = self.f.channels[-1]
        final = copy.deepcopy(channel['h2'])
        final.update(open_streams=0, active_stream_ids=[], reset_streams=1,
                     reset_records=[{'direction': 'download', 'stream_id': 1, 'error_code': 8}])
        channel['h2'] = channel['namespace_closed']['h2'] = final
        channel['finish_frontier']['active_stream_ids'] = [3]
        self.f.seal()
        with self.assertRaisesRegex(ValueError, 'unexplained reset|monotone stream'):
            subject.parent_finish_frontiers(self.f.parent,
                {ch['channel_id']: ch for ch in self.f.channels},
                [row for row in self.f.parent if row['kind'] == 'channel_authenticated'],
                self.f.marker, self.f.finishing)

    def test_unknown_parent_event_remains_rejected(self):
        self.f.frontiers[0]['kind'] = 'channel_finish_invented'; self.fails('incomplete lifecycle')

    def test_empty_requires_explicit_source_bound_zero_model_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Fixture(Path(tmp),count=0);f.write()
            with patch.object(subject,'REPO',f.repo):
                with self.assertRaisesRegex(ValueError,'channel count'):subject.verify_transport_integrity(f.stage,f.frozen)
                self.assertTrue(subject.verify_transport_integrity(f.stage,f.frozen,allow_empty=True)['passed'])
                f.frozen['sources'].pop(subject.PREFLIGHT_SOURCE_NAME)
                with self.assertRaisesRegex(ValueError,'source differs'):subject.verify_transport_integrity(f.stage,f.frozen,allow_empty=True)

    def test_drain_method_is_required_frozen_source(self):
        self.f.frozen['sources'].pop(subject.CAMPAIGN+'io-repair/CHANNEL_OWNER_DRAIN_V1.md')
        self.fails('source differs')

    def test_missing_or_duplicate_drain_ack_never_seals(self):
        row=next(x for x in self.f.parent if x['kind']=='owner_drain_ack')
        position=self.f.parent.index(row)
        self.f.parent.remove(row);self.fails('incomplete lifecycle')
        self.f.parent.insert(position,row)
        self.f.parent.insert(self.f.parent.index(row),copy.deepcopy(row));self.fails('incomplete lifecycle')

    def test_control_ack_cannot_be_invented_from_final_flag(self):
        row=next(x for x in self.f.parent if x['kind']=='frame' and x['frame_type']==11)
        self.f.parent.remove(row);self.fails('FINISH before drain acknowledgment')

    def test_original_deadline_cannot_restart_at_seal(self):
        self.f.drain_begin['start_monotonic_s']+=1
        self.f.drain_begin['deadline_monotonic_s']+=1
        self.fails('original durable 25-second')

    def test_original_deadline_cannot_be_extended(self):
        self.f.drain_begin['deadline_monotonic_s']+=25
        self.fails('original durable 25-second')

    def test_timeout_even_with_clean_final_retirement_fails(self):
        self.f.drain['completed_monotonic_s']=self.f.marker['monotonic_s']+25.001
        self.fails('completion/deadline')

    def test_missing_genuine_eof_cannot_be_filled_by_final_channel_close(self):
        row=self.f.channels[-1]['parent_eof'];self.f.parent.remove(row)
        self.f.channels[-1]['parent_eof']=None
        self.fails('genuine upload EOF')

    def test_missing_upload_drain_event_not_reconstructed_from_equal_meters(self):
        self.f.parent.remove(self.f.channels[-1]['upload_drained'])
        self.f.channels[-1]['upload_drained']=None
        self.fails('genuine upload EOF')

    def test_upload_drain_meters_must_preserve_all_uploaded_bytes(self):
        self.f.channels[-1]['upload_drained']['meters']['upload']['sha256']='e'*64
        self.fails('lost or invented bytes')

    def test_seal_frontier_cannot_replace_original_cancel_authority(self):
        frontier=copy.deepcopy(self.f.channels[-1]['finish_frontier'])
        later=copy.deepcopy(self.f.channels[-1]['h2'])
        later.update(last_stream_id=3,active_stream_ids=[1],open_streams=1,closed_streams=1)
        with self.assertRaisesRegex(ValueError,'new stream'):
            subject.channel_h2(later,frontier)

    def test_boolean_last_stream_identity_is_rejected(self):
        self.f.channels[-1]['h2']['last_stream_id']=True
        self.fails('monotone stream')

    def test_missing_namespace_original_frontier_rejected(self):
        row=next(x for x in self.f.namespace if x['kind']=='channel_finish_frontier')
        self.f.namespace.remove(row)
        for n,item in enumerate(self.f.namespace,1):item['sequence']=n
        self.fails('original frontier multiplicity')

    def test_namespace_ack_cardinality_and_upload_eof_mandatory(self):
        self.f.channels[-1]['namespace_closed']['upload_eof']=False
        self.f.refresh_closed_frames()
        self.fails('genuine upload EOF')

    def test_parent_data_after_final_seal_forbidden_but_download_may_drain(self):
        self.f.seal()
        frames=[dict(x,direction={'outgoing':'sent','incoming':'received'}[x['direction']])
                for x in self.f.parent if x['kind']=='frame']
        ns=[x for x in self.f.namespace if x['kind']=='frame']
        metadata={x['channel_id']:x['namespace_closed'] for x in self.f.channels}
        row=next(x for x in frames if x['frame_type']==3 and x['channel_id']==2 and x['direction']=='received')
        frames.remove(row);at=next(i for i,x in enumerate(frames) if x['frame_type']==7);frames.insert(at+1,row)
        nsrow=next(x for x in ns if x['frame_type']==3 and x['channel_id']==2 and x['direction']=='outgoing')
        ns.remove(nsrow);at=next(i for i,x in enumerate(ns) if x['frame_type']==7);ns.insert(at+1,nsrow)
        self.assertEqual(subject.framing_integrity(frames,ns,metadata,self.f.ready)[2]['download'],18)
        upload=next(x for x in frames if x['frame_type']==3 and x['channel_id']==2 and x['direction']=='sent')
        frames.remove(upload);at=next(i for i,x in enumerate(frames) if x['frame_type']==7);frames.insert(at+1,upload)
        with self.assertRaisesRegex(ValueError,'sealed FINISH'):
            subject.framing_integrity(frames,ns,metadata,self.f.ready)


    def test_denial_cannot_be_laundered_by_clean_final_flag(self):
        self.f.parent[-1]['denied']=1;self.fails('channel count')

    def test_foreign_pid(self):
        self.f.channels[0]['authentication']['owner_pid']=124;self.fails('foreign')

    def test_reused_pid_creation(self):
        self.f.channels[0]['authentication']['process_creation_filetime']=790;self.fails('foreign')

    def test_same_binary_name_different_file(self):
        self.f.channels[0]['authentication']['executable_file_identity'][1]=99;self.fails('foreign')

    def test_wrong_server_tuple(self):
        self.f.channels[0]['authentication']['server'][1]=5001;self.fails('listener')

    def test_nonestablished_or_late_tcp_lookup(self):
        for key,val in [('tcp_state',2),('lookup_elapsed_s',.251),('lookup_attempts',True)]:
            with self.subTest(key=key):
                original=self.f.channels[0]['authentication'][key]
                self.f.channels[0]['authentication'][key]=val;self.fails('lookup')
                self.f.channels[0]['authentication'][key]=original

    def test_parent_stream_loss(self):
        self.f.channels[0]['meters']['client_written']['bytes']-=1;self.fails('original bytes')

    def test_endpoint_hash_mismatch(self):
        self.f.channels[0]['namespace_closed']['upload']['sha256']='b'*64;self.fails('original bytes')

    def test_partial_http2_final_frame(self):
        self.f.channels[-1]['h2']['frames_complete']=False;self.fails('completion')

    def test_inflight_idle_eof_not_waived_by_later_finish(self):
        ch=self.f.channels[0];ch['h2'].update(open_streams=1,active_stream_ids=[1]);self.fails('Early channel EOF')

    def test_prefinish_reset_cannot_be_laundered(self):
        frontier=self.f.channels[-1]['namespace_closed']['finish_frontier']
        frontier.update(reset_streams=1,reset_records=[{'direction':'upload','stream_id':1,'error_code':8}])
        self.fails('Earlier HTTP2 reset')

    def test_postfinish_reset_must_be_cancel_on_previous_active_stream(self):
        value=self.f.channels[-1]['h2'];value.update(reset_streams=1,reset_records=[{'direction':'upload','stream_id':3,'error_code':8}])
        self.fails('unexplained reset')

    def test_opaque_frame_hash_mismatch(self):
        row=next(x for x in self.f.namespace if x['kind']=='frame' and x['frame_type']==3)
        row['payload_sha256']='c'*64;self.fails('frame identities')

    def test_duplicate_namespace_child(self):
        self.f.namespace[2]['kind']='child_started';self.fails('duplicate host')

    def test_missing_namespace_eof(self):
        self.f.finished['stdin_eof']=False;self.fails('cleanup')

    def test_unclean_retirement(self):
        self.f.retirement['observations'][0]['namespace_members']=[{'pid':42}];self.fails('empty namespace')

    def test_source_drift(self):
        self.f.write();(self.f.repo/subject.SOURCE_NAMES[0]).write_text('changed')
        with self.assertRaisesRegex(ValueError,'source differs'):self.verify()

    def test_truncated_ledger(self):
        self.f.write();p=self.f.stage/'codehost-transport-v3.jsonl';p.write_bytes(p.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError,'truncated'):self.verify()

    def test_duplicate_json_key(self):
        with self.assertRaisesRegex(ValueError,'Malformed'):subject.decode(b'{"a":1,"a":2}','fixture')

    def test_boolean_byte_counter_rejected(self):
        self.f.channels[0]['meters']['client_read']['bytes']=True;self.fails('stream identity')

    def test_foreign_owner_kind_does_not_masquerade_as_native_client(self):
        self.f.owner['owner_kind']='transport_probe';self.fails('kind differs')

    def test_client_owner_receipt_hash_cannot_be_replaced(self):
        self.f.client[0]['receipt_sha256']='0'*64;self.fails('registration receipt differs')

    def test_marker_after_transport_finish_rejected(self):
        self.f.marker['monotonic_s']=10000.;self.fails('ordering differs')

    def test_pid_boolean_not_integer(self):
        self.f.owner['pid']=True;self.fails('identity or kind')

    def test_namespace_source_omission_rejected(self):
        self.f.inside.pop('codehost_inside_v3.py');self.fails('READY identity')

    def test_finish_without_stdin_eof_is_not_complete(self):
        self.f.finished.pop('stdin_eof');self.fails('cleanup')

    def test_original_byte_digest_substitution_without_chain_rehash(self):
        self.f.write();p=self.f.stage/'codehost-transport-v3.jsonl'
        raw=p.read_bytes();p.write_bytes(raw.replace(b'"pid":123',b'"pid":124',1))
        with self.assertRaisesRegex(ValueError,'hash or chain'):self.verify()

    def test_aggregate_queue_over_bound(self):
        self.f.receipt['queue_maximum_bytes']=4194305;self.fails('queued-byte')

    def test_additional_retired_namespace_is_not_one_host(self):
        self.f.retirement['observations'][0]['namespace_ids'].append(988);self.fails('More than one')

    def test_unknown_framing_type_not_silently_ignored(self):
        next(x for x in self.f.parent if x['kind']=='frame' and x['frame_type']==3)['frame_type']=14
        self.fails('Framing type')

    def test_data_before_acknowledgement_rejected(self):
        row=next(x for x in self.f.parent if x['kind']=='frame' and x['frame_type']==2)
        row.update(frame_type=3,payload_bytes=1,payload_sha256=subject.digest(b'x'))
        self.fails('DATA before OPENED')

    def test_bound_cancel_after_finish_frontier_is_allowed(self):
        frontier=copy.deepcopy(self.f.channels[-1]['namespace_closed']['finish_frontier'])
        final=copy.deepcopy(frontier)
        final.update(open_streams=0,active_stream_ids=[],reset_streams=1,
                     reset_records=[{'direction':'download','stream_id':1,'error_code':8}])
        subject.channel_h2(final,frontier)
        final['reset_records'][0]['error_code']=2
        with self.assertRaisesRegex(ValueError,'unexplained reset'):subject.channel_h2(final,frontier)

    def test_extra_legacy_host_retirement_rejected(self):
        self.f.write();self.f.bind('codehost-1-retirement.json',raw_json(self.f.retirement))
        with self.assertRaisesRegex(ValueError,'Additional'):self.verify()

    def test_missing_framed_output_eof_rejected(self):
        next(x for x in self.f.parent if x['kind']=='namespace_output_closed')['after_finished']=False
        self.fails('framing EOF')

    def test_per_channel_headroom_is_within_original_limit(self):
        self.f.receipt['per_channel_queue_maximum_bytes']['1']=400000
        self.fails('Per-channel queue')

    def test_expected_failure_diagnostics_cannot_be_production_passes(self):
        for case in ('foreign_owner','in_flight_eof'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
                f,_=diagnostic_fixture(Path(tmp),case)
                with patch.object(subject,'REPO',f.repo):
                    value=subject.verify_expected_failure(f.stage,f.frozen,case=case)
                    self.assertTrue(value['expected_failure_verified']);self.assertNotIn('passed',value)
                    self.assertFalse(value['ordinary_transport_passed'])
                    with self.assertRaises(ValueError):subject.verify_transport_integrity(f.stage,f.frozen,owner_kind='transport_probe')

    def test_expected_inflight_failure_rejects_fabricated_input_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,declaration=diagnostic_fixture(Path(tmp),'in_flight_eof')
            declaration['injection']['fixed_upload_sha256']='f'*64
            f.bind('diagnostic-case.json',raw_json(declaration))
            with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,'45-byte'):
                subject.verify_expected_failure(f.stage,f.frozen,case='in_flight_eof')

    def test_expected_inflight_failure_requires_parent_frontier(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,_=diagnostic_fixture(Path(tmp),'in_flight_eof')
            f.parent.remove(f.frontiers[0]); f.write()
            with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,'frontier identity'):
                subject.verify_expected_failure(f.stage,f.frozen,case='in_flight_eof')

    def test_expected_inflight_failure_retains_strict_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,declaration=diagnostic_fixture(Path(tmp),'in_flight_eof')
            eof=next(row for row in f.parent if row['kind']=='client_eof')
            # Keep all transcript identities and the marker intact. Coarsen the
            # earlier ledger readings to the marker, retaining exact ordering.
            for row in f.parent[f.parent.index(eof):]:
                if row['monotonic_s'] < f.marker['monotonic_s']:
                    row['monotonic_s'] = f.marker['monotonic_s']
            f.write()
            with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,'EOF did not precede'):
                subject.verify_expected_failure(f.stage,f.frozen,case='in_flight_eof')

    def test_foreign_owner_has_zero_frontiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,_=diagnostic_fixture(Path(tmp),'foreign_owner')
            extra = {'kind':'channel_finish_frontier','channel_id':1,'client_finishing':True,
                     'h2':copy.deepcopy(self.f.channels[0]['h2']),
                     'wall_unix_s':f.finishing['wall_unix_s'],'monotonic_s':f.finishing['monotonic_s']}
            f.parent.insert(f.parent.index(f.finishing),extra); f.write()
            with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,'frontier identity'):
                subject.verify_expected_failure(f.stage,f.frozen,case='foreign_owner')

    def test_expected_failure_unknown_event_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,_=diagnostic_fixture(Path(tmp),'foreign_owner')
            next(row for row in f.parent if row['kind']=='failure')['kind']='unrecognized_failure'
            f.write()
            with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,'Unknown expected-failure'):
                subject.verify_expected_failure(f.stage,f.frozen,case='foreign_owner')

    def test_foreign_owner_diagnostic_rejects_registered_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,declaration=diagnostic_fixture(Path(tmp),'foreign_owner')
            declaration['injection']['sibling_process']['pid']=f.owner['pid']
            f.bind('diagnostic-case.json',raw_json(declaration))
            with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,'separately identified'):
                subject.verify_expected_failure(f.stage,f.frozen,case='foreign_owner')

    def test_foreign_owner_requires_specific_producer_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,_=diagnostic_fixture(Path(tmp),'foreign_owner')
            f.receipt['failures']=['channel_ValueError']
            f.parent[-1]['failures']=f.receipt['failures']
            next(row for row in f.parent if row['kind']=='failure')['reason']='channel_ValueError'
            f.write()
            with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,'unrelated failures'):
                subject.verify_expected_failure(f.stage,f.frozen,case='foreign_owner')

    def test_declared_probe_cases_and_boundary_source_binding(self):
        for case in ('multi_channel','boundary_single_channel'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
                f=positive_probe_fixture(Path(tmp),case)
                with patch.object(subject,'REPO',f.repo):
                    value=subject.verify_transport_integrity(f.stage,f.frozen,owner_kind='transport_probe')
                    self.assertTrue(value['passed'])
                    self.assertEqual(subject.BOUNDARY_SOURCE_NAME in value['source_bindings'],case=='boundary_single_channel')
                    if case=='boundary_single_channel':
                        f.frozen['sources'].pop(subject.BOUNDARY_SOURCE_NAME)
                        with self.assertRaisesRegex(ValueError,'Boundary transport source differs'):
                            subject.verify_transport_integrity(f.stage,f.frozen,owner_kind='transport_probe')

    def test_full_multichannel_probe_keeps_before_close_and_final_sent_phases_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=positive_probe_fixture(Path(tmp),'multi_channel')
            client=json.loads((f.stage/'client-result.json').read_text())
            self.assertEqual(client['result']['channels'][0]['sent'],stream(probe_baseline()))
            self.assertEqual(f.channels[0]['meters']['client_read'],stream(probe_baseline()+probe_shutdown()))
            with patch.object(subject,'REPO',f.repo):
                proof=subject.verify_transport_integrity(f.stage,f.frozen,owner_kind='transport_probe')
            self.assertTrue(proof['passed'])

    def test_full_multichannel_phase_proof_rejects_changed_baseline_control_and_endpoints(self):
        cases = {
            'wrong_saved_baseline': 'before-closing baseline',
            'wrong_baseline_data': 'baseline DATA slice',
            'wrong_final_digest': 'final baseline plus shutdown',
            'wrong_upload_endpoint': 'original bytes differ',
            'wrong_authenticated_endpoint': 'authenticated endpoint',
            'wrong_shutdown_data': 'shutdown DATA slice',
            'extra_shutdown_data': 'shutdown DATA slice',
            'missing_shutdown_proof': 'shutdown proof',
            'forged_frontier': 'protected event',
            'control_before_ack': 'pending read or chronology',
            'data_before_control_grant': 'DATA, genuine EOF or seal ordering',
            'prefix_missing_ack': 'prefix omits ACK',
            'prefix_includes_tail': 'prefix omits ACK',
            'prefix_not_record_boundary': 'prefix bytes differ',
            'wrong_child_control_hash': 'child control identity or order',
            'duplicate_child_control': 'child control identity or order',
            'child_control_after_close': 'child control identity or order',
            'other_channel_sent_mismatch': 'sent-byte identity',
        }
        for case, phrase in cases.items():
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
                f=positive_probe_fixture(Path(tmp),'multi_channel')
                client=json.loads((f.stage/'client-result.json').read_text())
                transcript=[json.loads(line) for line in (f.stage/'client-transcript.jsonl').read_text().splitlines()]
                proof=client['pending_read_shutdown'];ack=proof['acknowledgment'];front=proof['frontier']
                tail=next(row for row in f.parent if row.get('frame_type')==3 and row.get('direction')=='outgoing'
                          and row.get('channel_id')==1 and row['sequence']>front['sequence'])
                control=next(row for row in transcript if row['event']['kind']=='channel_shutdown_control')
                if case=='wrong_saved_baseline':client['result']['channels'][0]['sent']['sha256']='0'*64
                elif case=='wrong_baseline_data':
                    next(row for row in f.parent if row.get('frame_type')==3 and row.get('direction')=='outgoing')['payload_sha256']='0'*64
                elif case=='wrong_final_digest':f.channels[0]['meters']['client_read']['sha256']='0'*64
                elif case=='wrong_upload_endpoint':f.channels[0]['meters']['upload']['sha256']='0'*64
                elif case=='wrong_authenticated_endpoint':client['result']['channels'][0]['client'][1]+=1
                elif case=='wrong_shutdown_data':tail['payload_sha256']='0'*64
                elif case=='extra_shutdown_data':tail['payload_bytes']+=1
                elif case=='missing_shutdown_proof':client.pop('pending_read_shutdown')
                elif case=='forged_frontier':proof['frontier']['upload_read_pending']=False
                elif case=='control_before_ack':proof['grant_monotonic_s']=ack['monotonic_s']-.01
                elif case=='data_before_control_grant':
                    proof['grant_monotonic_s']=proof['control_sent_monotonic_s']=tail['monotonic_s']+.001
                elif case.startswith('prefix_'):
                    raw=(f.stage/'codehost-transport-v3.jsonl').read_bytes()
                    count=ack['sequence']-1 if case=='prefix_missing_ack' else tail['sequence']
                    part=b''.join(raw.splitlines(keepends=True)[:count])
                    if case=='prefix_not_record_boundary':part=part[:-1]
                    proof['retained_ledger_prefix'].update(stream(part))
                elif case=='wrong_child_control_hash':control['event']['sha256']='0'*64
                elif case=='duplicate_child_control':transcript.insert(transcript.index(control),copy.deepcopy(control))
                elif case=='child_control_after_close':transcript.remove(control);transcript.append(control)
                elif case=='other_channel_sent_mismatch':client['result']['channels'][1]['sent']['sha256']='0'*64
                next(row for row in transcript if row['event']['kind']=='ready_to_finish')['event']['result']=client['result']
                f.write()
                if case=='wrong_baseline_data':
                    for key,kind in (('frontier','channel_finish_frontier'),('drain_begin','owner_drain_begin'),('acknowledgment','owner_drain_ack')):
                        proof[key]=copy.deepcopy(next(row for row in f.parent if row['kind']==kind))
                    part=b''.join((f.stage/'codehost-transport-v3.jsonl').read_bytes().splitlines(keepends=True)[:proof['acknowledgment']['sequence']])
                    proof['retained_ledger_prefix'].update(stream(part))
                f.bind('client-result.json',raw_json(client))
                f.bind('client-transcript.jsonl',b''.join(subject.canonical(row)+b'\n' for row in transcript))
                with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,phrase):
                    subject.verify_transport_integrity(f.stage,f.frozen,owner_kind='transport_probe')

    def test_full_multichannel_tail_can_be_fragmented_without_changing_fixed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=positive_probe_fixture(Path(tmp),'multi_channel')
            client=json.loads((f.stage/'client-result.json').read_text())
            tail=probe_shutdown();front=client['pending_read_shutdown']['frontier']
            for rows,direction in ((f.parent,'outgoing'),(f.namespace,'incoming')):
                candidates=[r for r in rows if r.get('kind')=='frame' and r.get('frame_type')==3
                            and r.get('channel_id')==1 and r.get('direction')==direction]
                original=candidates[-1];at=rows.index(original);parts=[]
                for raw in (tail[:5],tail[5:]):
                    row=copy.deepcopy(original);row.update(payload_bytes=len(raw),payload_sha256=subject.digest(raw));parts.append(row)
                rows[at:at+1]=parts
            for sequence,row in enumerate(f.namespace,1):row['sequence']=sequence
            f.finished['frame_counts']={d:sum(r['kind']=='frame' and r.get('direction')==d for r in f.namespace)
                                        for d in ('incoming','outgoing')}
            f.write()
            # The closed prefix ends at the unchanged ACK; later fragmentation
            # changes neither its bytes nor the original phase-one witness.
            f.bind('client-result.json',raw_json(client))
            with patch.object(subject,'REPO',f.repo):
                self.assertTrue(subject.verify_transport_integrity(f.stage,f.frozen,owner_kind='transport_probe')['passed'])

    def test_full_probe_control_completion_clock_may_follow_child_and_relay(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=positive_probe_fixture(Path(tmp),'multi_channel')
            client=json.loads((f.stage/'client-result.json').read_text())
            close=next(json.loads(line)['event'] for line in (f.stage/'client-transcript.jsonl').read_text().splitlines()
                       if json.loads(line)['event']['kind']=='client_closed')
            client['pending_read_shutdown']['control_sent_monotonic_s']=close['monotonic_s']+.001
            f.bind('client-result.json',raw_json(client))
            with patch.object(subject,'REPO',f.repo):
                self.assertTrue(subject.verify_transport_integrity(f.stage,f.frozen,owner_kind='transport_probe')['passed'])

    def test_probe_foreign_transcript_pid_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=positive_probe_fixture(Path(tmp),'boundary_single_channel')
            p=f.stage/'client-transcript.jsonl';raw=p.read_bytes();p.write_bytes(raw.replace(b'"pid":123',b'"pid":124',1))
            with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,'Probe child identity'):
                subject.verify_transport_integrity(f.stage,f.frozen,owner_kind='transport_probe')

    def test_download_can_be_partial_at_seal_but_final_must_complete(self):
        channel=self.f.channels[-1];seal=copy.deepcopy(channel['h2'])
        seal['frame_complete']['download']=False;seal['frames_complete']=False
        seal['bytes']['download']-=1;seal['frames']['download']-=1
        # An original frontier with no download observed yet allows this real
        # directional progress without claiming simultaneous endpoint snapshots.
        original=copy.deepcopy(channel['finish_frontier'])
        original['bytes']['download']=0;original['frames']['download']=0
        subject.channel_h2(seal,original,complete=False)
        self.assertTrue(seal['upload_complete'])
        subject.h2_progress(channel['h2'],seal,complete=True)
        with self.assertRaisesRegex(ValueError,'completion'):
            subject.h2_summary(seal)

    def test_directional_completion_cannot_disagree_with_global_flags(self):
        self.f.channels[-1]['h2']['frame_complete']['upload']=False
        self.fails('directional completion')

    def test_partial_rejection_cannot_hide_unmatched_data_as_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,_=diagnostic_fixture(Path(tmp),'in_flight_eof')
            row=next(x for x in f.parent if x.get('frame_type')==10)
            row.update(frame_type=3,channel_id=1,payload_bytes=1,payload_sha256=subject.digest(b'x'))
            f.seal()
            with self.assertRaisesRegex(ValueError,'cleanup controls'):
                subject.partial_drain_rejection(f.parent,f.namespace,f.receipt,f.channels[0],f.marker)

    def test_partial_rejection_cannot_omit_actual_drain_or_change_byte_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,_=diagnostic_fixture(Path(tmp),'in_flight_eof')
            f.channels[0]['namespace_closed']['upload']['sha256']='b'*64
            with self.assertRaisesRegex(ValueError,'endpoint bytes'):
                subject.partial_drain_rejection(f.parent,f.namespace,f.receipt,f.channels[0],f.marker)

    def test_partial_rejection_cannot_claim_namespace_ack_or_launder_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,_=diagnostic_fixture(Path(tmp),'in_flight_eof')
            f.finished['owner_drain_acknowledged']=True
            with self.assertRaisesRegex(ValueError,'successful drain'):
                subject.partial_drain_rejection(f.parent,f.namespace,f.receipt,f.channels[0],f.marker)

    def test_failed_namespace_closed_before_intent_keeps_original_local_gate_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,_=diagnostic_fixture(Path(tmp),'in_flight_eof')
            early=[r for r in f.parent if r.get('frame_type')==5
                   or r.get('reason')=='namespace_finished_unqualified'
                   or r['kind'] in ('namespace_finished','namespace_output_closed')]
            for row in early:f.parent.remove(row)
            at=f.parent.index(f.frontiers[0]);f.parent[at:at]=early
            channel=f.channels[0];channel['h2']['retiring']=False;channel['seal_frontier']['retiring']=False
            for n,row in enumerate(f.parent):row.update(wall_unix_s=100+n*.01,monotonic_s=200+n*.01)
            f.marker.update(wall_unix_s=f.frontiers[0]['wall_unix_s']-.001,monotonic_s=f.frontiers[0]['monotonic_s']-.001)
            f.drain_begin.update(start_monotonic_s=f.marker['monotonic_s'],deadline_monotonic_s=f.marker['monotonic_s']+25)
            f.drain.update(start_monotonic_s=f.marker['monotonic_s'],deadline_monotonic_s=f.marker['monotonic_s']+25,
                           completed_monotonic_s=next(r['monotonic_s'] for r in f.parent if r['kind']=='owner_drain_completed'))
            next(r for r in f.parent if r['kind']=='owner_drain_completed').update(f.drain)
            f.seal()
            subject.partial_drain_rejection(f.parent,f.namespace,f.receipt,channel,f.marker)

    def test_partial_rejection_requires_clean_retirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            f,_=diagnostic_fixture(Path(tmp),'in_flight_eof')
            f.retirement['qualified']=False;f.write()
            with patch.object(subject,'REPO',f.repo),self.assertRaisesRegex(ValueError,'retirement'):
                subject.verify_expected_failure(f.stage,f.frozen,case='in_flight_eof')

    def test_typed_closed_pipe_negative_retains_failed_local_close_without_delivery_claim(self):
        for error in ('BrokenPipeError','ConnectionResetError'):
            with self.subTest(error=error),tempfile.TemporaryDirectory() as tmp:
                f=closed_pipe_fixture(Path(tmp),error)
                with patch.object(subject,'REPO',f.repo):
                    proof=subject.verify_expected_failure(f.stage,f.frozen,case='in_flight_eof')
                self.assertTrue(proof['expected_failure_verified'])
                self.assertEqual(proof['rejection_drain']['cleanup_controls_written'],[])
                self.assertTrue(proof['rejection_drain']['cleanup_control_write_failed'])
                self.assertFalse(proof['rejection_drain']['namespace_input_eof_proven'])
                self.assertNotIn('passed',proof)

    def test_closed_pipe_failure_does_not_authorize_other_errors_or_fake_eof(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=closed_pipe_fixture(Path(tmp),'BrokenPipeError')
            next(r for r in f.parent if r['kind']=='owner_input_closed')['after_finish_drain']=True
            with self.assertRaisesRegex(ValueError,'falsely claims delivered FINISH'):
                subject.partial_drain_rejection(f.parent,f.namespace,f.receipt,f.channels[0],f.marker)
            f.receipt['failures'].append('arbitrary_extra_failure')
            with self.assertRaisesRegex(ValueError,'unrelated or missing failures'):
                subject.partial_drain_rejection(f.parent,f.namespace,f.receipt,f.channels[0],f.marker)

    def test_native_initialization_cannot_precede_owner_registration(self):
        self.f.client[0],self.f.client[1]=self.f.client[1],self.f.client[0]
        self.fails('Native initialization')


class TerminalControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=Fixture(Path(self.tmp.name),terminal_control=True)

    def verify(self):
        self.f.refresh_closed_frames();self.f.write()
        with patch.object(subject,'REPO',self.f.repo):
            return subject.verify_transport_integrity(self.f.stage,self.f.frozen)

    def test_complete_top_level_accepts_normal_closed_control_without_active_reset(self):
        self.assertTrue(self.verify()['passed'])
        self.assertEqual(self.f.channels[0]['h2']['reset_streams'],0)
        self.assertEqual(self.f.channels[0]['h2']['reset_records'],[])
        self.assertEqual(self.f.channels[0]['meters']['upload']['bytes'],55)

    def test_full_live_channel_preserves_distinct_endpoint_local_frontiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.f=Fixture(Path(tmp),count=1,terminal_control=True)
            # Separate the namespace's independently observed proof. Its wire
            # anchors remain identical; only the local observed download count
            # differs, including all its later snapshots and EOF projections.
            def local(value):
                if isinstance(value,dict):
                    if value.get('schema')=='campaign002-passive-h2-3':
                        for row in value['terminal_control_records']:row['opposite_observed_frames']=2
                    for item in value.values():local(item)
                elif isinstance(value,list):
                    for item in value:local(item)
            self.f.namespace=copy.deepcopy(self.f.namespace);local(self.f.namespace)
            self.f.finished=self.f.namespace[-1]
            self.f.receipt['namespace_records']=self.f.namespace
            self.f.receipt['finished']=self.f.finished;self.f.terminal['finished']=self.f.finished
            for channel in self.f.channels:
                terminal=copy.deepcopy(channel['namespace_closed']);local(terminal)
                channel['namespace_closed']=terminal
                next(r for r in self.f.parent if r['kind']=='channel_closed' and r['channel_id']==channel['channel_id'])['namespace_closed']=terminal
            self.assertTrue(self.verify()['passed'])
            self.assertEqual(self.f.channels[0]['finish_frontier']['terminal_control_records'][0]['opposite_observed_frames'],3)
            self.assertEqual(self.f.channels[0]['namespace_closed']['finish_frontier']['terminal_control_records'][0]['opposite_observed_frames'],2)
            self.f.channels[0]['namespace_closed']['h2']['terminal_control_records'][0]['opposite_observed_frames']=3
            with self.assertRaises(ValueError):self.verify()

    def test_earlier_eof_control_evidence_cannot_change_or_disappear(self):
        row=self.f.channels[0]['parent_eof']['h2']['terminal_control_records'][0]
        row['opposite_observed_frames']=2
        with self.assertRaisesRegex(ValueError,'terminal control evidence'):self.verify()

    def test_strict_control_schema_types_identity_codes_and_positions(self):
        original=copy.deepcopy(self.f.channels[0]['h2'])
        changes=[('direction','download'),('error_code',0),('error_code',2),('error_code',8.0),
                 ('stream_id',True),('stream_id',3),('stream_id',2),('frame',True),('frame',2),
                 ('frame',4),('end_byte',54),('end_byte',56),('opposite_observed_frames',1),
                 ('opposite_observed_frames',4),('opposite_observed_frames',True)]
        for key,value in changes:
            with self.subTest(key=key,value=value):
                changed=copy.deepcopy(original);changed['terminal_control_records'][0][key]=value
                with self.assertRaises(ValueError):subject.h2_summary(changed)
        for key in terminal_record():
            changed=copy.deepcopy(original);changed['terminal_control_records'][0].pop(key)
            with self.subTest(missing=key),self.assertRaises(ValueError):subject.h2_summary(changed)
        changed=copy.deepcopy(original);changed['terminal_control_records'][0]['extra']=True
        with self.assertRaises(ValueError):subject.h2_summary(changed)
        changed=copy.deepcopy(original);changed.pop('terminal_control_records')
        with self.assertRaises(ValueError):subject.h2_summary(changed)

    def test_closure_proof_requires_exact_complete_order_and_wire_bounds(self):
        original=copy.deepcopy(self.f.channels[0]['h2'])
        mutations=[('opened_upload','frame',1),('opened_upload','frame',3),
                   ('opened_upload','end_byte',41),('upload_closed','frame',3),
                   ('upload_closed','end_byte',43),('download_closed','frame',1),
                   ('download_closed','frame',4),('download_closed','end_byte',36),
                   ('download_closed','end_byte',True)]
        for name,key,value in mutations:
            changed=copy.deepcopy(original);changed['terminal_control_records'][0]['normal_close'][name][key]=value
            with self.subTest(name=name,key=key,value=value),self.assertRaises(ValueError):subject.h2_summary(changed)
        for name in ('opened_upload','upload_closed','download_closed'):
            changed=copy.deepcopy(original);changed['terminal_control_records'][0]['normal_close'].pop(name)
            with self.assertRaises(ValueError):subject.h2_summary(changed)

    def test_duplicate_overflow_and_active_or_reset_identity_never_qualify(self):
        original=copy.deepcopy(self.f.channels[0]['h2'])
        for count in (2,65):
            changed=copy.deepcopy(original);changed['closed_streams']=count
            changed['terminal_control_records']*=count
            with self.assertRaises(ValueError):subject.h2_summary(changed)
        changed=copy.deepcopy(original);changed.update(open_streams=1,active_stream_ids=[1])
        with self.assertRaises(ValueError):subject.h2_summary(changed)
        changed=copy.deepcopy(original);changed.update(reset_streams=1,
            reset_records=[{'direction':'upload','stream_id':1,'error_code':8}])
        with self.assertRaises(ValueError):subject.h2_summary(changed)

    def test_controls_are_immutable_in_original_frontier_and_later_progress(self):
        old=copy.deepcopy(self.f.channels[0]['h2']);later=copy.deepcopy(old);later['retiring']=True
        subject.channel_h2(later,old)
        for mutate in ('missing','changed','new'):
            changed=copy.deepcopy(later);front=copy.deepcopy(old)
            if mutate=='missing':changed['terminal_control_records']=[]
            if mutate=='changed':changed['terminal_control_records'][0]['opposite_observed_frames']=2
            if mutate=='new':front['terminal_control_records']=[]
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):subject.channel_h2(changed,front)
        later['terminal_control_records'][0]['opposite_observed_frames']=2
        with self.assertRaises(ValueError):subject.h2_progress(later,old)
        before=copy.deepcopy(old);before['terminal_control_records']=[]
        subject.h2_progress(old,before)
        before['retiring']=True
        with self.assertRaises(ValueError):subject.h2_progress(old,before)

    def test_only_local_opposite_observation_is_projected(self):
        parent=copy.deepcopy(self.f.channels[0]['h2']);namespace=copy.deepcopy(parent)
        namespace['terminal_control_records'][0]['opposite_observed_frames']=2
        subject.h2_summary(parent);subject.h2_summary(namespace)
        self.assertEqual(subject.h2_facts(parent),subject.h2_facts(namespace))
        self.assertEqual(parent['terminal_control_records'][0]['opposite_observed_frames'],3)
        namespace['terminal_control_records'][0]['normal_close']['download_closed']['end_byte']=19
        self.assertNotEqual(subject.h2_facts(parent),subject.h2_facts(namespace))

    def test_full_verifier_rejects_changed_canonical_endpoint_and_dropped_bytes(self):
        self.assertTrue(self.verify()['passed'])
        channel=self.f.channels[0]
        channel['namespace_closed']['h2']=copy.deepcopy(channel['h2'])
        channel['namespace_closed']['h2']['terminal_control_records'][0]['normal_close']['download_closed']['end_byte']=19
        with self.assertRaisesRegex(ValueError,'endpoint|frontier|projection'):self.verify()
        channel['namespace_closed']['h2']=channel['h2']
        channel['meters']['upload']=stream(b'not the observed upload')
        with self.assertRaises(ValueError):self.verify()

    def test_full_verifier_still_rejects_missing_eof_and_retirement(self):
        row=self.f.channels[0]['parent_eof'];self.f.parent.remove(row)
        with self.assertRaises(ValueError):self.verify()
        self.f.parent.insert(next(i for i,r in enumerate(self.f.parent) if r.get('frame_type')==4),row)
        self.f.retirement['qualified']=False
        with self.assertRaises(ValueError):self.verify()

    def test_oversized_closed_metadata_never_bypasses_existing_frame_bound(self):
        row=next(r for r in self.f.parent if r.get('frame_type')==5)
        row['payload_bytes']=subject.MAX_FRAME_PAYLOAD+1
        self.f.write()
        with patch.object(subject,'REPO',self.f.repo),self.assertRaises(ValueError):
            subject.verify_transport_integrity(self.f.stage,self.f.frozen)


if __name__=='__main__':unittest.main()
