import itertools
import json
from pathlib import Path
import subprocess

import pytest

from q_factory import review_runner as r


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


@pytest.fixture
def spec(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.name', 'Fixture')
    git(repo, 'config', 'user.email', 'fixture@example.invalid')
    (repo / 'app.py').write_text('def add(a, b): return a - b\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'base')
    base = git(repo, 'rev-parse', 'HEAD')
    (repo / 'app.py').write_text('def add(a, b): return a + b\n')
    git(repo, 'commit', '-am', 'fix')
    return {'repository': str(repo), 'head': git(repo, 'rev-parse', 'HEAD'), 'base': base,
            'previous_reviewed_head': None, 'files': ['app.py'],
            'context': {'ticket': {'id': 'fixture', 'title': 'Add numbers', 'description': 'Fix sum'},
                        'epic': None, 'acceptance_criteria': ['Adds numbers'], 'prior_findings': []}}


def output(spec, session):
    return {'subtype': 'success', 'is_error': False, 'session_id': session,
            'modelUsage': {'claude-sonnet-4-6': {}, 'claude-haiku-4-5-20251001': {}},
            'structured_output': {'mode': 'incremental' if spec['previous_reviewed_head'] else 'full', 'previous_reviewed_head': spec['previous_reviewed_head'], 'head': spec['head'], 'limitations': ['Static review only'],
                'acceptance': [dict(row, status='met', evidence='Uses addition')
                               for row in r.acceptance_rows(spec['context']['acceptance_criteria'])],
                'lenses': {name: {'status': 'reviewed', 'summary': 'Inspected supplied source', 'findings': []} for name in r.LENSES}}}


def fake_cli(monkeypatch, spec, mutate=lambda value: value):
    real = subprocess.run
    calls = []
    def run(args, **kwargs):
        if args[0] != 'fixture-claude':
            return real(args, **kwargs)
        if args[1:3] == ['auth', 'status']:
            return subprocess.CompletedProcess(args, 0, json.dumps({'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'firstParty'}), '')
        listing = sorted(str(p.relative_to(kwargs['cwd'])) for p in Path(kwargs['cwd']).rglob('*'))
        mcp = json.loads(Path(args[args.index('--mcp-config') + 1]).read_text())
        calls.append((args, dict(kwargs, listing=listing, mcp=mcp)))
        data = mutate(output(spec, args[args.index('--session-id') + 1]))
        return subprocess.CompletedProcess(args, 0, json.dumps(data), '')
    monkeypatch.setattr(subprocess, 'run', run)
    return calls


def test_pair_identical_context_isolated_sessions_and_full_tools(spec, monkeypatch):
    calls = fake_cli(monkeypatch, spec)
    result = r.run_review(spec, executable='fixture-claude', environ={'HOME': '/fixture', 'PATH': '/bin', 'SECRET_OTHER': 'hidden'})
    assert result['status'] == 'candidates_require_lead_validation'
    assert len(calls) == 2
    assert calls[0][1]['input'] == calls[1][1]['input']
    assert calls[0][1]['cwd'] != calls[1][1]['cwd']
    assert len({item['session_id'] for item in result['reviews']}) == 2
    for args, kwargs in calls:
        assert '--tools' not in args and '--allowed-tools' not in args  # the full default toolset
        assert args[args.index('--permission-mode') + 1] == 'bypassPermissions'
        assert '--safe-mode' not in args and '--restricted' not in args  # safe mode switches off MCP
        assert args[args.index('--setting-sources') + 1] == '' and '--strict-mcp-config' in args
        assert '--bare' not in args and '--fallback-model' not in args
        assert 'SECRET_OTHER' not in kwargs['env'] and 'CLAUDE_CODE_SAFE_MODE' not in kwargs['env']
        assert kwargs['listing'] == ['app.py']  # its own snapshot of head
        assert kwargs['mcp'] == {'mcpServers': {}}  # no Jyra unless it was given
        assert not Path(kwargs['cwd']).exists()


def test_jyra_reaches_workers_through_a_private_mcp_config(spec, monkeypatch):
    calls = fake_cli(monkeypatch, spec)
    spec['pull_request'] = 'Owner/repo#12'
    r.run_review(spec, executable='fixture-claude', environ={},
                 jyra={'api_url': 'https://server.tail1234.ts.net/', 'token': 'qc_fixture-secret'})
    for args, kwargs in calls:
        assert kwargs['mcp'] == {'mcpServers': {'q-core': {'type': 'http', 'url': 'https://server.tail1234.ts.net/mcp/',
                                                           'headers': {'Authorization': 'Bearer qc_fixture-secret'}}}}
        assert not any('qc_fixture-secret' in arg for arg in args)  # never in the process list
        assert 'qc_fixture-secret' not in kwargs['input']
        prompt = args[args.index('--system-prompt') + 1]
        assert 'Owner/repo#12' in prompt and 'q-core MCP' in prompt and 'Never write to' in prompt


def test_pull_request_must_name_owner_repo_and_number(spec):
    spec['pull_request'] = 'just-a-number'
    with pytest.raises(r.ReviewError, match='OWNER/REPO#NUMBER'):
        r.freeze(spec)


def test_missing_factory_token_refuses_jyra_access(tmp_path, monkeypatch):
    (tmp_path / 'q-factory.toml').write_text(
        '[q_core]\napi_url = "http://127.0.0.1:8420"\n[self]\n'
        'project_id = "00000000-0000-4000-8000-000000000001"\nboard_id = "00000000-0000-4000-8000-000000000002"\n'
        'repository = "owner/repo"\n')
    for key in ('Q_CORE_API_TOKEN',):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(r.ReviewError, match='Reviewers need Jyra access'):
        r.jyra_access(tmp_path)
    monkeypatch.setenv('Q_CORE_API_TOKEN', 'qc_fixture')
    assert r.jyra_access(tmp_path) == {'api_url': 'http://127.0.0.1:8420', 'token': 'qc_fixture'}


def test_freeze_reads_commits_not_dirty_or_untracked_private_files(spec):
    repo = Path(spec['repository'])
    (repo / 'app.py').write_text('PRIVATE DIRTY CONTENT')
    (repo / '.env').write_text('PRIVATE SECRET')
    _, bundle = r.freeze(spec)
    assert 'PRIVATE' not in bundle
    assert 'a + b' in bundle and 'a - b' in bundle


@pytest.mark.parametrize('path', ['.env', 'data/profile.json', '../app.py', '/etc/passwd', 'private.key'])
def test_private_and_escaping_paths_refused(spec, path):
    spec['files'].append(path)
    with pytest.raises(r.ReviewError):
        r.freeze(spec)


def test_missing_changed_file_and_changed_head_refused(spec):
    spec['files'] = ['other.py']
    with pytest.raises(r.ReviewError, match='Every changed'):
        r.freeze(spec)
    spec['files'] = ['app.py']
    spec['head'] = spec['base']
    with pytest.raises(r.ReviewError, match='HEAD differs'):
        r.freeze(spec)


def test_deleted_file_included_from_base(spec):
    repo = Path(spec['repository'])
    git(repo, 'rm', 'app.py')
    git(repo, 'commit', '-m', 'delete')
    spec['head'] = git(repo, 'rev-parse', 'HEAD')
    data = json.loads(r.freeze(spec)[1])
    assert data['snapshots'][spec['head']]['app.py'] is None
    assert data['snapshots'][spec['base']]['app.py']


def test_incremental_requires_same_base_and_ancestor(spec):
    spec['previous_reviewed_head'] = spec['base']
    with pytest.raises(r.ReviewError, match='base changed'):
        r.freeze(spec)
    spec['previous_reviewed_base'] = spec['base']
    assert 'incremental_diff' in json.loads(r.freeze(spec)[1])
    spec['previous_reviewed_head'] = 'f' * 40
    with pytest.raises(r.ReviewError):
        r.freeze(spec)


def test_large_incremental_bundle_is_not_capped(spec, monkeypatch):
    # q-core#17 round 2: three snapshots of a few ~30 KB files outgrew the old 300,000-byte cap.
    repo = Path(spec['repository'])
    (repo / 'app.py').write_text('# line of source\n' * 30_000)
    git(repo, 'commit', '-am', 'grow')
    spec['previous_reviewed_head'], spec['previous_reviewed_base'] = spec['head'], spec['base']
    (repo / 'app.py').write_text('# line of source\n' * 30_001)
    git(repo, 'commit', '-am', 'grow again')
    spec['head'] = git(repo, 'rev-parse', 'HEAD')
    bundle = r.freeze(spec)[1]
    assert len(bundle.encode()) > 1_000_000
    calls = fake_cli(monkeypatch, spec)
    r.run_review(spec, executable='fixture-claude', environ={})
    assert [kwargs['input'] for _, kwargs in calls] == [bundle, bundle]


def test_context_error_names_allowed_missing_and_unexpected_keys(spec):
    del spec['context']['epic']
    spec['context']['project_conventions'] = 'Use tabs'
    with pytest.raises(r.ReviewError) as caught:
        r.freeze(spec)
    message = str(caught.value)
    assert 'ticket, epic, acceptance_criteria, prior_findings' in message
    assert 'missing epic' in message and 'unexpected project_conventions' in message


def test_missing_jsonschema_refused_before_any_reviewer_runs(spec, monkeypatch):
    calls = fake_cli(monkeypatch, spec)
    monkeypatch.setattr(r, 'jsonschema', None)
    with pytest.raises(r.ReviewError, match='jsonschema is not installed'):
        r.run_review(spec, executable='fixture-claude', environ={})
    assert calls == []


@pytest.mark.parametrize('env', [{'ANTHROPIC_API_KEY': 'secret'}, {'CLAUDE_CODE_USE_BEDROCK': '1'}, {'OPENAI_API_KEY': 'secret'}])
def test_provider_modes_refused(env):
    with pytest.raises(r.ReviewError, match='subscription'):
        r.subscription_environment(env)


@pytest.mark.parametrize('defect', ['missing_lens', 'wrong_head', 'wrong_model', 'no_model', 'wrong_session', 'missing_acceptance', 'failed', 'wrong_type', 'wrong_mode', 'wrong_previous'])
def test_incomplete_or_wrong_results_fail_the_worker_and_keep_its_output(spec, monkeypatch, defect):
    def mutate(data):
        if defect == 'missing_lens': del data['structured_output']['lenses']['correctness']
        if defect == 'wrong_head': data['structured_output']['head'] = spec['base']
        if defect == 'wrong_model': data['modelUsage'] = {'claude-opus-5': {}}
        if defect == 'no_model': data['modelUsage'] = {}
        if defect == 'wrong_session': data['session_id'] = 'other'
        if defect == 'missing_acceptance': data['structured_output']['acceptance'] = []
        if defect == 'failed': data['is_error'] = True
        if defect == 'wrong_type': return []
        if defect == 'wrong_mode': data['structured_output']['mode'] = 'incremental'
        if defect == 'wrong_previous': data['structured_output']['previous_reviewed_head'] = spec['base']
        return data
    fake_cli(monkeypatch, spec, mutate)
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'incomplete'
    for review in result['reviews']:
        assert review['status'] == 'failed' and review['reason'] and 'candidates' not in review
        if defect != 'wrong_type':
            assert review['raw_output']['structured_output']  # the reviewer's output is kept for the lead


LONG_CRITERIA = [
    {'label': 'M1', 'criterion': '**M1** `pytest -q` (the full suite, including the new fixture tests) passes on the PR head, '
                                 'with the output recorded on the ticket.'},
    {'label': 'M2', 'criterion': '**M2** A sum of two integers returns their total, and a sum with zero returns the other operand.'},
    {'label': 'M3', 'criterion': '**M3** The change touches only `app.py` and its tests; no other module changes behavior.'},
]


def condensed(data):
    # What Sonnet workers actually return for long markdown criteria: the right rows, shortened text.
    for row in data['structured_output']['acceptance']:
        row['criterion'] = row['criterion'].split('(')[0][:20]
    return data


def test_condensed_but_labelled_report_passes(spec, monkeypatch):
    # q-core#19: four complete, ordered reports were refused because the workers condensed the criteria.
    spec['context']['acceptance_criteria'] = LONG_CRITERIA
    calls = fake_cli(monkeypatch, spec, condensed)
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'candidates_require_lead_validation'
    assert json.loads(calls[0][1]['input'])['context']['acceptance_criteria'] == LONG_CRITERIA  # labels reach the workers
    for review in result['reviews']:
        rows = review['candidates']['acceptance']
        assert [row['label'] for row in rows] == ['M1', 'M2', 'M3']
        assert rows[0]['criterion'] != LONG_CRITERIA[0]['criterion']  # condensed text is kept as informational
    prompt = calls[0][0][calls[0][0].index('--system-prompt') + 1]
    assert 'label exactly as given' in prompt and 'verbatim where possible' in prompt
    assert 'exactly the supplied labels and nothing else' in prompt


def test_plain_text_criteria_are_labelled_by_position_and_exact_reports_still_pass(spec, monkeypatch):
    spec['context']['acceptance_criteria'] = ['Adds numbers', 'Keeps zero neutral']
    calls = fake_cli(monkeypatch, spec)
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'candidates_require_lead_validation'
    assert json.loads(calls[0][1]['input'])['context']['acceptance_criteria'] == [
        {'label': '1', 'criterion': 'Adds numbers'}, {'label': '2', 'criterion': 'Keeps zero neutral'}]
    assert [row['criterion'] for row in result['reviews'][0]['candidates']['acceptance']] == ['Adds numbers', 'Keeps zero neutral']


@pytest.mark.parametrize('defect, expected', [
    ('omitted', 'Reviewer omitted or reordered acceptance criteria: missing "M2".'),
    ('duplicated', 'Reviewer omitted or reordered acceptance criteria: missing "M3"; duplicate "M2".'),
    ('reordered', 'Reviewer omitted or reordered acceptance criteria: out of order.'),
    ('no_label_field', 'Reviewer returned incomplete or invalid structured output.'),
    # q-core#20: both workers added a row for the ticket's "Human acceptance criteria: None" line.
    ('extra_row', 'Reviewer returned an unexpected criterion row, not one of the supplied labels: "H1".'),
    ('wrong_label', 'Reviewer returned an unexpected criterion row, not one of the supplied labels: "**M1**".'),
])
def test_label_mismatch_fails_the_worker(spec, monkeypatch, defect, expected):
    spec['context']['acceptance_criteria'] = LONG_CRITERIA
    def mutate(data):
        rows = condensed(data)['structured_output']['acceptance']
        if defect == 'omitted': del rows[1]
        if defect == 'duplicated': rows[2] = dict(rows[1])
        if defect == 'reordered': rows.reverse()
        if defect == 'no_label_field': del rows[0]['label']
        if defect == 'extra_row': rows.append({'label': 'H1', 'criterion': 'Human acceptance criteria: None',
                                               'status': 'met', 'evidence': 'None required'})
        if defect == 'wrong_label': rows[0]['label'] = '**M1**'
        return data
    fake_cli(monkeypatch, spec, mutate)
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'incomplete'
    for review in result['reviews']:
        assert review['status'] == 'failed' and review['reason'] == expected
        assert review['raw_output']['structured_output']['acceptance']  # kept for the lead to inspect


@pytest.mark.parametrize('returned, message', [
    (['M1', 'M2', 'M3'], None),
    (['M1', 'M2', 'M3', 'M3'], 'omitted or reordered acceptance criteria: duplicate "M3".'),
    (['M1'], 'omitted or reordered acceptance criteria: missing "M2", "M3".'),
    (['M1', 'M2', 'M3', 'H1', 'H1', 'H2'], 'unexpected criterion row, not one of the supplied labels: "H1", "H2".'),
    (['M1', 'M2', 'M3', 'x' * 100], 'supplied labels: "' + 'x' * 59 + '.'),  # a label is capped in the message
])
def test_label_problems_are_named(returned, message):
    if message is None:
        r.check_acceptance_labels(returned, ['M1', 'M2', 'M3'])
        return
    with pytest.raises(r.ReviewError) as caught:
        r.check_acceptance_labels(returned, ['M1', 'M2', 'M3'])
    assert str(caught.value).endswith(message)


@pytest.mark.parametrize('criteria, message', [
    ([], 'nonempty list'),
    ([''], 'nonempty text entries'),
    ([{'label': '', 'criterion': 'x'}], 'nonempty label'),
    ([{'label': ' M1', 'criterion': 'x'}], 'surrounding whitespace'),
    ([{'label': 'M1', 'criterion': 'x', 'status': 'met'}], 'label, criterion'),
    ([{'label': 'M1', 'criterion': 'x'}, {'label': 'M1', 'criterion': 'y'}], 'unique'),
    (['first', {'label': '1', 'criterion': 'y'}], 'unique'),
])
def test_invalid_acceptance_criteria_refused(spec, criteria, message):
    spec['context']['acceptance_criteria'] = criteria
    with pytest.raises(r.ReviewError, match=message):
        r.freeze(spec)


def test_one_failed_worker_keeps_the_other_report(spec, monkeypatch):
    count = itertools.count()
    def mutate(data):
        if next(count) == 0:
            data['is_error'] = True
        return data
    fake_cli(monkeypatch, spec, mutate)
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'incomplete'
    assert sorted(review['status'] for review in result['reviews']) == ['complete', 'failed']
    complete = next(review for review in result['reviews'] if review['status'] == 'complete')
    assert complete['candidates']['acceptance'][0]['criterion'] == 'Adds numbers'


def test_out_of_bundle_citation_is_kept_and_flagged(spec, monkeypatch):
    def mutate(data):
        data['structured_output']['lenses']['correctness']['findings'] = [
            dict(severity='high', file='caller.py', evidence='x', impact='x', recommendation='x'),
            dict(severity='low', file='app.py', evidence='y', impact='y', recommendation='y')]
        return data
    fake_cli(monkeypatch, spec, mutate)
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'candidates_require_lead_validation'
    for review in result['reviews']:
        findings = review['candidates']['lenses']['correctness']['findings']
        assert [(f['file'], f['out_of_bundle']) for f in findings] == [('caller.py', True), ('app.py', False)]


def test_snapshot_holds_committed_head_without_private_paths(spec, tmp_path):
    repo = Path(spec['repository'])
    for name in ('.env', '.env.local', 'intake/statement.pdf', 'data/life.db', 'config/secrets/token',
                 'certs/server.pem', 'docs/guide.md', 'src/lib.py'):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text('fixture\n')
    (repo / 'link.py').symlink_to('/etc/passwd')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-m', 'more files')
    (repo / 'untracked.txt').write_text('never committed\n')
    (repo / 'app.py').write_text('dirty working copy\n')
    head = git(repo, 'rev-parse', 'HEAD')
    destination = tmp_path / 'snapshot'
    destination.mkdir()
    r.snapshot(repo, head, destination)
    files = sorted(str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file() or p.is_symlink())
    assert files == ['app.py', 'docs/guide.md', 'src/lib.py']
    assert (destination / 'app.py').read_text() == 'def add(a, b): return a + b\n'


def test_changed_commit_during_review_refused(spec, monkeypatch):
    calls = fake_cli(monkeypatch, spec)
    original = r._git
    reads = 0
    def changed(repo, *args):
        nonlocal reads
        if args == ('rev-parse', 'HEAD'):
            reads += 1
            if reads > 1:
                return (spec['base'] + '\n').encode()
        return original(repo, *args)
    monkeypatch.setattr(r, '_git', changed)
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'stale'
    assert len(calls) == 2 and len(result['reviews']) == 2


def test_child_failure_does_not_expose_stderr(spec, monkeypatch):
    fake_cli(monkeypatch, spec)
    previous = subprocess.run
    def failed(args, **kwargs):
        if '--print' in args:
            return subprocess.CompletedProcess(args, 1, '', 'PRIVATE SECRET')
        return previous(args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', failed)
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'incomplete'
    assert all(review['reason'].startswith('Reviewer subprocess failed') for review in result['reviews'])
    assert 'PRIVATE' not in json.dumps(result)


def test_bundle_too_large_for_reviewer_is_named(spec, monkeypatch):
    # A bundle past the reviewer's context makes the CLI exit 1 with this result on stdout.
    fake_cli(monkeypatch, spec)
    previous = subprocess.run
    def too_long(args, **kwargs):
        if '--print' in args:
            return subprocess.CompletedProcess(args, 1, json.dumps({'is_error': True, 'result': 'Prompt is too long'}), 'PRIVATE SECRET')
        return previous(args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', too_long)
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'incomplete'
    assert all("exceeds the reviewer's context" in review['reason'] for review in result['reviews'])
    assert 'PRIVATE' not in json.dumps(result)


def test_timeout_and_malformed_json_fail_the_workers(spec, monkeypatch):
    fake_cli(monkeypatch, spec)
    previous = subprocess.run
    mode = 'timeout'
    def broken(args, **kwargs):
        if '--print' in args:
            if mode == 'timeout':
                raise subprocess.TimeoutExpired(args, 1)
            return subprocess.CompletedProcess(args, 0, '{broken', '')
        return previous(args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', broken)
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'incomplete' and all('timed out' in review['reason'] for review in result['reviews'])
    mode = 'json'
    result = r.run_review(spec, executable='fixture-claude', environ={})
    assert result['status'] == 'incomplete' and all('malformed' in review['reason'] for review in result['reviews'])


def test_cli_writes_an_incomplete_pair_and_exits_nonzero(spec, tmp_path, monkeypatch, capsys):
    incomplete = {'status': 'incomplete', 'reviews': [{'session_id': 's1', 'status': 'failed', 'reason': 'Reviewer timed out after 1 seconds.'},
                                                      {'session_id': 's2', 'status': 'complete'}]}
    monkeypatch.setattr(r, 'run_review', lambda spec, timeout, jyra: incomplete)
    monkeypatch.setattr(r, 'jyra_access', lambda: {'api_url': 'http://127.0.0.1:8420', 'token': 'qc_fixture'})
    (tmp_path / 'in.json').write_text(json.dumps(spec))
    monkeypatch.setattr('sys.argv', ['review_runner', '--input', str(tmp_path / 'in.json'), '--output', str(tmp_path / 'out.json')])
    with pytest.raises(SystemExit) as exit_:
        r.main()
    assert exit_.value.code == 1
    assert json.loads((tmp_path / 'out.json').read_text()) == incomplete
    assert 's1: Reviewer timed out' in capsys.readouterr().err


def test_binary_and_symlink_tracked_files_refused(spec):
    repo = Path(spec['repository'])
    (repo / 'app.py').write_bytes(b'\0binary')
    git(repo, 'commit', '-am', 'binary')
    spec['head'] = git(repo, 'rev-parse', 'HEAD')
    with pytest.raises(r.ReviewError, match='binary'):
        r.freeze(spec)
    (repo / 'app.py').unlink()
    (repo / 'app.py').symlink_to('/etc/passwd')
    git(repo, 'add', 'app.py')
    git(repo, 'commit', '-m', 'link')
    spec['head'] = git(repo, 'rev-parse', 'HEAD')
    with pytest.raises(r.ReviewError, match='Symlinks'):
        r.freeze(spec)


def test_non_subscription_auth_refused_before_review(spec, monkeypatch):
    real = subprocess.run
    def run(args, **kwargs):
        if args[0] == 'fixture-claude':
            assert args[1:3] == ['auth', 'status']
            return subprocess.CompletedProcess(args, 0, json.dumps({'loggedIn': True, 'authMethod': 'api_key', 'apiProvider': 'firstParty'}), '')
        return real(args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(r.ReviewError, match='subscription'):
        r.run_review(spec, executable='fixture-claude', environ={})


@pytest.mark.parametrize('previous_only', ['reverted', 'deleted'])
def test_incremental_includes_reverted_and_previous_only_deleted_files(spec, previous_only):
    repo = Path(spec['repository'])
    # Base: app=old. Previous review: app=bad + transient file when deleted.
    base = spec['base']
    previous = spec['head']
    if previous_only == 'deleted':
        (repo / 'transient.py').write_text('prior finding lived here\n')
        git(repo, 'add', 'transient.py')
        git(repo, 'commit', '-m', 'previous transient change')
        previous = git(repo, 'rev-parse', 'HEAD')
        git(repo, 'rm', 'transient.py')
    (repo / 'app.py').write_text('def add(a, b): return a - b\n')
    (repo / 'other.py').write_text('new current change\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'revert earlier change and update other file')
    head = git(repo, 'rev-parse', 'HEAD')
    spec.update(head=head, previous_reviewed_head=previous, previous_reviewed_base=base,
                files=['other.py'])
    with pytest.raises(r.ReviewError, match='full and incremental'):
        r.freeze(spec)
    spec['files'].append('app.py')
    if previous_only == 'deleted':
        with pytest.raises(r.ReviewError, match='full and incremental'):
            r.freeze(spec)
        spec['files'].append('transient.py')
    frozen = json.loads(r.freeze(spec)[1])
    assert frozen['snapshots'][head]['app.py'] == frozen['snapshots'][base]['app.py']
    assert frozen['snapshots'][previous]['app.py'] != frozen['snapshots'][head]['app.py']
    assert 'app.py' in frozen['incremental_diff']
    if previous_only == 'deleted':
        assert frozen['snapshots'][previous]['transient.py'] == 'prior finding lived here\n'
        assert frozen['snapshots'][base]['transient.py'] is None
        assert frozen['snapshots'][head]['transient.py'] is None
        assert 'transient.py' in frozen['incremental_diff']


def test_scope_changes_actual_reviewer_prompt_and_binds_output(spec, monkeypatch):
    calls = fake_cli(monkeypatch, spec)
    full = r.run_review(spec, executable='fixture-claude', environ={})
    full_prompt = calls[0][0][calls[0][0].index('--system-prompt') + 1]
    assert 'FULL REVIEW: review the complete base-to-head diff' in full_prompt
    assert full['mode'] == 'full'
    spec.update(previous_reviewed_head=spec['base'], previous_reviewed_base=spec['base'])
    calls.clear()
    incremental = r.run_review(spec, executable='fixture-claude', environ={})
    prompt = calls[0][0][calls[0][0].index('--system-prompt') + 1]
    assert 'INCREMENTAL REVIEW: review only incremental_diff' in prompt
    assert 'Do not redispatch a resolved prior finding' in prompt
    assert 'FULL REVIEW:' not in prompt
    assert prompt != full_prompt
    assert incremental['mode'] == 'incremental'
    for result in incremental['reviews']:
        assert result['candidates']['previous_reviewed_head'] == spec['base']


def test_worker_prompt_carries_the_process_safety_rule(spec, monkeypatch):
    # Workers run Bash as the user on shared hosts; two agents pattern-killed test servers in an earlier build.
    calls = fake_cli(monkeypatch, spec)
    r.run_review(spec, executable='fixture-claude', environ={})
    for args, _ in calls:
        prompt = args[args.index('--system-prompt') + 1]
        assert ('Process safety: never use pkill, killall or any other pattern-matched kill. Stop only processes you '
                'started, by their recorded PID or your own process group, and never touch system services or other '
                "users' processes.") in prompt


def test_output_carries_a_criteria_digest_stable_across_rounds(spec, monkeypatch):
    from q_factory.review_state import specification_digest
    fake_cli(monkeypatch, spec)
    full = r.run_review(spec, executable='fixture-claude', environ={})
    spec.update(previous_reviewed_head=spec['base'], previous_reviewed_base=spec['base'])
    spec['context']['prior_findings'] = [{'id': 'R1-F1', 'disposition': 'fixed'}]
    incremental = r.run_review(spec, executable='fixture-claude', environ={})
    assert full['criteria_digest'] == incremental['criteria_digest'] == specification_digest(spec['context'])
    assert full['bundle_sha256'] != incremental['bundle_sha256']
