"""Retain lightweight host/client contract tests; no model, robot or simulator."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
INTEGRATION = HERE.parents[1]
REPO = INTEGRATION.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-name", help="New bounded record directory; preserve preceding qualification outputs")
    args = parser.parse_args()
    destination = HERE
    if args.record_name:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", args.record_name) is None:
            parser.error("record-name must be a bounded directory name")
        destination = HERE / args.record_name
        destination.mkdir(exist_ok=False)
    suites = []
    for name, folder in (("host", INTEGRATION / "host"), ("client", INTEGRATION / "client-tests")):
        command = [sys.executable, "-X", "utf8", "-B", "-m", "unittest", "discover", "-s", str(folder), "-p", "test_*.py", "-v"]
        result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, encoding="utf-8")
        output = result.stdout + result.stderr
        (destination / (name + "-tests.txt")).write_text(output, encoding="utf-8")
        count = re.search(r"Ran (\d+) tests", output)
        suites.append({"suite": name, "exit_status": result.returncode,
                       "tests": int(count.group(1)) if count else None,
                       "output": name + "-tests.txt", "command": command})
    sources = sorted((INTEGRATION / "host").glob("*.py")) + [INTEGRATION / "runtime-template" / "robot.py"]
    result = {"schema": "robot-codex-session10-host-verification-1.0",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Synthetic physics and actual loopback HTTP only; no model or Cell instantiated",
              "passed": all(row["exit_status"] == 0 for row in suites), "suites": suites,
              "source_sha256": {str(path.relative_to(INTEGRATION)).replace("\\", "/"):
                                hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}}
    (destination / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "suites": suites}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
