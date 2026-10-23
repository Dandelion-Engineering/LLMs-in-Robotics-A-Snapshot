#!/usr/bin/env python3
"""Tests for work.py. All scenarios use a temporary scaffold root."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "work.py"
TMP = Path(tempfile.mkdtemp(prefix="worktooltest-"))
PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'} {name}" + (f" <- {detail}" if detail and not condition else ""))


def make_root(name: str) -> Path:
    root = TMP / name
    (root / "Work" / "Active").mkdir(parents=True)
    (root / "Work" / "Done").mkdir(parents=True)
    (root / "Work" / "Dropped").mkdir(parents=True)
    (root / "AgentPrompt.md").write_text("# marker\n", encoding="utf-8")
    return root


def run(root: Path, *args: str) -> tuple[int, str]:
    process = subprocess.run(
        [sys.executable, str(TOOL), "--root", str(root), "--timeout", "5", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return process.returncode, (process.stdout or "") + (process.stderr or "")


def open_claim(root: Path, agent: str, session: str, name: str, paths: list[str]) -> tuple[int, str]:
    return run(
        root,
        "open",
        "--agent",
        agent,
        "--session",
        session,
        "--name",
        name,
        "--purpose",
        f"Purpose for {name}",
        "--paths",
        *paths,
    )


print("A. Open, overlap, and discovery")
root = make_root("basic")
rc, out = open_claim(root, "Claude", "1", "Build loader", ["src/loader.py", "tests/test_loader.py"])
check("opens a normalized active claim", rc == 0 and (root / "Work/Active/build-loader.md").is_file(), out)
rc, out = open_claim(root, "Codex", "1", "Edit source tree", ["SRC"])
check("directory overlap is refused case-insensitively", rc == 1 and "overlaps" in out, out)
rc, out = open_claim(root, "Codex", "1", "Build report", ["report/main.md"])
check("non-overlapping claim opens", rc == 0, out)
rc, out = run(root, "list")
check("list reports both live leads and paths", rc == 0 and "build-loader" in out and "build-report" in out and "Claude" in out and "Codex" in out, out)
rc, out = run(root, "verify")
check("verify accepts a valid active set", rc == 0 and "no overlap" in out, out)

print("\nB. Path safety")
for bad in ("../secret", "/absolute/path", "C:/drive/path", "."):
    rc, out = open_claim(root, "Claude", "2", f"Bad {bad}", [bad])
    check(f"refuses unsafe path {bad!r}", rc == 1 and "REFUSED" in out, out)

print("\nC. Transfer and terminal lifecycle")
rc, out = run(root, "transfer", "build-loader", "--from-agent", "Claude", "--to-agent", "Codex", "--session", "2")
check("transfers the live lead", rc == 0 and "Codex" in out, out)
rc, out = run(root, "close", "build-loader", "--agent", "Claude", "--session", "2", "--outcome", "Should not close")
check("former lead cannot close the live claim", rc == 1 and "current lead is Codex" in out, out)
rc, out = run(root, "close", "build-loader", "--agent", "Codex", "--session", "2", "--outcome", "Loader integrated")
done = root / "Work/Done/build-loader.md"
check("current lead closes and moves the record", rc == 0 and done.is_file() and not (root / "Work/Active/build-loader.md").exists(), out)
check("closed record preserves the outcome", "Loader integrated" in done.read_text(encoding="utf-8"))
rc, out = run(root, "drop", "build-report", "--agent", "Codex", "--session", "2", "--reason", "Report format changed")
dropped = root / "Work/Dropped/build-report.md"
check("drop moves and preserves the reason", rc == 0 and dropped.is_file() and "Report format changed" in dropped.read_text(encoding="utf-8"), out)

print("\nD. Concurrent overlapping opens")
root2 = make_root("race")
results: dict[str, tuple[int, str]] = {}
barrier = threading.Barrier(2)


def racer(agent: str, name: str) -> None:
    barrier.wait()
    results[agent] = open_claim(root2, agent, "1", name, ["shared/output.json"])


threads = [threading.Thread(target=racer, args=("Claude", "Claude output")), threading.Thread(target=racer, args=("Codex", "Codex output"))]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
codes = sorted(code for code, _ in results.values())
check("atomic lock allows exactly one overlapping claim", codes == [0, 1], str(results))
rc, out = run(root2, "verify")
check("winning concurrent state remains valid", rc == 0, out)

print("\nE. Verify catches tampering")
root3 = make_root("tamper")
open_claim(root3, "Claude", "1", "One", ["a/b.txt"])
open_claim(root3, "Codex", "1", "Two", ["c/d.txt"])
second = root3 / "Work/Active/two.md"
text = second.read_text(encoding="utf-8")
start = text.index("<!-- COLLABORATION-STATION-WORK-CLAIM\n") + len("<!-- COLLABORATION-STATION-WORK-CLAIM\n")
end = text.index("\n-->\n", start)
meta = json.loads(text[start:end])
meta["paths"] = ["a"]
second.write_text(text[:start] + json.dumps(meta, indent=2, sort_keys=True) + text[end:], encoding="utf-8")
rc, out = run(root3, "verify")
check("verify detects manually introduced overlap", rc == 1 and "overlap" in out, out)

print("\n" + "=" * 72)
print(f"PASSED {len(PASS)}   FAILED {len(FAIL)}")
for name in FAIL:
    print(f"  FAILED: {name}")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAIL else 0)
