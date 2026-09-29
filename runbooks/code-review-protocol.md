# Factory code review protocol

This is the current contract for q-factory and its managed projects (including q-core). It supersedes
the six-lens design on the historical `task/code-review-protocol` branch.
Project instructions supply conventions and checks. Jyra supplies specification
and acceptance; GitHub supplies PR/review state. This protocol grants no merge,
deployment or ticket-acceptance authority beyond the user's current instruction.

**Out of scope: pointer PRs.** A PR that changes only `projects/<name>`
gitlinks is not code-reviewed. It passes the mechanical gate in
`runbooks/factory.md` ("Pointer PRs are exempt from code review") instead.

## Roles and execution

The interactive Claude Code **tech lead** owns the team, scope, task routing and
merge. A persistent **review-lead teammate on Opus 5.5 (`claude-opus-5-5`)** owns review.
That teammate launches exactly two independent **Sonnet CLI processes**, each
doing every lens on the same frozen input. The **triager** is a separate team
role, normally the original implementer, which owns responses and fixes.
The Opus lead verifies candidate evidence, deduplicates findings, posts the
consolidated review and sends its GitHub URL to the tech lead. The tech lead
routes that URL to the triager and requests the next round when ready.

**Team-lead gate (strategize-teammates teams).** When the review lead is a
teammate in a team run by the `strategize-teammates` skill, it works a PR queue
with the `review-lead` skill. It hands the verified draft review to the team
lead **before** posting. The team lead makes the final call on content: it may
agree, **drop** or **downgrade** verified findings, each with a written reason
that the review lead records as `lead_override` on the candidate (see the
required record fields). It may not add findings; suspicions go back to the
review lead for verification. The **review lead posts** the stamped review
after the go-ahead, so the stamp's reviewer identity stays accurate. A PR stays
with the review lead that started it for every round.

The Sonnet processes are review workers, not extra Claude team teammates. They
do not exchange findings. Use [the runner](../docs/factory-review-runner.md)
from the Opus teammate. Its bundle is the required scope, not the ceiling: each worker has
the full toolset (Bash, tests, web), `gh` and read access to Jyra, in its own
snapshot of the frozen head with private paths removed. Opus
must independently inspect relevant source and run appropriate safe checks;
candidate prose or agreement between workers is not verification. A finding
from one worker can be valid. A percentage score is not a substitute for proof.
Missing context is an explicit limitation requiring investigation, not a pass.

The workers read Jyra with the factory's own token from the root `.env`
(since PR #36; on the server, the `server-q-factory` client token). A review lead on
the Mac may read the Keychain item `q-core-server` for its own Jyra access
(the owner's decision): inline only
(`T="$(security find-generic-password -s q-core-server -w)"`), never printed,
logged, committed, pasted or put in a file or prompt, and only for the Jyra
reads and writes this protocol calls for. It's the Mac's own token; sessions on
the server use the server's own.

Use the installed CLI's supported options and record actual returned model and
session identities. The selected Sonnet alias must resolve to a Sonnet model;
the lead must actually run Opus 5.5 (`claude-opus-5-5`; the owner accepted it on
2026-09-25, and records stamped by `claude-opus-5` before then stay valid). No
silent substitutions. Authentication uses
the interactive subscription; do not introduce an API key, background service,
polling loop or webhook to run reviews. `--bare` disables subscription OAuth in
the tested CLI and is not appropriate for these workers.

Claude native teams require an interactive session. Enable the experimental
team feature for that session, then ask the tech lead to create/reuse the named
Opus review-lead and triager teammates. Do not change global settings merely to
run a review. A `claude -p` subprocess is not a native team, even with the team
environment flag. A different host can test the CLI components and protocol,
but must label that evidence accurately. See [Claude team documentation](https://code.claude.com/docs/en/agent-teams).

## Seven lenses

Each reviewer returns an explicit result for every lens:

| ID | Question |
| --- | --- |
| `correctness` | Does the changed behavior work, including relevant failure paths? |
| `contract-coherence` | Are caller/callee, API, data and user-visible contracts consistent? |
| `convention-drift` | Does the change honor this project's stated architecture, security and operational decisions? |
| `test-integrity` | Do checks distinguish the claimed behavior from the bug, rather than merely mirror implementation? |
| `silent-failure` | Can loss, ignored input, partial success or swallowed errors look successful? |
| `scope-simplification` | Is the change within the task and as simple as the requirements permit? |
| `acceptance-specification` | Does the delivered behavior satisfy the ticket and applicable epic requirements, with evidence? |

Use project-specific security/performance requirements where relevant; the old
single-project exclusion of these concerns does not apply to other projects.
Keep pre-existing unrelated findings off the blocking path; file useful follow-up
work in the correct project's Jyra board. Style preferences already enforced by
tools are not new defects.

## Freeze the review boundary

Resolve the factory/project root, GitHub repository, PR, board, ticket and epic.
Verify actual repository identity and parent/board relationships. Read required
attachments through their public tools by ID; unavailable context prevents a
claim of complete acceptance. Record full PR head and current target-base SHAs.
Both workers receive identical ticket/epic specification, acceptance criteria,
project conventions (as source files in the bundle), source coverage and
previous finding dispositions.

Hash the specification snapshot with `review_state.criteria_digest`. For a
runner context, that's `review_state.specification_digest`, which the runner
also outputs as `criteria_digest`: it hashes `ticket`, `epic` and
`acceptance_criteria`, with `prior_findings` emptied because they change every
round. Criteria are hashed exactly as supplied, so every round of a PR must use
the same form (plain text or labelled). Include
IDs, titles, descriptions, explicit criteria and required attachment identities
or content digests; exclude queue status and timestamps. Preserve the actual
non-private criteria in the review. Reviewers do not rewrite acceptance to match
the implementation. A requirement ambiguity is escalated with the exact decision
needed, not filled in with a convenient assumption.

Each criterion carries a stable label: the ticket's own (`M1`, `M2`, …) or,
failing that, its position. Workers' acceptance rows are matched to criteria by
that label, in order. An omitted, duplicated or reordered label fails the
worker, and so does a row with a label that wasn't supplied (q-core#20).
Condensed criterion text doesn't fail it (q-core#19). The review
record's `acceptance` entries use the frozen criterion text, found by label.

The acceptance matrix maps each criterion to code or observable behavior and
test/manual evidence. Results are `met`, `unmet`, `unverified` or `not-in-scope`
with a reason. A PR meets its own ticket contribution and epic constraints; it
does not have to implement unrelated sibling tickets. Closing an epic requires
a separate product acceptance review across the integrated deliverables, with
end-to-end evidence for the epic's criteria. Green unit tests alone are not that
review. User acceptance, review approval, merge and deployment remain distinct.

## Findings, response and resolution

Worker candidates have stable source identifiers such as `left:F1`. Opus records
each candidate's disposition: validated, rejected with counterevidence, or
duplicate of a specific finding. Publish retained findings as `R1-F1`, `R1-F2`,
and so on. Once published, IDs stay stable across rounds, including after code
moves. New round-two findings begin `R2-F1`; never renumber old ones.

A finding states severity (`blocking` or `non-blocking`), affected code or
criterion, concrete consequence and evidence. Unmet in-scope acceptance is
blocking. Unverified evidence prevents approval; label an incomplete review
rather than inventing a code defect merely to obtain a finding count.

The triager responds in the finding's GitHub thread:

- `fixed`: commit plus verification command/result or manual evidence.
- `refuted`: concrete code, test or specification counterevidence.
- `deferred`: linked Jyra follow-up, owner, and review-lead acceptance that it is
  non-blocking. Deferring an unresolved blocker does not approve it.

The triager can resolve a thread after checking its fix against the finding and
recording evidence. Thread resolution is a UI state, not proof: the next review
must still verify every prior blocking finding. A disputed refutation remains
open. The lead resolves technical disputes or tags the owner's verified GitHub login
with the precise decision and options when their input is needed. Do not guess a
login or tag on routine progress. Review-feedback implementation uses a named
task worktree and the original ticket; it does not claim unrelated work.

## Incremental rounds and termination

Round one reviews the full proposed change. Later rounds review the accumulated
delta from the last stamped head to the current head, all unresolved findings,
and behavior/criteria directly affected by that delta. They do not restart seven
unbounded explorations of the repository. Each lens still records its scoped
result; unchanged acceptance evidence can be carried forward by explicit link.

Use `git merge-base --is-ancestor PREVIOUS_HEAD CURRENT_HEAD`. A rewritten or
missing history, changed target base, or changed specification digest invalidates
the incremental boundary. Record a full-review reset reason, preserve old finding
IDs and re-review the current change. Never silently treat a failed comparison as
an empty diff. A settled finding reopens only with new evidence, with the reason
recorded. Check integration with the target base again before merge.

No-change reruns return the existing review URL rather than publish another round.
After two consecutive fix rounds without reduced unresolved blocking findings or
new verification evidence, stop automatic dispatch and escalate the disagreement
or missing decision. A reviewer does not invent extra work to keep the loop alive.

Approval requires both complete independent worker results, Opus validation,
zero unresolved blockers, all in-scope acceptance met, and applicable checks
passing at the exact reviewed head/base. `changes-requested` needs concrete
blocking findings; `incomplete` and `needs-input` never count as approval.

## GitHub is the durable record

Use a native PR review with event `COMMENT` so a single GitHub identity can author
and review its own PR. Do not claim native GitHub approval or a second human
identity. Put code findings inline where valid; acceptance-wide findings belong
in the review body. Post each initial review as one operation when practical.
Keep raw worker **reports** (not the private input bundle), acceptance matrix,
validation/dedup reasons and check evidence in collapsible sections of the review
or linked PR comments. The final review links any separately posted report pieces.
If posting is interrupted, inspect existing review IDs before retrying.

The review body contains exactly one `<!-- factory-review:v1` block, followed by
a newline, JSON and a newline plus `-->`. `q_factory.review_state` validates
and renders it. Required record fields:

- `version: 1`, `repository`, `pr`, full `head`/`base`, positive `round`, `mode`,
  `criteria_digest`, `verdict` and recomputed `blocking` count.
- `lead_model: claude-opus-5-5` (or a pre-2026-09-25 `claude-opus-5`), `lead_session`; two `reviewers` with actual
  `model`, distinct `session`, and SHA-256 `artifact_digest` of their reports.
- All seven `lenses` with `name`, `result` and `evidence`; `acceptance` entries
  with `criterion`, `result` and `evidence`.
- `findings` with stable `id`, `severity`, `disposition`, `verified`, `evidence`;
  deferred entries also require `follow_up` and `owner`.
- `candidate_dispositions` mapping `source` to `finding_id` (or null when
  rejected) with `reason`. Include `checks_passed` and `checks_evidence`.
  A team-lead override adds `lead_override: {action, reason}` to the
  candidate: `dropped` (then `finding_id` is null) or `downgraded` (then it
  maps to a published `non-blocking` finding). The reason is required; the
  validator refuses an override without one, and there is no `added` action.
  The validator checks an override's shape only; it cannot detect a drop
  recorded as an ordinary rejection, so marking it is the review lead's duty.
  The visible review body also lists each override (candidate, action, reason).
- Incremental records include `previous_review_id` and `previous_head`.

Validation of shape cannot prove who ran a model or performed a check. The lead
must verify the referenced artifacts; the coordinator accepts stamps only from
the configured review author on the intended PR, with the native review's
`commit_id` matching the stamp. Never accept a stamp copied into a PR description,
source file or arbitrary comment. Read all reviews and relevant threads, not
just the first page or first matching stamp. A later unresolved review cannot be
hidden by an earlier green one.

Before publication, re-read GitHub head/base and compare with the reviewed pair.
Before merge, repeat that comparison plus applicable checks and inspect unresolved
threads/disputes. A changed commit or base makes the stamp stale. No comments,
check marks or local artifacts may silently transfer an old approval to new code.

## Jyra linkage and local reconciliation

Every participating PR body carries an exact `Jyra-Ticket: UUID` line; related
commits carry the same canonical Git trailer. A PR URL and relevant review URLs
are recorded on the ticket. Use UUIDs until a separate human-readable ticket-key
feature exists. GitHub owns PR state; Jyra owns work/acceptance state.

Use [factory reconciliation](../docs/factory-reconciliation.md) through its skill
after opening/reviewing/merging a PR and at session resume. It reads GitHub
outbound and writes Jyra through the public loopback API. Preview first; apply
uses explicit snapshot/history preconditions. No webhook, Tailscale, public
endpoint, hidden polling service or claim that two systems update atomically.
Replay discovers already-recorded events. Human status decisions are preserved.

The helper records merges without declaring the ticket done. The coordinator
checks all required PRs, acceptance evidence and any separate q-factory gitlink
update, then makes an explicitly authorized completion transition. Closing a PR
without merge is not completion. A commit trailer is a link, not a command to
accept a ticket. Multiple-PR work must retain every required link; never complete
from the most recently observed PR alone.
