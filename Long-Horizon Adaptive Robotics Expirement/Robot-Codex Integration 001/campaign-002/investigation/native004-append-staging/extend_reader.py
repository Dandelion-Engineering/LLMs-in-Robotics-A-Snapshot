"""One-time additive metadata-only support; never opens empirical run outputs."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
I = HERE.parent
SCHEMA = 'campaign002-completed-unassessed-interrupt-queue-1'
PINS = {
    'io-repair/single-interrupt-diagnostic-v4/run.py': {'sha256': '3ec098c7aaee147adf3c6228e3330eb9322fdbf20f3738dca3af668db417c3ec', 'bytes': 4959},
    'io-repair/single-interrupt-diagnostic-v4/common.py': {'sha256': 'cf19bff9747bc2f3a1a5580522f64a53d295a5ed6810d89721f01dbfacdf11b1', 'bytes': 12503},
    'io-repair/single-interrupt-diagnostic-v4/launch.py': {'sha256': '63af0d5c9e1383c7e51d52c30dab38043c707b9df42ba5dc01a247ce742cf79d', 'bytes': 4074},
    'io-repair/native-shutdown-order-001/DECLARATION.md': {'sha256': '972723405658a32d8e76cdbdeca6fa6f4b49d64bd7ba9738615c94d57f4d9478', 'bytes': 3097},
}


def replace(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def common(text):
    text = replace(text, '\ndef failed_single_interrupt_dispatch(',
        '\n# Only Native004 may use this completed, explicitly unassessed branch.\n'
        + 'COMPLETED_INTERRUPT_SCHEMA = ' + repr(SCHEMA) + '\n'
        + 'ORDERED_INTERRUPT_SOURCES = ' + repr(PINS) + '\n\n\ndef failed_single_interrupt_dispatch(')
    return replace(text, '        required_sources = SOCKET_INTERRUPT_SOURCES\n',
        '        required_sources = SOCKET_INTERRUPT_SOURCES\n'
        "    elif row.get('run_id') == 'RCI001-C02-shutdown-diagnostic-004':\n"
        "        if row.get('queue_completion_contract', row.get('queue_completion', {})).get('schema') != COMPLETED_INTERRUPT_SCHEMA:\n"
        "            raise ValueError('Native004 requires the separate completed unassessed contract')\n"
        "        run, revision = 'RCI001-C02-shutdown-diagnostic-004', 'RCI001-C02-dev-092'\n"
        "        root = CAMPAIGN / 'io-repair/shutdown-diagnostic-004'\n"
        "        script = CAMPAIGN / 'io-repair/single-interrupt-diagnostic-v4/run.py'\n"
        "        protocol = 'RCI001-Campaign002-single-interrupt-diagnostic-v4'\n"
        '        required_sources = ORDERED_INTERRUPT_SOURCES\n')


def report(text):
    original = text[text.index('def failed_queue_row('):text.index('\ndef failed_diagnostic_dispatch(')]
    completed = original.replace('failed_queue_row', 'completed_diagnostic_row')
    completed = completed.replace('queue_failure_contract', 'queue_completion_contract')
    completed = completed.replace("not in ('campaign002-failed-queue-diagnostic-1', 'campaign002-failed-diagnostic-queue-1', SINGLE_INTERRUPT_SCHEMA)", '!= COMPLETED_INTERRUPT_SCHEMA')
    completed = completed.replace("row.get('status') != 'failed'", "row.get('status') != 'completed'")
    completed = completed.replace("'preflight_contract'))", "'preflight_contract', 'queue_failure_contract', 'diagnostic_contract'))")
    completed = completed.replace("job.get('state') != 'failed'", "job.get('state') != 'succeeded'")
    completed = completed.replace("job['exit_status'] == 0", "job['exit_status'] != 0")
    completed = completed.replace("single = contract['schema'] == SINGLE_INTERRUPT_SCHEMA", 'single = True')
    completed = completed.replace("    contract = row.get('queue_completion_contract', {})", "    if row.get('run_id') != 'RCI001-C02-shutdown-diagnostic-004':\n        raise ValueError('Only the declared Native004 completion is supported')\n    contract = row.get('queue_completion_contract', {})")
    completed = completed.replace("'status': 'failed'", "'status': 'completed'")
    completed = completed.replace("'queue_failure': failure", "'queue_completion': failure")
    completed = completed.replace('official_terminal_execution_failure', 'official_terminal_unassessed_completion')
    completed = completed.replace('Failed queue', 'Completed diagnostic').replace('failed queue', 'completed diagnostic')
    completed = completed.replace('terminal failed official', 'terminal successful official')
    completed = completed.replace('Terminal official queue failed with integer nonzero exit required', 'Terminal official queue succeeded with integer zero exit required')
    completed = completed.replace('Terminal execution failure metadata only', 'Terminal execution completion metadata only')
    completed = completed.replace('No assessment, timing, canary, model-call count', 'No qualification assessment, timing, canary, model-call count')
    completed = completed.replace('The official queue records terminal execution failure.', 'The official queue records execution completion only.')
    completed = completed.replace('failed-attempt outputs', 'unassessed diagnostic outputs')
    text = replace(text, '\ndef failed_diagnostic_dispatch(', '\n' + completed + '\ndef failed_diagnostic_dispatch(')
    text = replace(text, 'def qualification_row(row, output):\n',
        'def qualification_row(row, output):\n'
        "    if 'queue_completion_contract' in row:\n"
        "        return completed_diagnostic_row(row, row.get('artifacts', []), output)\n")
    return common(text)


def qa(text):
    original = text[text.index('def failed_queue_guard('):text.index('\ndef failed_diagnostic_dispatch(')]
    completed = original.replace('failed_queue_guard', 'completed_diagnostic_guard')
    completed = completed.replace("row.get('queue_failure')", "row.get('queue_completion')")
    completed = completed.replace("not in ('campaign002-failed-queue-diagnostic-1', 'campaign002-failed-diagnostic-queue-1', SINGLE_INTERRUPT_SCHEMA)", '!= COMPLETED_INTERRUPT_SCHEMA')
    completed = completed.replace('official_terminal_execution_failure', 'official_terminal_unassessed_completion')
    completed = completed.replace("row.get('status') != 'failed'", "row.get('status') != 'completed'")
    completed = completed.replace("row.get('queue_state') != 'failed'", "row.get('queue_state') != 'succeeded'")
    completed = completed.replace("row['queue_exit_status'] == 0", "row['queue_exit_status'] != 0")
    completed = completed.replace("job.get('state') != 'failed'", "job.get('state') != 'succeeded'")
    completed = completed.replace("    failure = row.get('queue_completion') or {}", "    if row.get('run_id') != 'RCI001-C02-shutdown-diagnostic-004' or row.get('queue_failure') is not None:\n        raise ValueError('Only the separate Native004 completion is supported')\n    failure = row.get('queue_completion') or {}")
    start = completed.index("    if failure['schema'] == SINGLE_INTERRUPT_SCHEMA:")
    completed = completed[:start] + "    failed_single_interrupt_dispatch(row, job, paths, manifest, snapshot, failure['manifest_sha256'])\n    return diagnostic_links_guard(failure.get('diagnostic_links', []), output, links, context='Completed diagnostic')\n\n"
    completed = completed.replace('Failed queue', 'Completed diagnostic').replace('failed-job', 'completed unassessed job')
    text = replace(text, '\ndef failed_diagnostic_dispatch(', '\n' + completed + '\ndef failed_diagnostic_dispatch(')
    text = replace(text, "if row['status'] not in ('passed', 'failed', 'cancelled', 'not_run') or row['scorable']", "if row['status'] not in ('passed', 'failed', 'cancelled', 'not_run', 'completed') or row['scorable']")
    text = replace(text, "        if row.get('queue_failure') is not None:\n            urls.extend(failed_queue_guard(row, output))",
        "        if row.get('queue_completion') is not None or row['status'] == 'completed':\n            urls.extend(completed_diagnostic_guard(row, output))\n"
        "        elif row.get('queue_failure') is not None:\n            urls.extend(failed_queue_guard(row, output))")
    return common(text)


def main():
    before = HERE / 'reader-before'
    before.mkdir()
    changes = {}
    for name, transform in [('qualification_report.py', report), ('qualification_qa.py', qa)]:
        path = I / name
        raw = path.read_bytes()
        (before / name).write_bytes(raw)
        result = transform(raw.decode('utf-8').replace('\r\n', '\n')).encode('utf-8')
        path.write_bytes(result)
        changes[name] = {'before': hashlib.sha256(raw).hexdigest(), 'after': hashlib.sha256(result).hexdigest()}
    (HERE / 'reader-change.json').write_text(json.dumps(changes, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
