"""Public API mock plus disposable real submodules for the factory CLI."""
import json
from pathlib import Path
import subprocess

import httpx
import pytest

from q_factory.client import Client
from q_factory.git import FactoryError
from q_factory.status import report
from q_factory.__main__ import execute, parser, main


PROJECT = {'id': 'p1', 'name': 'App', 'attributes': {'repository_path': 'projects/app'}}
BOARD = {'id': 'b1', 'entity_id': 'p1', 'title': 'Delivery'}
TICKET = '12345678-1234-1234-1234-123456789abc'
# An initiative with its own entity and board, whose tickets live in App's repository.
INITIATIVE_BOARD = {'id': 'art', 'entity_id': 'initiative', 'title': 'Initiative'}
# Initiative-style: a project entity with no repository_path. Another managed project owns its own repo.
INITIATIVE = {'id': 'initiative', 'name': 'Initiative', 'attributes': {}}
OTHER_PROJECT = {'id': 'p2', 'name': 'Core', 'attributes': {'repository_path': 'projects/core'}}
OTHER_BOARD = {'id': 'core', 'entity_id': 'p2', 'title': 'Core development'}


def api(projects=None, boards=None, tickets=None, fail=None, ticket_board='b1'):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.method == 'GET'
        assert request.headers['Authorization'] == 'Bearer private-test-token'
        if request.url.path == fail:
            return httpx.Response(503, text='private-test-token')
        data = {'/entities': projects if projects is not None else [PROJECT],
                '/boards': boards if boards is not None else [BOARD],
                '/tickets': tickets if tickets is not None else [
                    {'id': 't1', 'board_id': 'b1', 'status': 'agent_ready'},
                    {'id': 't2', 'board_id': 'b1', 'status': 'review'}]}
        if request.url.path.startswith('/tickets/'):
            return httpx.Response(200, json={'id': TICKET, 'board_id': ticket_board})
        if request.url.path.startswith('/boards/'):
            # The real detail shape: the entity embedded, no flat entity_id (pinned by the q-core integration test).
            known = {board['id']: {'id': board['id'], 'title': board['title'], 'entity': {'id': board['entity_id'], 'type': 'project'}}
                     for board in data['/boards'] + [INITIATIVE_BOARD]}
            wanted = request.url.path.split('/')[2]
            return httpx.Response(200, json=known[wanted]) if wanted in known else httpx.Response(404, json={})
        rows = data[request.url.path]
        offset = int(request.url.params.get('offset', 0))
        # Force multiple pages, even though the client requests 200.
        return httpx.Response(200, json={'items': rows[offset:offset+1], 'total': len(rows)})
    return Client('http://127.0.0.1:8420', 'private-test-token', transport=httpx.MockTransport(handler)), requests


def run(path, *args):
    return subprocess.run(['git', '-C', str(path), *args], check=True, capture_output=True, text=True).stdout.strip()


FACTORY_TOML = """[q_core]
api_url = "http://127.0.0.1:8420"
[self]
project_id = "00000000-0000-4000-8000-000000000001"
board_id = "00000000-0000-4000-8000-000000000002"
repository = "ascinocco/q-factory-clean"
"""


@pytest.fixture
def workspace(tmp_path):
    root, source = tmp_path / 'factory', tmp_path / 'source'
    for path in (root, source):
        path.mkdir()
        run(path, 'init')
        run(path, 'config', 'user.name', 'Test')
        run(path, 'config', 'user.email', 'test@example.invalid')
    (source / 'README.md').write_text('app')
    run(source, 'add', '.')
    run(source, 'commit', '-m', 'Initial')
    (root / 'projects').mkdir()
    (root / 'projects/README.md').write_text('Factory projects')
    (root / 'CLAUDE.md').write_text('Factory')
    (root / 'q-factory.toml').write_text(FACTORY_TOML)
    run(root, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(source), 'projects/app')
    run(root, 'add', '.')
    run(root, 'commit', '-m', 'Factory')
    return root


def test_status_reads_multiple_pages_without_changes(workspace):
    client, requests = api()
    before = run(workspace, 'status', '--porcelain')
    result = report(workspace, client)['projects'][0]
    assert result['git']['initialized'] is True
    assert result['git']['matches_pin'] is True
    assert result['git']['dirty'] is False
    assert result['boards'][0]['title'] == 'Delivery'
    assert result['boards'][0]['counts'] == {'agent_ready': 1, 'agent_coding': 0, 'review': 1, 'blocked': 0}
    assert any(r.url.params.get('offset') == '1' for r in requests)
    assert run(workspace, 'status', '--porcelain') == before
    assert result['git']['worktrees'][0]['worktree'] == str(workspace / 'projects/app')
    assert 'url' not in result['git']


def test_status_dirty_detached_and_pin_difference(workspace):
    repo = workspace / 'projects/app'
    run(repo, 'config', 'user.name', 'Test')
    run(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'new').write_text('new')
    run(repo, 'add', '.')
    run(repo, 'commit', '-m', 'Next')
    run(repo, 'checkout', '--detach')
    (repo / 'dirty').write_text('local')
    row = report(workspace, api()[0])['projects'][0]
    assert row['git']['dirty'] is True
    assert row['git']['detached'] is True
    assert row['git']['matches_pin'] is False


@pytest.mark.parametrize('failure', ['missing', 'mismatched'])
def test_bad_checkout_retains_board_and_pin(workspace, failure):
    if failure == 'missing':
        run(workspace, 'submodule', 'deinit', '-f', 'projects/app')
    else:
        run(workspace / 'projects/app', 'remote', 'set-url', 'origin', 'https://secret@example.invalid/other')
    row = report(workspace, api()[0])['projects'][0]
    assert row['errors']
    assert row['git']['pinned_commit']
    assert row['git']['head'] is None
    assert row['boards'][0]['counts']['review'] == 1
    assert 'secret' not in json.dumps(row)


def test_api_failure_is_unknown_not_zero(workspace):
    row = report(workspace, api(fail='/tickets')[0])['projects'][0]
    assert row['boards'][0]['counts'] is None
    assert '503' in row['boards'][0]['error']
    row = report(workspace, api(fail='/boards')[0])['projects'][0]
    assert row['boards'] is None
    assert row['git']['initialized'] is True
    with pytest.raises(FactoryError, match='503'):
        report(workspace, api(fail='/entities')[0])


def test_project_board_and_duplicate_path_resolution():
    client, _ = api(boards=[BOARD, {**BOARD, 'id': 'b2'}])
    with pytest.raises(FactoryError, match='explicit'):
        client.resolve('App')
    assert client.resolve('p1', 'b2')[1]['id'] == 'b2'
    with pytest.raises(FactoryError, match='associated'):
        client.resolve('p1', 'wrong')
    client, _ = api(projects=[PROJECT, {**PROJECT, 'id': 'p2'}])
    with pytest.raises(FactoryError, match='unique exact name'):
        client.resolve('App')
    with pytest.raises(FactoryError, match='Multiple projects'):
        client.resolve('p1')


def test_partial_or_repeated_pagination_refused():
    for second in ([], [{'id': 'same'}]):
        def handler(request):
            rows = [{'id': 'same'}] if request.url.params['offset'] == '0' else second
            return httpx.Response(200, json={'items': rows, 'total': 2})
        client = Client('http://localhost:8420', 'x', transport=httpx.MockTransport(handler))
        with pytest.raises(FactoryError, match='pagination'):
            client.projects()


@pytest.mark.parametrize('url', ['https://example.com:8420', 'http://127.0.0.1',
    'http://user:secret@127.0.0.1:8420', 'http://127.0.0.1:8420/path', 'file:///tmp/x'])
def test_nonlocal_and_credential_urls_refused(url):
    with pytest.raises(FactoryError, match='loopback'):
        Client(url, 'x')


def test_cli_start_checks_ticket_before_git_mutation(workspace, monkeypatch):
    args = parser().parse_args(['--root', str(workspace), 'worktree', 'start', '--project', 'p1',
                               '--task', 'task', '--base', 'HEAD', '--owner', 'worker', '--ticket', TICKET])
    client, _ = api()
    from q_factory import git
    called = []
    monkeypatch.setattr(git, 'start', lambda *values: called.append(values) or {'started': True})
    assert execute(args, client) == {'started': True}
    assert called[0][1:] == ('projects/app', 'task', 'HEAD', 'worker', TICKET)
    called.clear()
    original = client.get
    monkeypatch.setattr(client, 'get', lambda path, **params: {'id': TICKET, 'board_id': 'other'}
                        if path.startswith('/tickets/') else original(path, **params))
    with pytest.raises(FactoryError, match='does not belong'):
        execute(args, client)
    assert called == []


def start_args(workspace, *extra):
    return parser().parse_args(['--root', str(workspace), 'worktree', 'start', '--project', 'p1', '--task', 'task',
                                '--base', 'HEAD', '--owner', 'worker', '--ticket', TICKET, *extra])


def test_cli_start_takes_a_ticket_from_another_entitys_board(workspace, monkeypatch):
    # The project's own boards are ambiguous here: --ticket-board doesn't need one chosen.
    # The initiative is itself a registered project entity, just without a repository_path.
    client, requests = api(projects=[PROJECT, INITIATIVE, OTHER_PROJECT],
                           boards=[BOARD, {**BOARD, 'id': 'b2'}], ticket_board='art')
    from q_factory import git
    called = []
    monkeypatch.setattr(git, 'start', lambda *values, **options: called.append((values, options)) or {'started': True})
    assert execute(start_args(workspace, '--ticket-board', 'art'), client) == {'started': True}
    assert called == [((workspace, 'projects/app', 'task', 'HEAD', 'worker', TICKET),
                       {'ticket_board': {'project_id': 'p1', 'ticket_board_id': 'art', 'ticket_board_entity_id': 'initiative'}})]
    assert '/boards/art' in [request.url.path for request in requests]


@pytest.mark.parametrize('extra, ticket_board, message', [
    (['--ticket-board', 'art'], 'b1', 'does not belong to the selected board'),  # the ticket isn't on the named board
    (['--ticket-board', 'art', '--board', 'b1'], 'art', 'not both'),
    (['--ticket-board', 'b1'], 'b1', "project's own board"),
    (['--ticket-board', 'missing'], 'art', 'HTTP 404'),
    # Another managed project's board would record this worktree under that project's ticket.
    (['--ticket-board', 'core'], 'core', 'another managed project'),
])
def test_cli_ticket_board_refusals_happen_before_git(workspace, monkeypatch, extra, ticket_board, message):
    client, _ = api(projects=[PROJECT, INITIATIVE, OTHER_PROJECT], boards=[BOARD, OTHER_BOARD], ticket_board=ticket_board)
    from q_factory import git
    called = []
    monkeypatch.setattr(git, 'start', lambda *values, **options: called.append(values))
    with pytest.raises(FactoryError, match=message):
        execute(start_args(workspace, *extra), client)
    assert called == []


def test_cli_error_does_not_print_settings_or_credentials(workspace, monkeypatch, capsys):
    monkeypatch.delenv('Q_CORE_API_TOKEN', raising=False)
    assert main(['--root', str(workspace), 'status']) == 1
    output = capsys.readouterr()
    assert output.out == ''
    assert json.loads(output.err)['error'].startswith('Set Q_CORE_API_TOKEN')


def test_status_continues_after_duplicate_registry_and_board_failure(workspace):
    other = {'id': 'p2', 'name': 'Duplicate', 'attributes': {'repository_path': 'projects/app'}}
    rows = report(workspace, api(projects=[PROJECT, other])[0])['projects']
    assert len(rows) == 2
    assert all(row['git'] is None and row['errors'] for row in rows)


def test_redirect_is_not_followed_and_error_is_sanitized():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={'Location': 'https://secret@example.invalid/leak'})
    client = Client('http://127.0.0.1:8420', 'private', transport=httpx.MockTransport(handler))
    with pytest.raises(FactoryError, match='HTTP 302') as failure:
        client.projects()
    assert len(requests) == 1
    assert 'secret' not in str(failure.value)


def test_list_and_finish_delegate_selected_repository(workspace, monkeypatch):
    from q_factory import git
    common = ['--root', str(workspace), 'worktree']
    client, _ = api()
    listed = execute(parser().parse_args(common + ['list', '--project', 'App']), client)
    assert listed['project_id'] == 'p1'
    calls = []
    monkeypatch.setattr(git, 'finish', lambda *args: calls.append(args) or {'removed': True})
    args = parser().parse_args(common + ['finish', '--project', 'App', '--task', 'feature',
                              '--owner', 'worker', '--merged-into', 'origin/main', '--inactive'])
    assert execute(args, client) == {'removed': True}
    assert calls == [(workspace, 'projects/app', 'feature', 'worker', 'origin/main', True)]


def test_status_reports_active_task_worktree(workspace):
    task = workspace / '.worktrees/app/feature'
    task.parent.mkdir(parents=True)
    run(workspace / 'projects/app', 'worktree', 'add', '-b', 'task/feature', str(task), 'HEAD')
    row = report(workspace, api()[0])['projects'][0]
    assert any(w['worktree'] == str(task) and w.get('branch') == 'refs/heads/task/feature'
               for w in row['git']['worktrees'])


def test_cli_success_outputs_json(workspace, monkeypatch, capsys):
    import q_factory.__main__ as cli
    client, _ = api()
    monkeypatch.setenv('Q_CORE_API_TOKEN', 'private-test-token')
    seen = {}
    monkeypatch.setattr(cli, 'Client', lambda url, token, tailnet=None: seen.update(url=url, token=token) or client)
    assert main(['--root', str(workspace), 'status']) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    assert json.loads(captured.out)['projects'][0]['id'] == 'p1'
    assert 'private-test-token' not in captured.out
    # The origin and token come from q-factory.toml and the environment.
    assert seen == {'url': 'http://127.0.0.1:8420', 'token': 'private-test-token'}


def test_cli_api_url_overrides_the_configured_origin(workspace, monkeypatch, capsys):
    import q_factory.__main__ as cli
    client, _ = api()
    monkeypatch.setenv('Q_CORE_API_TOKEN', 'private-test-token')
    seen = {}
    monkeypatch.setattr(cli, 'Client', lambda url, token, tailnet=None: seen.update(url=url) or client)
    assert main(['--root', str(workspace), '--api-url', 'http://127.0.0.1:9999', 'status']) == 0
    capsys.readouterr()
    assert seen == {'url': 'http://127.0.0.1:9999'}
