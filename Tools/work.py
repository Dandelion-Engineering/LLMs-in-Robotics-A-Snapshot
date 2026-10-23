#!/usr/bin/env python3
"""Atomic lifecycle management for Collaboration Station write claims.

A work claim reserves repository-relative paths that one agent is actively
writing. It does not reserve ideas, subjects, read-only inspection, or permanent
ownership. This tool exists to make the one mechanical guarantee the convention
cannot make by itself: two concurrent sessions cannot both open overlapping
claims after reading the same stale directory state.

Standard library only. No credentials or network.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

OK = 0
PROBLEM = 1
LOCK_BUSY = 4
LOCK_NAME = ".work-tool.lock"
MARKER_START = "<!-- COLLABORATION-STATION-WORK-CLAIM\n"
MARKER_END = "\n-->\n"
VERSION = 1

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except (AttributeError, OSError):  # pragma: no cover
    pass


def say(text: str = "") -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S %Z")


def repo_root(explicit: str | None = None) -> Path:
    if explicit:
        root = Path(explicit).resolve()
        if not (root / "AgentPrompt.md").is_file():
            raise ValueError(f"{root} has no AgentPrompt.md and is not a scaffold root")
        return root

    here = Path(__file__).resolve().parent
    current = here
    while True:
        if (current / "AgentPrompt.md").is_file():
            return current
        if current.parent == current:
            raise ValueError(f"no AgentPrompt.md found above {here}")
        current = current.parent


def work_dirs(root: Path) -> tuple[Path, Path, Path, Path]:
    base = root / "Work"
    return base, base / "Active", base / "Done", base / "Dropped"


def ensure_dirs(root: Path) -> None:
    for path in work_dirs(root):
        path.mkdir(parents=True, exist_ok=True)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    slug = slug[:80].rstrip("-")
    if not slug:
        raise ValueError("the work name must contain at least one letter or number")
    return slug


def normalize_claim_path(raw: str) -> str:
    value = raw.strip().replace("\\", "/")
    if not value:
        raise ValueError("claim paths may not be empty")
    if value.startswith(("/", "~/")) or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"claim path must be repository-relative: {raw!r}")

    parts: list[str] = []
    for part in PurePosixPath(value).parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError(f"claim path may not traverse upward: {raw!r}")
        parts.append(part)
    if not parts:
        raise ValueError("claiming the repository root is not supported; name concrete paths")
    normalized = "/".join(parts).rstrip("/")
    if normalized.casefold().startswith(".git/") or normalized.casefold() == ".git":
        raise ValueError("the .git directory cannot be claimed")
    return normalized


def path_key(path: str) -> str:
    # The standard project environment includes Windows. Case-folding makes the
    # claim system conservative on both case-sensitive and case-insensitive hosts.
    return path.replace("\\", "/").strip("/").casefold()


def paths_overlap(left: str, right: str) -> bool:
    a, b = path_key(left), path_key(right)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def first_overlap(left: Iterable[str], right: Iterable[str]) -> tuple[str, str] | None:
    for a in left:
        for b in right:
            if paths_overlap(a, b):
                return a, b
    return None


def acquire_lock(lock_path: Path, agent: str, timeout: int, poll: float = 0.2) -> bool:
    deadline = time.time() + max(0, timeout)
    announced = False
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"agent": agent, "pid": os.getpid(), "acquired": now()}, handle)
            return True
        except FileExistsError:
            if not announced:
                holder: dict[str, Any] = {}
                try:
                    holder = json.loads(lock_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass
                say(
                    "Work lock held by %s (pid %s, since %s). Waiting up to %ds."
                    % (
                        holder.get("agent", "?"),
                        holder.get("pid", "?"),
                        holder.get("acquired", "?"),
                        timeout,
                    )
                )
                announced = True
            if time.time() >= deadline:
                say(f"REFUSED: could not acquire {lock_path} within {timeout}s")
                say("Confirm no work.py process is active before removing a stale lock manually.")
                return False
            time.sleep(poll)


def release_lock(lock_path: Path, timeout: float = 2.0, poll: float = 0.02) -> None:
    """Release a lock after transient Windows readers let go of the file.

    A waiter reads the lock metadata before polling. On Windows that brief read
    can deny deletion, so a winner that immediately unlinks may otherwise leave
    a completed claim and a stranded lock behind.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        try:
            lock_path.unlink()
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(poll)


@dataclass
class Claim:
    path: Path
    metadata: dict[str, Any]

    @property
    def claim_id(self) -> str:
        return str(self.metadata["id"])

    @property
    def lead(self) -> str:
        return str(self.metadata["lead"])

    @property
    def paths(self) -> list[str]:
        return list(self.metadata["paths"])


def parse_claim(path: Path) -> Claim:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(MARKER_START):
        raise ValueError(f"{path} is missing the work-claim metadata marker")
    end = text.find(MARKER_END, len(MARKER_START))
    if end < 0:
        raise ValueError(f"{path} has an unterminated work-claim metadata marker")
    try:
        metadata = json.loads(text[len(MARKER_START) : end])
    except ValueError as exc:
        raise ValueError(f"{path} has invalid JSON metadata: {exc}") from exc
    validate_metadata(metadata, path)
    return Claim(path=path, metadata=metadata)


def validate_metadata(metadata: dict[str, Any], path: Path | None = None) -> None:
    required = {
        "version",
        "id",
        "name",
        "lead",
        "session",
        "opened",
        "state",
        "purpose",
        "paths",
        "collaborators",
        "history",
    }
    missing = sorted(required - set(metadata))
    if missing:
        raise ValueError(f"missing metadata fields: {', '.join(missing)}")
    if metadata["version"] != VERSION:
        raise ValueError(f"unsupported work-claim version: {metadata['version']!r}")
    if slugify(str(metadata["name"])) != metadata["id"]:
        raise ValueError("claim id does not match the normalized name")
    if path and path.stem != metadata["id"]:
        raise ValueError(f"filename {path.name!r} does not match id {metadata['id']!r}")
    if not str(metadata["lead"]).strip():
        raise ValueError("lead may not be empty")
    if metadata["state"] not in {"active", "done", "dropped"}:
        raise ValueError(f"invalid claim state: {metadata['state']!r}")
    if not isinstance(metadata["paths"], list) or not metadata["paths"]:
        raise ValueError("paths must be a non-empty list")
    normalized = [normalize_claim_path(str(item)) for item in metadata["paths"]]
    if normalized != metadata["paths"]:
        raise ValueError("claim paths are not normalized")
    if len({path_key(item) for item in normalized}) != len(normalized):
        raise ValueError("claim contains duplicate paths")
    for index, left in enumerate(normalized):
        for right in normalized[index + 1 :]:
            if paths_overlap(left, right):
                raise ValueError(f"claim redundantly overlaps itself: {left!r} and {right!r}")
    if not isinstance(metadata["collaborators"], list):
        raise ValueError("collaborators must be a list")
    if not isinstance(metadata["history"], list):
        raise ValueError("history must be a list")


def render_claim(metadata: dict[str, Any]) -> str:
    encoded = json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True)
    collaborators = ", ".join(metadata["collaborators"]) or "none"
    paths = "\n".join(f"- `{path}`" for path in metadata["paths"])
    history = "\n".join(
        f"- **{entry.get('time', '?')}** — {entry.get('event', 'event')} "
        f"by {entry.get('agent', '?')} (Session {entry.get('session', '?')})"
        + (f": {entry['detail']}" if entry.get("detail") else "")
        for entry in metadata["history"]
    )
    terminal = ""
    if metadata["state"] == "done":
        terminal = f"\n## Outcome\n\n{metadata.get('outcome', '')}\n"
    elif metadata["state"] == "dropped":
        terminal = f"\n## Reason dropped\n\n{metadata.get('reason', '')}\n"

    return (
        f"{MARKER_START}{encoded}{MARKER_END}"
        f"# {metadata['name']}\n\n"
        f"**State:** {metadata['state']}  \n"
        f"**Lead:** {metadata['lead']}  \n"
        f"**Collaborators:** {collaborators}  \n"
        f"**Opened:** {metadata['opened']} (Session {metadata['session']})\n\n"
        f"## Purpose\n\n{metadata['purpose']}\n\n"
        f"## Write scope\n\n{paths}\n"
        f"{terminal}\n## History\n\n{history}\n"
    )


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def load_active(root: Path) -> list[Claim]:
    _, active, _, _ = work_dirs(root)
    claims: list[Claim] = []
    for path in sorted(active.glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        claims.append(parse_claim(path))
    return claims


def locate_claim(root: Path, identifier: str) -> Claim:
    slug = identifier[:-3] if identifier.lower().endswith(".md") else identifier
    slug = slugify(slug)
    for directory in work_dirs(root)[1:]:
        path = directory / f"{slug}.md"
        if path.is_file():
            return parse_claim(path)
    raise ValueError(f"no work claim found with id {slug!r}")


def assert_lead(claim: Claim, agent: str) -> None:
    if claim.lead.casefold() != agent.strip().casefold():
        raise ValueError(f"{agent} is not the live lead; current lead is {claim.lead}")


def cmd_list(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    ensure_dirs(root)
    claims = load_active(root)
    if not claims:
        say("No active work claims.")
        return OK
    say(f"{len(claims)} active work claim(s):")
    for claim in claims:
        say(f"- {claim.claim_id}: {claim.metadata['name']}")
        say(f"  lead: {claim.lead}; session: {claim.metadata['session']}")
        say(f"  purpose: {claim.metadata['purpose']}")
        say(f"  paths: {', '.join(claim.paths)}")
    return OK


def cmd_show(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    claim = locate_claim(root, args.identifier)
    sys.stdout.write(claim.path.read_text(encoding="utf-8"))
    return OK


def cmd_open(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    ensure_dirs(root)
    base, active, done, dropped = work_dirs(root)
    lock = base / LOCK_NAME
    if not acquire_lock(lock, args.agent, args.timeout):
        return LOCK_BUSY
    try:
        claim_id = slugify(args.name)
        for directory in (active, done, dropped):
            if (directory / f"{claim_id}.md").exists():
                raise ValueError(
                    f"claim id {claim_id!r} already exists in {directory.relative_to(root)}; "
                    "choose a name that describes the new work"
                )
        paths = [normalize_claim_path(item) for item in args.paths]
        if len({path_key(item) for item in paths}) != len(paths):
            raise ValueError("duplicate claim paths were supplied")
        for index, left in enumerate(paths):
            for right in paths[index + 1 :]:
                if paths_overlap(left, right):
                    raise ValueError(f"the new claim overlaps itself: {left!r} and {right!r}")

        for existing in load_active(root):
            overlap = first_overlap(paths, existing.paths)
            if overlap:
                raise ValueError(
                    f"requested path {overlap[0]!r} overlaps {overlap[1]!r} in active "
                    f"claim {existing.claim_id!r}, led by {existing.lead}"
                )

        opened = now()
        metadata = {
            "version": VERSION,
            "id": claim_id,
            "name": args.name.strip(),
            "lead": args.agent.strip(),
            "session": str(args.session),
            "opened": opened,
            "state": "active",
            "purpose": args.purpose.strip(),
            "paths": paths,
            "collaborators": [item.strip() for item in (args.collaborators or []) if item.strip()],
            "history": [
                {
                    "event": "opened",
                    "agent": args.agent.strip(),
                    "session": str(args.session),
                    "time": opened,
                    "detail": args.purpose.strip(),
                }
            ],
        }
        validate_metadata(metadata)
        destination = active / f"{claim_id}.md"
        atomic_write(destination, render_claim(metadata))
        say(f"Opened {destination.relative_to(root)}")
        say(f"Lead: {metadata['lead']}")
        say(f"Paths: {', '.join(paths)}")
        return OK
    except ValueError as exc:
        say(f"REFUSED: {exc}")
        return PROBLEM
    finally:
        release_lock(lock)


def mutate_active(args: argparse.Namespace, event: str) -> int:
    root = repo_root(args.root)
    ensure_dirs(root)
    base, active, done, dropped = work_dirs(root)
    lock = base / LOCK_NAME
    if not acquire_lock(lock, getattr(args, "agent", getattr(args, "from_agent", "?")), args.timeout):
        return LOCK_BUSY
    try:
        claim = locate_claim(root, args.identifier)
        if claim.path.parent != active:
            raise ValueError(f"claim {claim.claim_id!r} is not active")

        stamp = now()
        metadata = dict(claim.metadata)
        metadata["history"] = list(metadata["history"])

        if event == "transfer":
            assert_lead(claim, args.from_agent)
            new_lead = args.to_agent.strip()
            if not new_lead:
                raise ValueError("new lead may not be empty")
            metadata["lead"] = new_lead
            metadata["session"] = str(args.session)
            metadata["history"].append(
                {
                    "event": "transferred",
                    "agent": args.from_agent.strip(),
                    "session": str(args.session),
                    "time": stamp,
                    "detail": f"live lead transferred to {new_lead}",
                }
            )
            atomic_write(claim.path, render_claim(metadata))
            say(f"Transferred {claim.claim_id} to {new_lead}")
            return OK

        assert_lead(claim, args.agent)
        if event == "close":
            metadata["state"] = "done"
            metadata["outcome"] = args.outcome.strip()
            metadata["closed"] = stamp
            metadata["history"].append(
                {
                    "event": "closed",
                    "agent": args.agent.strip(),
                    "session": str(args.session),
                    "time": stamp,
                    "detail": args.outcome.strip(),
                }
            )
            destination = done / claim.path.name
        else:
            metadata["state"] = "dropped"
            metadata["reason"] = args.reason.strip()
            metadata["closed"] = stamp
            metadata["history"].append(
                {
                    "event": "dropped",
                    "agent": args.agent.strip(),
                    "session": str(args.session),
                    "time": stamp,
                    "detail": args.reason.strip(),
                }
            )
            destination = dropped / claim.path.name

        if destination.exists():
            raise ValueError(f"destination already exists: {destination.relative_to(root)}")
        atomic_write(claim.path, render_claim(metadata))
        os.replace(claim.path, destination)
        say(f"Moved {claim.claim_id} to {destination.parent.relative_to(root)}")
        return OK
    except ValueError as exc:
        say(f"REFUSED: {exc}")
        return PROBLEM
    finally:
        release_lock(lock)


def cmd_transfer(args: argparse.Namespace) -> int:
    return mutate_active(args, "transfer")


def cmd_close(args: argparse.Namespace) -> int:
    return mutate_active(args, "close")


def cmd_drop(args: argparse.Namespace) -> int:
    return mutate_active(args, "drop")


def cmd_verify(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    ensure_dirs(root)
    try:
        claims = load_active(root)
        for index, left in enumerate(claims):
            for right in claims[index + 1 :]:
                overlap = first_overlap(left.paths, right.paths)
                if overlap:
                    raise ValueError(
                        f"active claims {left.claim_id!r} and {right.claim_id!r} overlap at "
                        f"{overlap[0]!r} / {overlap[1]!r}"
                    )
        say(f"OK - {len(claims)} active claim(s), no overlap or metadata problems.")
        return OK
    except (OSError, ValueError) as exc:
        say(f"INVALID: {exc}")
        return PROBLEM


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atomic lifecycle management for live write claims.")
    parser.add_argument("--root", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, default=30, help="seconds to wait for the work lock")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="list active claims")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="print one claim from any lifecycle folder")
    p_show.add_argument("identifier")
    p_show.set_defaults(func=cmd_show)

    p_open = sub.add_parser("open", help="atomically open a non-overlapping write claim")
    p_open.add_argument("--agent", required=True)
    p_open.add_argument("--session", required=True)
    p_open.add_argument("--name", required=True)
    p_open.add_argument("--purpose", required=True)
    p_open.add_argument("--paths", nargs="+", required=True)
    p_open.add_argument("--collaborators", nargs="*", default=[])
    p_open.set_defaults(func=cmd_open)

    p_transfer = sub.add_parser("transfer", help="transfer the live lead")
    p_transfer.add_argument("identifier")
    p_transfer.add_argument("--from-agent", required=True)
    p_transfer.add_argument("--to-agent", required=True)
    p_transfer.add_argument("--session", required=True)
    p_transfer.set_defaults(func=cmd_transfer)

    p_close = sub.add_parser("close", help="move completed work to Work/Done")
    p_close.add_argument("identifier")
    p_close.add_argument("--agent", required=True)
    p_close.add_argument("--session", required=True)
    p_close.add_argument("--outcome", required=True)
    p_close.set_defaults(func=cmd_close)

    p_drop = sub.add_parser("drop", help="move abandoned work to Work/Dropped")
    p_drop.add_argument("identifier")
    p_drop.add_argument("--agent", required=True)
    p_drop.add_argument("--session", required=True)
    p_drop.add_argument("--reason", required=True)
    p_drop.set_defaults(func=cmd_drop)

    p_verify = sub.add_parser("verify", help="check active metadata and pairwise non-overlap")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return PROBLEM
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        say(f"REFUSED: {exc}")
        return PROBLEM


if __name__ == "__main__":
    sys.exit(main())
