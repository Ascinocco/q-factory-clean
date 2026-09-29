# On-demand factory CLI

Run from the q-factory checkout with its Python environment. The selected root
must be a prepared q-factory checkout. The default root is the checkout containing
the installed module; explicitly select another checkout with `--root`.

```sh
python -m q_factory --root /path/to/q-factory status
```

The command reads project entities and their associated boards through the public
q-core API, then reads Git metadata. It does not fetch, initialize submodules,
claim tickets, repair checkouts or mutate the API. JSON output includes pinned
and checked-out commits, dirty/detached state, registered worktrees, and each
board's ready/coding/review/blocked counts. Non-software projects are counted as
unmanaged. Counts represent all matching ticket types, including planning tickets.

Unavailable Git information or board counts are `null` with an explicit error.
One broken checkout or board does not hide other projects. Failure to read the
project registry fails the command with exit 1; per-project failures remain in
the report and do not change its exit status. Pagination inconsistencies are
reported as failures rather than silently displaying incomplete counts. These
reads are an overview, not an atomic snapshot of concurrent board changes.

The q-core API origin comes from `[q_core] api_url` in `q-factory.toml`; pass
`--api-url` before the command to override it. Accepted origins are loopback
HTTP(S) with an explicit port, or `https://<machine>.<tailnet>` (the q-core
Tailscale Serve URL) for the one tailnet pinned as `[q_core] tailnet`; with no
tailnet pinned, loopback only. Authentication uses `Q_CORE_API_TOKEN`
from the environment or the factory root's
`.env`. Tokens,
remote URLs and HTTP response bodies are not printed. Redirects and proxy
environment variables are disabled.

## Worktree commands

Select a project by exact ID or unique exact name. If it has multiple boards,
`--board` must explicitly name the associated board ID. Worktree commands resolve
the registry and refuse duplicate path assignments, missing projects or ambiguous
boards before changing Git state.

```sh
python -m q_factory --root /path/to/q-factory worktree list --project PROJECT_ID
python -m q_factory --root /path/to/q-factory worktree start \
  --project PROJECT_ID --board BOARD_ID --ticket TICKET_UUID \
  --task scoring-feature --base origin/main --owner worker-name
python -m q_factory --root /path/to/q-factory worktree finish \
  --project PROJECT_ID --board BOARD_ID --task scoring-feature \
  --owner worker-name --merged-into origin/main --inactive
```

A ticket on an **initiative board**, one attached to a different entity with
no repository of its own (an initiative), names the project whose repository
holds its code. Start it with `--ticket-board` in place of `--board`:

```sh
python -m q_factory --root /path/to/q-factory worktree start \
  --project Q_CORE_PROJECT_ID --ticket-board INITIATIVE_BOARD_ID --ticket TICKET_UUID \
  --task initiative-a6 --base origin/main --owner worker-name
```

The project's own board isn't needed then. The ticket board must exist and
must not be the project's own board (use `--board` for that); the two flags
can't be combined. The ownership record adds `project_id`, `ticket_board_id`
and `ticket_board_entity_id`; records from `--board` starts are unchanged.
`finish` and `list` work through the project as usual.

Start requires a real ticket UUID belonging to the selected board. It does not
claim the ticket: follow the project delivery skill before starting implementation.
The base is explicit and uses locally available refs; fetching remains a separate
deliberate step. Finish delegates ownership, cleanliness and ancestry checks to
the Git helper. Supply `--inactive` only after confirming no worker is using the
checkout. Cleanup retains the task branch and refuses files that would be lost.

Commands print JSON to stdout on success and a concise JSON error to stderr with
exit 1 on refusal. CLI syntax errors use argparse's standard exit 2.

## Stage a verified project pointer

```sh
python -m q_factory --root /path/to/q-factory pin \
  --project PROJECT_ID --board BOARD_ID \
  --commit ACCEPTED_COMMIT_SHA --expected-old RECORDED_COMMIT_SHA
```

Both SHAs must be full lowercase 40-character commit IDs. This command explicitly
fetches the requested commit into a disposable repository to verify remote
availability and ancestry, then updates only the selected project checkout and
stages its gitlink. It requires a named factory branch and no unrelated parent
changes. It never commits or pushes. The API remains GET-only; `status` still
performs no fetch or Git mutation. Repeat results distinguish `staged`,
`already_staged`, and `already_recorded`.

Supply the accepted commit after the authorized project review/merge workflow;
this helper cannot attest PR review. See the [integration procedure](../runbooks/factory-integration.md)
for exact-commit evidence, concurrent pointer changes, clean-clone validation and
recovery.
