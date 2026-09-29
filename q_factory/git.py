"""Git operations with explicit repository identity and owned task worktrees."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class FactoryError(ValueError):
    """An actionable refusal; callers must not substitute another repository."""


def git(root: Path, *args: str, check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}, timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise FactoryError("Git operation timed out; inspect the selected repository locally.") from None
    if check and result.returncode:
        # Do not echo Git stderr: remote URLs can contain credentials.
        raise FactoryError(f"Git {args[0]} failed (exit {result.returncode}); inspect the repository locally.")
    return result.stdout.strip() if result.returncode == 0 else ""


def factory_root(root: str | Path) -> Path:
    root = Path(root).resolve()
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise FactoryError("The factory root must be the top level of its own checkout.")
    if not (root / "CLAUDE.md").is_file() or not (root / "projects" / "README.md").is_file():
        raise FactoryError("The selected checkout is not a prepared q-factory root.")
    return root


def contained(root: Path, relative: str) -> Path:
    path = root / relative
    if path.resolve() != path.absolute() or not path.resolve().is_relative_to(root):
        raise FactoryError("Workspace paths must not traverse symlinks or escape the selected root.")
    return path


def module(root: Path, repository_path: str) -> dict:
    if not repository_path.startswith("projects/") or not SLUG.fullmatch(repository_path[9:]):
        raise FactoryError("A managed repository path must be projects/<lowercase-slug>.")
    path = contained(root, repository_path)
    config = contained(root, ".gitmodules")
    if not config.is_file():
        raise FactoryError("This workspace has no .gitmodules; onboard the project first.")
    rows = git(root, "config", "--file", str(config), "--get-regexp", r"^submodule\..*\.path$", check=False)
    matches = [line.split(" ", 1)[0][:-5] for line in rows.splitlines()
               if " " in line and line.split(" ", 1)[1] == repository_path]
    if len(matches) != 1:
        raise FactoryError("The project must have exactly one matching .gitmodules entry.")
    entry = git(root, "ls-files", "--stage", "--", repository_path).splitlines()
    if len(entry) != 1 or not entry[0].startswith("160000 ") or not entry[0].split("\t")[0].endswith(" 0"):
        raise FactoryError("The project must be an unconflicted Git submodule in the index.")
    url = git(root, "config", "--file", str(config), "--get", matches[0] + ".url")
    if not url or url.startswith("-"):
        raise FactoryError("The submodule needs a repository URL.")
    return {"path": path, "repository_path": repository_path, "url": url,
            "pinned_commit": entry[0].split()[1], "config_section": matches[0]}


def project(root: Path, repository_path: str) -> dict:
    info = module(root, repository_path)
    path = info["path"]
    if not path.is_dir() or Path(git(path, "rev-parse", "--show-toplevel")).resolve() != path:
        raise FactoryError("Project is uninitialized or is not its own repository; initialize its submodule explicitly.")
    actual = git(path, "remote", "get-url", "origin")
    expected = info["url"]
    # Relative .gitmodules URLs are resolved by Git at initialization time.
    if expected.startswith(("./", "../")):
        expected = git(root, "config", "--get", info["config_section"] + ".url", check=False)
        if not expected:
            raise FactoryError("Relative submodule URL cannot be resolved; use an absolute remote URL for this workspace.")
    if actual != expected:
        raise FactoryError("Project origin differs from the registered submodule URL.")
    info["head"] = git(path, "rev-parse", "HEAD")
    info["dirty"] = bool(git(path, "status", "--porcelain"))
    info["branch"] = git(path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False) or None
    return info


def worktrees(repo: Path) -> list[dict]:
    records = []
    for block in git(repo, "worktree", "list", "--porcelain").split("\n\n"):
        row = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            row[key] = value or True
        if row:
            # Apple Git 2.39 can report the absorbed submodule gitdir as
            # its primary worktree. Callers pass the verified primary
            # checkout, so normalize only that exact metadata-directory row.
            if row.get("worktree") and Path(row["worktree"]).resolve() == _identity(repo):
                row["worktree"] = str(Path(git(repo, "rev-parse", "--show-toplevel")).resolve())
            records.append(row)
    return records


def task_paths(root: Path, repository_path: str, task: str) -> tuple[Path, Path]:
    if not SLUG.fullmatch(task):
        raise FactoryError("Task names must be lowercase slugs.")
    relative = f".worktrees/{repository_path[9:]}/{task}"
    return contained(root, relative), contained(root, relative + ".json")


def _identity(repo: Path) -> Path:
    return Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()


def start(root: Path, repository_path: str, task: str, base: str, owner: str, ticket: str,
          ticket_board: dict | None = None) -> dict:
    """ticket_board, for a ticket on another entity's board, adds its project and board IDs to the record."""
    info = project(root, repository_path)
    repo = info["path"]
    if not owner.strip() or not ticket.strip() or not base or base.startswith("-"):
        raise FactoryError("Owner, ticket and explicit base revision are required.")
    if info["dirty"]:
        raise FactoryError("The submodule checkout has local changes; preserve them before starting work.")
    base_sha = git(repo, "rev-parse", "--verify", base + "^{commit}")
    path, state = task_paths(root, repository_path, task)
    branch = "task/" + task
    expected = {"repository_path": repository_path, "task": task, "branch": branch,
                "base_commit": base_sha, "owner": owner, "ticket": ticket, "path": str(path), **(ticket_board or {})}
    if path.exists() or state.exists():
        if not state.is_file() or not path.is_dir():
            raise FactoryError("Partial or occupied task checkout; inspect it before recovery.")
        existing = json.loads(state.read_text())
        if existing != expected or _identity(path) != _identity(repo):
            raise FactoryError("Existing task checkout has different ownership, base or repository.")
        if git(path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False) != branch:
            raise FactoryError("Existing task checkout is no longer on its recorded branch.")
        return {**existing, "resumed": True}
    if git(repo, "show-ref", "--verify", "refs/heads/" + branch, check=False):
        raise FactoryError("Task branch already exists; choose another task or resume its existing checkout.")
    path.parent.mkdir(parents=True, exist_ok=True)
    git(repo, "worktree", "add", "-b", branch, str(path), base_sha)
    # An exclusive file makes partial failures visible rather than overwriting
    # someone else's ownership record. No force cleanup on failure.
    with state.open("x") as handle:
        json.dump(expected, handle, indent=2)
    git(repo, "worktree", "lock", "--reason", f"factory owner {owner}; ticket {ticket}", str(path))
    return {**expected, "resumed": False}


def finish(root: Path, repository_path: str, task: str, owner: str, merged_into: str, inactive: bool) -> dict:
    repo = project(root, repository_path)["path"]
    path, state = task_paths(root, repository_path, task)
    if not inactive:
        raise FactoryError("Confirm the worker is inactive before removing its checkout.")
    if not state.is_file() or not path.is_dir():
        raise FactoryError("No complete owned task checkout exists.")
    record = json.loads(state.read_text())
    if record.get("owner") != owner or record.get("repository_path") != repository_path or record.get("path") != str(path):
        raise FactoryError("Task ownership does not match.")
    if _identity(path) != _identity(repo) or git(path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False) != record.get("branch"):
        raise FactoryError("Task repository or branch does not match its ownership record.")
    if git(path, "status", "--porcelain", "--untracked-files=all", "--ignored"):
        raise FactoryError("Task has tracked, untracked or ignored files; preserve them before cleanup.")
    if not merged_into or merged_into.startswith("-"):
        raise FactoryError("An explicit merged-into revision is required.")
    target = git(repo, "rev-parse", "--verify", merged_into + "^{commit}")
    head = git(path, "rev-parse", "HEAD")
    if git(repo, "merge-base", head, target) != head:
        raise FactoryError("Task commits are not contained in the specified accepted revision.")
    git(repo, "worktree", "unlock", str(path))
    try:
        git(repo, "worktree", "remove", str(path))
    except FactoryError:
        git(repo, "worktree", "lock", "--reason", "factory cleanup failed; preserve ownership", str(path))
        raise
    state.unlink()
    return {"removed": str(path), "branch_retained": record["branch"], "accepted_commit": target}
