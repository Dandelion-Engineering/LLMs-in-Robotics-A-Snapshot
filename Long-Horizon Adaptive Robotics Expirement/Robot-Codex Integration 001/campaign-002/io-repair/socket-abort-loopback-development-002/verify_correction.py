"""No-execution source parity and original-artifact preservation checks."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'socket-abort-loopback-development-001'


def bind(path):
    raw=path.read_bytes()
    return {'path':str(path.resolve()),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def main():
    original=json.loads((HERE/'original-001-bindings.json').read_text(encoding='utf-8'))['files']
    assert [bind(path) for path in sorted(OLD.rglob('*')) if path.is_file()]==original
    changes={
        'fixture.py':[
            ('        OSError: "OSError",\n','        OSError: "OSError",\n        TypeError: "TypeError",\n'),
            ('recorder.emit("receive_terminal", case=name, **value)','recorder.emit("receive_terminal", case=name, observation=value)'),
            ('recorder.emit("case_error", case=name, **observation)','recorder.emit("case_error", case=name, observation=observation)'),
        ],
        'launch.py':[
            ('paths = [Path(__file__), HERE / "fixture.py", METHOD, Path(sys.executable)]',
             'paths = [Path(__file__), HERE / "fixture.py", METHOD, HERE / "CORRECTION.md", Path(sys.executable)]'),
        ],
    }
    combined=[]
    for name,replacements in changes.items():
        before=(OLD/name).read_bytes();after=(HERE/name).read_bytes();expected=before
        for old,new in replacements:
            assert expected.count(old.encode())==1
            expected=expected.replace(old.encode(),new.encode(),1)
        assert after==expected
        ast.parse(after)
        combined.extend(difflib.unified_diff(before.decode().splitlines(True),after.decode().splitlines(True),
            fromfile='development-001/'+name,tofile='development-002/'+name))
    with (HERE/'source.diff').open('x',encoding='utf-8',newline='\n') as stream:stream.write(''.join(combined))
    tree=ast.parse((HERE/'fixture.py').read_text(encoding='utf-8'))
    calls=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='emit':
            assert len(node.args)==1 and isinstance(node.args[0],ast.Constant) and type(node.args[0].value) is str
            assert all(keyword.arg not in (None,'kind') for keyword in node.keywords)
            calls.append({'line':node.lineno,'event_kind':node.args[0].value,'fields':[key.arg for key in node.keywords]})
    calls.sort(key=lambda row:row['line'])
    red=json.loads((HERE/'red-001/receipt.json').read_text(encoding='utf-8'))
    green=json.loads((HERE/'green-001/receipt.json').read_text(encoding='utf-8'))
    assert red['exit_code']==1 and green['exit_code']==0
    assert green['source_fixture_sha256']==bind(HERE/'fixture.py')['sha256']
    assert green['test_sha256']==bind(HERE/'no_socket_regression.py')['sha256']
    assert not (HERE/'execution-001').exists()
    receipt={'schema':'campaign002-loopback-logging-correction-1','passed':True,
        'declaration':bind(HERE/'CORRECTION.md'),
        'original_failure_receipt_sha256':'4f4718e83f6d381ec73c90d0f096dfa80558fbd95bcd8ddaec840793aa53be6a',
        'original_001_files_preserved':len(original),'original_bindings':bind(HERE/'original-001-bindings.json'),
        'exact_source_delta':{'fixture.py':'Two kwargs collisions replaced by nested observation; finite TypeError metadata added.',
                              'launch.py':'Only correction declaration added to source_paths; HERE resolves the fresh directory.'},
        'exact_declared_replacements_equal_new_sources':True,
        'all_other_source_bytes_unchanged':True,
        'sources':{name:bind(HERE/name) for name in ('fixture.py','launch.py','no_socket_regression.py','verify_correction.py')},
        'source_diff':bind(HERE/'source.diff'),'emit_call_inventory':calls,
        'red':{'receipt':bind(HERE/'red-001/receipt.json'),'stderr':bind(HERE/'red-001/stderr.txt'),
               'tests':8,'failures':2,'errors':5,'original_duplicate_kind_reproduced':True},
        'green':{'receipt':bind(HERE/'green-001/receipt.json'),'stderr':bind(HERE/'green-001/stderr.txt'),'tests':8},
        'execution_001_absent':True,
        'scope':'No fixture/launcher main, event loop, socket, native app server, model or queue launched. Tests execute only extracted observe_pending/case_error code with an immediate fake reader and actual file Recorder.',
        'limits':'Logging correction is not a transport repair, four-case Windows observation, Smoke026 reproduction or historical outcome promotion.'}
    with (HERE/'receipt.json').open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'receipt':bind(HERE/'receipt.json'),'fixture':bind(HERE/'fixture.py'),'launcher':bind(HERE/'launch.py'),
                      'original_files_unchanged':len(original),'emit_callers_reviewed':len(calls),'tests_passed':8}))


if __name__=='__main__':main()
