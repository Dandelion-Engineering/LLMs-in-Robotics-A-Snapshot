from pathlib import Path
import sys,json
import assess
p=Path(sys.argv[1]);j=lambda n:json.loads((p/n).read_text(encoding='utf-8'))
result=assess.verify_transport(p,j('paired-registry.json'),j('paired-history.json'))
(p/'independent-proof.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':result['passed'],'proof':result['mirror_epoch_denial']}))
