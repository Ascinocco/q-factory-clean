"""scripts/session-sync.sh against real throwaway repositories.

The hook's contract: fast-forward `main` when that is all it takes, otherwise
skip with a one-line reason and change nothing. Never merge, rebase, stash,
reset or discard; always exit 0 so a session is never blocked.
"""
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "session-sync.sh"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def commit(repo, name, text="x"):
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", f"add {name}")
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repos(tmp_path):
    """origin (bare), a checkout under test, and an upstream author checkout."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    author = tmp_path / "author"
    subprocess.run(["git", "clone", "-q", str(origin), str(author)], check=True, capture_output=True)
    for repo in (author,):
        git(repo, "config", "user.name", "Test"); git(repo, "config", "user.email", "t@example.invalid")
    git(author, "checkout", "-q", "-b", "main")
    commit(author, "README.md", "v1")
    git(author, "push", "-q", "origin", "main")
    checkout = tmp_path / "factory"
    subprocess.run(["git", "clone", "-q", str(origin), str(checkout)], check=True, capture_output=True)
    git(checkout, "config", "user.name", "Test"); git(checkout, "config", "user.email", "t@example.invalid")
    return origin, author, checkout


def sync(checkout):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(checkout)}
    result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("\n") == 1 and result.stdout.startswith("q-factory sync: "), result.stdout
    return result.stdout.strip()


def state(checkout):
    """Everything a skip must leave alone: HEAD, the main ref, branch, tree, stash."""
    def maybe(*args):
        result = subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    return {
        "head": maybe("rev-parse", "HEAD"),
        "main": maybe("rev-parse", "--verify", "refs/heads/main"),
        "branch": maybe("symbolic-ref", "--quiet", "HEAD"),
        "status": maybe("status", "--porcelain", "--untracked-files=all"),
        "stash": maybe("stash", "list"),
        "files": sorted(str(p.relative_to(checkout)) for p in checkout.rglob("*") if ".git" not in p.parts),
    }


def upstream_change(author, name="new.txt"):
    sha = commit(author, name, "upstream")
    git(author, "push", "-q", "origin", "main")
    return sha


def test_up_to_date(repos):
    _, _, checkout = repos
    before = git(checkout, "rev-parse", "HEAD")
    assert "up to date" in sync(checkout)
    assert git(checkout, "rev-parse", "HEAD") == before


def test_fast_forwards_main(repos):
    _, author, checkout = repos
    upstream = upstream_change(author)
    out = sync(checkout)
    assert "fast-forwarded main by 1 commit" in out
    assert git(checkout, "rev-parse", "HEAD") == upstream
    assert (checkout / "new.txt").read_text() == "upstream"


def test_untracked_files_do_not_block_and_are_kept(repos):
    _, author, checkout = repos
    upstream = upstream_change(author)
    (checkout / "scratch.txt").write_text("mine")
    assert "fast-forwarded" in sync(checkout)
    assert git(checkout, "rev-parse", "HEAD") == upstream
    assert (checkout / "scratch.txt").read_text() == "mine"


def test_untracked_file_in_the_way_is_skipped_not_overwritten(repos):
    _, author, checkout = repos
    before = git(checkout, "rev-parse", "HEAD")
    upstream_change(author, "clash.txt")
    (checkout / "clash.txt").write_text("mine")
    snapshot = state(checkout)
    out = sync(checkout)
    assert "fast-forward refused" in out and "untracked working tree files" in out  # git's own reason
    assert state(checkout) == snapshot
    assert git(checkout, "rev-parse", "HEAD") == before
    assert (checkout / "clash.txt").read_text() == "mine"


def test_uncommitted_tracked_change_is_skipped(repos):
    _, author, checkout = repos
    before = git(checkout, "rev-parse", "HEAD")
    upstream_change(author)
    (checkout / "README.md").write_text("local edit")
    snapshot = state(checkout)
    assert "uncommitted changes" in sync(checkout)
    assert state(checkout) == snapshot
    assert git(checkout, "rev-parse", "HEAD") == before
    assert (checkout / "README.md").read_text() == "local edit"


def test_other_branch_is_skipped(repos):
    _, author, checkout = repos
    git(checkout, "checkout", "-q", "-b", "task/x")
    upstream_change(author)
    snapshot = state(checkout)
    assert "on task/x, not main" in sync(checkout)
    assert state(checkout) == snapshot  # HEAD, refs/heads/main and the tree did not move
    assert git(checkout, "symbolic-ref", "--short", "HEAD") == "task/x"


def test_detached_head_is_skipped(repos):
    _, author, checkout = repos
    git(checkout, "checkout", "-q", "--detach")
    upstream_change(author)
    snapshot = state(checkout)
    assert "detached HEAD" in sync(checkout)
    assert state(checkout) == snapshot and snapshot["branch"] is None


def test_local_commits_are_skipped(repos):
    _, _, checkout = repos
    local = commit(checkout, "local.txt")
    snapshot = state(checkout)
    assert "local commits not on origin" in sync(checkout)
    assert state(checkout) == snapshot
    assert git(checkout, "rev-parse", "HEAD") == local


def test_diverged_is_skipped(repos):
    _, author, checkout = repos
    local = commit(checkout, "local.txt")
    upstream_change(author)
    snapshot = state(checkout)
    assert "diverged" in sync(checkout)
    assert state(checkout) == snapshot
    assert git(checkout, "rev-parse", "HEAD") == local


def test_offline_is_skipped(repos, tmp_path):
    _, _, checkout = repos
    git(checkout, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    before = git(checkout, "rev-parse", "HEAD")
    snapshot = state(checkout)
    out = sync(checkout)
    assert "could not fetch origin" in out and "missing.git" in out  # git's reason
    assert state(checkout) == snapshot
    assert git(checkout, "rev-parse", "HEAD") == before


def test_not_a_git_checkout_is_skipped(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "notes.txt").write_text("kept")
    before = sorted(p.name for p in plain.iterdir())
    assert "not a git checkout" in sync(plain)
    assert sorted(p.name for p in plain.iterdir()) == before == ["notes.txt"]
    assert (plain / "notes.txt").read_text() == "kept"


def test_fetch_error_line_never_carries_url_credentials(repos, tmp_path):
    _, _, checkout = repos
    git(checkout, "remote", "set-url", "origin", "https://user:s3cret-value@127.0.0.1:9/none.git")
    out = sync(checkout)
    assert "could not fetch origin" in out and "s3cret-value" not in out


def test_project_submodules_are_not_moved_even_with_recursion_configured(tmp_path):
    """The pin moves on origin; the fast-forward must not touch the submodule checkout."""
    allow = ["-c", "protocol.file.allow=always"]
    project = tmp_path / "project"
    subprocess.run(["git", "init", "-q", "-b", "main", str(project)], check=True)
    git(project, "config", "user.name", "Test"); git(project, "config", "user.email", "t@example.invalid")
    pin_one = commit(project, "app.txt", "v1")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    author = tmp_path / "author"
    subprocess.run(["git", "clone", "-q", str(origin), str(author)], check=True, capture_output=True)
    git(author, "config", "user.name", "Test"); git(author, "config", "user.email", "t@example.invalid")
    git(author, "checkout", "-q", "-b", "main")
    git(author, *allow, "submodule", "add", "-q", str(project), "projects/p")
    git(author, "commit", "-q", "-m", "pin p")
    git(author, "push", "-q", "origin", "main")
    checkout = tmp_path / "factory"
    subprocess.run(["git", *allow, "clone", "-q", "--recurse-submodules", str(origin), str(checkout)],
                   check=True, capture_output=True)
    git(checkout, "config", "submodule.recurse", "true")
    git(checkout, "config", "protocol.file.allow", "always")
    # Upstream moves the pin.
    pin_two = commit(project, "app.txt", "v2")
    git(author / "projects/p", "fetch", "-q", "origin")
    git(author / "projects/p", "checkout", "-q", pin_two)
    git(author, "commit", "-q", "-am", "move pin")
    git(author, "push", "-q", "origin", "main")
    assert "fast-forwarded main by 1 commit" in sync(checkout)
    assert git(checkout, "ls-tree", "HEAD", "projects/p").split()[2] == pin_two  # the recorded pin moved
    assert git(checkout / "projects/p", "rev-parse", "HEAD") == pin_one          # the checkout did not
    assert (checkout / "projects/p/app.txt").read_text() == "v1"


def test_the_hook_is_registered_for_session_start():
    import json
    settings = json.loads((SCRIPT.parent.parent / ".claude" / "settings.json").read_text())
    entry = settings["hooks"]["SessionStart"][0]
    assert "startup" in entry["matcher"]
    command = entry["hooks"][0]["command"]
    assert "scripts/session-sync.sh" in command and "$CLAUDE_PROJECT_DIR" in command
    assert os.access(SCRIPT, os.X_OK)
