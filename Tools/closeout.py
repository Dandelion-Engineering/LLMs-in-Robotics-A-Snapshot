#!/usr/bin/env python3
"""Serialized, attributable Git closeout for parallel agent sessions.


A successful non-dry-run invocation is the final action of a session.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

LOCK_NAME = ".closeout-session.lock"
OK = 0
PROBLEM = 1
LOCK_BUSY = 4

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except (AttributeError, OSError):
    pass


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    process = subprocess.run(
        ["git", "-C", here, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode == 0 and process.stdout.strip():
        return os.path.abspath(process.stdout.strip())
    directory = here
    while True:
        if os.path.isfile(os.path.join(directory, "AgentPrompt.md")):
            sys.stdout.write(
                "REFUSED: %s looks like a project root but is not a git repository, so there is nothing to commit to. Initialise it first.\n"
                % directory
            )
            sys.exit(PROBLEM)
        parent = os.path.dirname(directory)
        if parent == directory:
            sys.stdout.write(
                "REFUSED: %s is not inside a git repository and no AgentPrompt.md was found above it.\n"
                % here
            )
            sys.exit(PROBLEM)
        directory = parent


def git(root, *args, index=None):
    env = dict(os.environ, GIT_INDEX_FILE=index) if index else None
    process = subprocess.run(
        ["git"] + list(args),
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return process.returncode, ((process.stdout or "") + (process.stderr or "")).strip("\r\n")


def say(line=""):
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def pid_alive(pid):
    try:
        if os.name == "nt":
            output = subprocess.run(
                ["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True
            ).stdout
            return str(pid) in output
        os.kill(pid, 0)
        return True
    except Exception:
        return True


def read_lock(lock_path):
    try:
        with open(lock_path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def acquire(lock_path, agent, timeout, poll=2):
    deadline = time.time() + timeout
    announced = False
    while True:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "agent": agent,
                        "pid": os.getpid(),
                        "acquired": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    },
                    handle,
                )
            return True
        except FileExistsError:
            holder = read_lock(lock_path)
            if not announced:
                say(
                    "Closeout lock held by %s (pid %s, since %s). Waiting up to %ds."
                    % (
                        holder.get("agent", "?"),
                        holder.get("pid", "?"),
                        holder.get("acquired", "?"),
                        timeout,
                    )
                )
                announced = True
            if time.time() >= deadline:
                say("")
                say("Could not acquire the closeout lock within %ds." % timeout)
                pid = holder.get("pid")
                if isinstance(pid, int) and not pid_alive(pid):
                    say("The holding process (pid %s) is no longer running, so the lock is probably stale." % pid)
                    say("Confirm nothing else is committing, then delete this exact lock file manually:")
                    say(lock_path)
                    say("This tool will not break a lock automatically.")
                else:
                    say("The other agent is still closing out. Wait and run this again.")
                return False
            time.sleep(poll)


def scratch_index(root):
    rc, path = git(root, "rev-parse", "--git-path", "index")
    if rc != 0 or not path.strip():
        return None
    real = os.path.join(root, path.strip())
    scratch = real + ".closeout-dryrun"
    try:
        shutil.copyfile(real, scratch)
    except FileNotFoundError:
        pass
    except OSError:
        return None
    return scratch


def run_closeout(root, args):
    if not args.dry_run:
        return _closeout(root, args, None)
    scratch = scratch_index(root)
    if scratch is None:
        say("Could not make a scratch copy of the git index. Refusing to write the real index during a dry run.")
        return PROBLEM
    try:
        return _closeout(root, args, scratch)
    finally:
        try:
            os.remove(scratch)
        except OSError:
            pass


def stage_explicit_paths(root, paths, index):
    for path in paths:
        absolute = path if os.path.isabs(path) else os.path.join(root, path)
        if os.path.lexists(absolute):
            rc, output = git(root, "add", "--", path, index=index)
        else:
            staged_rc, staged_output = git(root, "diff", "--cached", "--quiet", "--", path, index=index)
            if staged_rc == 1:
                rc, output = OK, ""
            elif staged_rc != 0:
                rc, output = staged_rc, staged_output
            else:
                rc, output = git(root, "add", "-u", "--", path, index=index)
        if rc != 0:
            return rc, output
    return OK, ""


def path_is_requested(root, path, requested_paths):
    endpoint = os.path.normcase(path).replace("\\", "/").lstrip("./")
    for requested in requested_paths:
        if os.path.isabs(requested):
            requested = os.path.relpath(requested, root)
        candidate = os.path.normcase(os.path.normpath(requested)).replace("\\", "/").lstrip("./")
        if candidate in ("", "."):
            return True
        candidate = candidate.rstrip("/")
        if endpoint == candidate or endpoint.startswith(candidate + "/"):
            return True
    return False


def one_sided_renames(root, requested_paths, index):
    rc, output = git(root, "diff", "HEAD", "--name-status", "-M", index=index)
    if rc != 0:
        return None, output
    one_sided = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0].startswith("R"):
            source, destination = parts[1], parts[2]
            source_selected = path_is_requested(root, source, requested_paths)
            destination_selected = path_is_requested(root, destination, requested_paths)
            if source_selected != destination_selected:
                one_sided.append((source, destination, source_selected, destination_selected))
    return one_sided, ""


def _closeout(root, args, index):
    label = "%s Session %s" % (args.agent, args.session)
    pathspec = ["--"] + list(args.paths) if args.paths else []

    tracked_lock_rc, _ = git(root, "ls-files", "--error-unmatch", "--", LOCK_NAME, index=index)
    if tracked_lock_rc == 0:
        say("REFUSED: %s is tracked. Remove it from version control and ignore it before trying again." % LOCK_NAME)
        return PROBLEM

    rc, remote_output = git(root, "remote")
    if rc != 0:
        say("FAILED while reading configured Git remotes:\n%s" % remote_output)
        return PROBLEM
    remotes = [line.strip() for line in remote_output.splitlines() if line.strip()]
    upstream = None
    if remotes:
        rc, upstream_output = git(
            root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
        )
        if rc != 0 or not upstream_output.strip():
            say("REFUSED: a Git remote is configured, but the current branch has no upstream.")
            say("Configure the intended upstream before closeout so this tool cannot guess where to push.")
            return PROBLEM
        upstream = upstream_output.strip()
    else:
        say("No Git remote is configured. Closeout will commit locally and skip push.")
        say("")

    rc, before = git(root, "status", "--short", index=index)
    say("Working tree before:")
    say(before if before else "  (clean)")
    say("")

    if args.paths:
        say("Staging (explicit pathspec): %s" % ", ".join(args.paths))
        rc, output = stage_explicit_paths(root, args.paths, index)
    else:
        say("Staging: git add -A")
        rc, output = git(root, "add", "-A", index=index)
    if rc != 0:
        say("FAILED at stage:\n%s" % output)
        return PROBLEM

    rc, output = git(root, "rm", "--cached", "-q", "--ignore-unmatch", "--", LOCK_NAME, index=index)
    if rc != 0:
        say("FAILED while isolating the live closeout lock:\n%s" % output)
        return PROBLEM

    if pathspec:
        rc, staged = git(root, "diff", "--cached", "--name-only", *pathspec, index=index)
    else:
        rc, staged = git(root, "diff", "--cached", "--name-only", index=index)
    if rc != 0:
        say("FAILED while reading staged paths:\n%s" % staged)
        return PROBLEM
    staged_files = [item for item in staged.splitlines() if item.strip()]

    if pathspec:
        one_sided, rename_error = one_sided_renames(root, args.paths, index)
        if one_sided is None:
            say("FAILED while checking moves:\n%s" % rename_error)
            return PROBLEM
        if one_sided:
            say("")
            say("REFUSED: a move has only one endpoint in --paths.")
            for source, destination, source_selected, destination_selected in one_sided:
                say("  source      : %s (%s)" % (source, "selected" if source_selected else "missing"))
                say("  destination : %s (%s)" % (destination, "selected" if destination_selected else "missing"))
            say("Pass both the source and destination paths.")
            return PROBLEM

    if args.dry_run:
        say("")
        say("DRY RUN - nothing committed or pushed, and the index was not touched.")
        say("would commit : %s" % label)
        say("would include: %d file(s)" % len(staged_files))
        for filename in staged_files:
            say("  %s" % filename)
        return OK

    if not staged_files:
        say("Nothing staged. Another closeout may already have committed these paths; no work is lost.")
    else:
        say("Committing %d file(s) as: %s" % (len(staged_files), label))
        commit_args = ["commit", "-m", label] + pathspec
        rc, output = git(root, *commit_args)
        if rc != 0:
            if "nothing to commit" in output or "no changes added" in output:
                say("Nothing to commit.")
            else:
                say("FAILED at commit:\n%s" % output)
                return PROBLEM
        else:
            say(output.splitlines()[0] if output else "committed")

    say("")
    if upstream is None:
        say("No remote configured; the closeout commit remains local.")
    else:
        rc, output = git(root, "push")
        if rc == 0 and "Everything up-to-date" in output:
            say("Nothing to push.")
        elif rc == 0:
            say("Pushed to %s." % upstream)
        else:
            lowered = output.lower()
            divergence = any(
                marker in lowered
                for marker in ("non-fast-forward", "fetch first")
            )
            if divergence:
                say("PUSH REFUSED. The upstream differs from the local state.")
                say("This tool will not pull, rebase, merge, force-push, or resolve the divergence.")
            else:
                say("PUSH FAILED. Git could not update %s; the commit remains local." % upstream)
                say("Resolve the reported Git or connection problem, then coordinate the next closeout.")
            say(output.splitlines()[-1] if output else "")
            return PROBLEM

    rc, after = git(root, "status", "--short")
    say("")
    say("Working tree after:")
    say(after if after else "  (clean)")
    rc, log = git(root, "log", "--oneline", "-3")
    say("")
    say("Recent commits:")
    for line in log.splitlines():
        say("  %s" % line)
    say("")
    say("Closeout complete. The session is over; do not perform further project work in this session.")
    return OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serialized, attributable git closeout for parallel agent sessions.")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--session", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="stage everything; use only when this session is the sole writer")
    group.add_argument("--paths", nargs="+", metavar="PATH", help="stage and commit only these paths")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = repo_root()
    lock_path = os.path.join(root, LOCK_NAME)
    if not acquire(lock_path, args.agent, args.timeout):
        return LOCK_BUSY
    try:
        return run_closeout(root, args)
    finally:
        try:
            os.remove(lock_path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
