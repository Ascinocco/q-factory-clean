# Local GitHub and Jyra reconciliation

This is an on-demand, explicitly bounded operation: outbound GitHub reads through
local `gh` authentication, and public loopback q-core API reads/writes. It needs
no webhook, tunnel, background service or GitHub write permission. It does not
fetch Git objects, edit descriptions, merge PRs, deploy, or mark tickets done.

## Link work explicitly

Put an exact standalone declaration in the PR body, outside code fences or HTML
comments, and in the final trailer block of at least one current PR commit:

```text
Jyra-Ticket: bbbbbbbb-bbbb-4bbb-8bbb-ab1234567890
```

The example is synthetic. Use the selected ticket's canonical UUIDv4. Commit
trailers follow a blank line after the commit message. A mention in ordinary
prose, a quoted example, an old force-pushed commit or a malformed identifier is
not linkage. This first version requires the PR body and all declared commit
trailers to link only the selected ticket. Multi-ticket PRs need an explicit
workflow decision rather than guessed allocation.

## Preview, inspect, apply

```sh
python -m q_factory.reconcile --root /path/to/q-factory \
  --project PROJECT_ID --board BOARD_UUID --ticket TICKET_UUID \
  --pr https://github.com/OWNER/REPO/pull/PR_NUMBER
```

Use `--self` instead of `--project` only for q-factory's own project, board and
origin as documented in `q-factory.toml`. Managed projects resolve their registered
submodule and board; an arbitrary repository or another project's ticket is
refused. `--api-url` defaults to `q-factory.toml`'s q-core origin.
`Q_CORE_API_TOKEN` comes from
the environment or the factory root `.env`; `gh` handles GitHub authentication.
Errors do not echo tokens or remote diagnostic bodies.

Preview prints JSON with selected PR snapshots, current/proposed status,
`expected_transition_id` and `receipt`. Inspect it, then repeat the same command
with:

```text
--apply --expected-transition PREVIEW_HISTORY_UUID --expected-receipt PREVIEW_RECEIPT_UUID
```

Apply re-reads the evidence and refuses a changed receipt or history. The API
checks the latest transition UUID under a SQLite writer lock before writing the
status and receipt together. Checking an event UUID detects even a same-second
human status roundtrip; comparing status or a timestamp alone would not.

The history note records a deterministic receipt and explicit PR URLs. A lost
response is recoverable by previewing again: an existing receipt makes a repeat
a no-op, even if a human has changed the ticket since. Descriptions are preserved.
The command applies one ticket atomically; separate ticket invocations may finish
independently. Stop and inspect failures rather than continuing a blind batch.

## Status and review ownership

By default apply records evidence with the current status. It never treats a
commit, merged PR or a green native GitHub review state as ticket acceptance.

For explicit owned-work advancement, add `--advance-owned --actor WORKER_NAME`
and repeatable `--review-author EXPECTED_GITHUB_LOGIN`. The ticket’s `claimed_by` and latest non-sync history actor must both match
the requested worker; writing a sync receipt cannot transfer ownership.
Only owned `agent_coding`, `in_progress` or `review` states can change:

- Current changes-requested evidence returns work to `in_progress` for correction.
- All selected PRs open or merged with valid approved review evidence can move to
  `review`; acceptance and project/epic integration remain separate.
- Closed without merge, draft, stale, incomplete or unknown evidence retains the
  current status and requires inspection.
- Human-owned, backlog, blocked and done states are preserved.

Approval requires the strict `factory-review:v1` stamp from the expected author
in a GitHub PR **review**, scoped to this repository, PR and exact current head
and base. Native review `commit_id` must match that head. PR body text and issue
comments cannot certify review. A native review without a valid protocol stamp cannot advance work. Native
changes-requested reviews cannot be hidden by an earlier approval stamp; stale or unexpected-author blockers prevent automatic
advancement. The shared protocol parser validates review completeness. This is
not a proof that every discussion is resolved or permission to merge. Reconciliation
validates the stamp's `criteria_digest` shape but does not recompute it from the
current ticket/epic specification. Its verdict reports PR-stamp state only. Before
merge or completion, the coordinating review workflow must recompute and compare
the current specification digest, inspect every finding and verify thread
resolution. A changed specification invalidates acceptance even if head/base still
match.

## Bounded PR selection and pagination

Pass every intended PR with repeated `--pr`. Later reconciliations must include
all PR URLs recorded by earlier reconciliation receipts. The command does **not**
claim to discover every GitHub PR associated with a ticket; first-use scope is
explicitly the selected set. It never completes a ticket, even if all selected
PRs merged, so an undiscovered follow-up cannot prematurely close work.

GitHub commits and reviews use `gh api --paginate`, decoding successive JSON
arrays without requiring newer CLI flags (validated locally with gh 2.32). Empty
responses, non-array pages and trailing malformed data fail explicitly. Commit
count and head checks reject
truncated lists, including PRs beyond the upstream commits endpoint's supported
list. Jyra histories drain pagination and refuse incomplete pages. The PR snapshot
is rechecked after paginated reads. GitHub and Jyra are separate systems, so there
is no cross-service atomic snapshot: a later GitHub event appears on the next
preview, while concurrent Jyra moves are protected by the atomic precondition.
