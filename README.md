# q-factory

The software factory: managed projects as Git submodules under `projects/`,
isolated task worktrees, Jyra-driven delivery, and the seven-lens review
protocol. Services it talks to (such as the q-core API) live in their own
repositories.

## Setup (any machine)

```sh
git clone git@github.com:Ascinocco/q-factory-clean.git
cd q-factory-clean
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
echo 'Q_CORE_API_TOKEN=...' > .env   # a q-core token for this machine; never commit it
.venv/bin/python -m pytest            # q-core is not required
```

`q-factory.toml` names the q-core API origin: the server's Tailscale Serve URL.
The committed values are placeholders; set the real host, tailnet and Jyra ids
locally.
The token is this machine's own `full` client token from q-core's `/ui/tokens`.
Keep it in the untracked root `.env`, as above: `q_factory` reads it from
there, so only the factory's own commands see it. On the Mac the token also
lives in Keychain as `q-core-server`; to use it without a file, set it for a
single command:
`Q_CORE_API_TOKEN="$(security find-generic-password -s q-core-server -w)" .venv/bin/python -m q_factory ...`.
Avoid exporting it from a shell profile: that hands a full-scope token to every
process the shell starts, Claude Code sessions and their agents included.

Then open a Claude Code session in this folder; `CLAUDE.md` explains the rest.

## Start here

- Rules and routing: [`CLAUDE.md`](CLAUDE.md)
- Runbooks: [`runbooks/INDEX.md`](runbooks/INDEX.md)
- CLI: [`docs/factory-cli.md`](docs/factory-cli.md)
- Integration tests against a real q-core checkout: `tests/integration/conftest.py`
