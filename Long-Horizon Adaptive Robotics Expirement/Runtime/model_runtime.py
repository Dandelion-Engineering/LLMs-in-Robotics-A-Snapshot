"""Context-managed local inference. Start only inside a compute_queue job.

The supervisor must mediate candidate requests. This is an inference adapter,
not a sandbox, actuator interface, or source of evaluator observations.
"""
from __future__ import annotations

import atexit
import ctypes
import hashlib
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

from model_setup import MODEL_FILE, MODEL_REPO, MODEL_REVISION, MODEL_SHA256, LLAMA_RELEASE, LLAMA_COMMIT, VENDOR, sha256


def gpu_buffer_report(log_text,budget_bytes):
    buffers={}
    for device,role,value in re.findall(r'(CUDA\d+)\s+(model|KV|compute) buffer size\s*=\s*([0-9.]+) MiB',log_text):
        key=device+':'+role
        buffers[key]=max(buffers.get(key,0),int(float(value)*1024**2))
    roles={key.split(':')[1] for key in buffers}
    if roles!={'model','KV','compute'}:raise RuntimeError('Required GPU allocation evidence missing from owned server log')
    total=sum(buffers.values())
    if total>budget_bytes:raise RuntimeError('Reported model/KV/compute GPU buffers exceed the declared allocation target')
    return {'reported_buffers_bytes':buffers,'reported_total_bytes':total,'target_bytes':budget_bytes,
            'scope':'llama.cpp reported CUDA model, KV and compute buffers; excludes driver, graph and other applications',
            'allocation_level_hard_cap':False,'fits_reported_buffer_target':True}


def _windows_kill_on_close_job(process: subprocess.Popen, memory_bytes: int, cpu_cores: int):
    """Bind only the owned server to a kernel lifetime tied to this process."""
    if os.name != "nt":
        return None
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class IOCounts(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                       "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IOCounts),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetProcessAffinityMask.argtypes=[wintypes.HANDLE,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
    kernel.GetProcessAffinityMask.restype=wintypes.BOOL
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ExtendedLimits()
    # Private committed memory, one process, and a real core-affinity bound.
    # Working-set file mappings and CUDA allocations are separately measured.
    limits.BasicLimitInformation.LimitFlags = 0x00002000|0x00000100|0x00000010|0x00000008
    limits.ProcessMemoryLimit=memory_bytes
    limits.BasicLimitInformation.ActiveProcessLimit=1
    process_mask=ctypes.c_size_t();system_mask=ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(wintypes.HANDLE(int(process._handle)),ctypes.byref(process_mask),ctypes.byref(system_mask)):
        kernel.CloseHandle(handle);raise ctypes.WinError(ctypes.get_last_error())
    available=[1<<i for i in range(ctypes.sizeof(ctypes.c_size_t)*8) if process_mask.value & (1<<i)]
    if len(available)<cpu_cores:
        kernel.CloseHandle(handle);raise RuntimeError('Insufficient allowed CPU cores for model budget')
    limits.BasicLimitInformation.Affinity=sum(available[:cpu_cores])
    try:
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    return kernel, handle


@dataclass(frozen=True)
class ModelConfig:
    context_tokens: int = 16384
    max_output_tokens: int = 1024
    threads: int = 3
    process_memory_bytes: int = 12 * 1024 * 1024 * 1024
    cpu_cores: int = 3
    gpu_reported_buffer_budget_bytes: int = 12 * 1024 * 1024 * 1024
    gpu_layers: int = 99
    temperature: float = 0.0
    top_p: float = 1.0
    top_k: int = 0
    min_p: float = 0.0
    seed: int = 1729
    request_timeout_s: float = 30.0
    startup_timeout_s: float = 180.0


class LocalModel:
    def __init__(self, config: ModelConfig | None = None, *, log_path: str | Path | None = None, port: int = 0):
        self.config = config or ModelConfig()
        self.log_path = Path(log_path) if log_path else VENDOR / f"llama-server-{os.getpid()}.log"
        self.port = port
        self.process: subprocess.Popen | None = None
        self._log = None
        self._lock = threading.Lock()
        self.startup_latency_s = None
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._manifest = None
        self._windows_job = None
        self.gpu_allocation_report = None

    @property
    def identity(self) -> dict:
        manifest = self._manifest or json.loads((VENDOR / "asset_manifest.json").read_text(encoding="utf-8"))
        server = next(p for p in manifest["installed_files"] if p["path"] == manifest["server_relative_path"])
        return {"model_repo": MODEL_REPO, "model_revision": MODEL_REVISION,
                "model_file": MODEL_FILE, "model_sha256": MODEL_SHA256,
                "llama_release": LLAMA_RELEASE, "llama_commit": LLAMA_COMMIT,
                "server_sha256": server["sha256"], "config": asdict(self.config),
                "thinking_enabled": False, "prompt_cache_enabled": False,
                "context_overflow": "reject before generation; no context shift",
                "resource_enforcement": {"private_committed_memory_bytes":self.config.process_memory_bytes,
                    "cpu_affinity_cores":self.config.cpu_cores,"processes":1,
                    "scope":"owned model server after Windows job assignment; GPU allocation and mapped-file RSS measured separately"},
                "server_lifetime": "Windows kill-on-close job" if os.name == "nt" else "context-managed subprocess"}

    def _request(self, path: str, payload: dict | None = None, timeout: float = 5) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=body, headers={"Content-Type": "application/json"})
        with self._opener.open(request, timeout=timeout) as response:
            return json.loads(response.read())

    def start(self) -> "LocalModel":
        if self.process is not None:
            raise RuntimeError("This LocalModel has already started")
        self._manifest = json.loads((VENDOR / "asset_manifest.json").read_text(encoding="utf-8"))
        model_path = VENDOR / MODEL_FILE
        if sha256(model_path) != MODEL_SHA256:
            raise RuntimeError("Model hash does not match frozen weights")
        for entry in self._manifest["installed_files"]:
            if sha256(VENDOR / entry["path"]) != entry["sha256"]:
                raise RuntimeError(f"Runtime binary changed: {entry['path']}")
        if not self.port:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                self.port = listener.getsockname()[1]
        server_path = VENDOR / self._manifest["server_relative_path"]
        args = [str(server_path), "-m", str(model_path), "--host", "127.0.0.1", "--port", str(self.port),
                "--ctx-size", str(self.config.context_tokens), "--threads", str(self.config.threads),
                "--threads-batch", str(self.config.threads), "--threads-http", "2", "--parallel", "1",
                "--n-gpu-layers", str(self.config.gpu_layers), "--flash-attn", "on",
                "--no-webui", "--no-slots", "--no-cache-prompt", "--no-context-shift", "--cache-ram", "0",
                "--reasoning", "off", "--chat-template-kwargs", '{"enable_thinking":false}',
                "--timeout", str(int(self.config.request_timeout_s)), "--seed", str(self.config.seed)]
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("wb")
        started = time.perf_counter()
        # Do not inherit LLAMA_ARG overrides from an interactive host environment.
        env = {k: v for k, v in os.environ.items() if not k.startswith("LLAMA_")}
        try:
            self.process = subprocess.Popen(args, cwd=server_path.parent, stdin=subprocess.DEVNULL,
                                            stdout=self._log, stderr=subprocess.STDOUT, env=env,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self._windows_job = _windows_kill_on_close_job(self.process,self.config.process_memory_bytes,self.config.cpu_cores)
            atexit.register(self.stop)
            while time.perf_counter() - started < self.config.startup_timeout_s:
                if self.process.poll() is not None:
                    raise RuntimeError(f"Local server exited {self.process.returncode}; see {self.log_path}")
                try:
                    if self._request("/health").get("status") == "ok":
                        self.gpu_allocation_report=gpu_buffer_report(self.log_path.read_text(encoding='utf-8',errors='replace'),self.config.gpu_reported_buffer_budget_bytes)
                        self.startup_latency_s = time.perf_counter() - started
                        return self
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(0.2)
            raise TimeoutError("Local model startup timed out")
        except BaseException:
            self.stop()
            raise

    def generate_json(self, prompt: str, schema: dict, *, system: str = "Return a JSON object satisfying the supplied schema.",
                      seed: int | None = None, max_tokens: int | None = None, timeout_s: float | None = None) -> dict:
        """Return parsed JSON plus raw text, tokens, latency, sampling identity.

        Prompts are self-contained and are never appended to a hidden dialogue.
        The caller validates the resulting action against current public state.
        Errors propagate; there is no silent scripted policy fallback.
        """
        return self.complete([{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                             schema, seed=seed, max_tokens=max_tokens, timeout_s=timeout_s)

    def complete(self, messages: list[dict], schema: dict, *, max_tokens: int | None = None,
                 seed: int | None = None, timeout_s: float | None = None) -> dict:
        """Complete the exact supplied text dialogue under a JSON grammar.

        The return has text/output, tokens/usage, latency_s/latency, identity,
        finish_reason and llama.cpp timing evidence. Only text messages are
        accepted: remote image URLs and built-in tools are not enabled.
        """
        if not messages or any(m.get("role") not in {"system", "user", "assistant"}
                               or not isinstance(m.get("content"), str) for m in messages):
            raise ValueError("messages must contain supported roles and text content")
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("Local model is not running")
        used_seed = self.config.seed if seed is None else seed
        output_limit = self.config.max_output_tokens if max_tokens is None else max_tokens
        if not 1 <= output_limit <= self.config.max_output_tokens:
            raise ValueError("max_tokens must be within the frozen output cap")
        payload = {"model": MODEL_FILE, "messages": messages,
                   "response_format": {"type": "json_object", "schema": schema},
                   "chat_template_kwargs": {"enable_thinking": False}, "cache_prompt": False,
                   "temperature": self.config.temperature, "top_p": self.config.top_p, "top_k": self.config.top_k,
                   "min_p": self.config.min_p, "seed": used_seed, "max_tokens": output_limit, "stream": False}
        budget = self.config.request_timeout_s if timeout_s is None else timeout_s
        if not 0 < budget <= self.config.request_timeout_s:
            raise ValueError("timeout_s must be positive and within the frozen timeout")
        started = time.perf_counter()
        if not self._lock.acquire(timeout=budget):
            raise TimeoutError("Local inference timed out waiting for the request slot")
        try:
            try:
                def bounded_request(path,body):
                    remaining = budget - (time.perf_counter() - started)
                    if remaining <= 0:
                        raise TimeoutError("Local inference request budget exhausted")
                    return self._request(path,body,remaining)
                # b9000 applies the identical oaicompat_chat_params_parse path
                # to /apply-template and /v1/chat/completions. Supplying the
                # complete same body preserves template/grammar parameters.
                template=bounded_request("/apply-template",payload)["prompt"]
                if not isinstance(template,str):
                    raise RuntimeError("Text-only prompt template was not a string")
                tokenized=bounded_request("/tokenize",{"content":template,"add_special":True,"parse_special":True})
                prompt_count=len(tokenized["tokens"])
                if prompt_count+output_limit>self.config.context_tokens:
                    raise ValueError(f"Context budget exceeded: {prompt_count} prompt + {output_limit} reserved output > {self.config.context_tokens}; no text was truncated or generated")
                response = bounded_request("/v1/chat/completions",payload)
            except (TimeoutError, socket.timeout) as error:
                # Terminating the owned server guarantees the timed-out generation
                # cannot keep consuming GPU or return into a later incarnation.
                self.stop()
                raise TimeoutError("Local inference timed out; owned server stopped") from error
        finally:
            self._lock.release()
        elapsed = time.perf_counter() - started
        choice = response["choices"][0]
        raw = choice["message"]["content"]
        if choice.get("finish_reason") != "stop":
            raise RuntimeError(f"Incomplete generation: {choice.get('finish_reason')}; raw={raw!r}")
        parsed = json.loads(raw)
        usage = response.get("usage", {})
        if usage.get("prompt_tokens")!=prompt_count:
            raise RuntimeError(f"Prompt token accounting mismatch: preflight={prompt_count}, inference={usage.get('prompt_tokens')}; response withheld")
        return {"output": parsed, "raw_text": raw, "text": raw, "usage": usage,
                "tokens": usage.get("total_tokens"), "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"), "identity": self.identity,
                "timings": response.get("timings", {}), "latency_s": elapsed, "latency": elapsed,
                "prompt_preflight_tokens":prompt_count,"reserved_output_tokens":output_limit,
                "prompt_preflight_sha256":hashlib.sha256(template.encode("utf-8")).hexdigest(),
                "context_budget_tokens":self.config.context_tokens,"context_truncated":False,
                "gpu_allocation_at_startup":self.gpu_allocation_report,
                "seed": used_seed, "finish_reason": choice.get("finish_reason")}

    def stop(self) -> None:
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        if self._log is not None:
            self._log.close()
            self._log = None
        if self._windows_job is not None:
            kernel, handle = self._windows_job
            kernel.CloseHandle(handle)
            self._windows_job = None
        atexit.unregister(self.stop)

    def __enter__(self) -> "LocalModel":
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()


def smoke() -> dict:
    schema = {"type": "object", "properties": {"action": {"type": "string", "enum": ["hold", "inspect", "pick"]},
               "target": {"type": "string"}}, "required": ["action", "target"], "additionalProperties": False}
    prompt = "A robot is holding above the tray. A part marked part-7 is visible, but its identity has not been verified. Inspect part-7 before trying to pick it. Select the next action."
    with LocalModel() as model:
        result = {"identity": model.identity, "startup_latency_s": model.startup_latency_s,
                  "prompt": prompt, "schema": schema, "response": model.generate_json(prompt, schema)}
        assert result["response"]["output"] == {"action": "inspect", "target": "part-7"}, result
    result["server_stopped"] = model.process is None
    result["completed_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    evidence_path=VENDOR / f"smoke_result-{time.time_ns()}.json"
    result["evidence_file"]=evidence_path.name
    evidence_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(smoke(), indent=2))
