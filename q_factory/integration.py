"""Stage one verified project revision without publishing or accepting it."""
from pathlib import Path
import re
import tempfile

from .git import FactoryError, factory_root, git, project


COMMIT = re.compile(r'[0-9a-f]{40}\Z')


def _head_pin(root: Path, repository_path: str) -> str:
    entry = git(root, 'ls-tree', 'HEAD', '--', repository_path)
    if not entry.startswith('160000 commit '):
        raise FactoryError('The project must already be recorded as a submodule in the factory HEAD.')
    return entry.split()[2]


def _guard(root: Path, repository_path: str, target: str, expected_old: str) -> dict:
    if not git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False):
        raise FactoryError('Create a named q-factory branch before staging a project pointer.')
    info = project(root, repository_path)
    if info['dirty']:
        raise FactoryError('The project checkout has local changes; preserve them before updating its pointer.')
    head_pin = _head_pin(root, repository_path)
    if head_pin not in {expected_old, target}:
        raise FactoryError('Recorded project revision changed; inspect ancestry and use its current expected-old commit.')
    if info['pinned_commit'] not in {head_pin, target}:
        raise FactoryError('A different project pointer is already staged; do not overwrite it.')
    if info['head'] not in {head_pin, target}:
        raise FactoryError('The project checkout differs from the recorded or requested revision; preserve that work first.')
    # Exclude only the selected gitlink. All other staged, unstaged and untracked
    # changes belong to a different parent change and must remain untouched.
    if git(root, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none',
           '--', '.', ':(exclude)' + repository_path):
        raise FactoryError('The q-factory checkout has unrelated changes; use a clean pointer-update branch/worktree.')
    info['head_pin'] = head_pin
    return info


def pin(root: Path, repository_path: str, target: str, expected_old: str) -> dict:
    """Verify remote availability and ancestry, then checkout and stage one gitlink.

    The caller supplies the reviewed accepted commit. This function verifies Git
    properties; it does not attest review, merge approval, or deployment authority.
    """
    if not COMMIT.fullmatch(target) or not COMMIT.fullmatch(expected_old):
        raise FactoryError('Commit and expected-old must be complete lowercase 40-character commit SHAs.')
    root = factory_root(root)
    before = _guard(root, repository_path, target, expected_old)
    repo = before['path']
    remote = git(repo, 'remote', 'get-url', 'origin')
    with tempfile.TemporaryDirectory(prefix='q-factory-pin-') as temporary:
        verified = Path(temporary)
        git(verified, 'init', '--bare')
        # Fetch into an empty repository, proving the remote can supply this
        # object without relying on objects already cached in the checkout.
        git(verified, 'fetch', '--no-tags', '--', remote, target)
        if git(verified, 'rev-parse', 'FETCH_HEAD^{commit}') != target:
            raise FactoryError('Remote retrieval did not resolve to the exact requested commit.')
        if git(verified, 'merge-base', expected_old, target, check=False) != expected_old:
            raise FactoryError('Requested revision does not descend from expected-old; inspect concurrent changes instead of downgrading.')
        # Network verification can take time; refuse changes made meanwhile.
        after = _guard(root, repository_path, target, expected_old)
        if any(before[key] != after[key] for key in ('head_pin', 'head', 'pinned_commit')):
            raise FactoryError('Project state changed during remote verification; inspect it before retrying.')
        if after['head_pin'] == target and after['pinned_commit'] == target and after['head'] == target:
            return {'repository_path': repository_path, 'commit': target,
                    'state': 'already_recorded', 'remote_verified': True}
        already_staged = after['pinned_commit'] == target and after['head'] == target
        if not already_staged:
            # Import only objects from the just-verified disposable repository.
            # Checkout or add failures leave discoverable state; a repeat with
            # the same expected-old/target can resume without force or reset.
            git(repo, 'fetch', '--no-tags', '--', str(verified), target)
            git(repo, 'checkout', '--no-overwrite-ignore', '--detach', target)
            git(root, 'add', '--', repository_path)
        return {'repository_path': repository_path, 'previous_commit': after['head_pin'],
                'commit': target, 'state': 'already_staged' if already_staged else 'staged',
                'remote_verified': True}
