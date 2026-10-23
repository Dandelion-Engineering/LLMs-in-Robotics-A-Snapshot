"""Hash-bound location of a closed, noncredential workspace archive."""
import json
from pathlib import Path
from common import sha

PUBLIC_EXPORT_ROOT=Path('D:/Dandelion-Campaign005-Exports')

def locate(block_evidence):
    root=Path(block_evidence);ref=root/'archive-location.json'
    if not ref.is_file():return root/'evidence.tar.gz'
    value=json.loads(ref.read_text(encoding='utf-8'));path=Path(value['path'])
    if path.stat().st_size!=value['bytes'] or sha(path)!=value['sha256']:
        raise ValueError('Closed workspace archive identity changed')
    return path
