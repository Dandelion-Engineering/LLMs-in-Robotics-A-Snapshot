"""Publish audited ZIP bytes and bounded, lossless JSONL views for GitHub."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def text_new(path, text):
    write_new(path, (text + '\n').encode('utf-8'))


def main(package):
    archive = package / 'campaign002-behavioral-evidence-v1.zip'
    manifest_path = archive.with_suffix('.manifest.json')
    manifest = json.loads(manifest_path.read_bytes())
    if manifest['passed'] is not True or sha(archive.read_bytes()) != manifest['sha256']:
        raise ValueError('Authenticated archive identity required')
    expected = {entry['path']: entry for entry in manifest['entries']}
    if len(expected) != 315 or len(expected) != len(manifest['entries']):
        raise ValueError('Expected complete, unique 315-entry public inventory')
    corpus, browse = package / 'corpus', package / 'browse'
    if corpus.exists() or browse.exists():
        raise ValueError('Fresh publication directories required')
    views, largest_record = [], 0
    with zipfile.ZipFile(archive) as source:
        if len(source.infolist()) != len(expected) or set(source.namelist()) != set(expected):
            raise ValueError('ZIP public inventory mismatch')
        for name, entry in expected.items():
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe public entry path')
            raw = source.read(name)
            if len(raw) != entry['bytes'] or sha(raw) != entry['sha256']:
                raise ValueError('ZIP byte mismatch: ' + name)
            write_new(corpus / name, raw)
            if not name.endswith('.jsonl') or len(raw) <= 262144:
                continue
            if not raw.endswith(b'\n'):
                raise ValueError('JSONL without final LF: ' + name)
            pieces, current, first_line, line_number, offset = [], [], 1, 0, 0
            for record in raw.split(b'\n')[:-1]:
                line_number += 1
                line = record + b'\n'
                if record.strip():
                    json.loads(record)
                largest_record = max(largest_record, len(line))
                if current and sum(map(len, current)) + len(line) > 262144:
                    piece = b''.join(current)
                    pieces.append((piece, first_line, line_number - 1, offset))
                    offset += len(piece)
                    current, first_line = [], line_number
                current.append(line)
            if current:
                pieces.append((b''.join(current), first_line, line_number, offset))
            destination = browse / path.parent.name / path.stem
            rows = ['| Part | Source LF lines | Source byte range (end exclusive) |', '|---|---:|---:|']
            parts = []
            for number, (piece, first, last, start) in enumerate(pieces, 1):
                part = destination / f'part-{number:04d}.jsonl'
                write_new(part, piece)
                parts.append({'path': part.relative_to(package).as_posix(), 'sha256': sha(piece),
                              'bytes': len(piece), 'start_byte': start, 'end_byte': start + len(piece),
                              'first_lf_line': first, 'last_lf_line': last})
                rows.append(f'| [{number:04d}]({part.name}) | {first}-{last} | {start}-{start + len(piece)} |')
            relative_source = '../../../corpus/' + name
            text_new(destination / 'README.md', '\n\n'.join([
                '# ' + path.parent.name + ' / ' + path.name,
                f'Exact ordered parts of [the complete source]({relative_source}). Concatenating the part bytes in order reproduces that file exactly. No records, fields, timestamps or provenance were changed.',
                f'Source SHA256 `{entry["sha256"]}`; {len(raw):,} bytes. LF line numbers count byte-delimited lines, including any retained empty lines. Byte offsets are authoritative. Larger individual records remain intact.',
                '\n'.join(rows)]))
            views.append({'source': 'corpus/' + name, 'source_sha256': entry['sha256'],
                          'bytes': len(raw), 'parts': parts})
    # Independent readback of every published file and every concatenated view.
    for name, entry in expected.items():
        raw = (corpus / name).read_bytes()
        if sha(raw) != entry['sha256'] or len(raw) != entry['bytes']:
            raise ValueError('Unpacked byte mismatch: ' + name)
    for view in views:
        restored = b''.join((package / part['path']).read_bytes() for part in view['parts'])
        if sha(restored) != view['source_sha256'] or restored != (package / view['source']).read_bytes():
            raise ValueError('Parts do not reproduce complete source')
    actual = {p.relative_to(corpus).as_posix() for p in corpus.rglob('*') if p.is_file()}
    if actual != set(expected):
        raise ValueError('Unexpected published evidence file')
    run_ids = sorted(p.name for p in (corpus / 'runs').iterdir())
    if len(run_ids) != 10:
        raise ValueError('All ten original valid runs required')
    rows = ['| Run | Exact evidence and final workspace | Ordered trace parts |', '|---|---|---|']
    for run_id in run_ids:
        links = []
        for view in views:
            path = PurePosixPath(view['source'])
            if path.parent.name == run_id:
                links.append(f'[{path.stem}]({run_id}/{path.stem}/README.md)')
        rows.append(f'| {run_id} | [Run index](../corpus/runs/{run_id}/README.md) | ' + ' · '.join(links) + ' |')
    text_new(browse / 'README.md', '\n\n'.join([
        '# Campaign 002 evidence on GitHub',
        'All ten existing valid successes have [complete evidence files](../corpus/README.md) committed directly to Git. Start with each run index for metadata, final workspace files, content/version records and recovery gaps. The larger JSONL traces also have ordered text parts below. Parts retain complete records and exact source bytes; they contain no behavioral interpretation.',
        '\n'.join(rows),
        'Follow event IDs and original source provenance across parts. Background observations prove availability, not an agent read. Exact intermediate filesystem states remain unknown. Hidden reasoning and credentials are excluded by the original audited public export.',
        '[Publication identity checks](../github-publication.json) · [Original archive manifest](../campaign002-behavioral-evidence-v1.manifest.json) · [Independent source audit](../verification.json)']))
    guards = json.loads((package / 'guards.json').read_bytes())['inputs']
    for entry in guards:
        raw = Path(entry['path']).read_bytes()
        if sha(raw) != entry['sha256'] or len(raw) != entry['bytes']:
            raise ValueError('Original input changed: ' + entry['path'])
    repo = Path(__file__).resolve().parents[2]
    evidence_paths = sorted(p for root in (corpus, browse) for p in root.rglob('*') if p.is_file())
    path_input = b'\0'.join(p.relative_to(repo).as_posix().encode() for p in evidence_paths) + b'\0'
    attrs = subprocess.run(['git', 'check-attr', '-z', '--stdin', 'text', 'filter'], cwd=repo,
                           input=path_input, capture_output=True, check=True).stdout.split(b'\0')
    for index in range(0, len(attrs) - 1, 3):
        _, attribute, value = attrs[index:index + 3]
        if (attribute == b'text' and value != b'unset') or (attribute == b'filter' and value != b'unspecified'):
            raise ValueError('Git would transform exact evidence bytes')
    receipt = {'schema': 'behavioral-evidence-github-publication-1', 'passed': True,
               'archive_sha256': manifest['sha256'], 'archive_manifest_sha256': sha(manifest_path.read_bytes()),
               'exact_unpacked_files_checked': len(expected), 'exact_unpacked_bytes': sum(e['bytes'] for e in expected.values()),
               'runs': run_ids, 'ordered_views': views,
               'lossless_views_checked': len(views), 'part_count': sum(len(v['parts']) for v in views),
               'part_target_bytes': 262144, 'largest_intact_jsonl_record_bytes': largest_record,
               'original_inputs_unchanged': len(guards), 'git_byte_preservation_paths_checked': len(evidence_paths),
               'no_new_experiment': True, 'no_behavioral_interpretation': True}
    text_new(package / 'github-publication.json', json.dumps(receipt, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in receipt.items() if k != 'ordered_views'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    main(args.package.resolve())
