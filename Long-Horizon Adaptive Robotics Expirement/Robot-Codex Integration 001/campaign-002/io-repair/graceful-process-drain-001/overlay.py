"""One explicit process-local candidate installation, restored on scope exit."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent

@contextmanager
def installed(physical, evidence):
    sys.path.insert(0, str(HERE))
    import candidate_native
    import process_drain
    runtime = sys.modules[physical.Runtime.__module__]
    bootstrap = runtime.bootstrap
    bridge_scope = runtime.with_codehost.__globals__
    original_close, original_bridge = bootstrap.Client.close, bridge_scope['Bridge']
    if getattr(runtime, '_process_drain_installed', False): raise RuntimeError('Duplicate process-drain overlay')
    if original_close.__module__ != bootstrap.__name__ or original_bridge.__module__ != runtime.with_codehost.__module__:
        raise RuntimeError('Unexpected original runtime method identity')
    class CandidateBridge(original_bridge):
        def native_exit_barrier(self, request): return process_drain.bridge_join(self, request)
    def close(client): return candidate_native.close(client, bootstrap.MAX_BYTES)
    names = ('candidate_native.py', 'process_drain.py', 'overlay.py')
    receipt = {'schema': 'campaign002-process-drain-overlay-1', 'scope': 'this one orchestrator process',
        'bootstrap_module': bootstrap.__name__, 'bridge_module': runtime.with_codehost.__module__,
        'overrides': ['Client.close', 'Bridge.native_exit_barrier'],
        'sources': {n: {'bytes': (HERE/n).stat().st_size,
                       'sha256': hashlib.sha256((HERE/n).read_bytes()).hexdigest()} for n in names}}
    process_drain.save(Path(evidence)/'process-drain-overlay.json', receipt)
    runtime._process_drain_installed = True
    bootstrap.Client.close, bridge_scope['Bridge'] = close, CandidateBridge
    try: yield
    finally:
        bootstrap.Client.close, bridge_scope['Bridge'] = original_close, original_bridge
        runtime._process_drain_installed = False
