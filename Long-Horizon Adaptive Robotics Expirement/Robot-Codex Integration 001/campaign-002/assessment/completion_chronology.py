"""Conservative completion bounds for authenticated executor read evidence.

Callers authenticate the capture hash chain, complete process bytes and app/tool
identity first. This helper checks the local sequence and timestamps again. A
post-send delivery log is not an app acknowledgment or an emission predecessor.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite_time(value):
    require(type(value) in (int, float), 'Completion clock must be a numeric timestamp')
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError('Completion clock is outside finite range') from error
    require(math.isfinite(number), 'Completion clock must be finite')
    return number


def decimal_time(value):
    finite_time(value)
    return Decimal(str(value))


def upper_float(value):
    """Round an exact decimal upper bound outward, never subtracting coverage."""
    number = float(value)
    require(math.isfinite(number), 'Completion bound is outside finite range')
    if Decimal.from_float(number) < value:
        number = math.nextafter(number, math.inf)
    require(math.isfinite(number), 'Completion bound is outside finite range')
    return number


def terminal_process_order(process):
    """Authenticate order without moving bytes; only the exit may overtake close."""
    require(isinstance(process, list) and process, 'Missing process stream')
    closed = [row for row in process if row['message'].get('method') == 'process/closed']
    exits = [row for row in process if row['message'].get('method') == 'process/exited']
    require(len(closed) == 1, 'Missing unique terminal process close')
    require(len(exits) == 1, 'Missing unique process exit')
    require(all(row['message'].get('method') in ('process/output', 'process/exited', 'process/closed')
                for row in process), 'Unknown process notification')
    order = [row['message']['params'].get('seq') for row in process]
    outputs = [row for row in process if row['message']['method'] == 'process/output']
    outseq = [row['message']['params'].get('seq') for row in outputs]
    require(all(type(n) is int for n in order) and len(set(order)) == len(order)
            and set(order) == set(range(1, len(process) + 1))
            and closed[0]['message']['params']['seq'] == len(process),
            'Incomplete/nonterminal process sequence')
    require(all(a < b for a, b in zip(outseq, outseq[1:]))
            and all(row['sequence'] < closed[0]['sequence'] for row in outputs),
            'Reordered output or output after process close')
    return {'closed': closed[0], 'exit': exits[0], 'order': order, 'output_order': outseq,
            'exit_arrived_after_close': exits[0]['sequence'] > closed[0]['sequence']}


def completion_chronology(rows, delivered, request, process_id, emitted_ms):
    """Return original emission data and a separately named evidence upper bound.

    The accepted subset requires close capture below the native interval's upper
    endpoint. Native startup completion can precede closure on a deadline; this
    restriction is sufficient evidence here, not a universal native invariant.
    """
    require(type(emitted_ms) is int and 0 <= emitted_ms <= 2**63 - 1,
            'Native emittedAtMs must be an exact nonnegative signed-64-bit integer')
    require(isinstance(rows, list) and rows and isinstance(request, dict),
            'Missing completion capture/request')
    require(isinstance(delivered, set) and all(type(n) is int for n in delivered),
            'Invalid authenticated delivery set')
    for sequence, row in enumerate(rows, 1):
        require(isinstance(row, dict) and type(row.get('sequence')) is int
                and row['sequence'] == sequence, 'Executor capture sequence/order inconsistent')
        finite_time(row.get('wall_unix_s'))
    require(all(a['wall_unix_s'] <= b['wall_unix_s'] for a, b in zip(rows, rows[1:])),
            'Executor capture clock/order inconsistent')
    request_sequence = request.get('sequence')
    require(type(request_sequence) is int and 1 <= request_sequence <= len(rows)
            and rows[request_sequence - 1] == request, 'Request is not the authenticated capture row')
    message = request.get('message') or {}
    params = message.get('params') or {}
    require(request.get('kind') == 'request' and message.get('method') == 'process/start'
            and params.get('processId') == process_id and isinstance(process_id, str) and process_id,
            'Completion request/process identity mismatch')
    process = [row for row in rows if row.get('kind') == 'response'
               and (row.get('message') or {}).get('method') in
               ('process/output', 'process/exited', 'process/closed')
               and ((row.get('message') or {}).get('params') or {}).get('processId') == process_id]
    closed = [row for row in process if row['message']['method'] == 'process/closed']
    starts = [row for row in rows if row.get('kind') == 'response'
              and (row.get('message') or {}).get('id') == message.get('id')]
    require(len(starts) == 1 and ((starts[0].get('message') or {}).get('result') or {}).get('processId') == process_id
            and 'error' not in starts[0]['message'], 'Missing unique successful process start receipt')
    ordering = terminal_process_order(process)
    required = sorted(starts + process, key=lambda row: row['sequence'])
    require(all(row['sequence'] > request_sequence for row in required),
            'Process response precedes request capture')
    delivery_rows = []
    for response in required:
        sequence = response['sequence']
        matches = [row for row in rows if row.get('kind') == 'delivered'
                   and type(row.get('response_sequence')) is int and row['response_sequence'] == sequence]
        require(sequence in delivered and len(matches) == 1
                and matches[0]['sequence'] > sequence
                and response['wall_unix_s'] <= matches[0]['wall_unix_s'],
                'Missing/ambiguous or unordered required process delivery')
        delivery_rows.append(matches[0])
    start, close = request['wall_unix_s'], closed[0]['wall_unix_s']
    lower, upper = Decimal(emitted_ms) / 1000, Decimal(emitted_ms + 1) / 1000
    require(start < close, 'Process request must strictly precede close capture')
    require(decimal_time(close) < upper,
            'Process close is outside conservative native completion interval')
    evidence_upper = max(upper, *(decimal_time(row['wall_unix_s']) for row in delivery_rows))
    source = Path(__file__)
    raw = source.read_bytes()
    return {
        'request_wall_unix_s': start,
        'closed_wall_unix_s': close,
        'closed_capture_sequence': closed[0]['sequence'],
        'exit_arrived_after_close': ordering['exit_arrived_after_close'],
        'app_emitted_at_ms': emitted_ms,
        # Kept for compatibility and original evidence, never used as an upper bound.
        'app_complete_wall_unix_s': emitted_ms / 1000,
        'app_emission_interval': {
            'lower_numerator_ms': emitted_ms, 'upper_numerator_ms': emitted_ms + 1,
            'denominator': 1000, 'lower_decimal_seconds': str(lower),
            'upper_decimal_seconds': str(upper), 'lower_inclusive': True, 'upper_exclusive': True,
        },
        'required_delivery_capture_sequences': [row['sequence'] for row in delivery_rows],
        'required_delivery_wall_unix_s': [row['wall_unix_s'] for row in delivery_rows],
        'evidence_complete_upper_decimal_seconds': str(evidence_upper),
        'evidence_complete_upper_wall_unix_s': upper_float(evidence_upper),
        'completion_chronology_source': {'path': str(source), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)},
        'completion_chronology_scope': 'Conservative evidence bound; not actual app emission time or acknowledgment. '
                                      'No universal closed-before-completed claim; no epsilon.',
    }
