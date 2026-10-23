"""Pinned public model/bootstrap assets; run downloads through compute_queue.

No package installation, credentials, account, or remote inference is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor" / "model"
MODEL_REPO = "Qwen/Qwen3-14B-GGUF"
MODEL_REVISION = "530227a7d994db8eca5ab5ced2fb692b614357fd"
MODEL_FILE = "Qwen3-14B-Q4_K_M.gguf"
MODEL_SHA256 = "500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0"
LLAMA_RELEASE = "b9000"
LLAMA_COMMIT = "1a03cf47f67be591699d1f0f7ca28e1ed6eb8c7e"
ASSETS = [
    {"name": MODEL_FILE, "url": f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{MODEL_FILE}", "sha256": MODEL_SHA256, "size_bytes": 9001752960},
    {"name": "llama-b9000-bin-win-cuda-13.1-x64.zip", "url": "https://github.com/ggml-org/llama.cpp/releases/download/b9000/llama-b9000-bin-win-cuda-13.1-x64.zip", "sha256": "ef8dc3b39295a586b7da641765b19b5c3561c8c6649df0cba825dae1e8fcbec4", "size_bytes": 134909459},
    {"name": "cudart-llama-bin-win-cuda-13.1-x64.zip", "url": "https://github.com/ggml-org/llama.cpp/releases/download/b9000/cudart-llama-bin-win-cuda-13.1-x64.zip", "sha256": "f96935e7e385e3b2d0189239077c10fe8fd7e95690fea4afec455b1b6c7e3f18", "size_bytes": 402582216},
]
LICENSE_URLS = {
    "QWEN-LICENSE.txt": f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/LICENSE",
    "LLAMA-LICENSE.txt": f"https://raw.githubusercontent.com/ggml-org/llama.cpp/{LLAMA_COMMIT}/LICENSE",
    "CUDA-EULA.html": "https://docs.nvidia.com/cuda/archive/13.1.0/eula/index.html",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(asset: dict) -> Path:
    path = VENDOR / asset["name"]
    if path.exists() and path.stat().st_size == asset["size_bytes"] and sha256(path) == asset["sha256"]:
        print(f"Verified existing {path.name}", flush=True)
        return path
    partial = path.with_suffix(path.suffix + ".part")
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(asset["url"], headers={"User-Agent": "DandelionRoboticsLocalSetup/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
                total = 0
                milestone = 0
                while block := response.read(8 * 1024 * 1024):
                    output.write(block)
                    total += len(block)
                    if total // (256 * 1024 * 1024) > milestone:
                        milestone = total // (256 * 1024 * 1024)
                        print(f"Downloading {path.name}: {total}/{asset['size_bytes']} bytes", flush=True)
            if partial.stat().st_size != asset["size_bytes"] or sha256(partial) != asset["sha256"]:
                raise RuntimeError(f"Pinned size/hash verification failed: {path.name}")
            os.replace(partial, path)
            print(f"Verified download {path.name}", flush=True)
            return path
        except Exception as error:
            last_error = error
            print(f"Download attempt {attempt + 1} failed for {path.name}: {error}", flush=True)
            if attempt < 2:
                time.sleep(2)
    raise RuntimeError(f"Download failed: {path.name}") from last_error


def setup() -> dict:
    VENDOR.mkdir(parents=True, exist_ok=True)
    (VENDOR / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    for asset in ASSETS:
        path = download(asset)
        if path.suffix == ".zip":
            destination = VENDOR / "llama"
            destination.mkdir(exist_ok=True)
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    resolved = (destination / member.filename).resolve()
                    if not resolved.is_relative_to(destination.resolve()):
                        raise RuntimeError("Unsafe archive member path")
                archive.extractall(destination)
    for name, url in LICENSE_URLS.items():
        with urllib.request.urlopen(url, timeout=60) as response:
            (VENDOR / name).write_bytes(response.read())
    servers = list((VENDOR / "llama").rglob("llama-server.exe"))
    if len(servers) != 1:
        raise RuntimeError(f"Expected one server executable, found {len(servers)}")
    manifest = {
        "model_repo": MODEL_REPO, "model_revision": MODEL_REVISION,
        "model_file": MODEL_FILE, "model_sha256": MODEL_SHA256,
        "model_license": "Apache-2.0", "llama_release": LLAMA_RELEASE,
        "llama_commit": LLAMA_COMMIT, "llama_license": "MIT",
        "cuda_runtime": "13.1", "cuda_license": "NVIDIA CUDA EULA",
        "assets": ASSETS,
        "server_relative_path": str(servers[0].relative_to(VENDOR)),
        "installed_files": [
            {"path": str(p.relative_to(VENDOR)), "size_bytes": p.stat().st_size, "sha256": sha256(p)}
            for p in sorted((VENDOR / "llama").rglob("*")) if p.is_file()
        ],
        "license_files": [{"path": name, "url": url, "sha256": sha256(VENDOR / name)} for name, url in LICENSE_URLS.items()],
        "verified_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (VENDOR / "asset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Also start, test and stop the local server inside this queued job")
    arguments = parser.parse_args()
    print(json.dumps(setup(), indent=2), flush=True)
    if arguments.smoke:
        from model_runtime import smoke
        print(json.dumps(smoke(), indent=2), flush=True)
