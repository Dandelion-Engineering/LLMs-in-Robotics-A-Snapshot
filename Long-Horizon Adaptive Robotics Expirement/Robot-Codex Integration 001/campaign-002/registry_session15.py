"""Run the existing registry with only Session 15 attribution substituted."""
import hashlib
from pathlib import Path

if __name__ == '__main__':
    path=Path(__file__).with_name('registry.py')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != 'db030c8708d0e555dec52b4775d87157f38d6892d97ea80af5b243503a5fd391':
        raise ValueError('Bound registry source changed')
    old=b"'author':'Codex session 14'"
    if raw.count(old) != 1:raise ValueError('Registry attribution is ambiguous')
    scope={'__name__':'__main__','__file__':str(path)}
    exec(compile(raw.replace(old,b"'author':'Codex session 15'"),str(path),'exec'),scope)
