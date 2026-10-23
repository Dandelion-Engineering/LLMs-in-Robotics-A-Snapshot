"""Derive the v3 operator freezer from the established v2 preparation path."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
APP=HERE.parents[1]
text=(APP/'revision_freeze.py').read_text(encoding='utf-8')
def replace(old,new):
    global text
    assert text.count(old)==1,old
    text=text.replace(old,new)
replace('"""Freeze the commissioned v2 revision and create its pristine matched pair."""','"""Freeze independently commissioned v3; no condition is launched here."""')
replace('from common import HERE,REPO,DEFAULT_ROOT,canonical,inventory,read,save,sha',
    'OPS=Path(__file__).resolve().parent\nsys.path.insert(0,str(OPS.parents[1]))\nfrom common import HERE,REPO,DEFAULT_ROOT,canonical,inventory,read,save,sha')
replace('from revision_config import CONFIG,REVISION,PREFIX',
    "from revision_config import CONFIG\nREVISION='APARTMENT-v3-cup-physics-frozen'\nPREFIX='APARTMENT-v3'")
replace("status=read(validation/'queue-status.json');proof=read(validation/'output/result.json')",
    "assert root==Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3').resolve()\n    assert read(OPS/'publication-pushed.json')['passed'] is True\n    status=read(OPS/'commissioning001-terminal.json');proof=read(validation/'output/result.json')")
replace("assert proof['passed'] is True and all(proof['checks'].values())",
    "assert proof['passed'] is True and len(proof['checks'])==10 and all(proof['checks'].values())")
replace("save(HERE/'commissioning.json',certificate);save(HERE/'commissioning-audit.json',proof)",
    "prior=OPS/'previous-working-certificates';prior.mkdir(exist_ok=False)\n    for name in ('commissioning.json','commissioning-audit.json','prepared.json','preparation-readback.json','analysis-freeze.json'):\n        shutil.copyfile(HERE/name,prior/name)\n    save(HERE/'commissioning.json',certificate);save(HERE/'commissioning-audit.json',proof)")
replace("('RELIABILITY-REVISION.md','ANALYSIS.md','SECOND-FAILURE-INVESTIGATION.md')",
    "('RELIABILITY-REVISION.md','ANALYSIS.md','CUP-PHYSICS-REVISION.md')")
replace("authority=HERE/'operations/session-33/launch-authority.json'",
    "authority=OPS/'authority-original.md'\n    assert '**Randy (2026-10-08 17:27 PDT):**' in authority.read_text(encoding='utf-8')")
replace("authority_target=frozen/'operations/session-33/launch-authority.json'",
    "authority_target=frozen/'operations/session-37/authority-original.md'")
replace("original=DEFAULT_ROOT/'official/apartment-v1';previous=DEFAULT_ROOT/'official/apartment-v1-restart001'",
    "assert not any('original-v2-filesystems' in name for name in inventory(root/'frozen_repository'))\n    original=DEFAULT_ROOT/'official/apartment-v2';previous=DEFAULT_ROOT/'official/apartment-v1-restart001'")
replace("prior_histories_engineering_only=[str(original),str(previous)]",
    "prior_histories_engineering_only=[str(original),str(previous),str(DEFAULT_ROOT/'official/apartment-v1')]")
replace("October 7 11:50 PDT prospective amendment and launch instruction",
    "October 8 17:27 PDT publication, complete commissioning and conditional Baseline authority")
replace("schema='apartment-analysis-freeze-3'","schema='apartment-analysis-freeze-4'")
replace("['apartment','frozen','reliability','recovery','revised-geometry']","['apartment','frozen','cup-physics','pristine-pair']")
replace("'parent_revision_id':'APARTMENT-v1-storage2-frozen'","'parent_revision_id':'APARTMENT-v2-reliability-frozen'")
replace("'title':'Apartment v2 verified session boundaries and revised shared environment'","'title':'Apartment v3 two-attribute cylindrical-cup correction'")
replace("'summary':'Pristine actual filesystem pair; 360/600-second windows, wider kitchen access, deliberately unreachable bedroom port, structured errors and explicit immutable clean-boundary recovery.'",
    "'summary':'Pristine matched pair after independent commissioning: original v2 apparatus except collision tolerance 1e-10 and cup condim6; same schedule, templates, model and 360/600-second windows.'")
replace("'mechanism':'Continuous MuJoCo perception-only embodied tasks, unchanged gpt-6-astra/max and sensors; verified world/RNG/inode/replay checkpoints at every normal boundary, clock epochs and failed-tail preserving recovery branches. No native retries or model fallback.'",
    "'mechanism':'Tightened convex collision tolerance and activated prescribed rolling resistance on the existing cylindrical cup. Continuous MuJoCo tasks, gpt-6-astra/max, sensors, controls, templates, verified checkpoints and recovery remain unchanged. Fresh fixed physics/integrated and actual-terminal recording checks pass; no learned state is carried forward.'")
replace("'protocol_id':'APARTMENT-v2'","'protocol_id':'APARTMENT-v3'")
replace("'paired_block_id':'APARTMENT-pair-002'","'paired_block_id':'APARTMENT-pair-003'")
replace("prior_failed_histories='engineering evidence only'","prior_failed_histories='All original v1/v2 histories retained separately; no learning transferred'")
replace("'APARTMENT-v1-baseline','APARTMENT-v1-restart001-baseline'","'APARTMENT-v1-baseline','APARTMENT-v1-restart001-baseline','APARTMENT-v2-baseline','APARTMENT-v2-maps'")
replace("'body':'Randy explicitly authorized this pristine revised pair, 360/600-second windows and shared environment changes. Both prior failed official histories are now engineering evidence only and contribute no learned or scored state. The original hidden schedule and pristine template bytes are retained. Every normal session boundary checkpoints; explicit immutable recovery preserves and counts failed tails. Baseline launch and 30-minute monitoring are authorized after commissioning; Maps requires a later human instruction. Preparation is not a scientific result.'",
    "'body':'Randy ordered original-filesystem publication first, recorder correction and complete independent qualification second, then a pristine revised pair and one Baseline launch. Publication and all 10 independent commissioning groups passed. Only the two cup physics attributes change the official apparatus; the original schedule, 360/600-second windows, pristine templates, model and recovery remain matched. Original v2 histories stay immutable and contribute no learning or physical state. Baseline observation every 30 minutes is authorized; Maps and final comparison require later direction. Preparation is not a scientific result.'")
replace("save(root/'preparation-readback.json',receipt);save(HERE/'preparation-readback.json',receipt)",
    "receipt['no_published_corpus_in_frozen_inputs']=True\n    save(root/'preparation-readback.json',receipt);save(HERE/'preparation-readback.json',receipt);save(OPS/'preparation-v3.json',receipt)")
compile(text,'freeze_v3.py','exec')
target=HERE/'freeze_v3.py'
with target.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
print('Created v3 freezer; no preparation or experiment executed')
