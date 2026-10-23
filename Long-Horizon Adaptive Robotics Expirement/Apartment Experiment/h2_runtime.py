"""Bounded proof of ordinary client CANCEL races (RFC 9113 sections 5.1, 6.4).

Only pre-cleanup, pre-retirement upload CANCEL on a proved opened stream is
eligible. Original byte traces, raw reset counts and endpoint-local ordering
remain visible. No payload is changed and no connection error is excused.
"""
import json
import codehost_mux_protocol as mux

MAX_RUNTIME_CANCELS=64
Original=mux.H2Witness

class H2Witness(Original):
    def __init__(self):
        super().__init__();self._runtime_records=[]

    def _complete(self,direction,frame):
        if frame['kind']!=3 or self.cleanup_phase_nonce is not None or self.retirement_streams is not None:
            return super()._complete(direction,frame)
        stream=frame['stream'];evidence=self._evidence.get(stream)
        if (direction!='upload' or frame['flags'] or int.from_bytes(frame['prefix'],'big')!=8
                or frame['cleanup_at_start'] is not None or frame['retirement_at_start']):
            raise ValueError('HTTP/2 runtime reset is not client CANCEL')
        if (stream in self._cancelled or evidence is None
                or evidence['opening_headers_complete'] is None
                or stream not in self.streams and stream not in self._normal_close_proofs):
            raise ValueError('HTTP/2 runtime cancellation lacks unique complete opening')
        if len(self._runtime_records)>=MAX_RUNTIME_CANCELS:
            raise ValueError('HTTP/2 runtime cancellation bound')
        state=self.directions[direction]
        position={'frame':state['frames']+1,'end_byte':state['wire_bytes']}
        active=stream in self.streams
        if active:
            if self.resets>=mux.MAX_H2_STREAMS:raise ValueError('HTTP/2 reset bound')
            ri,ti=len(self.reset_records),None
            self.resets+=1;self.reset_records.append(dict(direction='upload',stream_id=stream,error_code=8))
            value=self.streams.pop(stream)
        else:
            if len(self.terminal_control_records)>=mux.MAX_TERMINAL_CONTROLS:
                raise ValueError('HTTP/2 terminal control bound')
            ri,ti=None,len(self.terminal_control_records)
            self.terminal_control_records.append(dict(direction='upload',stream_id=stream,error_code=8,
                **position,normal_close={k:dict(v) for k,v in self._normal_close_proofs[stream].items()},
                opposite_observed_frames=self.directions['download']['frames']))
            value=self._normal_states[stream]
        self._cancelled[stream]=dict(value)
        self._runtime_records.append(dict(schema='apartment-h2-runtime-cancel-1',stream_id=stream,
            cancel=dict(direction='upload',type=3,flags=0,payload_length=4,error_code=8,**position,
                        start_byte=frame['start_byte'],sha256=frame['digest'].hexdigest()),
            local=dict(classification='active' if active else 'normal_closed',reset_record_index=ri,
                       terminal_control_index=ti,opposite_observed_frames=self.directions['download']['frames'])))

    def _explained_resets(self):
        rows=self._cleanup_records+self._runtime_records
        active=[r for r in rows if r['local']['classification']=='active']
        indices=[r['local']['reset_record_index'] for r in active]
        return (len(indices)==self.resets==len(self.reset_records)
                and sorted(indices)==list(range(self.resets))
                and all(self.reset_records[r['local']['reset_record_index']]==dict(direction='upload',stream_id=r['stream_id'],error_code=8)
                        for r in active)
                and all(r['phase_nonce']==self.cleanup_phase_nonce for r in self._cleanup_records))

    def validate_reset_scope(self,frontier=None):
        if self._explained_resets():return
        raise ValueError('Unexplained HTTP/2 reset')

    def begin_cleanup(self,nonce):
        if (not isinstance(nonce,str) or len(nonce)!=32 or any(c not in '0123456789abcdef' for c in nonce)):
            raise ValueError('Invalid HTTP/2 cleanup nonce')
        if self.cleanup_phase_nonce is not None or self.retirement_streams is not None:
            raise ValueError('Duplicate or late HTTP/2 cleanup')
        if self.error or not self._explained_resets():raise ValueError('HTTP/2 cleanup follows unexplained reset or error')
        frontier=self.summary();self.cleanup_phase_nonce=nonce
        self._cleanup_active=frozenset(s for s in self.streams if self._evidence[s]['opening_headers_complete'] is not None)
        self._cleanup_frontier={d+'_'+k:self.directions[d][k] for d in ('upload','download') for k in ('frames','wire_bytes')}
        self._cleanup_frontier['last_stream_id']=self.last_stream
        return frontier

    def summary(self):
        value=super().summary();rows=[]
        for record in self._runtime_records:
            row=json.loads(mux.canonical(record));evidence=self._evidence[row['stream_id']]
            for key in ('opened_upload','opening_headers_complete','upload_end_stream','upload_headers_complete','download_end_stream','download_headers_complete'):
                row[key]=dict(evidence[key]) if evidence[key] is not None else None
            row['wire']={d:dict(frames=t['frames'],bytes=t['bytes'],sha256=t['digest'].hexdigest()) for d,t in evidence['_wire'].items()}
            rows.append(row)
        value['runtime_cancel_records']=rows
        return value

    def idle_eof(self):
        value=self.summary()
        if (value['error'] or not all(value[n] for n in ('preface_complete','settings_complete','frames_complete','headers_complete'))
                or value['open_streams'] or not self._explained_resets()):
            raise ValueError('HTTP/2 EOF is not proven clean and idle')
        return value

def install():
    mux.H2Witness=H2Witness
