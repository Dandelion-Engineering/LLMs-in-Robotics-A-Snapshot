"""Once-only post-certification pair preparation or independent preflight."""
import argparse
from release2 import *

def require_terminal(name):
    receipt=read(HERE/(name+'-queue.json'))
    status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',receipt['id']],text=True,encoding='utf-8'))
    assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0,name
    assert read(ROOT/name/'output/result.json')['passed'] is True,name

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('freeze','preflight'));args=parser.parse_args()
    require_terminal('audit003')
    certificate=read(ROOT/'audit003/output/certificate.json')
    assert certificate['passed'] and certificate['release_manifest_sha256']==sha(RELEASE/'manifest.json')
    if args.mode=='freeze':
        register('freeze001','freeze_pair.py','Prepare one unused pristine matched v4 pair from the newly certified release, original schedule and actual templates; no native start or model request.',[(HERE/'attempts.py','operator-attempts.py')],['Fresh independent certificate; exact source/config/environment; both pristine original templates; authenticated original hidden schedule; zero starts'],official_writes=True)
    else:
        require_terminal('freeze001')
        register('preflight001','verify_pair.py','Independently verify both pristine v4 conditions, fresh certificate and source/schedule/configuration manifests, original template bytes, current environment, capacity and absence of duplicate official runtimes. No native start or model request.',cases=['Both conditions pristine, prospective analysis, source/environment admission, no duplicate runtime, storage margin'])
    build()

if __name__=='__main__':main()
