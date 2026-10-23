#!/usr/bin/env python3
"""Focused tests for closeout.py using throwaway repositories and remotes."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_TOOL = HERE / "closeout.py"
TMP = Path(tempfile.mkdtemp(prefix="closeouttooltest-"))
PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'} {name}" + (f" <- {detail}" if detail and not condition else ""))


def git(repo: Path, *args: str) -> tuple[int, str]:
    process = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True,
        encoding="utf-8", errors="replace"
    )
    return process.returncode, ((process.stdout or "") + (process.stderr or "")).strip()


def make_repo(name: str) -> Path:
    bare = TMP / f"{name}.git"
    repo = TMP / name
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(bare), str(repo)], check=True, capture_output=True)
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "Tools").mkdir()
    shutil.copy2(SOURCE_TOOL, repo / "Tools/closeout.py")
    (repo / "AgentPrompt.md").write_text("# marker\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".closeout-session.lock\n", encoding="utf-8")
    (repo / "seed.md").write_text("seed\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "Initial")
    git(repo, "push", "-u", "origin", "main")
    return repo


def run(repo: Path, *args: str) -> tuple[int, str]:
    process = subprocess.run(
        [sys.executable, str(repo / "Tools/closeout.py"), *args],
        cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return process.returncode, (process.stdout or "") + (process.stderr or "")


print("A. Dry run and explicit attribution")
repo = make_repo("basic")
(repo / "agents/Claude").mkdir(parents=True)
(repo / "agents/Codex").mkdir(parents=True)
(repo / "agents/Claude/report.md").write_text("Claude\n", encoding="utf-8")
(repo / "agents/Codex/report.md").write_text("Codex\n", encoding="utf-8")
rc, out = run(repo, "--agent", "Claude", "--session", "1", "--dry-run", "--paths", "agents/Claude")
_, staged = git(repo, "diff", "--cached", "--name-only")
check("dry run names only requested paths", rc == 0 and "agents/Claude/report.md" in out and "agents/Codex/report.md" not in out.split("would include:")[-1], out)
check("dry run leaves the real index untouched", staged == "", staged)
rc, out = run(repo, "--agent", "Claude", "--session", "1", "--paths", "agents/Claude")
check("explicit closeout commits and pushes", rc == 0 and "Pushed" in out and "session is over" in out.lower(), out)
_, head_files = git(repo, "show", "--name-only", "--format=", "HEAD")
check("commit contains Claude path but not Codex path", "agents/Claude/report.md" in head_files and "agents/Codex/report.md" not in head_files, head_files)
check("unclaimed Codex path remains in working tree", (repo / "agents/Codex/report.md").exists())

print("\nB. Local-only and upstream preflight")
local_repo = make_repo("local-only")
git(local_repo, "remote", "remove", "origin")
(local_repo / "local.md").write_text("local\n", encoding="utf-8")
rc, out = run(local_repo, "--agent", "Codex", "--session", "1", "--paths", "local.md")
check("local-only closeout succeeds explicitly", rc == 0 and "commit remains local" in out, out)
_, local_tree = git(local_repo, "ls-tree", "-r", "--name-only", "HEAD")
check("local-only closeout commits the requested path", "local.md" in local_tree, local_tree)

no_upstream_repo = make_repo("no-upstream")
git(no_upstream_repo, "switch", "-c", "work")
(no_upstream_repo / "work.md").write_text("work\n", encoding="utf-8")
_, before_head = git(no_upstream_repo, "rev-parse", "HEAD")
rc, out = run(no_upstream_repo, "--agent", "Codex", "--session", "1", "--paths", "work.md")
_, after_head = git(no_upstream_repo, "rev-parse", "HEAD")
check("configured remote without upstream is refused before commit", rc == 1 and "has no upstream" in out and before_head == after_head, out)

push_failure_repo = make_repo("push-failure")
git(push_failure_repo, "remote", "set-url", "origin", str(TMP / "missing-remote.git"))
(push_failure_repo / "offline.md").write_text("offline\n", encoding="utf-8")
rc, out = run(push_failure_repo, "--agent", "Codex", "--session", "1", "--paths", "offline.md")
check("non-divergence push failure is diagnosed accurately", rc == 1 and "PUSH FAILED" in out and "upstream differs" not in out, out)
_, failed_push_tree = git(push_failure_repo, "ls-tree", "-r", "--name-only", "HEAD")
check("failed push leaves the closeout commit local", "offline.md" in failed_push_tree and "commit remains local" in out, out)

print("\nC. Move endpoints")
(repo / "Work/Active").mkdir(parents=True)
(repo / "Work/Done").mkdir(parents=True)
(repo / "Work/Active/item.md").write_text("claim\n", encoding="utf-8")
git(repo, "add", "Work/Active/item.md")
git(repo, "commit", "-m", "Add claim")
git(repo, "push")
(repo / "Work/Active/item.md").replace(repo / "Work/Done/item.md")
rc, out = run(repo, "--agent", "Claude", "--session", "2", "--paths", "Work/Done/item.md")
check("one-sided move is refused", rc == 1 and "only one endpoint" in out, out)
rc, out = run(repo, "--agent", "Claude", "--session", "2", "--paths", "Work/Active/item.md", "Work/Done/item.md")
check("two-sided move succeeds", rc == 0, out)
_, tree = git(repo, "ls-tree", "-r", "--name-only", "HEAD")
check("only destination remains in HEAD", "Work/Done/item.md" in tree and "Work/Active/item.md" not in tree, tree)

print("\nD. Runtime lock exclusion")
_, tree = git(repo, "ls-tree", "-r", "--name-only", "HEAD")
check("closeout lock never enters history", ".closeout-session.lock" not in tree, tree)

print("\n" + "=" * 72)
print(f"PASSED {len(PASS)}   FAILED {len(FAIL)}")
for name in FAIL:
    print(f"  FAILED: {name}")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAIL else 0)
