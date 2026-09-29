"""A read-only overview; unavailable state is explicit, never zero work."""
from pathlib import Path

from . import git
from .client import Client


COUNTS = ('agent_ready', 'agent_coding', 'review', 'blocked')


def report(root: Path, client: Client) -> dict:
    root = git.factory_root(root)
    projects = client.projects()
    managed = [p for p in projects if p.get('attributes', {}).get('repository_path')]
    output = []
    for entity in managed:
        path = entity['attributes']['repository_path']
        row = {'id': entity['id'], 'name': entity.get('name'), 'repository_path': path,
               'git': None, 'boards': None, 'errors': []}
        duplicate = sum(p['attributes']['repository_path'] == path for p in managed) > 1
        try:
            if duplicate:
                raise git.FactoryError('Multiple projects assign this repository_path.')
            metadata = git.module(root, path)
            row['git'] = {'pinned_commit': metadata['pinned_commit'], 'initialized': None,
                          'head': None, 'dirty': None, 'detached': None, 'worktrees': None}
            info = git.project(root, path)
            row['git'] = {'pinned_commit': info['pinned_commit'], 'initialized': True,
                          'head': info['head'], 'dirty': info['dirty'], 'detached': info['branch'] is None,
                          'branch': info['branch'], 'matches_pin': info['head'] == info['pinned_commit'],
                          'worktrees': git.worktrees(info['path'])}
        except git.FactoryError as exc:
            if row['git'] is not None and 'uninitialized' in str(exc):
                row['git']['initialized'] = False
            row['errors'].append(str(exc))
        except (OSError, ValueError):
            row['errors'].append('Repository metadata unavailable; inspect the project checkout.')
        try:
            boards = client.all('/boards', entity_id=entity['id'])
            row['boards'] = []
            for board in boards:
                board_row = {'id': board['id'], 'title': board['title'], 'counts': None, 'error': None}
                try:
                    if board.get('entity_id') != entity['id']:
                        raise git.FactoryError('Board association mismatch.')
                    tickets = client.all('/tickets', board_id=board['id'])
                    if any(t.get('board_id') != board['id'] for t in tickets):
                        raise git.FactoryError('Ticket association mismatch.')
                    board_row['counts'] = {s: sum(t.get('status') == s for t in tickets) for s in COUNTS}
                except git.FactoryError as exc:
                    board_row['error'] = str(exc)
                row['boards'].append(board_row)
        except git.FactoryError as exc:
            row['errors'].append(str(exc))
        output.append(row)
    return {'root': str(root), 'projects': output, 'unmanaged_projects': len(projects) - len(managed)}
