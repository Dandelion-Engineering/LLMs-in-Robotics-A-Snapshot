"""Bounded readback of retained engineering evidence, with no model or simulation."""
import ast
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import traceback

from launch_maps import HERE, CODE, OP, FROZEN_CODE
from common import read, save, sha, canonical
from recording import verify_checkpoint, verify_prefix
from audit import native
from repair_validation import transport_readback


def main():
    destination = OP / 'reader-validation.json'
    assert not destination.exists()
    result = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), passed=False,
                  scope='Retained engineering readback only; no new native calls or simulator dynamics', checks={})
    try:
        spec = importlib.util.spec_from_file_location('retained_lifecycle', CODE / 'operations/session-34/summarize_endpoint.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result['lifecycle_fixtures'] = module.validate_fixtures()
        result['checks']['four_retained_lifecycle_fixtures_and_duplicate_rejection'] = True
        root = Path('D:/Dandelion-Apartment-Experiment/engineering/APARTMENT-reliability-live002/output/recovered/maps')
        path = Path(read(root / 'latest-checkpoint.json')['path'])
        result['checkpoint'] = verify_checkpoint(path)
        result['prefix'] = verify_prefix(root, path)
        result['native'] = native(root)
        result['transport'] = {p.name: transport_readback(p / 'native') for p in sorted((root / 'sessions').iterdir())}
        result['checks']['retained_maps_checkpoint_native_inode_sensor_replay_transport'] = True
        original = ast.parse((CODE / 'operations/session-33/audit_terminal.py').read_text(encoding='utf-8'))
        adapted = ast.parse((HERE / 'audit_maps_terminal.py').read_text(encoding='utf-8'))
        def core(tree):
            function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'audit')
            function.args = ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[])
            for node in ast.walk(function):
                if isinstance(node, ast.Constant) and node.value == 'maps':
                    node.value = 'baseline'
            block = next(n for n in function.body if isinstance(n, ast.Try))
            block.body = [n for n in block.body if not (isinstance(n, ast.If) and ast.unparse(n.test) == "run['stage'] == 'official'")]
            return ast.dump(function, include_attributes=False)
        assert core(original) == core(adapted), 'Terminal audit core changed beyond condition routing and official pair gate'
        result['checks']['terminal_audit_core_preserved'] = True
        result['reader_sha256'] = sha(HERE / 'audit_maps_terminal.py')
        result['frozen_readers'] = {name: sha(FROZEN_CODE / name) for name in ('audit.py', 'recording.py', 'repair_validation.py', 'recovery.py', 'run.py')}
        result['passed'] = True
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
    save(destination, result)
    print(canonical({k: v for k, v in result.items() if k in ('passed', 'checks', 'error', 'traceback')}).decode())
    return result['passed']


if __name__ == '__main__':
    raise SystemExit(0 if main() else 1)
