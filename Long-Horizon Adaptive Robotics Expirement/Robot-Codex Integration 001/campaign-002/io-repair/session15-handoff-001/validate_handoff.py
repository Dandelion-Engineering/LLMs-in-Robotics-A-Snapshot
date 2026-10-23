"""Read-only final identity checks, with one new exclusive validation record.

No empirical outputs are consumed. Queue metadata is refreshed first; only
source archives, existing diagnostic summaries and published records are read.
"""
import collections
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote
import zipfile

HERE = Path(__file__).resolve().parent
IO = HERE.parent
C = IO.parent
ROOT = C.parents[2]
MAP = ROOT / 'Long-Horizon Adaptive Robotics Expirement/Architecture Map'
OUTPUT = IO / 'session15-final-validation.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path), 'sha256': sha(raw), 'bytes': len(raw)}


def verify_item(item):
    p = Path(item['path'])
    actual = binding(p)
    assert actual['sha256'] == item['sha256'], str(p)
    if 'bytes' in item:
        assert actual['bytes'] == item['bytes'], str(p)
    return actual


def command(argv):
    p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if p.returncode:
        raise RuntimeError((argv, p.returncode, p.stdout[-3000:], p.stderr[-3000:]))
    return p.stdout


if __name__ == '__main__':
    if OUTPUT.exists():
        raise RuntimeError('Final validation already exists; do not overwrite')
    out = {'schema': 'campaign002-session15-final-validation-1',
           'started_at': datetime.now(timezone.utc).isoformat(),
           'scope': 'Source/preservation/record and handoff checks, not scientific assessment or campaign completion.',
           'active_empirical_outputs_read': False, 'empirical_outcomes_recomputed': False}
    py = [sys.executable, '-X', 'utf8', '-B']
    # Official metadata is the only queue surface read here.
    queue = json.loads(command(py + [str(ROOT.parent / 'tools/compute_queue/compute_queue.py'), 'list', '--project', 'LLMs-in-Robotics']))
    official = {v['id']: v for v in queue}
    account = read(C / 'registration/session15-accounting.json')
    final_jobs = []
    for row in account['rows']:
        old = row['official_queue']
        new = official[old['id']]
        assert all(new.get(k) == v for k, v in old.items()), old['id']
        assert type(new['exit_status']) is int
        assert (new['state'], new['exit_status']) in [('succeeded', 0), ('failed', 1)]
        final_jobs.append({k: new[k] for k in old})
    assert len(final_jobs) == 122
    out['fresh_official_jobs'] = {'authenticated_at': datetime.now(timezone.utc).isoformat(),
                                 'count': len(final_jobs), 'states': dict(collections.Counter(j['state'] for j in final_jobs)),
                                 'active_accounted_jobs': [], 'jobs': final_jobs}
    out['protected_preservation'] = json.loads(command(py + [str(C / 'preserve.py'), 'verify', str(C / 'preservation-baseline.json')]))
    assert out['protected_preservation'] == {'preserved': 1054, 'map_prefixes': 5}
    out['source_archives'] = []
    for revision, expected_count in [('RCI001-C02-dev-096', 958), ('RCI001-wsl-010d', 624)]:
        release = MAP / 'releases' / revision
        snapshot = read(release / 'snapshot.json')
        assert len(snapshot['sources']) == expected_count
        with zipfile.ZipFile(release / 'code.zip') as archive:
            assert set(archive.namelist()) == set(snapshot['sources'])
            for name, expected in snapshot['sources'].items():
                local = (ROOT / name).read_bytes()
                archived = archive.read(name)
                assert len(local) == expected['bytes'] and sha(local) == expected['sha256'], name
                assert local == archived, name
        out['source_archives'].append({'revision': revision, 'count': expected_count, 'current_and_archive_match': True,
                                       'snapshot': binding(release / 'snapshot.json'), 'archive': binding(release / 'code.zip')})
    production = read(IO / 'native-pre-exit-drain-001/production-state-004.json')
    assert production['passed'] is True and production['sources_unchanged'] is True
    for item in production['sources']:
        verify_item(item)
    out['unchanged_tested_production_sources'] = len(production['sources'])
    assert out['unchanged_tested_production_sources'] == 234
    report_tests = read(C / 'investigation/native004-append-staging/full-checks-001/receipt.json')
    assert report_tests['passed'] is True and report_tests['tests'] == 151
    assert report_tests['before'] == report_tests['after']
    for name, expected in report_tests['after'].items():
        assert sha((C / 'investigation' / name).read_bytes()) == expected
    out['report_tests_unchanged'] = 151
    audit = read(C / 'registration/session15-accounting-001/execution-001/receipt.json')
    for key in ('old_accounting_unchanged', 'accounting'):
        out[key] = verify_item(audit[key])
    old = read(Path(audit['old_accounting_unchanged']['path']))
    # Preserve every old binding as an exact object, not only a path/hash pair.
    serialized_old = [json.dumps(x, sort_keys=True) for x in old['source_bindings']]
    serialized_new = [json.dumps(x, sort_keys=True) for x in account['source_bindings']]
    assert not (collections.Counter(serialized_old) - collections.Counter(serialized_new))
    assert len(serialized_old) == 913 and len(serialized_new) == 960
    for item in audit['exports_preserved']:
        verify_item(item)
    assert len(audit['exports_preserved']) == 19
    out['accounting_bindings'] = {'preserved': len(serialized_old), 'current': len(serialized_new), 'exports_unchanged': 19}
    publication = read(C / 'investigation/v29-append-staging/smoke027-publication-receipt.json')
    assert publication['rows_after'] == 129 and publication['prior_raw_rows_preserved'] == 128
    out['history'] = verify_item(publication['history_after'])
    assert out['history']['sha256'] == 'cc2bc83f1c7b887c3e8f16d0cab65beb509f1f7e55e44310833725000375590e'
    out['history']['rows'] = 129
    existing_map = read(MAP / 'validation.json')
    assert existing_map['ok'] is True and not existing_map['errors']
    for name, expected in existing_map['canonical_sha256'].items():
        assert sha((MAP / name).read_bytes()) == expected
    assert sha((MAP / 'Catalog.md').read_bytes()) == existing_map['catalog_sha256']
    out['map'] = {'validation': binding(MAP / 'validation.json'), 'counts': existing_map['counts'],
                  'canonical_and_catalog_hashes_still_match': True}
    free = shutil.disk_usage(ROOT).free
    assert free >= 102 * 10**9
    out['storage'] = {'free_bytes': free, 'required_reserve_plus_headroom_bytes': 102 * 10**9}
    doc_paths = [ROOT / 'agents/Codex/Session Summaries/HumanReport15.md', C / 'README.md', IO / 'PROGRESS.md',
                 IO / 'smoke027-os-trace-readiness-001/PLAN.md']
    links = []
    pending_claim = ROOT / 'Work/Done/document-session15-admin-trace-boundary.md'
    for path in doc_paths:
        text = path.read_text(encoding='utf-8').split('**Retained Session14 and earlier checkpoints')[0]
        for label, target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text):
            if target.startswith(('https:', 'http:', '#')):
                continue
            resolved = (path.parent / unquote(target.split('#')[0])).resolve()
            state = 'exists'
            if resolved == OUTPUT:
                state = 'this_exclusive_validation_output'
            elif resolved == pending_claim and not resolved.exists():
                assert (ROOT / 'Work/Active' / pending_claim.name).is_file()
                state = 'active_claim_to_be_closed_before_git_closeout'
            else:
                assert resolved.exists(), (path, target)
            links.append({'from':str(path),'target':str(resolved),'state':state})
    out['documentation_links'] = links
    chat = read(HERE / 'chat-receipt.json')
    transcript = Path(chat['before']['path']).read_bytes()
    assert len(transcript) == chat['after']['bytes'] and sha(transcript) == chat['after']['sha256']
    assert sha(transcript[:chat['before']['bytes']]) == chat['before']['sha256']
    assert chat['exact_prior_byte_prefix_preserved'] is True and len(chat['new_headers_after_prior_physical_line_count']) == 1
    out['chat'] = {'receipt':binding(HERE / 'chat-receipt.json'), 'prefix_and_single_header_verified':True}
    out['concluded_transcripts'] = []
    for subject, expected in [('Audit Storage', '594ce8f3ea3852d6abd1a5ead49a965f6f998fd6e0f25e8371091658bee0005a'),
                              ('Long-Horizon Adaptive Robotics Experiment', '05d8a927832fd376f9411b6536e4de14288496e7b23f413122c2670ee6ba4504')]:
        concluded = ROOT / 'chats/Codex-Human' / subject / (subject + ' - Concluded.md')
        actual = binding(concluded)
        assert actual['sha256'] == expected
        out['concluded_transcripts'].append(actual)
    # The exact user-authorized chat renames were already verified separately;
    # include both directory scopes so Git closeout cannot stage half a move.
    status = command(['git','status','--porcelain=v1','-z','--untracked-files=all']).split('\0')
    changes = [line for line in status if line]
    paths = [str(C.relative_to(ROOT)).replace('\\','/'), 'agents/Codex/Session Summaries/HumanReport15.md',
             'agents/Codex/Summary of Only Necessary Context.md']
    map_base = MAP.relative_to(ROOT).as_posix()
    paths += [map_base + '/' + name for name in ('Catalog.md','results.jsonl','revisions.jsonl','runs.jsonl','validation.json')]
    paths += [map_base + '/releases/RCI001-C02-dev-' + n for n in ('092','093','094','095','096')]
    paths += ['chats/Codex-Human/' + subject for subject in ('Audit Storage','Long-Horizon Adaptive Robotics Experiment','Robot-Codex Campaign 002')]
    work_paths = sorted(line[3:] for line in changes if line[3:].startswith('Work/'))
    paths += work_paths
    if pending_claim.relative_to(ROOT).as_posix() not in paths:
        paths.append(pending_claim.relative_to(ROOT).as_posix())
    for line in changes:
        name = line[3:]
        assert any(name == scope or name.startswith(scope + '/') for scope in paths), line
    manifest = {'schema':'campaign002-session15-closeout-paths-1','paths':paths,
                'scope':'All inspected Session15 changes, including director-requested chat conclusions and existing director continuation append.',
                'change_count_at_validation':len(changes)}
    manifest_path = IO / 'session15-closeout-paths.json'
    with manifest_path.open('x',encoding='utf-8') as stream:
        json.dump(manifest,stream,indent=2);stream.write('\n')
    out['closeout_paths'] = binding(manifest_path)
    whitespace = command(['git','-c','core.whitespace=cr-at-eol','diff','--check','--'] + paths)
    assert not whitespace.strip()
    out['scoped_diff_check_passed'] = True
    out['finished_at'] = datetime.now(timezone.utc).isoformat()
    out['passed'] = True
    with OUTPUT.open('x',encoding='utf-8') as stream:
        json.dump(out,stream,indent=2);stream.write('\n')
    print(json.dumps({'passed':True,'sources':958,'original_sources':624,'protected':1054,'map_prefixes':5,
                      'accounted_jobs':122,'history_rows':129,'free_bytes':free,'scope_count':len(paths),
                      'output':binding(OUTPUT)}))
