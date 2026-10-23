"""Secret-safe diagnostic metadata; never retains dynamic stderr content."""
import hashlib
import time

MARKERS = {
    'code_mode_host': (b'code_mode_host', b'code-mode-host'),
    'exec_server': (b'exec_server', b'exec-server', b'exec server'),
    'grpc': (b'grpc',),
    'transport': (b'transport',),
    'connection_closed': (b'connection closed', b'connectionclosed', b'channel closed'),
    'connection_reset': (b'connection reset', b'connectionreset'),
    'disconnected': (b'disconnected',),
    'unavailable': (b'unavailable',),
    'timeout': (b'timeout', b'timed out'),
    'refused': (b'connection refused',),
    'broken_pipe': (b'broken pipe', b'brokenpipe'),
    'error_level': (b' error ', b'error:'),
    'warning_level': (b' warn ', b'warning:'),
}


def metadata(data):
    if not isinstance(data, bytes):
        raise TypeError('stderr metadata requires original bytes')
    lower = data.lower()
    return {'kind': 'stderr', 'schema': 'campaign002-stderr-metadata-1',
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'wall_unix_s': time.time(), 'monotonic_s': time.monotonic(),
            'markers': [name for name, patterns in MARKERS.items()
                        if any(pattern in lower for pattern in patterns)],
            'text_retained': False,
            'scope': 'Fixed lexical markers only; no error message or causal diagnosis.'}


def announce_finishing(client):
    """Persist owner intent before allowing the bridge to accept normal EOF.

    A logging error leaves finishing unset and latches abort, while returning so
    the caller still retires the process. The caller must report the failure.
    """
    finishing = getattr(client.args, 'client_finishing', None)
    if finishing is None:
        return True
    try:
        client.log({'kind': 'client_finishing_before_close',
                    'schema': 'campaign002-client-finishing-1',
                    'wall_unix_s': time.time(), 'monotonic_s': time.monotonic()})
    except Exception:
        abort = getattr(client.args, 'abort_event', None)
        if abort is not None:
            abort.set()
        return False
    finishing.set()
    return True
