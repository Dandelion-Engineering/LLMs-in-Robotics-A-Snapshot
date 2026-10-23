"""Prepare explicit v6 wrappers from retained one-shot guarded launch sources."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent/'single-interrupt-diagnostic-v4'

def write(name, text):
    with (HERE/name).open('x', encoding='utf-8', newline='\n') as stream: stream.write(text)

def main():
    common = (HERE.parent/'single-interrupt-diagnostic-v5/common.py').read_text(encoding='utf-8')
    common = common.replace('shutdown-diagnostic-005', 'shutdown-diagnostic-006')
    common = common.replace('RCI001-C02-dev-097', 'RCI001-C02-dev-098')
    common = common.replace('single-interrupt-diagnostic-v5', 'single-interrupt-diagnostic-v6')
    common = common.replace("METHOD = CAMPAIGN / 'io-repair/native-os-closure-001/DECLARATION.md'",
                            "METHOD = CAMPAIGN / 'io-repair/graceful-process-drain-001/IMPLEMENTATION.md'")
    start = common.index('# All previously frozen')
    end = common.index('\ndef validate_manifest', start)
    common = common[:start]+'''# Preserve all986 prior source inputs and append the prospective candidate.
PREVIOUS = RCI.parent/'Architecture Map/releases/RCI001-C02-dev-097/snapshot.json'
CANDIDATE = CAMPAIGN/'io-repair/graceful-process-drain-001'

def required_inputs():
    prior = read(PREVIOUS)['sources']
    paths = list(HERE.glob('*.py'))+[ROOT/'DECLARATION.md', METHOD, REFERENCE, PHYSICAL,
        GUARD, STORAGE_POLICY, STORAGE_BASELINE]
    paths += [p for p in CANDIDATE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    return sorted(set(prior)|{p.relative_to(REPO).as_posix() for p in paths})

'''+common[end:]
    runner = (PRIOR/'common.py').read_text(encoding='utf-8').split('\ndef runner_argv', 1)[1]
    common = common[:common.index('\ndef control_digest')]+'\ndef runner_argv'+runner
    write('common.py', common)
    write('launch.py', (PRIOR/'launch.py').read_text(encoding='utf-8'))
    run = (PRIOR/'run.py').read_text(encoding='utf-8')
    run = run.replace('"""One unchanged smoke interruption invocation; never resume or qualify."""',
                      '"""One declared candidate interruption invocation; never resume or qualify."""')
    old = "        first = physical.run_invocation('interrupt', args.evidence / 'interrupt', control, args.workspace)"
    new = """        sys.path.insert(0, str(common.CANDIDATE))
        import overlay
        with overlay.installed(physical, args.evidence):
            first = physical.run_invocation('interrupt', args.evidence / 'interrupt', control, args.workspace)"""
    if run.count(old) != 1: raise ValueError('Original one-call wrapper differs')
    write('run.py', run.replace(old, new))

if __name__ == '__main__': main()
