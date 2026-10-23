"""Comparison-relevant installed runtime identity; no credential inspection."""
import platform
import sys
import mujoco
import numpy
from common import sha

def identity():
    from native_runtime import old,linux
    import json
    native=json.loads(linux("import hashlib,json,sys;from pathlib import Path;print(json.dumps([hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sys.argv[1:]]))",old.prior.LINUX_CODEX,old.prior.LINUX_CODEHOST))
    return dict(python_version=platform.python_version(),python_sha256=sha(sys.executable),mujoco=mujoco.__version__,numpy=numpy.__version__,
        windows_codex_sha256=sha(old.bootstrap.LAUNCH.CODEX),linux_executor_sha256=native[0],linux_codehost_sha256=native[1],
        model=old.bootstrap.LAUNCH.MODEL,effort=old.bootstrap.LAUNCH.EFFORT,platform=platform.platform(),wsl_distribution='Ubuntu-24.04')
