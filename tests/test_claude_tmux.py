"""Behavior of scripts/claude-tmux.sh against a private, disposable tmux server.

Every test gets its own HOME and TMUX_TMPDIR, so the script's default tmux
socket is a throwaway one and personal sessions are never listed or touched.
`claude` is a fake that only sleeps, so no Claude session is ever started.
"""
import json
import os
import pty
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / 'scripts' / 'claude-tmux.sh'
INSTALL = REPO / 'scripts' / 'install-claude-tmux.sh'
SYNC = REPO / 'scripts' / 'session-sync.sh'
TMUX = shutil.which('tmux') or next((p for p in ('/opt/homebrew/bin/tmux', '/usr/local/bin/tmux') if os.path.exists(p)), None)
SYSTEM_DIRS = ('/usr/bin', '/bin', '/usr/sbin', '/sbin')
# The scripts start with `#!/usr/bin/env bash`. A Mac has /bin/bash (3.2) and needs
# nothing more; NixOS has no bash in the system dirs, only in a directory that holds
# every other tool too, so script_path adds a copy of it without claude and tmux.
BASH_DIR = str(Path(shutil.which('bash') or '/bin/bash').parent)
SYSTEM_BASH = any(os.path.exists(f'{d}/bash') for d in ('/bin', '/usr/bin'))
# Set to a bash binary (e.g. a local 3.2 build) to run the scripts under it instead.
TEST_BASH = os.environ.get('CLAUDE_TMUX_TEST_BASH')

pytestmark = pytest.mark.skipif(TMUX is None, reason='tmux is required for claude-tmux tests')


def script_path(bin_dir: Path, bash_dir: str = BASH_DIR) -> str:
    """A minimal PATH for the scripts: bin_dir (with TEST_BASH linked in), then the system.

    Never bash_dir itself: a `claude` beside bash (Homebrew, a Nix profile) would
    reach the scripts, and the tests decide whether claude and tmux are present.
    """
    bin_dir.mkdir(exist_ok=True)
    if TEST_BASH and not (bin_dir / 'bash').exists():
        (bin_dir / 'bash').symlink_to(TEST_BASH)
    dirs = [str(bin_dir), *SYSTEM_DIRS]
    if not SYSTEM_BASH:
        tools = bin_dir.parent / f'{bin_dir.name}-bash-dir'
        if not tools.exists():
            tools.mkdir()
            for entry in Path(bash_dir).iterdir():
                if entry.name not in ('claude', 'tmux'):
                    (tools / entry.name).symlink_to(entry)
        dirs.append(str(tools))
    return ':'.join(dirs)


class Host:
    def __init__(self, root: Path, with_claude: bool = True):
        self.root = root
        self.home = root / 'home'
        self.home.mkdir()
        self.bin = root / 'bin'
        self.bin.mkdir()
        (self.bin / 'tmux').symlink_to(TMUX)
        if with_claude:
            claude = self.bin / 'claude'
            claude.write_text('#!/bin/sh\nexec sleep 600\n')
            claude.chmod(0o755)
        # Unix socket paths are limited to ~104 bytes; pytest's tmp_path is too deep.
        self.tmpdir = Path(tempfile.mkdtemp(prefix='ctmux-', dir='/tmp'))
        self.env = {
            'HOME': str(self.home), 'TMUX_TMPDIR': str(self.tmpdir), 'TERM': 'xterm-256color',
            'PATH': script_path(self.bin), 'LANG': 'en_US.UTF-8',
        }

    def run(self, *args, cwd=None):
        return subprocess.run([str(SCRIPT), *args], env=self.env, cwd=cwd or self.home,
                              capture_output=True, text=True, timeout=20)

    def tmux(self, *args, check=True):
        return subprocess.run([TMUX, *args], env=self.env, capture_output=True, text=True,
                              timeout=10, check=check).stdout.strip()

    def sessions(self):
        out = subprocess.run([TMUX, 'list-sessions', '-F', '#{session_name}'], env=self.env,
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip().split('\n') if out.returncode == 0 and out.stdout.strip() else []

    def describe(self, target):
        fields = '#{pane_start_command}|#{pane_current_path}|#{session_attached}|#{window_panes}'
        # '=name' is only an exact *session* target; panes need the trailing ':'.
        target = target + ':' if target.startswith('=') else target
        return self.tmux('display-message', '-p', '-t', target, fields)

    def in_terminal(self, *args, cwd):
        """Run the script with a real pseudo-terminal, as a user in a terminal would."""
        leader, follower = pty.openpty()
        process = subprocess.Popen([str(SCRIPT), *args], env=self.env, cwd=cwd,
                                   stdin=follower, stdout=follower, stderr=follower, start_new_session=True)
        os.close(follower)
        return process, leader

    def kill(self):
        # Name the private socket explicitly: never let this reach a real tmux server,
        # even if the environment above ever inherited $TMUX.
        socket = self.tmpdir / f'tmux-{os.getuid()}' / 'default'
        assert str(socket).startswith('/tmp/ctmux-') and 'TMUX' not in self.env
        subprocess.run([TMUX, '-S', str(socket), 'kill-server'], env=self.env, capture_output=True, timeout=10)

    def cleanup(self):
        self.kill()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


@pytest.fixture
def host(tmp_path):
    h = Host(tmp_path)
    yield h
    h.cleanup()


def result(completed):
    lines = completed.stdout.strip().split('\n')
    assert len(lines) == 1, completed.stdout
    return json.loads(lines[0])


def wait_for(predicate, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError('condition not met in time')


def test_create_starts_detached_claude_in_folder(host):
    folder = host.home / 'Projects' / 'demo'
    folder.mkdir(parents=True)
    completed = host.run('create', 'demo', '--dir', str(folder))
    assert completed.returncode == 0, completed.stderr
    out = result(completed)
    assert out == {'ok': True, 'name': 'demo', 'id': out['id'], 'dir': str(folder.resolve())}
    assert out['id'].startswith('$')
    assert host.sessions() == ['demo']
    start, path, attached, panes = host.describe(out['id']).split('|')
    assert start == 'claude'
    assert Path(path).resolve() == folder.resolve()
    assert attached == '0'
    assert panes == '1'


def test_create_runs_claude_even_if_server_path_lacks_it(host):
    # tmux (3.x) gives a new pane the creating command's PATH, not the server's.
    # create relies on that: over SSH the server may predate the login shell.
    bare = dict(host.env, PATH='/usr/bin:/bin')
    subprocess.run([TMUX, 'new-session', '-d', '-s', 'server-started-elsewhere', 'sleep 600'], env=bare, check=True, timeout=10)
    out = result(host.run('create', 'survives', '--dir', str(host.home)))
    time.sleep(0.5)
    assert 'survives' in host.sessions()
    assert host.tmux('display-message', '-p', '-t', out['id'], '#{pane_current_command}') == 'sleep'


def test_create_expands_tilde_folder(host):
    (host.home / 'Projects').mkdir()
    out = result(host.run('create', 'tilde', '--dir', '~/Projects'))
    assert out['dir'] == str((host.home / 'Projects').resolve())
    home = result(host.run('create', 'home', '--dir', '~'))
    assert home['dir'] == str(host.home.resolve())


def test_create_sanitizes_name_like_new(host):
    out = result(host.run('create', 'my.proj:1 x', '--dir', str(host.home)))
    assert out['name'] == 'my-proj-1-x'
    assert host.sessions() == ['my-proj-1-x']


def test_create_refuses_duplicate_name(host):
    assert host.run('create', 'dup', '--dir', str(host.home)).returncode == 0
    completed = host.run('create', 'dup', '--dir', str(host.home))
    assert completed.returncode == 3
    assert result(completed) == {'ok': False, 'error': 'name_taken', 'message': "claude-tmux: session 'dup' already exists"}
    assert "already exists" in completed.stderr
    assert host.sessions() == ['dup']


def test_create_refuses_duplicate_after_sanitizing(host):
    assert host.run('create', 'a.b', '--dir', str(host.home)).returncode == 0
    completed = host.run('create', 'a:b', '--dir', str(host.home))
    assert completed.returncode == 3
    assert result(completed)['error'] == 'name_taken'


def test_create_refuses_missing_folder(host):
    completed = host.run('create', 'nofolder', '--dir', '~/does-not-exist')
    assert completed.returncode == 4
    assert result(completed) == {'ok': False, 'error': 'folder_missing',
                                 'message': "claude-tmux: folder '~/does-not-exist' does not exist"}
    assert host.sessions() == []


def test_create_refuses_a_file_as_folder(host):
    (host.home / 'file').write_text('x')
    completed = host.run('create', 'filefolder', '--dir', str(host.home / 'file'))
    assert completed.returncode == 4
    assert host.sessions() == []


def test_create_reports_claude_missing_verbatim(tmp_path):
    h = Host(tmp_path, with_claude=False)
    try:
        completed = h.run('create', 'noclaude', '--dir', str(h.home))
        assert completed.returncode == 5
        assert result(completed) == {'ok': False, 'error': 'claude_missing',
                                     'message': 'claude-tmux: claude CLI not found on PATH'}
        assert h.sessions() == []
    finally:
        h.cleanup()


def test_claude_beside_bash_stays_off_the_scripts_path(tmp_path):
    """A `claude` in the same directory as bash (Homebrew's, a Nix profile's) must
    not reach the scripts, or the claude-missing test would find it."""
    beside = tmp_path / 'bash-and-claude'
    beside.mkdir()
    for entry in Path(BASH_DIR).iterdir():
        if entry.name != 'claude':
            (beside / entry.name).symlink_to(entry)
    (beside / 'claude').write_text('#!/bin/sh\nexec sleep 600\n')
    (beside / 'claude').chmod(0o755)
    h = Host(tmp_path, with_claude=False)
    try:
        own = tmp_path / 'beside-bin'  # not h.bin: its copy of the real bash dir is already made
        own.mkdir()
        (own / 'tmux').symlink_to(TMUX)
        h.env['PATH'] = script_path(own, bash_dir=str(beside))
        completed = h.run('create', 'noclaude', '--dir', str(h.home))
        assert completed.returncode == 5, completed.stdout
        assert result(completed)['error'] == 'claude_missing'
    finally:
        h.cleanup()


def test_create_reports_tmux_missing(host):
    """No tmux anywhere on PATH. On Linux tmux lives in /usr/bin (on NixOS beside
    bash), so removing the private link is not enough: the system dirs and bash's
    are replaced by a copy of their links without tmux (on macOS it passed only
    because Homebrew's dir was absent)."""
    (host.bin / 'tmux').unlink()
    system = host.bin.parent / 'system-without-tmux'
    system.mkdir()
    for directory in SYSTEM_DIRS:
        if not Path(directory).is_dir():  # e.g. no /sbin on some minimal images
            continue
        for entry in Path(directory).iterdir():
            if entry.name != 'tmux' and not (system / entry.name).exists():
                (system / entry.name).symlink_to(entry)
    # script_path's copy of bash's directory (NixOS) already leaves tmux out.
    host.env['PATH'] = host.env['PATH'].replace(':'.join(SYSTEM_DIRS), str(system))
    completed = host.run('create', 'x', '--dir', str(host.home))
    assert completed.returncode == 6
    assert result(completed)['error'] == 'tmux_missing'


@pytest.mark.parametrize('args', [[], ['onlyname'], ['--dir', '/tmp'], ['a', 'b', '--dir', '/tmp'], ['a', '--dir']])
def test_create_usage_errors(host, args):
    completed = host.run('create', *args)
    assert completed.returncode == 2
    assert result(completed)['error'] == 'usage'


def test_json_escapes_unusual_folder(host):
    folder = host.home / 'we"ird \\ dir'
    folder.mkdir()
    out = result(host.run('create', 'weird', '--dir', str(folder)))
    assert out['dir'] == str(folder.resolve())


def test_close_kills_matching_session(host):
    out = result(host.run('create', 'bye', '--dir', str(host.home)))
    instance = host.tmux('display-message', '-p', '-t', out['id'], '#{pid}:#{session_created}')
    completed = host.run('close', 'bye', '--id', out['id'], '--instance', instance)
    assert completed.returncode == 0, completed.stderr
    assert result(completed) == {'ok': True, 'name': 'bye', 'id': out['id']}
    assert host.sessions() == []


def test_close_without_identity_uses_exact_name(host):
    result(host.run('create', 'plain', '--dir', str(host.home)))
    result(host.run('create', 'plain2', '--dir', str(host.home)))
    assert host.run('close', 'plain').returncode == 0
    assert host.sessions() == ['plain2']


def test_close_refuses_stale_id(host):
    host.tmux('new-session', '-d', '-s', 'keepalive', 'sleep 600')  # keep the server, so ids advance
    first = result(host.run('create', 'stale', '--dir', str(host.home)))
    host.tmux('kill-session', '-t', first['id'])
    second = result(host.run('create', 'stale', '--dir', str(host.home)))
    assert second['id'] != first['id']
    completed = host.run('close', 'stale', '--id', first['id'])
    assert completed.returncode == 8
    assert result(completed)['error'] == 'replaced'
    assert sorted(host.sessions()) == ['keepalive', 'stale']


def test_close_refuses_replacement_that_reused_the_id(host):
    # A tmux server restart reuses $0, so the id alone cannot detect replacement.
    first = result(host.run('create', 'reused', '--dir', str(host.home)))
    instance = host.tmux('display-message', '-p', '-t', first['id'], '#{pid}:#{session_created}')
    host.kill()
    time.sleep(1.1)  # session_created has one-second resolution
    second = result(host.run('create', 'reused', '--dir', str(host.home)))
    assert second['id'] == first['id']
    completed = host.run('close', 'reused', '--id', first['id'], '--instance', instance)
    assert completed.returncode == 8
    assert result(completed)['error'] == 'replaced'
    assert host.sessions() == ['reused']


def test_close_reports_missing_session(host):
    completed = host.run('close', 'ghost', '--id', '$9')
    assert completed.returncode == 7
    assert result(completed) == {'ok': False, 'error': 'not_found', 'message': "claude-tmux: no session named 'ghost'"}


def test_close_any_tmux_session_by_exact_unusual_name(host):
    name = 'alpha $(touch pwned) 你好'
    host.tmux('new-session', '-d', '-s', name, 'sleep 600')
    host.tmux('new-session', '-d', '-s', 'alpha', 'sleep 600')
    session_id = host.tmux('display-message', '-p', '-t', '=' + name + ':', '#{session_id}')
    completed = host.run('close', name, '--id', session_id)
    assert completed.returncode == 0, completed.stderr
    assert host.sessions() == ['alpha']
    assert not (host.home / 'pwned').exists()


def test_close_works_without_a_utf8_locale(host):
    # SSH commands usually run with no LANG; tmux then escapes tabs and non-ASCII.
    host.env.pop('LANG')
    name = 'beta 你好'
    host.tmux('new-session', '-d', '-s', name, 'sleep 600')
    session_id = host.tmux('-u', 'display-message', '-p', '-t', '=' + name + ':', '#{session_id}')
    completed = host.run('close', name, '--id', session_id)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert host.sessions() == []


@pytest.mark.parametrize('args', [[], ['--id', '$1'], ['a', 'b'], ['a', '--id'], ['a', '--instance']])
def test_close_usage_errors(host, args):
    completed = host.run('close', *args)
    assert completed.returncode == 2
    assert result(completed)['error'] == 'usage'


def test_close_does_not_need_claude(tmp_path):
    h = Host(tmp_path, with_claude=False)
    try:
        h.tmux('new-session', '-d', '-s', 'nc', 'sleep 600')
        assert h.run('close', 'nc').returncode == 0
    finally:
        h.cleanup()


def test_new_name_in_terminal_matches_create(host):
    project = host.home / 'Projects' / 'same'
    project.mkdir(parents=True)
    process, leader = host.in_terminal('new', 'terminal-made', cwd=project)
    try:
        wait_for(lambda: 'terminal-made' in host.sessions() and host.describe('=terminal-made').startswith('claude|'))
        created = result(host.run('create', 'phone-made', '--dir', str(project)))
        terminal = host.describe('=terminal-made').split('|')
        phone = host.describe(created['id']).split('|')
        # Same command, folder and layout; only attachment differs until a client attaches.
        assert terminal[0] == phone[0] == 'claude'
        assert Path(terminal[1]).resolve() == Path(phone[1]).resolve() == project.resolve()
        assert terminal[3] == phone[3] == '1'
        assert wait_for(lambda: host.describe('=terminal-made').split('|')[2] == '1')
        for option in ('default-command', 'default-shell'):
            assert host.tmux('show-options', '-v', '-t', '=terminal-made', option, check=False) == \
                host.tmux('show-options', '-v', '-t', '=phone-made', option, check=False)
    finally:
        host.kill()
        process.wait(timeout=10)
        os.close(leader)


def test_new_refuses_existing_name_in_terminal(host):
    result(host.run('create', 'taken', '--dir', str(host.home)))
    completed = host.run('new', 'taken')
    assert completed.returncode == 1
    assert "already exists" in completed.stderr


def test_plain_command_lists_sessions_and_changes_nothing(host):
    empty = host.run()
    assert empty.returncode == 0, empty.stderr
    assert 'No tmux sessions running.' in empty.stdout
    assert 'claude-tmux new NAME' in empty.stdout and 'claude-tmux connect NAME' in empty.stdout
    assert host.sessions() == []
    project = host.home / 'myproj'
    project.mkdir()
    result(host.run('create', 'work', '--dir', str(project)))
    listed = host.run(cwd=project)
    assert listed.returncode == 0, listed.stderr
    line = next(l for l in listed.stdout.splitlines() if l.strip().startswith('work'))
    assert '~/myproj' in line, listed.stdout
    assert host.sessions() == ['work'], 'no per-folder session is created'
    assert host.describe('=work').split('|')[2] == '0', 'nothing attaches'


def test_plain_command_abbreviates_only_the_home_folder(host):
    # bash 5.2+ tilde-expanded the '~' in ${path/#$HOME/~} back into $HOME, and
    # bash 3.2 turned a sibling such as $HOME-old into '~-old'.
    sibling = host.root / 'home-old'
    sibling.mkdir()
    (host.home / 'deep' / 'er').mkdir(parents=True)
    for name, folder in (('at-home', host.home), ('nested', host.home / 'deep' / 'er'), ('sibling', sibling)):
        result(host.run('create', name, '--dir', str(folder)))
    listed = host.run()
    assert listed.returncode == 0, listed.stderr
    shown = {l.split()[0]: l.split()[1] for l in listed.stdout.splitlines() if l.startswith('  ') and len(l.split()) >= 2
             and l.split()[0] in ('at-home', 'nested', 'sibling')}
    # tmux reports the pane's real path, so compare against resolved folders.
    assert shown == {'at-home': '~', 'nested': '~/deep/er', 'sibling': str(sibling.resolve())}, listed.stdout


def test_plain_command_works_without_claude(tmp_path):
    h = Host(tmp_path, with_claude=False)
    try:
        completed = h.run()
        assert completed.returncode == 0, completed.stderr
        assert 'No tmux sessions running.' in completed.stdout
    finally:
        h.cleanup()


@pytest.mark.parametrize('args', [('--model', 'opus'), ('stray',), ('bogus', 'x')])
def test_plain_command_refuses_stray_arguments(host, args):
    completed = host.run(*args)
    assert completed.returncode == 2
    assert 'claude-tmux new NAME' in completed.stderr
    assert host.sessions() == []


def test_new_without_name_numbers_per_folder(host):
    project = host.home / 'proj'
    project.mkdir()
    # The trailing '-' is long-standing (basename's newline), kept so names stay familiar.
    for expected in ('claude-proj-', 'claude-proj-2'):
        process, leader = host.in_terminal('new', cwd=project)
        try:
            wait_for(lambda: expected in host.sessions())
        finally:
            process.kill()
            process.wait(timeout=10)
            os.close(leader)


def identity(host, session_id):
    return host.tmux('display-message', '-p', '-t', session_id, '#{pid}:#{session_created}')


def test_rename_while_attached_keeps_the_session_and_client(host):
    out = result(host.run('create', 'before', '--dir', str(host.home)))
    process, leader = host.in_terminal('connect', 'before', cwd=host.home)
    try:
        wait_for(lambda: host.describe('=before').split('|')[2] == '1')
        completed = host.run('rename', 'before', 'after', '--id', out['id'], '--instance', identity(host, out['id']))
        assert completed.returncode == 0, completed.stderr
        assert result(completed) == {'ok': True, 'old': 'before', 'name': 'after', 'id': out['id']}
        assert host.sessions() == ['after']
        assert host.tmux('display-message', '-p', '-t', '=after:', '#{session_id}') == out['id'], 'same session'
        assert host.describe('=after').split('|')[2] == '1', 'the client stays attached'
        assert host.describe('=after').startswith('claude|'), 'claude keeps running'
    finally:
        host.kill()
        process.wait(timeout=10)
        os.close(leader)


def test_rename_to_the_same_name_is_a_no_op(host):
    out = result(host.run('create', 'same', '--dir', str(host.home)))
    completed = host.run('rename', 'same', 'same', '--id', out['id'])
    assert completed.returncode == 0, completed.stderr
    assert result(completed) == {'ok': True, 'old': 'same', 'name': 'same', 'id': out['id']}


def test_rename_refuses_a_taken_name(host):
    out = result(host.run('create', 'one', '--dir', str(host.home)))
    result(host.run('create', 'two', '--dir', str(host.home)))
    completed = host.run('rename', 'one', 'two', '--id', out['id'])
    assert completed.returncode == 3
    assert result(completed)['error'] == 'name_taken'
    assert sorted(host.sessions()) == ['one', 'two']


@pytest.mark.parametrize('bad', ['has space', 'dot.ted', 'co:lon', '', 'x' * 65, '-dash', 'semi;colon', '$(id)', 'naïve'])
def test_rename_refuses_invalid_names(host, bad):
    out = result(host.run('create', 'valid', '--dir', str(host.home)))
    completed = host.run('rename', 'valid', bad, '--id', out['id'])
    assert completed.returncode == 2
    assert result(completed)['error'] in ('invalid_name', 'usage')
    assert host.sessions() == ['valid']


@pytest.mark.parametrize('bad', ['naïve', 'é', 'ß', 'Ａ'])
@pytest.mark.parametrize('locale', [{'LANG': 'en_US.UTF-8'}, {'LC_ALL': 'en_US.UTF-8'}, {'LC_ALL': 'C.UTF-8'},
                                    {'LC_ALL': 'C'}, {}], ids=['LANG=en_US', 'LC_ALL=en_US', 'C.UTF-8', 'C', 'none'])
def test_rename_refuses_non_ascii_in_any_locale(host, locale, bad):
    # A range like [A-Za-z] follows the locale's collation: under en_US.UTF-8 on
    # glibc it matched every one of these.
    host.env.pop('LANG')
    host.env.update(locale)
    out = result(host.run('create', 'valid', '--dir', str(host.home)))
    completed = host.run('rename', 'valid', bad, '--id', out['id'])
    assert completed.returncode == 2, completed.stdout
    assert result(completed)['error'] == 'invalid_name'
    assert '(ASCII letters, digits' in result(completed)['message']
    assert host.sessions() == ['valid']
    ok = host.run('rename', 'valid', 'Az_09-z', '--id', out['id'])
    assert ok.returncode == 0, ok.stdout + ok.stderr


def test_rename_reports_a_missing_session(host):
    completed = host.run('rename', 'ghost', 'new-name', '--id', '$9')
    assert completed.returncode == 7
    assert result(completed)['error'] == 'not_found'


def test_rename_refuses_a_replaced_session(host):
    host.tmux('new-session', '-d', '-s', 'keepalive', 'sleep 600')  # keep the server, so ids advance
    first = result(host.run('create', 'stale', '--dir', str(host.home)))
    host.tmux('kill-session', '-t', first['id'])
    result(host.run('create', 'stale', '--dir', str(host.home)))
    completed = host.run('rename', 'stale', 'other', '--id', first['id'])
    assert completed.returncode == 8
    assert result(completed)['error'] == 'replaced'
    assert sorted(host.sessions()) == ['keepalive', 'stale']


def test_rename_refuses_a_replacement_that_reused_the_id(host):
    first = result(host.run('create', 'reused', '--dir', str(host.home)))
    instance = identity(host, first['id'])
    host.kill()
    time.sleep(1.1)  # session_created has one-second resolution
    second = result(host.run('create', 'reused', '--dir', str(host.home)))
    assert second['id'] == first['id']
    completed = host.run('rename', 'reused', 'other', '--id', first['id'], '--instance', instance)
    assert completed.returncode == 8
    assert host.sessions() == ['reused']


def test_rename_by_exact_name_for_manual_use(host):
    out = result(host.run('create', 'typed', '--dir', str(host.home)))
    result(host.run('create', 'typed2', '--dir', str(host.home)))
    completed = host.run('rename', 'typed', 'retyped')
    assert completed.returncode == 0, completed.stderr
    assert result(completed) == {'ok': True, 'old': 'typed', 'name': 'retyped', 'id': out['id']}
    assert sorted(host.sessions()) == ['retyped', 'typed2'], 'exact name, not a prefix match'
    missing = host.run('rename', 'nope', 'x')
    assert missing.returncode == 7 and result(missing)['error'] == 'not_found'
    taken = host.run('rename', 'retyped', 'typed2')
    assert taken.returncode == 3 and result(taken)['error'] == 'name_taken'


@pytest.mark.parametrize('args', [('rename',), ('rename', 'a'), ('rename', 'a', 'b', 'c', '--id', '$0'),
                                  ('rename', 'a', 'b', '--id'), ('rename', 'a', 'b', '--instance'),
                                  ('rename', 'a', 'b', '--instance', '1:2')])
def test_rename_usage_errors(host, args):
    completed = host.run(*args)
    assert completed.returncode == 2
    assert result(completed)['error'] == 'usage'


def test_close_by_id_finds_a_session_renamed_elsewhere(host):
    out = result(host.run('create', 'original', '--dir', str(host.home)))
    instance = identity(host, out['id'])
    host.tmux('rename-session', '-t', out['id'], 'renamed')  # e.g. from another device
    completed = host.run('close', 'original', '--id', out['id'], '--instance', instance)
    assert completed.returncode == 0, completed.stderr
    assert host.sessions() == []


def test_connect_attaches_existing_and_rejects_missing(host):
    missing = host.run('connect', 'nope')
    assert missing.returncode == 1
    assert "no session named 'nope'" in missing.stderr
    result(host.run('create', 'attachme', '--dir', str(host.home)))
    process, leader = host.in_terminal('connect', 'attachme', cwd=host.home)
    try:
        wait_for(lambda: host.describe('=attachme').split('|')[2] == '1')
    finally:
        host.kill()
        process.wait(timeout=10)
        os.close(leader)


def install(home, *args):
    env = {'HOME': str(home), 'PATH': script_path(home / 'bin'), 'SHELL': '/bin/zsh'}
    return subprocess.run([str(INSTALL), *args], env=env, capture_output=True, text=True, timeout=20)


def test_install_links_script_and_adds_alias_once(tmp_path):
    first = install(tmp_path)
    assert first.returncode == 0, first.stderr
    link = tmp_path / '.claude' / 'scripts' / 'claude-tmux.sh'
    assert link.is_symlink() and link.resolve() == SCRIPT.resolve()
    assert install(tmp_path).returncode == 0
    rc = (tmp_path / '.zshrc').read_text()
    assert rc.count('alias claude-tmux=') == 1


def test_install_keeps_existing_script_and_alias(tmp_path):
    scripts = tmp_path / '.claude' / 'scripts'
    scripts.mkdir(parents=True)
    (scripts / 'claude-tmux.sh').write_text('#!/bin/sh\necho old\n')
    (tmp_path / '.zshrc').write_text('alias claude-tmux="~/.claude/scripts/claude-tmux.sh"\n')
    completed = install(tmp_path)
    assert completed.returncode == 0, completed.stderr
    backups = list(scripts.glob('claude-tmux.sh.bak-*'))
    assert len(backups) == 1 and 'echo old' in backups[0].read_text()
    assert (scripts / 'claude-tmux.sh').resolve() == SCRIPT.resolve()
    assert (tmp_path / '.zshrc').read_text().count('alias claude-tmux=') == 1


def test_install_uses_bashrc_for_bash_or_explicit_rc(tmp_path):
    env = {'HOME': str(tmp_path), 'PATH': script_path(tmp_path / 'bin'), 'SHELL': '/bin/bash'}
    assert subprocess.run([str(INSTALL)], env=env, capture_output=True, timeout=20).returncode == 0
    assert 'alias claude-tmux=' in (tmp_path / '.bashrc').read_text()
    custom = tmp_path / 'custom-rc'
    assert install(tmp_path, '--rc', str(custom)).returncode == 0
    assert 'alias claude-tmux=' in custom.read_text()


def test_install_repoints_a_link_into_another_checkout(tmp_path):
    """A link that points into an old checkout; rerunning from q-factory re-links cleanly."""
    elsewhere = tmp_path / 'old-checkout' / 'scripts' / 'claude-tmux.sh'
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_text('#!/bin/sh\necho old-checkout copy\n')
    scripts = tmp_path / '.claude' / 'scripts'
    scripts.mkdir(parents=True)
    (scripts / 'claude-tmux.sh').symlink_to(elsewhere)
    completed = install(tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert (scripts / 'claude-tmux.sh').resolve() == SCRIPT.resolve()
    assert not list(scripts.glob('claude-tmux.sh.bak-*'))  # a link is replaced, not backed up
    assert elsewhere.read_text() == '#!/bin/sh\necho old-checkout copy\n'  # the old checkout is untouched


def git(cwd, *args):
    return subprocess.run(['git', '-C', str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def factory_clone(root: Path, marker=True):
    """A q-factory-shaped clone one commit behind its origin. Returns (clone, origin head)."""
    origin = root / 'origin.git'
    subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(origin)], check=True)
    author = root / 'author'
    subprocess.run(['git', 'clone', '-q', str(origin), str(author)], check=True, capture_output=True)
    git(author, 'config', 'user.name', 'Test'); git(author, 'config', 'user.email', 't@example.invalid')
    git(author, 'checkout', '-q', '-b', 'main')
    (author / 'scripts').mkdir()
    shutil.copy2(SYNC, author / 'scripts' / 'session-sync.sh')
    if marker:
        (author / 'q-factory.toml').write_text('# invented\n')
    git(author, 'add', '.'); git(author, 'commit', '-q', '-m', 'v1'); git(author, 'push', '-q', 'origin', 'main')
    clone = root / 'factory'
    subprocess.run(['git', 'clone', '-q', str(origin), str(clone)], check=True, capture_output=True)
    (author / 'new.txt').write_text('upstream')
    git(author, 'add', '.'); git(author, 'commit', '-q', '-m', 'v2'); git(author, 'push', '-q', 'origin', 'main')
    return clone, git(author, 'rev-parse', 'HEAD')


def test_create_fast_forwards_a_factory_clone_before_claude_starts(host):
    clone, upstream = factory_clone(host.root)
    (clone / 'sub').mkdir()
    completed = host.run('create', 'fresh', '--dir', str(clone / 'sub'))
    out = result(completed)  # stdout stays one JSON line
    assert out['ok'] is True
    assert git(clone, 'rev-parse', 'HEAD') == upstream
    assert 'q-factory sync: fast-forwarded main by 1 commit(s)' in completed.stderr


def test_create_leaves_other_repositories_alone(host):
    clone, upstream = factory_clone(host.root, marker=False)
    before = git(clone, 'rev-parse', 'HEAD')
    completed = host.run('create', 'other', '--dir', str(clone))
    assert result(completed)['ok'] is True
    assert git(clone, 'rev-parse', 'HEAD') == before != upstream
    assert 'q-factory sync' not in completed.stderr


def test_create_starts_claude_even_when_sync_skips(host):
    clone, upstream = factory_clone(host.root)
    git(clone, 'checkout', '-q', '-b', 'task/x')
    completed = host.run('create', 'branchy', '--dir', str(clone))
    assert result(completed)['ok'] is True
    assert 'branchy' in host.sessions()
    assert 'skipped (on task/x, not main)' in completed.stderr


def test_new_fast_forwards_a_factory_clone_before_claude_starts(host):
    clone, upstream = factory_clone(host.root)
    process, leader = host.in_terminal('new', 'termfresh', cwd=clone)
    try:
        wait_for(lambda: 'termfresh' in host.sessions())
        assert git(clone, 'rev-parse', 'HEAD') == upstream
    finally:
        host.kill()
        process.wait(timeout=10)
        os.close(leader)
