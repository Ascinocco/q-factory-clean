"""Real disposable repositories exercise ownership and Git isolation."""
import json
from pathlib import Path

import pytest

from q_factory.git import FactoryError, factory_root, finish, git, module, project, start, worktrees


def init_repo(path):
    path.mkdir(parents=True)
    git(path, "init", "-b", "main")
    git(path, "config", "user.name", "Factory test")
    git(path, "config", "user.email", "factory@example.invalid")
    (path / "README.md").write_text("fixture\n")
    git(path, "add", ".")
    git(path, "commit", "-m", "Initial")
    return path


@pytest.fixture
def workspace(tmp_path):
    origin = init_repo(tmp_path / "origin")
    root = init_repo(tmp_path / "factory")
    (root / "CLAUDE.md").write_text("Factory fixture\n")
    (root / "projects").mkdir()
    (root / "projects/README.md").write_text("Managed projects\n")
    (root / ".gitignore").write_text("/.worktrees/\n")
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", str(origin), "projects/demo")
    git(root, "add", ".")
    git(root, "commit", "-m", "Register")
    repo = root / "projects/demo"
    git(repo, "config", "user.name", "Factory test")
    git(repo, "config", "user.email", "factory@example.invalid")
    git(repo, "checkout", "--detach")
    return root, repo, origin


def test_task_start_resume_and_finish_preserve_detached_checkout(workspace):
    root, repo, _ = workspace
    head = git(repo, "rev-parse", "HEAD")
    record = start(root, "projects/demo", "first", head, "worker", "ticket-1")
    path = Path(record["path"])
    assert git(path, "branch", "--show-current") == "task/first"
    assert git(repo, "rev-parse", "HEAD") == head
    assert project(root, "projects/demo")["branch"] is None
    assert start(root, "projects/demo", "first", head, "worker", "ticket-1")["resumed"]
    assert len(worktrees(repo)) == 2
    assert Path(worktrees(repo)[0]["worktree"]).resolve() == repo.resolve()
    finish(root, "projects/demo", "first", "worker", head, True)
    assert not path.exists()
    assert len(worktrees(repo)) == 1


LINK = {"project_id": "p1", "ticket_board_id": "art", "ticket_board_entity_id": "initiative"}


def test_single_board_record_is_unchanged(workspace):
    root, repo, _ = workspace
    record = start(root, "projects/demo", "first", "HEAD", "worker", "t")
    stored = json.loads(Path(record["path"] + ".json").read_text())
    assert set(stored) == {"repository_path", "task", "branch", "base_commit", "owner", "ticket", "path"}


def test_ticket_board_is_recorded_and_bound_on_resume(workspace):
    root, repo, _ = workspace
    head = git(repo, "rev-parse", "HEAD")
    record = start(root, "projects/demo", "first", head, "worker", "t", ticket_board=LINK)
    stored = json.loads(Path(record["path"] + ".json").read_text())
    assert {key: stored[key] for key in LINK} == LINK and stored["repository_path"] == "projects/demo"
    assert start(root, "projects/demo", "first", head, "worker", "t", ticket_board=LINK)["resumed"]
    for other in (None, {**LINK, "ticket_board_id": "elsewhere"}):
        with pytest.raises(FactoryError, match="different ownership"):
            start(root, "projects/demo", "first", head, "worker", "t", ticket_board=other)
    finish(root, "projects/demo", "first", "worker", head, True)
    assert not Path(record["path"]).exists()


@pytest.mark.parametrize("change", ["owner", "ticket", "base"])
def test_resume_refuses_changed_ownership_or_base(workspace, change):
    root, repo, _ = workspace
    original = git(repo, "rev-parse", "HEAD")
    start(root, "projects/demo", "first", original, "worker", "ticket-1")
    args = dict(base=original, owner="worker", ticket="ticket-1")
    if change == "base":
        (repo / "next").write_text("new")
        git(repo, "add", "next")
        git(repo, "commit", "-m", "New base")
        args[change] = "HEAD"
    else:
        args[change] = "different"
    with pytest.raises(FactoryError, match="different ownership"):
        start(root, "projects/demo", "first", **args)


def test_dirty_submodule_and_foreign_remote_are_refused(workspace):
    root, repo, _ = workspace
    (repo / "untracked").write_text("preserve")
    with pytest.raises(FactoryError, match="local changes"):
        start(root, "projects/demo", "first", "HEAD", "worker", "t")
    git(repo, "remote", "set-url", "origin", "/different/repository")
    with pytest.raises(FactoryError, match="origin differs"):
        project(root, "projects/demo")
    assert (repo / "untracked").read_text() == "preserve"


def test_cleanup_refuses_active_foreign_dirty_and_unmerged_work(workspace):
    root, repo, _ = workspace
    record = start(root, "projects/demo", "first", "HEAD", "worker", "t")
    path = Path(record["path"])
    with pytest.raises(FactoryError, match="inactive"):
        finish(root, "projects/demo", "first", "worker", "HEAD", False)
    with pytest.raises(FactoryError, match="ownership"):
        finish(root, "projects/demo", "first", "other", "HEAD", True)
    (path / "untracked").write_text("preserve")
    with pytest.raises(FactoryError, match="untracked"):
        finish(root, "projects/demo", "first", "worker", "HEAD", True)
    git(path, "add", "untracked")
    git(path, "commit", "-m", "Work")
    with pytest.raises(FactoryError, match="not contained"):
        finish(root, "projects/demo", "first", "worker", "HEAD", True)
    assert path.is_dir()
    assert any(r.get("locked") for r in worktrees(repo))
    finish(root, "projects/demo", "first", "worker", "task/first", True)


def test_ignored_local_files_are_not_deleted(workspace):
    root, repo, _ = workspace
    (repo / ".gitignore").write_text("secrets.local\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-m", "Ignore local")
    record = start(root, "projects/demo", "first", "HEAD", "worker", "t")
    (Path(record["path"]) / "secrets.local").write_text("fixture")
    with pytest.raises(FactoryError, match="ignored"):
        finish(root, "projects/demo", "first", "worker", "HEAD", True)


def test_same_task_name_is_isolated_across_projects(workspace):
    root, _, origin = workspace
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", str(origin), "projects/second")
    one = start(root, "projects/demo", "first", "HEAD", "one", "t1")
    two = start(root, "projects/second", "first", "HEAD", "two", "t2")
    assert one["path"] != two["path"]
    assert Path(one["path"]).is_dir() and Path(two["path"]).is_dir()


def test_explicit_linked_factory_root_does_not_substitute_main_checkout(workspace, tmp_path):
    root, _, _ = workspace
    linked = tmp_path / "linked"
    git(root, "worktree", "add", "--detach", str(linked), "HEAD")
    assert factory_root(linked) == linked
    assert module(linked, "projects/demo")["path"] == linked / "projects/demo"
    with pytest.raises(FactoryError, match="uninitialized"):
        project(linked, "projects/demo")


def test_symlink_worktree_root_is_refused(workspace, tmp_path):
    root, _, _ = workspace
    (root / ".worktrees").symlink_to(tmp_path / "outside")
    with pytest.raises(FactoryError, match="symlinks"):
        start(root, "projects/demo", "first", "HEAD", "worker", "t")


@pytest.mark.parametrize("invalid", ["../escape", "projects/../escape", "/tmp/demo", "projects/demo/sub", "projects/Demo"])
def test_noncanonical_repository_paths_are_refused(workspace, invalid):
    with pytest.raises(FactoryError, match="managed repository path"):
        project(workspace[0], invalid)


def test_relative_remote_uses_actual_submodule_section(workspace):
    root, _, origin = workspace
    git(root, "config", "--file", ".gitmodules", "--rename-section", "submodule.projects/demo", "submodule.custom-name")
    git(root, "config", "--file", ".gitmodules", "submodule.custom-name.url", "../origin")
    git(root, "config", "submodule.custom-name.url", str(origin))
    assert project(root, "projects/demo")["head"] == git(origin, "rev-parse", "HEAD")


def test_git_timeouts_are_sanitized_and_optional_index_writes_disabled(tmp_path, monkeypatch):
    import subprocess
    def timeout(args, **kwargs):
        assert kwargs['env']['GIT_OPTIONAL_LOCKS'] == '0'
        raise subprocess.TimeoutExpired(args, 60, stderr='credential-shaped fixture')
    monkeypatch.setattr(subprocess, 'run', timeout)
    with pytest.raises(FactoryError, match='timed out') as error:
        git(tmp_path, 'status')
    assert 'credential-shaped' not in str(error.value)
