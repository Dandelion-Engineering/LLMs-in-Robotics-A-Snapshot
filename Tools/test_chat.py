#!/usr/bin/env python3
"""Focused tests for chat.py. Uses only temporary transcripts and state."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "chat.py"
TMP = Path(tempfile.mkdtemp(prefix="chattooltest-"))
ROOT = TMP / "repo"
(ROOT / "Tools").mkdir(parents=True)
(ROOT / "AgentPrompt.md").write_text("# marker\n", encoding="utf-8")
PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'} {name}" + (f" <- {detail}" if detail and not condition else ""))


def run(*args: str, stdin_text: str | None = None) -> tuple[int, str]:
    process = subprocess.run(
        [sys.executable, str(TOOL), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return process.returncode, (process.stdout or "") + (process.stderr or "")


def make_transcript(subject: str, channel: str = "Claude-Codex", eol: str = "\n", active: bool = True) -> Path:
    folder = ROOT / "chats" / channel / subject
    folder.mkdir(parents=True, exist_ok=True)
    state = "Active" if active else "Concluded"
    path = folder / f"{subject} - {state}.md"
    path.write_bytes((f"# {subject}{eol}{eol}seed{eol}").encode("utf-8"))
    return path


def body(name: str, text: str) -> Path:
    path = TMP / name
    path.write_text(text, encoding="utf-8")
    return path


print("A. Discovery and inbox checkpoints")
transcript = make_transcript("Architecture")
concluded = make_transcript("Old Topic", active=False)
other_channel = make_transcript("Human Only", channel="Codex-Human")
rc, out = run("inbox", "--agent", "Claude", "--root", str(ROOT))
check("first inbox establishes an unseen baseline", rc == 0 and "NO CHECKPOINT YET" in out and "Architecture" in out, out)
check("concluded transcript is absent from inbox", "Old Topic - Concluded" not in out)
check("channel not naming the agent is absent", "Human Only" not in out)
rc, out = run("inbox", "--agent", "Claude", "--root", str(ROOT))
check("unchanged inbox reports nothing new", rc == 0 and "Nothing new" in out, out)

print("\nB. Safe append and stale refusal")
expected = transcript.stat().st_size
rc, out = run(
    "post", str(transcript), "--agent", "Codex", "--session", "1",
    "--body-file", str(body("codex.md", "A new design idea.")),
    "--expect-bytes", str(expected), "--root", str(ROOT),
)
check("post appends and verifies", rc == 0 and "POSTED and verified" in out, out)
rc, out = run("inbox", "--agent", "Claude", "--root", str(ROOT))
check("inbox shows exactly the newly appended message", rc == 0 and "A new design idea." in out and "NEW IN" in out, out)

stale_count = transcript.stat().st_size
run(
    "post", str(transcript), "--agent", "Codex", "--session", "2",
    "--body-file", str(body("codex2.md", "Another message.")),
    "--expect-bytes", str(stale_count), "--root", str(ROOT),
)
rc, out = run(
    "post", str(transcript), "--agent", "Claude", "--session", "2",
    "--body-file", str(body("claude.md", "A stale reply.")),
    "--expect-bytes", str(stale_count), "--root", str(ROOT),
)
check("stale post is refused and shows what arrived", rc == 1 and "REFUSED" in out and "Another message." in out, out)

print("\nC. Human-safe interactive append")
human_chat = make_transcript("Human Input", channel="Claude-Codex-Human", eol="\r\n")
rc, out = run(
    "human", str(human_chat), "--root", str(ROOT),
    stdin_text="Randy\nA timestamped human message.\nSecond line.\n.\n",
)
human_data = human_chat.read_bytes()
human_text = human_data.decode("utf-8")
human_crlf = human_data.count(b"\r\n")
human_bare_lf = human_data.count(b"\n") - human_crlf
check("human command appends and verifies", rc == 0 and "POSTED and verified" in out, out)
check(
    "human header carries the agent-style date and time",
    re.search(r"\*\*Randy \(\d{4}-\d{2}-\d{2} \d{2}:\d{2} \S+\):\*\*", human_text) is not None,
    human_text,
)
check("human command preserves CRLF", human_bare_lf == 0)
rc, out = run("verify", str(human_chat))
check("verify recognizes the timestamped human message", rc == 0 and "human messages: 1" in out, out)

not_human = make_transcript("Agent Only", channel="Claude-Codex")
rc, out = run(
    "human", str(not_human), "--name", "Randy", "--root", str(ROOT),
    stdin_text="Must not post.\n.\n",
)
check("human command refuses a non-human channel", rc == 1 and "not an active transcript" in out, out)

rc, out = run("human", "--root", str(ROOT), stdin_text="q\n")
check(
    "human chooser lists only active human chats",
    rc == 0 and "Human Input - Active.md" in out and "Agent Only - Active.md" not in out,
    out,
)

before_cancel = human_chat.read_bytes()
rc, out = run(
    "human", str(human_chat), "--name", "Randy", "--root", str(ROOT), stdin_text=":cancel\n"
)
check(
    "human can cancel without changing the transcript",
    rc == 0 and "No message posted" in out and human_chat.read_bytes() == before_cancel,
    out,
)

stale_human = make_transcript("Human Stale", channel="Claude-Human")
process = subprocess.Popen(
    [
        sys.executable,
        str(TOOL),
        "human",
        str(stale_human),
        "--name",
        "Randy",
        "--root",
        str(ROOT),
    ],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
)
prompt_output = ""
while "Type :cancel" not in prompt_output:
    line = process.stdout.readline()
    if not line:
        break
    prompt_output += line
with stale_human.open("ab") as fh:
    fh.write(b"\n---\n\n**Claude (Session 9, 2026-08-20 16:55 PDT):**\n\nConcurrent message.\n")
remaining_output, _ = process.communicate("A now-stale human reply.\n.\n", timeout=10)
stale_output = prompt_output + remaining_output
check(
    "human post refuses an intervening append and shows it",
    process.returncode == 1 and "REFUSED" in stale_output and "Concurrent message." in stale_output
    and "A now-stale human reply." not in stale_human.read_text(encoding="utf-8"),
    stale_output,
)

print("\nD. Line endings and verification")
crlf = make_transcript("CRLF", eol="\r\n")
rc, out = run(
    "post", str(crlf), "--agent", "Claude", "--session", "3",
    "--body-file", str(body("crlf.md", "Preserve the transcript.")),
    "--expect-bytes", str(crlf.stat().st_size), "--root", str(ROOT),
)
data = crlf.read_bytes()
crlf_count = data.count(b"\r\n")
bare_lf = data.count(b"\n") - crlf_count
check("post preserves CRLF without bare LF", rc == 0 and bare_lf == 0, out)
rc, out = run("verify", str(crlf))
check("verify accepts the resulting transcript", rc == 0 and "OK - no problems" in out, out)

print("\nE. Bounded wait")
wait_subject = make_transcript("Wait")
run("inbox", "--agent", "Claude", "--mark", "--root", str(ROOT))
t0 = time.time()
rc, out = run("wait", "--agent", "Claude", "--timeout", "2", "--interval", "1", "--root", str(ROOT))
check("wait times out with exit code 3", rc == 3 and "Nothing arrived" in out and time.time() - t0 < 10, out)


def delayed_post() -> None:
    time.sleep(1)
    run(
        "post", str(wait_subject), "--agent", "Codex", "--session", "4",
        "--body-file", str(body("late.md", "Arrived during the wait.")),
        "--expect-bytes", str(wait_subject.stat().st_size), "--root", str(ROOT),
    )


threading.Thread(target=delayed_post, daemon=True).start()
rc, out = run("wait", "--agent", "Claude", "--timeout", "10", "--interval", "1", "--root", str(ROOT))
check("wait returns when identified content arrives", rc == 0 and "Arrived during the wait." in out, out)

print("\n" + "=" * 72)
print(f"PASSED {len(PASS)}   FAILED {len(FAIL)}")
for name in FAIL:
    print(f"  FAILED: {name}")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAIL else 0)
