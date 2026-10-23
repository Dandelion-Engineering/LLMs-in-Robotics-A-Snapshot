"""Bind the small private deliverable copy to completed verification and playback."""
from pathlib import Path
import hashlib,json,shutil
D=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    v=load(D/'video-verification.json');b=load(D/'browser-playback-review.json');m=load(D/'source-timecode-manifest.json')
    assert v['passed'] and b['passed'] and b['source_video']['sha256']==v['video']['sha256']==m['video']['sha256']
    assert b['final']['ended'] and b['final']['rate']==1 and b['final']['time']==140
    assert sha(v['video']['path'])==v['video']['sha256']
    for p,r in m['input_identities'].items():assert sha(p)==r['sha256'] and Path(p).stat().st_size==r['bytes']
    folder=D/'deliverables';folder.mkdir(exist_ok=True);target=folder/Path(v['video']['path']).name
    if target.exists():assert sha(target)==v['video']['sha256']
    else:shutil.copyfile(v['video']['path'],target)
    assert sha(target)==v['video']['sha256']
    result={'passed':True,'production_date':'2026-10-23','video':{'repository_path':str(target),'render_source':v['video']['path'],
          'sha256':sha(target),'bytes':target.stat().st_size,'duration_s':140,'width':1920,'height':1080,'fps':24,'audio_streams':0},
        'caption_transcript':'captions.txt','subtitle_sidecar':'captions.srt','source_timecode_manifest':'source-timecode-manifest.json',
        'frame_sources':'frame-sources.jsonl.gz','cue_source_bindings':'cue-evidence-bindings.json',
        'verification_sha256':sha(D/'video-verification.json'),'playback_receipt_sha256':sha(D/'browser-playback-review.json'),
        'post_playback_original_input_identities_unchanged':len(m['input_identities']),
        'publication':False,'historical_sources_or_experiments_modified':False}
    (D/'delivery-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
