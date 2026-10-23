"""Bounded operator artifact verification; no scientific execution or mutation."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from urllib.parse import unquote

OPS = Path(__file__).resolve().parent
sys.path.insert(0, str(OPS.parent / 'session-63'))
import common63 as c


def command(*args):
    p = subprocess.run(list(args), cwd=c.REPO, capture_output=True)
    assert p.returncode == 0, (args, p.stdout, p.stderr)
    return p.stdout


def ref(row):
    p = Path(row['uri'])
    assert p.is_file() and c.sha(p) == row['sha256'], str(p)
    if 'bytes' in row:
        assert p.stat().st_size == row['bytes'], str(p)


def main():
    parsed = []
    for p in OPS.iterdir():
        if p.suffix == '.json':
            c.read(p)
            parsed.append(p.name)
        elif p.suffix == '.py':
            ast.parse(p.read_text(encoding='utf-8'))
            parsed.append(p.name)
    endpoint = c.read(OPS / 'endpoint.json')
    assert (OPS / 'endpoint.json').read_bytes() == (c.BASE / 'endpoint-session74/verified-endpoint.json').read_bytes()
    for row in endpoint['evidence'].values():
        ref(row)
    for name in ('audit-manifest.json', 'audit-completion-manifest.json'):
        m = c.read(OPS / name)
        for row in m['readers'] + m.get('prior_evidence', []):
            ref(row)
    result = c.read(c.BASE / 'endpoint-session74/completion001/result.json')
    original = c.read(c.BASE / 'endpoint-session74/audit001/result.json')
    assert result['passed'] and len(result['checks']) == 9 and all(result['checks'].values())
    assert not original['passed'] and result['first_stage_failure']['error'] == original['error']
    inherited = set(original) - {'passed', 'checks', 'error', 'traceback', 'finished_utc', 'evidence'}
    assert all(result[k] == original[k] for k in inherited)
    for label, row in result['preservation_before'].items():
        after = result['preservation_after'][label]
        assert row['files'] == after['files'] and row['inventory']['sha256'] == after['inventory']['sha256']
        ref(row['inventory']); ref(after['inventory'])
    for name, expected in [('scientific-terminal.json', 'succeeded'), ('audit-terminal.json', 'succeeded'), ('audit001-terminal.json', 'failed')]:
        receipt = c.read(OPS / name)
        assert c.queue('status', receipt['id']) == receipt and receipt['state'] == expected
        assert type(receipt['exit_status']) is int and receipt['exit_status'] == (0 if expected == 'succeeded' else 1)

    # Original abandoned call: retain its failed report cardinality while checking
    # the remaining native qualification fields without requiring a valid closeout.
    from audit import chain
    from h2_readback import paired
    abandoned = c.PARENT / 'sessions/session-00006'
    native = abandoned / 'native'
    client = c.read(native / 'client/result.json')
    assert client['preflight_passed'] and client['auth_type'] == 'chatgpt'
    assert client['success'] and client['model_effective'] == 'gpt-6-astra' and client['effort_effective'] == 'max'
    stream = c.read(native / 'client/native-stream.json')
    assert stream['passed'] and stream['readers_retired'] and not stream['reader_errors']
    assert stream['retained_event_bytes'] == (native / 'client/events.jsonl').stat().st_size <= stream['retained_event_limit']
    assert stream['raw_consumed_bytes'] <= stream['raw_stream_limit'] + stream['cleanup_extra_bytes']
    assert stream['pending_terminal_peak'] <= 4 and stream['queue_peak_items'] <= stream['queue_item_limit']
    assert stream['queue_peak_bytes'] <= max(stream['queue_byte_limit'], stream['per_message_limit'])
    probes = {}
    for name in ('canary.json', 'codehost-canary.json'):
        probe = c.read(native / name)
        assert type(probe['exit_status']) is int and probe['exit_status'] == 0 and json.loads(probe['stdout'])['qualified']
        probes[name] = c.ref(native / name)
    bridge = c.read(native / 'codehost-owner-bridge-v3.json')
    assert bridge['qualified'] and c.read(native / 'cleanup.json')['clean']
    for channel in bridge['channels']:
        paired(channel['h2'], channel['namespace_closed']['h2'])
    clocks = chain(abandoned / 'workspace/clock-bridge.jsonl')
    assert len(clocks) > 1 and all(x['payload']['before']['sim_time'] <= x['payload']['after']['sim_time'] for x in clocks)

    before = c.read(OPS / 'monitoring-before.json')
    after = c.read(OPS / 'monitoring-paused.json')
    for old, now in zip(before['monitors'], after['monitors']):
        assert old['id'] == now['id']
        ref(now['record'])
        data = tomllib.loads(Path(now['record']['uri']).read_text(encoding='utf-8'))
        assert data['status'] == 'PAUSED'
        if old['id'] != 'apartment-v4-maps-recovery-observations':
            assert old['record']['sha256'] == now['record']['sha256']
        else:
            assert {k: v for k, v in old['data'].items() if k not in ('status', 'updated_at')} == {k: v for k, v in data.items() if k not in ('status', 'updated_at')}

    maproot = c.REPO / 'Long-Horizon Adaptive Robotics Expirement/Architecture Map'
    validation = c.read(maproot / 'validation.json')
    assert validation['ok'] and not validation['errors']
    for name, digest in validation['canonical_sha256'].items():
        assert c.sha(maproot / name) == digest
    assert c.sha(maproot / 'Catalog.md') == validation['catalog_sha256']
    for name in ('architectures.jsonl', 'revisions.jsonl', 'runs.jsonl', 'results.jsonl', 'notes.jsonl'):
        p = maproot / name
        prior = command('git', 'show', 'HEAD:' + p.relative_to(c.REPO).as_posix())
        current = p.read_bytes()
        if name in ('results.jsonl', 'notes.jsonl'):
            assert current.startswith(prior)
            added = current[len(prior):].splitlines()
            assert len(added) == 1
            expected = c.read(OPS / ('map-result.json' if name == 'results.jsonl' else 'map-note.json'))
            assert json.loads(added[0]) == expected
        else:
            assert current == prior

    chat_before = c.read(OPS / 'chat-before.json')
    chat_after = c.read(OPS / 'chat-after.json')
    transcript = Path(chat_before['path'])
    data = transcript.read_bytes()
    assert hashlib.sha256(data[:chat_before['bytes']]).hexdigest() == chat_before['sha256']
    ref(chat_after['record'])
    documents = [c.REPO / 'agents/Codex/Session Summaries/HumanReport74.md', c.REPO / 'agents/Codex/Summary of Only Necessary Context.md']
    for p, base in [(p, p.parent) for p in documents] + [(OPS / 'human-reply.md', transcript.parent)]:
        for target in re.findall(r'\]\(([^)]+)\)', p.read_text(encoding='utf-8')):
            if not target.startswith(('http:', 'https:')):
                assert (base / unquote(target)).resolve().is_file(), (p, target)
    command('git', 'diff', '--check')
    # Hash-bound operator evidence must survive Git's configured clean/smudge rules.
    roundtrip = []
    for p in sorted(OPS.iterdir()):
        if not p.is_file():
            continue
        relative = p.relative_to(c.REPO).as_posix()
        oid = command('git', 'hash-object', '-w', '--path=' + relative, str(p)).decode().strip()
        restored = command('git', 'cat-file', '--filters', '--path=' + relative, oid)
        assert restored == p.read_bytes(), relative
        roundtrip.append(dict(path=relative, git_object=oid, sha256=c.sha(p)))
    c.save(OPS / 'closeout-verification.json', dict(recorded_utc=c.now(), passed=True, parsed_files=parsed,
        endpoint=c.ref(OPS / 'endpoint.json'), inherited_five_gates_unchanged=True,
        all_nine_gates_passed=True, four_inventory_hashes_unchanged=True,
        failed_original_native_qualification=dict(passed=True, client=c.ref(native / 'client/result.json'),
            stream=c.ref(native / 'client/native-stream.json'), probes=probes, bridge=c.ref(native / 'codehost-owner-bridge-v3.json'),
            clock_bridge=c.ref(abandoned / 'workspace/clock-bridge.jsonl'), clock_brackets=len(clocks), failed_report_closeout_preserved=True),
        monitor_pause_verified=True, map_append_only=True, validation=c.ref(maproot / 'validation.json'),
        chat_old_prefix_unchanged=True, document_links_resolve=True, git_diff_check=True, git_roundtrip=roundtrip))
    print(json.dumps(dict(passed=True, parsed_files=len(parsed), roundtrip_files=len(roundtrip), audit_gates=9,
        abandoned_clock_brackets=len(clocks), counts=validation['counts'])))


if __name__ == '__main__':
    main()
