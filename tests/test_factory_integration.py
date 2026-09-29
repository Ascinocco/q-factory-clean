"""Pointer updates against disposable real remotes, including clean-clone proof."""
from pathlib import Path
import subprocess

import pytest

from q_factory.git import FactoryError
from q_factory.integration import pin


def run(path, *args):
    return subprocess.run(['git', '-C', str(path), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def commit(path, name):
    (path / name).write_text(name)
    run(path, 'add', name)
    run(path, 'commit', '-m', name)
    return run(path, 'rev-parse', 'HEAD')


@pytest.fixture
def factory(tmp_path):
    root, source, remote = [tmp_path / name for name in ('factory', 'source', 'remote.git')]
    remote.mkdir()
    run(remote, 'init', '--bare')
    for path in (root, source):
        path.mkdir()
        run(path, 'init')
        run(path, 'config', 'user.name', 'Test')
        run(path, 'config', 'user.email', 'test@example.invalid')
    old = commit(source, 'first')
    run(source, 'remote', 'add', 'origin', str(remote))
    run(source, 'push', '-u', 'origin', 'HEAD')
    (root / 'projects').mkdir()
    (root / 'projects/README.md').write_text('projects')
    (root / 'CLAUDE.md').write_text('factory')
    run(root, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(remote), 'projects/app')
    run(root, 'add', '.')
    run(root, 'commit', '-m', 'factory')
    target = commit(source, 'second')
    run(source, 'push', 'origin', 'HEAD')
    return root, source, old, target


def test_pin_stage_repeat_and_clean_clone(factory, tmp_path):
    root, source, old, target = factory
    assert pin(root, 'projects/app', target, old)['state'] == 'staged'
    assert run(root, 'diff', '--cached', '--name-only') == 'projects/app'
    assert run(root / 'projects/app', 'rev-parse', 'HEAD') == target
    assert pin(root, 'projects/app', target, old)['state'] == 'already_staged'
    run(root, 'commit', '-m', 'accepted pointer')
    assert pin(root, 'projects/app', target, old)['state'] == 'already_recorded'
    clone = tmp_path / 'clone'
    run(tmp_path, 'clone', '--no-local', str(root), str(clone))
    run(clone, '-c', 'protocol.file.allow=always', 'submodule', 'update', '--init', 'projects/app')
    assert run(clone / 'projects/app', 'rev-parse', 'HEAD') == target


def test_unpublished_commit_refused_without_checkout_or_index_mutation(factory):
    root, source, old, _ = factory
    unpublished = commit(source, 'unpublished')
    with pytest.raises(FactoryError, match='fetch failed'):
        pin(root, 'projects/app', unpublished, old)
    assert run(root, 'status', '--porcelain') == ''
    assert run(root / 'projects/app', 'rev-parse', 'HEAD') == old


def test_expected_old_conflict_and_downgrade(factory):
    root, source, old, target = factory
    with pytest.raises(FactoryError, match='Recorded project revision changed'):
        pin(root, 'projects/app', target, 'a' * 40)
    pin(root, 'projects/app', target, old)
    run(root, 'commit', '-m', 'accepted')
    with pytest.raises(FactoryError, match='does not descend'):
        pin(root, 'projects/app', old, target)
    assert run(root, 'status', '--porcelain') == ''
    assert run(root / 'projects/app', 'rev-parse', 'HEAD') == target


@pytest.mark.parametrize('change', ['dirty-project', 'staged-parent', 'unstaged-parent', 'untracked-parent', 'detached-parent'])
def test_existing_work_preserved(factory, change):
    root, source, old, target = factory
    if change == 'dirty-project':
        (root / 'projects/app/first').write_text('local')
    elif change == 'detached-parent':
        run(root, 'checkout', '--detach')
    elif change == 'untracked-parent':
        (root / 'local').write_text('local')
    else:
        (root / 'CLAUDE.md').write_text('local')
        if change == 'staged-parent':
            run(root, 'add', 'CLAUDE.md')
    before = run(root, 'status', '--porcelain')
    with pytest.raises(FactoryError):
        pin(root, 'projects/app', target, old)
    assert run(root, 'status', '--porcelain') == before
    assert run(root / 'projects/app', 'rev-parse', 'HEAD') == old


def test_resume_after_checkout_before_stage(factory):
    root, source, old, target = factory
    repo = root / 'projects/app'
    run(repo, 'fetch', 'origin')
    run(repo, 'checkout', '--detach', target)
    assert pin(root, 'projects/app', target, old)['state'] == 'staged'
    assert run(root, 'diff', '--cached', '--name-only') == 'projects/app'


def test_unrelated_project_checkout_head_refused(factory):
    root, source, old, target = factory
    other = commit(source, 'third')
    run(source, 'push', 'origin', 'HEAD')
    repo = root / 'projects/app'
    run(repo, 'fetch', 'origin')
    run(repo, 'checkout', '--detach', other)
    with pytest.raises(FactoryError, match='checkout differs'):
        pin(root, 'projects/app', target, old)
    assert run(repo, 'rev-parse', 'HEAD') == other


def test_cli_pin_resolves_before_mutating(factory, monkeypatch):
    from q_factory import __main__ as cli
    root, source, old, target = factory
    calls = []
    class Client:
        def resolve(self, selector, board):
            assert selector == 'project-id' and board == 'board-id'
            return {'attributes': {'repository_path': 'projects/app'}}, {'id': 'board-id'}
    monkeypatch.setattr(cli, 'pin', lambda *args: calls.append(args) or {'state': 'staged'})
    args = cli.parser().parse_args(['--root', str(root), 'pin', '--project', 'project-id',
                                   '--board', 'board-id', '--commit', target, '--expected-old', old])
    assert cli.execute(args, Client()) == {'state': 'staged'}
    assert calls == [(root, 'projects/app', target, old)]


def test_ignored_project_file_is_not_overwritten(factory):
    root, source, old, target = factory
    repo = root / 'projects/app'
    exclude = Path(run(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'info/exclude'))
    exclude.write_text(exclude.read_text() + '\nsecond\n')
    (repo / 'second').write_text('local ignored data')
    with pytest.raises(FactoryError, match='checkout failed'):
        pin(root, 'projects/app', target, old)
    assert (repo / 'second').read_text() == 'local ignored data'
    assert run(repo, 'rev-parse', 'HEAD') == old
    assert run(root, 'diff', '--cached', '--name-only') == ''
