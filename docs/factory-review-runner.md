# Subscription review runner

Run from the q-factory Python environment (it needs `jsonschema`; without it
the runner refuses before starting any reviewer). From a bare checkout, prefix
the command with `uv run --with-requirements requirements-dev.txt`:

```sh
python -m q_factory.review_runner --input /path/to/context.json \
  --output /path/to/candidates.json
```

`--timeout` is per worker and defaults to 3600 seconds. It only exists to stop a
hung worker, so there is no upper bound; raise it for a PR whose tests are slow.
The workers read Jyra with q-factory's own q-core origin (`q-factory.toml`) and
token (`Q_CORE_API_TOKEN` in the environment or the root `.env`); without a
token the runner refuses before starting them.

The input names a checked-out repository whose HEAD is the frozen full SHA.
All paths changed in either base-to-head or previous-review-to-head must be
explicitly selected, including deletions and changes reverted to the base. Include
unchanged dependency files needed for meaningful review. The runner reads Git
blobs at the base/head (and previous reviewed head for incremental review),
never dirty working files. It refuses symlinks, submodule gitlinks, binary
content and private/runtime paths. Bundle size is not capped: the bundle
reaches each reviewer on stdin, and one too large for the reviewer's context
fails the pair with an error naming the bundle size rather than being
truncated. A partial/truncated bundle is not a complete review.

Input JSON shape (replace illustrative paths/SHAs):

```json
{
  "repository": "/absolute/project/task-worktree",
  "head": "FULL_40_CHARACTER_COMMIT_SHA",
  "base": "FULL_40_CHARACTER_BASE_SHA",
  "previous_reviewed_head": null,
  "context": {
    "ticket": {"id": "ticket-id", "title": "Requested change", "description": "Frozen ticket specification"},
    "epic": null,
    "acceptance_criteria": [
      {"label": "M1", "criterion": "**M1** Observable required behavior"},
      {"label": "M2", "criterion": "**M2** Another observable behavior"}
    ],
    "prior_findings": []
  },
  "files": ["src/changed.py", "src/dependency.py", "tests/test_changed.py"]
}
```

`context` takes exactly these four keys; any other key is refused by name.
Project conventions are not a context key: add the project's convention files
(its `CLAUDE.md`, and any runbook the change must honor) to `files`, so both
reviewers read them at the frozen head. Don't paste them into the ticket
description; that changes the frozen specification and its criteria digest.
The criteria digest (`review_state.specification_digest`, also in the runner's
output) hashes the context with `prior_findings` emptied, so it covers `ticket`,
`epic` and `acceptance_criteria` and stays the same across rounds while they do.
It covers the criteria **exactly as supplied**: plain-text and labelled forms of
the same criteria give different digests, so every round of a PR must use the
same form.
An epic, when present, has the same `id/title/description` shape as the ticket.

Each acceptance criterion is either `{"label", "criterion"}` or plain text.
Give the ticket's own label (`M1`, `M2`, …) when it has one. Plain text is
labelled by its position (`"1"`, `"2"`, …), so older inputs still work. Labels
must be nonempty, have no surrounding whitespace and be unique. The bundle
carries every criterion with its label. Reviewers return one acceptance row per
criterion, in order, echoing the label exactly and the criterion text verbatim
where they can, and no rows of their own. **Rows are matched by label, not
text**: a row whose label wasn't supplied, such as one a reviewer added for the
ticket's "Human acceptance criteria: None" line (q-core#20), fails as an
unexpected criterion row. Labels that aren't exactly the supplied ones in
order (an omitted, duplicated or reordered row) fail as omitted or reordered.
Both reasons name the offending labels (`missing "M2"`, `duplicate "M3"`,
`out of order`). A reviewer that condenses a long criterion still passes. The returned `criterion` text is informational;
the lead maps each row back to the frozen criterion by its label.
Freeze its relevant requirements instead of letting reviewers fetch mutable
board state. Context must contain no private documents, secrets or credentials.
Path screening is a guard against common private/runtime files, not a secret
scanner: the coordinator must inspect the selected material before disclosure.

For incremental review, supply `previous_reviewed_head` and
`previous_reviewed_base`. The prior head must be an ancestor and the prior base
must equal this review's base. Prior findings are objects with a nonempty
`disposition` explaining their current state and enough original evidence to
reassess them. A rewritten history or changed base requires a full review:
set previous head to null and record `full_reset_reason`. An incremental pass applies all seven lenses only to the previous-head-to-head
delta, unresolved prior findings and affected acceptance criteria. Supply those
criteria in the context. Base snapshots/full diff are background; resolved
findings are not redispatched unless the delta reintroduces them. A full reset
reviews the whole base-to-head change.

## Isolation and authentication

Two fresh CLI sessions receive byte-identical bundles and the same
review instructions. Each runs in its own temporary directory holding a
snapshot of the repository at the frozen head: `git archive` of the committed
tree, never untracked or dirty files, links or submodule contents, with every
path the bundle would refuse (`intake/`, `data/`, `.env*`, credentials,
databases, etc.) removed. The bundle is the required scope, not the ceiling.
Reviewers have **every tool they need to validate the change** (the owner,
2026-09-26): the full default toolset with Bash, so they can run the tests and
scripts and install dependencies in their snapshot, plus web search and fetch;
`gh` with your GitHub login, to read the PR named by the optional
`pull_request` input (`OWNER/REPO#NUMBER`); and the q-core MCP, to read the
ticket, epic, board and history in Jyra. Permissions are bypassed inside the
worker, so nothing stops for approval.

The instructions tell workers never to kill processes by pattern (the factory's
process-safety rule), never to write to Jyra or GitHub, never to use
q-core's financial, document or inventory tools, and never to read outside
their snapshot. With Bash running as you, that's an instruction, not a
sandbox. The token and the private paths are kept out of the snapshot, and the
token goes to the CLI in a private MCP config file, never on its command line.
Empty setting sources and disabled skills/session persistence keep your user
and project hooks, plugins and settings out. `--safe-mode` is not used,
because it also switches off the q-core MCP. Workers have no shared
conversation and no access to each other's results. Source text is untrusted
review data, not agent instructions. The runner is an on-demand CLI pair, not a native interactive
agent team, standing service or autonomous approval mechanism.

The installed `claude` CLI must report first-party `claude.ai` authentication.
The helper refuses API-key/provider environment variables and forwards only a
small environment allowlist. Subscription/keychain authentication remains
available: **do not add `--bare`**, which disables OAuth/keychain access. No
fallback model is requested. Actual `modelUsage` keys must include Sonnet;
auxiliary Haiku is allowed, other families or missing model evidence fail.
Administrator-managed policy still applies, so runtime failures or a model
policy mismatch stop this helper rather than silently loosening its settings.

## Evidence and limits

Each pass returns all seven lens statuses/summaries, concrete candidate
findings, limitations and an ordered, labelled acceptance matrix (`met`,
`unmet`, or `unverified`). Missing context is reported with an `incomplete` lens.
Workers may run the tests and scripts in their snapshot. Their results are
evidence for the review lead to verify, not to trust. The report preserves both
independent results, actual model IDs, session IDs, bound full/incremental mode,
previous reviewed head, frozen commits, a bundle digest (`bundle_sha256`) and the
record's `criteria_digest`. It never labels the change approved. The review lead must validate findings, check
behavior/tests independently, deduplicate and post the review record under the
project's review protocol.

Once the reviewers have started, the runner always writes its output, and
nothing a reviewer produced is thrown away. Each review carries a `status`:
`complete`, or `failed` with a `reason` (nonzero exit, timeout, oversized
bundle, malformed JSON, invalid schema including a row without a label, wrong
model/session/head/mode, an unexpected criterion row, or acceptance labels
that differ from the supplied ones in order) and the reviewer's `raw_output`
when it produced any. The pair's `status` is
`candidates_require_lead_validation` only when both reviews are complete;
otherwise it is `incomplete`, or `stale` when HEAD moved during the run. The
CLI exits 1 for anything but a complete pair, naming each failure. An
incomplete or stale pair is evidence to inspect, never an approval: the review
record still needs two complete reviewers. A finding may cite any repository
path. One outside the supplied `files` is kept with `out_of_bundle: true`, for
the lead to verify against the source. The runner doesn't validate that ticket
text is still current remotely; the lead owns that check. A valid report
containing incomplete lenses still requires missing coverage to be resolved
before acceptance.

Output is created with private permissions and will not overwrite previous
evidence. Keep it outside the project source unless explicitly publishing
reviewed, nonprivate evidence. Subprocess stderr/auth metadata are deliberately
not printed. No GitHub posting or repository mutation is performed.
