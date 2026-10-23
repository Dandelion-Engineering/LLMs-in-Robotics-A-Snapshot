"""Validate report references and time boundaries, without running physics."""
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent


def read_ref(ref):
    path = HERE / unquote(ref['href'])
    raw = path.read_bytes()
    assert len(raw) == ref['bytes'], path
    assert hashlib.sha256(raw).hexdigest() == ref['sha256'], path
    return json.loads(raw)


def main():
    index = json.loads((HERE / 'data/index.json').read_text())
    read_ref(index['source_package'])
    builder = (HERE / index['builder']['href']).read_bytes()
    assert hashlib.sha256(builder).hexdigest() == index['builder']['sha256']
    report = {'episodes': [], 'verified_payloads': 0, 'referenced_frames': 0}
    seen = set()
    for ref in index['episodes']:
        e = read_ref(ref)
        assert e['start_sim_time'] < e['end_sim_time']
        assert abs(e['duration_sim_time_s'] - (e['end_sim_time'] - e['start_sim_time'])) < 1e-9
        for rows, key in [(e['motion'], 'sim_time_s'), (e['events'], 'sim_time_s'),
                          (e['filesystem'], 'sim_time_s'), (e['model_calls'], 'request_sim_time_s')]:
            assert all(a[key] <= b[key] for a, b in zip(rows, rows[1:]))
        refs = [r['payload_ref'] for r in e['filesystem']]
        for call in e['model_calls']:
            assert call['request_event_id'] <= e['physical_end_event_id']
            assert call['request_sim_time_s'] <= call['response_sim_time_s']
            request, response = read_ref(call['input_ref']), read_ref(call['output_ref'])
            assert request['messages'] and isinstance(request['schema'], dict)
            assert isinstance(response['result']['raw_text'], str)
            refs.extend([call['input_ref'], call['output_ref']])
        for row in e['filesystem']:
            value = read_ref(row['payload_ref'])
            raw = value['content_utf8'].encode('utf-8')
            assert hashlib.sha256(raw).hexdigest() == row['sha256']
            assert len(raw) == row['byte_count']
        for event in e['events']:
            if event.get('payload_ref'):
                refs.append(event['payload_ref'])
            for artifact in event.get('artifact_refs', {}).values():
                assert (HERE / unquote(artifact['href'])).is_file()
                report['referenced_frames'] += 1
        for ref2 in refs:
            if ref2['sha256'] not in seen:
                read_ref(ref2)
                seen.add(ref2['sha256'])
        report['episodes'].append({'architecture': e['architecture'], 'outcome': e['result']['outcome'],
                                  'accepted': e['result']['independent_outcome']['accepted_count'],
                                  'calls': len(e['model_calls']), 'checkpoints': len(e['filesystem']),
                                  'sim_start': e['start_sim_time'], 'sim_end': e['end_sim_time']})
    report['verified_payloads'] = len(seen)
    facts = json.loads((HERE / 'architectures.json').read_text())
    for source in facts['shared']['sources']:
        assert (HERE.parent.parent / source['file']).is_file(), source
    for name in ['index.html', 'style.css', 'app.js', 'scene.js', 'temporal.js', 'architectures.json']:
        assert (HERE / name).is_file()
    report['state'] = 'passed'
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
