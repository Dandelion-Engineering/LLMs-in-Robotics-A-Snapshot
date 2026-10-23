"""Single-use registered block launcher; no retry or repair branch."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from common import sha
from coordinator import approved_manifest,run

def launch(path):
    path=Path(path).resolve();m=approved_manifest(path)
    allocation=m['allocation_reference'];assert sha(allocation['path'])==allocation['sha256']
    a=json.loads(Path(allocation['path']).read_text())
    assert (a['blocks'],a['encounters_per_block'],a['max_sessions_per_occurrence'],a['max_model_sessions'])==(1,3,3,9)
    assert a['no_replacements'] is True and not Path(m['output']).exists()
    assert m['model']==dict(name='gpt-6-astra',effort='max',bootstrap='Follow the instructions in RobotAgentPrompt.md.',fresh_ephemeral_thread=True)
    return run(m['output'],path)

if __name__=='__main__':raise SystemExit(launch(sys.argv[1]))
