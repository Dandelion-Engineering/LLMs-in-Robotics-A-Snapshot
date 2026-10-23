"""Explicit versioned production wiring from the verified diagnostic candidate."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
H, A = C/'harness', C/'assessment'
CANDIDATE = HERE.parent/'graceful-process-drain-001'
REPO = HERE.parents[4]
SNAPSHOT = HERE.parents[3]/'Architecture Map/releases/RCI001-C02-dev-098/snapshot.json'

def bind(path):
    raw = path.read_bytes(); return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def replace(text, old, new):
    if text.count(old) != 1: raise ValueError('Expected unique source seam: '+old[:100])
    return text.replace(old, new)

def main():
    frozen = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    for name, identity in frozen['sources'].items():
        if bind(REPO/name) != identity: raise ValueError('Diagnostic source changed before promotion: '+name)
    changed = {}
    path = H/'bootstrap_client_v4.py'; text = path.read_text(encoding='utf-8')
    changed[path] = replace(text, '    def close(self):\n        from native_quiescence import close\n        return close(self, MAX_BYTES)',
        '''    def close(self):
        selected = getattr(self.args, "native_process_drain", False)
        require(type(selected) is bool, "Native process-drain selection must be boolean")
        if selected:
            from native_process_quiescence import close
        else:
            from native_quiescence import close
        return close(self, MAX_BYTES)''')
    path = H/'runtime.py'; text = path.read_text(encoding='utf-8')
    changed[path] = replace(text, '                args.native_exit_barrier=self.native_exit_barrier\n',
        '                args.native_exit_barrier=self.native_exit_barrier\n                args.native_process_drain=True\n')
    path = H/'codehost_bridge_v3.py'; text = path.read_text(encoding='utf-8')
    changed[path] = replace(text, '    def native_exit_barrier(self, request):\n        import native_exit_drain\n',
        '''    def native_exit_barrier(self, request):
        if isinstance(request, dict) and request.get('schema') == 'campaign002-process-drain-request-1':
            import process_drain
            return process_drain.bridge_join(self, request)
        import native_exit_drain
''')
    path = A/'transport_integrity_v3.py'; text = path.read_text(encoding='utf-8')
    text = replace(text, 'import pre_exit_integrity\n', 'import pre_exit_integrity\nimport process_integrity\n')
    old = '''    if pre_exit_integrity.enabled(frozen) and owner_kind == 'model_client':
        pre_exit = pre_exit_integrity.verify(root, frozen, rows, channels, quiescence, repo=REPO)
        for name, binding in pre_exit['input_bindings'].items():
            require(name not in inputs or inputs[name] == binding, 'Pre-exit inputs changed during verification')
            inputs[name] = binding
        result['native_pre_exit_drain'] = pre_exit
'''
    new = '''    process_method = process_integrity.enabled(frozen)
    ordering_reader = process_integrity if process_method else pre_exit_integrity
    if ordering_reader.enabled(frozen) and owner_kind == 'model_client':
        ordering = ordering_reader.verify(root, frozen, rows, channels, quiescence, repo=REPO)
        for name, binding in ordering['input_bindings'].items():
            require(name not in inputs or inputs[name] == binding, 'Native ordering inputs changed during verification')
            inputs[name] = binding
        result['native_process_drain' if process_method else 'native_pre_exit_drain'] = ordering
'''
    changed[path] = replace(text, old, new)
    added = {H/'native_process_quiescence.py': (CANDIDATE/'candidate_native.py').read_text(encoding='utf-8'),
             H/'process_drain.py': (CANDIDATE/'process_drain.py').read_text(encoding='utf-8')}
    text = (CANDIDATE/'process_integrity.py').read_text(encoding='utf-8')
    start, end = text.index('BASE = '), text.index('\ndef require', text.index('BASE = '))
    text = text[:start]+'''METHOD = PREFIX+'io-repair/GRACEFUL_PROCESS_DRAIN_V1.md'
HELPER = PREFIX+'harness/process_drain.py'
CONTROLLER = PREFIX+'harness/native_process_quiescence.py'
ASSESSOR = PREFIX+'assessment/process_integrity.py'
EXCLUSIVE = (METHOD, HELPER, CONTROLLER, ASSESSOR)
SOURCE_NAMES = EXCLUSIVE+tuple(PREFIX+n for n in (
    'harness/bootstrap_client_v4.py', 'harness/runtime.py', 'harness/codehost_bridge_v3.py',
    'harness/native_quiescence.py', 'harness/native_exit_drain.py',
    'assessment/transport_integrity_v3.py', 'assessment/pre_exit_integrity.py'))
'''+text[end:]
    text = replace(text, '''    require(all(name in frozen.get('sources', {}) for name in SOURCE_NAMES), 'incomplete candidate source lineage')
    return True''', '''    present = [name in frozen.get('sources', {}) for name in EXCLUSIVE]
    require(all(present) or not any(present), 'incomplete process-drain source lineage')
    return all(present)''')
    text = replace(text, '    enabled(frozen)\n    sources = {}',
                   "    require(enabled(frozen), 'process-drain method absent')\n    sources = {}")
    added[A/'process_integrity.py'] = text
    for path in added:
        if path.exists(): raise ValueError('Existing production candidate footprint')
    before = {p.relative_to(REPO).as_posix(): bind(p) for p in changed}
    (HERE/'original').mkdir(exist_ok=False)
    for path in changed: (HERE/'original'/path.name).write_bytes(path.read_bytes())
    with (HERE/'before.json').open('x', encoding='utf-8') as stream:
        json.dump({'diagnostic_snapshot': bind(SNAPSHOT), 'unchanged_prior_sources': len(frozen['sources']),
                   'sources': before}, stream, indent=2); stream.write('\n')
    diff = []
    for path, text in changed.items():
        name = path.relative_to(REPO).as_posix()
        diff.extend(difflib.unified_diff(path.read_text(encoding='utf-8').splitlines(True), text.splitlines(True),
                                       fromfile='before/'+name, tofile='after/'+name))
        path.write_text(text, encoding='utf-8', newline='\n')
    for path, text in added.items():
        with path.open('x', encoding='utf-8', newline='\n') as stream: stream.write(text)
    with (HERE/'source.diff').open('x', encoding='utf-8') as stream: stream.write(''.join(diff))
    with (HERE/'after.json').open('x', encoding='utf-8') as stream:
        json.dump({'sources': {p.relative_to(REPO).as_posix(): bind(p) for p in [*changed, *added]},
                   'controller_identical_to_diagnostic': bind(H/'native_process_quiescence.py') == bind(CANDIDATE/'candidate_native.py'),
                   'helper_identical_to_diagnostic': bind(H/'process_drain.py') == bind(CANDIDATE/'process_drain.py'),
                   'diagnostic_candidate_files_unchanged': all(bind(REPO/n) == v for n,v in frozen['sources'].items()
                        if '/graceful-process-drain-001/' in n)}, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'changed': len(changed), 'added': len(added), 'scope': 'trusted method dispatch and independent proof selection'}))

if __name__ == '__main__': main()
