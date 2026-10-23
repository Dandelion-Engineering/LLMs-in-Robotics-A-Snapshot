"""Bound the instrumentation diff without running native code or assessments."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

D = Path(__file__).resolve().parent.parent
OUTPUT = D / 'final-check-002'
C = D.parent.parent
R = C.parent
REPO = R.parent.parent


def sha(data): return hashlib.sha256(data).hexdigest()


def bind(path):
    data=path.read_bytes()
    return {'path':str(path.resolve()),'bytes':len(data),'sha256':sha(data)}


def write(name, value):
    with (OUTPUT/name).open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,indent=2)+'\n')


def dump(node): return ast.dump(node,include_attributes=False)


def main():
    method=C/'io-repair/SOCKET_ABORT_DIAGNOSTICS_V1.md'
    assert sha(method.read_bytes())=='ec46e6212cfc9b2844fd45715014a1a96b749d3764a2031fe4eec6d6076109d8'
    old=(D/'before-codehost_bridge_v3.py').read_bytes()
    current=(C/'harness/codehost_bridge_v3.py').read_bytes()
    old_test=(D/'before-test_codehost_bridge_v3.py').read_bytes()
    current_test=(C/'harness/test_codehost_bridge_v3.py').read_bytes()
    assert sha(old)=='332bca286235715c241b36996a7c35c38f4bb966152395a32976eeebd1244263'
    assert sha(old_test)=='2cdbc6689ac420c055dbcd5e2ffd9923dd4bdbee5d3b3e47f4600e5c3ee90ea1'
    release=R.parent/'Architecture Map/releases/RCI001-C02-dev-090'
    with zipfile.ZipFile(release/'code.zip') as archive:
        for name,data in [('codehost_bridge_v3.py',old),('test_codehost_bridge_v3.py',old_test)]:
            assert archive.read((C/'harness'/name).relative_to(REPO).as_posix()) == data
    reversed_source=current.replace(b'        self.socket_failure_seen = False\n',b'',1)
    start=reversed_source.index(b'    def record_socket_failure(')
    end=reversed_source.index(b'    async def upload(',start)
    reversed_source=reversed_source[:start]+reversed_source[end:]
    added=(b"                except OSError as error:\n"
           b"                    self.record_socket_failure(channel, 'upload_read', error)\n"
           b"                    raise\n")
    assert reversed_source.count(added)==1
    reversed_source=reversed_source.replace(added,b'',1)
    added=(b'                    try:\n'
           b'                        channel.writer.write(data); await channel.writer.drain()\n'
           b'                    except OSError as error:\n'
           b"                        self.record_socket_failure(channel, 'download_write', error)\n"
           b'                        raise\n')
    assert reversed_source.count(added)==1
    reversed_source=reversed_source.replace(added,b'                    channel.writer.write(data); await channel.writer.drain()\n',1)
    assert reversed_source==old
    a=current_test.index(b'    async def test_socket_abort_metadata_does_not_qualify_or_invent_eof(')
    z=current_test.index(b'class SocketAdapterTests',a)
    assert current_test[:a]+current_test[z:]==old_test
    before_tree=ast.parse(old);after_tree=ast.parse(current)
    changes=[]
    for before,after in zip(before_tree.body,after_tree.body,strict=True):
        if dump(before)==dump(after): continue
        assert isinstance(before,ast.ClassDef) and before.name in ('Channel','Bridge') and after.name==before.name
        prior={node.name:node for node in before.body if hasattr(node,'name')}
        final={node.name:node for node in after.body if hasattr(node,'name')}
        for name,node in final.items():
            if name not in prior or dump(node)!=dump(prior[name]): changes.append(before.name+'.'+name)
    assert changes==['Channel.__init__','Bridge.record_socket_failure','Bridge.upload','Bridge.sink']
    for name,data in [('codehost_bridge_v3.py',current),('test_codehost_bridge_v3.py',current_test)]:
        with (OUTPUT/('final-'+name)).open('xb') as stream: stream.write(data)
    diff=''.join(difflib.unified_diff(old.decode().splitlines(True),current.decode().splitlines(True),
                                  fromfile='dev090/codehost_bridge_v3.py',tofile='instrumented/codehost_bridge_v3.py'))
    with (OUTPUT/'source.diff').open('x',encoding='utf-8',newline='\n') as stream: stream.write(diff)
    parity={'schema':'campaign002-socket-diagnostic-source-parity-1','passed':True,
        'method':bind(method),'source_before':bind(D/'before-codehost_bridge_v3.py'),
        'source_after':bind(C/'harness/codehost_bridge_v3.py'),
        'tests_before':bind(D/'before-test_codehost_bridge_v3.py'),
        'tests_after':bind(C/'harness/test_codehost_bridge_v3.py'),
        'old_sources_equal_dev090_archive':True,'source_exact_byte_reversal':True,
        'tests_exact_addition_reversal':True,'changed_ast_nodes':changes,
        'SocketReader_and_SocketWriter_unchanged':True,
        'all_other_production_AST_nodes_unchanged':True,
        'all_preexisting_test_AST_nodes_unchanged':True,'source_diff':bind(OUTPUT/'source.diff')}
    write('source-parity.json',parity)
    red=json.loads((D/'red-001/receipt.json').read_text(encoding='utf-8'))
    green=json.loads((D/'green-002/receipt.json').read_text(encoding='utf-8'))
    assert red['exit_code']==1 and green['exit_code']==0
    assert green['sources']=={n:sha((C/'harness'/n).read_bytes()) for n in ('codehost_bridge_v3.py','test_codehost_bridge_v3.py')}
    stderr=(D/'green-002/stderr.txt').read_text(encoding='utf-8')
    assert 'Ran 9 tests' in stderr and stderr.rstrip().endswith('OK')
    write('receipt.json',{'schema':'campaign002-socket-abort-instrumentation-development-1','passed':True,
        'scope':'Metadata instrumentation only; no transport acceptance, genuine EOF, owner, frame, drain, timing or retirement gate changes. No native/model/queue launch.',
        'method':bind(method),'source_bindings':{n:bind(C/'harness'/n) for n in ('codehost_bridge_v3.py','test_codehost_bridge_v3.py')},
        'prior_full_bridge_checkpoint':bind(D/'green-001/receipt.json'),'prior_instrumentation_receipt':bind(D/'receipt.json'),'before':bind(D/'before.json'),'source_parity':bind(OUTPUT/'source-parity.json'),
        'red':{'receipt':bind(D/'red-001/receipt.json'),'stderr':bind(D/'red-001/stderr.txt'),
               'tests':9,'failures':2,'errors':6,'note':'Subtest error count includes both writer sites; cancellation negatives already passed.'},
        'green':{'receipt':bind(D/'green-002/receipt.json'),'stderr':bind(D/'green-002/stderr.txt'),'tests':9},
        'event_contract':{'kind':'socket_failure','diagnostic_schema':'campaign002-socket-failure-1',
            'first_only':'per authenticated channel, before existing fatal handling',
            'operation':['upload_read','download_write'],'numeric_codes':'genuine integers in [-2^31,2^31), otherwise null',
            'exception_classes':['OSError','ConnectionError','ConnectionAbortedError','ConnectionRefusedError','ConnectionResetError','BrokenPipeError','TimeoutError','BlockingIOError','InterruptedError','OtherOSError'],
            'forbidden':'exception messages/args, dynamic class names, payloads, headers, endpoints, credentials, capabilities, traceback text',
            'recording_failure':'Original socket error is rethrown; ledger retains its existing abort behavior; no alternate success.'},
        'limits':'Synthetic in-memory tests establish diagnostic behavior, not the OS cause of Smoke026 or real Windows loopback behavior.'})
    print(json.dumps({'receipt':bind(OUTPUT/'receipt.json'),'sources':parity['source_after'],'tests':parity['tests_after'],'tests_passed':9}))


if __name__=='__main__': main()
