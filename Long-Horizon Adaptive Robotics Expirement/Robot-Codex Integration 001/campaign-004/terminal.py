"""Append framework terminal evidence only after resumption AND process retirement."""
import hashlib
import json
import os
from pathlib import Path
import time
from common import canonical, save

def digest(raw):return hashlib.sha256(raw).hexdigest()

class TerminalAppend:
    def __init__(self,evidence):
        self.root=Path(evidence);self.root.mkdir(parents=True,exist_ok=True)

    def finalize(self,continuity,accepted,resumed,retirement):
        if not (accepted.get('status')=='completed' and accepted.get('kind')=='handback'
                and accepted.get('phase')=='terminal' and resumed.get('owner')=='conventional'
                and resumed.get('handback_request_id')==accepted['request_id']
                and resumed.get('authority_epoch')==accepted['new_authority_epoch']
                and resumed.get('session_id')==accepted['session_id']
                and resumed.get('run_id')==accepted['run_id']
                and retirement.get('all_namespaces_retired') is True
                and retirement.get('session_id')==accepted['session_id']
                and retirement.get('run_id')==accepted['run_id']
                and len(retirement.get('evidence_sha256',''))==64):
            raise ValueError('Successful handback, authoritative resumption and namespace retirement required')
        identity=digest(canonical([accepted['run_id'],accepted['session_id'],accepted['request_id']]))
        receipt_path=self.root/(identity+'.json');intent_path=self.root/(identity+'.intent.json')
        path=Path(continuity)
        if path.is_symlink():raise ValueError('Pass canonical continuity backing, not a link')
        raw=path.read_bytes()
        if receipt_path.exists():
            receipt=json.loads(receipt_path.read_text());
            if digest(raw)!=receipt['after_sha256']:raise ValueError('Terminal receipt exists but continuity changed')
            return receipt
        if intent_path.exists():intent=json.loads(intent_path.read_text())
        else:
            if len(raw)>65536:raise ValueError('Canonical continuity exceeds declared bound')
            record={'schema':'campaign004-framework-terminal-1','author':'framework','record_id':identity,
                'run_id':accepted['run_id'],'session_id':accepted['session_id'],
                'handback_request_id':accepted['request_id'],'authority_epoch':accepted['new_authority_epoch'],
                'accepted_event_id':accepted['event_id'],'resumption_event_id':resumed['event_id'],
                'accepted_sim_time_s':accepted['sim_time_s'],'resumed_sim_time_s':resumed['sim_time_s'],
                'resumed_wall_unix_ns':resumed['wall_unix_ns'],'resumption_evidence_sha256':digest(canonical(resumed)),
                'retirement_evidence_sha256':retirement['evidence_sha256'],
                'claim':'Handback accepted; conventional control resumed. This is framework evidence, not an agent claim.',
                'appended_wall_unix_ns':time.time_ns()}
            suffix=b'\n\n<!-- Machine-authored terminal record -->\n'+canonical(record)+b'\n'
            if len(suffix)>4096 or len(raw+suffix)>65536:raise ValueError('Terminal continuity reserve exhausted')
            intent={'before_sha256':digest(raw),'after_sha256':digest(raw+suffix),'suffix_utf8':suffix.decode(),
                    'record':record,'original_bytes':len(raw)}
            save(intent_path,intent)
        if digest(raw)==intent['before_sha256']:
            new=raw+intent['suffix_utf8'].encode();temp=path.with_name('.terminal-next')
            with temp.open('xb') as stream:stream.write(new);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,path)
        elif digest(raw)!=intent['after_sha256']:raise ValueError('Continuity diverged after terminal intent')
        if digest(path.read_bytes())!=intent['after_sha256']:raise ValueError('Terminal append readback failed')
        result={k:v for k,v in intent.items() if k!='suffix_utf8'}
        save(receipt_path,result)
        return result
