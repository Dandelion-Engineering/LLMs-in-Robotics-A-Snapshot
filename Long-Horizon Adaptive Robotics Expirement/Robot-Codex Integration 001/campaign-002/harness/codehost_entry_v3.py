"""Original namespace entry, new fixed inside relay and read-only mux helper."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BOUNDARY = HERE.parents[1] / 'readiness-session-10/boundary'


def replace_inside(argv, original, replacement, helper, cleanup_helper=None):
    result = list(argv)
    locations = [i for i in range(len(result)-2)
                 if result[i:i+3] == ['--ro-bind', str(original), '/inside.py']]
    if len(locations) != 1 or result[-4:] != ['/usr/bin/python3','-I','-B','/inside.py']:
        raise ValueError('Original namespace inside binding changed')
    if any(item in ('/codehost_mux_protocol.py', '/native_cleanup_protocol.py') for item in result):
        raise ValueError('Duplicate fixed helper binding')
    remounts = [i for i in range(len(result)-1) if result[i:i+2] == ['--remount-ro', '/']]
    if len(remounts) != 1 or remounts[0] != len(result)-6:
        raise ValueError('Original terminal root remount changed')
    result[locations[0]+1] = str(replacement)
    # Its destination must exist before the original final root remount.
    bindings = ['--ro-bind', str(helper), '/codehost_mux_protocol.py']
    if cleanup_helper is not None:
        bindings += ['--ro-bind', str(cleanup_helper), '/native_cleanup_protocol.py']
    result[remounts[0]:remounts[0]] = bindings
    return result


def main():
    if len(sys.argv) < 2 or sys.argv[1] != 'codehost':
        raise SystemExit('Additive entry supports codehost mode only')
    sys.path.insert(0,str(BOUNDARY))
    import linux_entry
    original_command = linux_entry.command
    def command(*args, **kwargs):
        return replace_inside(original_command(*args, **kwargs), BOUNDARY/'inside.py',
                              HERE/'codehost_inside_v3.py', HERE/'codehost_mux_protocol.py',
                              HERE/'native_cleanup_protocol.py')
    linux_entry.command = command
    linux_entry.main()


if __name__ == '__main__':
    main()
