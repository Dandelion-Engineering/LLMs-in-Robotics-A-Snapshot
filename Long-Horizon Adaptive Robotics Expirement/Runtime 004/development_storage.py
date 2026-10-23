"""Development-only evidence locations; no file creation or evaluation authority."""
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
DEFAULT_RAW_ROOT = HERE.parent / 'Evidence' / 'raw'
SCHEMA = 'development-evidence-location-1'


def safe_run_id(run_id):
    if (not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', run_id)
            or run_id.endswith('.') or Path(run_id).name != run_id
            or run_id.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                                               *('COM' + str(i) for i in range(1, 10)),
                                               *('LPT' + str(i) for i in range(1, 10))}):
        raise ValueError('Development run ID must be one safe directory name')
    return run_id


def location(run_id, raw_root=None, *, default_root=None, require_fresh=False):
    safe_run_id(run_id)
    supplied = Path(raw_root if raw_root is not None else (default_root or DEFAULT_RAW_ROOT))
    if not supplied.is_absolute():
        raise ValueError('Development raw root must be an absolute local path')
    if os.name == 'nt' and (len(supplied.drive) != 2 or supplied.drive[1] != ':'):
        raise ValueError('Development raw root must use a local Windows drive')
    root = supplied.resolve()
    if root.exists() and not root.is_dir():
        raise ValueError('Development raw root must be a directory')
    if (any(part.casefold() == 'candidate_state' for part in root.parts)
            or any(root.is_relative_to(path.resolve()) for path in (HERE, HERE.parent / 'Architecture Map'))):
        raise ValueError('Development evidence cannot be inside source, map or candidate state')
    path = root / run_id
    if path.resolve() != path or path.resolve().parent != root:
        raise ValueError('Development run directory escaped its exact assigned root')
    if require_fresh and path.exists():
        raise ValueError('Development run evidence directory must be fresh')
    return {'schema_version': SCHEMA, 'raw_root': str(root), 'evidence_dir': str(path)}


def registered_location(run_id, value):
    if value is None:
        return location(run_id)
    if not isinstance(value, dict) or set(value) != {'schema_version', 'raw_root', 'evidence_dir'}:
        raise ValueError('Malformed registered development evidence location')
    expected = location(run_id, value['raw_root'])
    if value != expected:
        raise ValueError('Registered development evidence location does not match the exact run directory')
    return expected
