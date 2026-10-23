"""Reuse the original namespace entry; replace only codehost's /inside.py bind."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BOUNDARY = HERE.parents[1] / 'readiness-session-10/boundary'


def replace_inside(argv, original, replacement):
    result = list(argv)
    locations = [i for i in range(len(result) - 2)
                 if result[i:i + 3] == ['--ro-bind', str(original), '/inside.py']]
    if len(locations) != 1 or result[-4:] != ['/usr/bin/python3', '-I', '-B', '/inside.py']:
        raise ValueError('Original namespace inside binding changed')
    result[locations[0] + 1] = str(replacement)
    return result


def main():
    if len(sys.argv) < 2 or sys.argv[1] != 'codehost':
        raise SystemExit('Additive entry supports codehost mode only')
    sys.path.insert(0, str(BOUNDARY))
    import linux_entry
    original_command = linux_entry.command
    def command(*args, **kwargs):
        return replace_inside(original_command(*args, **kwargs), BOUNDARY / 'inside.py',
                              HERE / 'codehost_inside_v2.py')
    linux_entry.command = command
    # Original validation, resource limits, identity creation and execv remain exact.
    linux_entry.main()


if __name__ == '__main__':
    main()
