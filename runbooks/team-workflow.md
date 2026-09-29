# Team workflow: persistent teammates, worktrees, PRs

How build-mode work on this repo gets executed once more than one
teammate is involved. Supersedes ad hoc `superpowers:subagent-driven-development`-style
dispatch (spin up a subagent per task, kill it when the task lands) as the
default execution path for this repo's own development — plan production
(brainstorming, `writing-plans`) is unchanged, only *dispatch* of the
resulting plan's tasks changes.

## Current routing and historical scope

Start managed-project work with [the factory guide](factory.md). It is the
current concise delivery procedure. This document preserves the evidence and
lessons from earlier runs in a predecessor repository: fixed team sizes, model names, old worktree
paths and autonomous-run grants below describe those runs, not prerequisites
or standing authorization for every project. Use the available harness and
current session authority. Project-specific deployment follows that project's
instructions; it must not restart the personal services.

Jyra is the authoritative backlog. `project-management.json` is frozen;
references below to allocating IDs or updating it are historical only.

The current [factory review protocol](code-review-protocol.md) replaces the
historical single-reviewer mechanics below: an interactive Claude team's Opus 5
review-lead teammate launches two independent Sonnet CLI workers, validates and
deduplicates their seven-lens findings, and posts exact-commit review state on
GitHub. The tech lead routes the review to the triager/implementer and subsequent
incremental rounds. Native team support is a host capability, not something a
print-mode CLI process can claim. Use the corresponding review/response skills.

## Roles

**Current team shape (2026-09-25):** use the `strategize-teammates` skill.
The team lead sizes **2–4 implementation and 1–2 review-lead teammates** (full
Opus 5.5 sessions in tmux panes) to the work. That supersedes the fixed
3 + 1 + 1 ad hoc structure below, which is kept as the record of the earlier
runs. Review leads follow the `review-lead` skill.

Historical structure:

- **Tech lead** — the coordinating session (not a spawned teammate). Owns
  dispatch, task sequencing (no two active tasks touch overlapping files),
  merge order, and conflict resolution. Reads/updates this file and
  the target project's Jyra board.
- **3 implementation teammates** — long-lived, one task in flight at a
  time each, picked up via `SendMessage` rather than a fresh `Agent` spawn
  per task.
- **1 code review teammate** — long-lived, reviews every PR before the
  tech lead merges it.
- **Occasional 5th, ad hoc** — spun up for a single fresh-eyes look at a
  specific narrow question (a spike, a second opinion on an approach) and
  stopped (`TaskStop`) once it answers that question. This is the only
  role meant to be short-lived.

All 5 roles run on Opus 5 (`model: "opus"` on the `Agent` tool). Steady
state is 4 persistent + up to 1 ad hoc = 5 concurrent, checked via
`ListAgents` before spawning anything new — dispatch to an existing
teammate instead of spawning a duplicate of an already-filled role.

## Process safety

Never use pkill, killall or any other pattern-matched kill. Stop only
processes you started, by their recorded PID or your own process group,
and never touch system services or other users' processes. Hosts such as
the server are shared with production and other agents.
Put this rule in every teammate brief. The review runner puts it in every
worker's prompt.

## Git mechanics

One task = one worktree = one branch = one PR.

```bash
git worktree add .claude/worktrees/<task-slug> -b task/<task-slug> main
```

- Implementation teammate does the task in that worktree, commits, pushes,
  opens a PR (`gh pr create`) into `main`.
- Review teammate reviews the PR (correctness, and against this repo's own
  conventions — `runbooks/decisions-log.md`, `CLAUDE.md`) and either
  approves or leaves findings for the implementation teammate to address
  in the same branch.
- Tech lead merges once approved, then removes the worktree:
  `git worktree remove .claude/worktrees/<task-slug>`.
- Branch naming: `task/<slug>`, slug matches the plan's task name closely
  enough to trace back to it.
- **Before opening a PR that adds a route, an MCP tool, a table, a
  migration or a skill, regenerate the system inventory:** `python
  scripts/system_inventory.py --write`, and commit the result.
  `docs/SYSTEM.md` embeds a block derived from the tree and
  `tests/test_system_doc.py` fails when the two disagree. Skipping it
  does not fail your branch — it fails the **composed** suite, in
  whichever PR the tech lead merges next, which is someone else's.
  That asymmetry is the reason this is a listed step rather than a
  habit: the person who pays is not the person who skipped it.
- **A spawned teammate inherits whatever cwd the spawning session happens
  to be in at that moment.** This is the most common way two sessions end
  up anchored to the same worktree, and it's silent on both sides — the
  tech lead doesn't choose it and the teammate has no way to know its cwd
  wasn't deliberate. A tech lead who `cd`'d into a task worktree to run a
  verification probe, and then spawns a teammate, hands that teammate the
  probed worktree as its primary working directory rather than the main
  checkout (observed directly: an ad hoc teammate was spawned into
  `.claude/worktrees/task-validation-envelope` — the live head of another
  teammate's open PR — immediately after the tech lead ran a check there).
  The teammate's own brief will often say something different ("your
  working directory is the main checkout"), which is exactly what makes it
  worth verifying instead of trusting. Both halves of the fix are needed:
  - **Tech lead:** don't spawn from inside a task worktree. Run probes as
    inline `cd <path> && ...` so the session's own cwd never moves, or
    return to the main checkout before spawning.
  - **Teammate:** on startup, check `pwd` and `git worktree list` against
    what your brief claims, and say so if they disagree rather than
    assuming the brief is right. If you've landed in someone else's task
    worktree, treat it as read-only — no writes, no scratch files, no
    branch-switching git commands — and use inline `cd` for everything
    else until you cut your own worktree.
- **Before removing a worktree, confirm with its owning teammate that
  nothing of theirs is still using it — don't assume either way.** Whether
  a teammate's shell cwd persists inside a worktree between messages or
  resets per command is harness-dependent — some do, some don't (observed
  directly: one teammate's cwd reset to its own session worktree after
  every `Bash` call regardless of what it `cd`'d into mid-command, another
  genuinely persisted). Ask it to confirm it's clear (a `pwd` plus, if
  unsure, `lsof +D <path>` for open file handles) rather than telling it
  to "`cd` out" as if the persistence model were universal. Skipping this
  risks pulling the floor out from under a live session mid-task. **Check
  with every teammate, not just the one you suspect** — two teammates can
  independently be anchored to the same worktree as their primary cwd
  (observed directly: two separate teammates both had
  `.claude/worktrees/api-phase2-entities` as their harness-assigned
  primary working directory, discovered only because both happened to
  mention it unprompted). Absence of a complaint from a given teammate
  isn't confirmation it's clear for them. This only stays harmless while
  every occupant treats the shared anchor as a base to `cd` out of (inline
  `cd <target> && ...` per command, not a persistent `cd`) rather than a
  place to run branch-switching git commands or write scratch files
  directly — flag it explicitly to teammates sharing an anchor rather than
  assuming they'll each independently land on that discipline. Also
  check for untracked files (`git status`) before removing — `git worktree
  remove` refuses to remove a worktree with untracked files without
  `--force`, and `--force` deletes them permanently; look before forcing.

This replaces the older pattern (seen in the Phase 2 entities work) of one
long-lived worktree per *plan* accumulating every task's commits
unreviewed until the whole plan finished — that pattern predates PRs
existing on this repo (`origin` wasn't created until partway through Phase
2) and shouldn't be repeated now that per-task PRs are possible.

## Task sequencing — check for file collisions before dispatching

Before dispatching two tasks to two different teammates at once, diff
their plan's `Files:` sections. If they declare the same file(s) — even
just "modify" on both sides — don't run them in parallel; unlike a stacked
PR (where the second task's work is additive on top of the first's merged
diff and resolves cleanly via merge-base), two teammates independently
editing the same region of the same file at the same time produces a real
conflict neither can resolve alone. Options, in order of preference:
1. **Stack both on one teammate**, second task branched off the first
   task's head (same pattern as a dependent PR — see stacked-PR handling
   below). Best when the second task's work directly consumes the first's
   output and one teammate holding both in context is a win, not just a
   conflict-avoidance measure.
2. **Serialize across two teammates** — second task dispatched only after
   the first merges. Costs wall-clock, frees a teammate slot sooner.
3. **Pre-agreed file split** for genuinely parallel work on the same
   file — usually not worth the coordination overhead for task-sized
   chunks of work; prefer 1 or 2 unless the tasks are large.

## Review mechanics (learned the first time through)

- **Neither `gh pr review --approve` nor `--request-changes` works on this
  repo.** Every PR is opened from the same GitHub account the review
  teammate is also authenticated as, and GitHub rejects any formal review
  state on your own PR outright ("Can not approve your own pull request"
  — the same rejection covers requesting changes, not just approving).
  There is no formal green-checkmark or red-blocker state here and there
  won't be one without a second GitHub identity. The review teammate posts
  its verdict — approve or block — as a regular PR comment instead,
  explicitly labeled as the review gate, and the tech lead acts on that
  comment, not on `reviewDecision`. Don't wait for a native review state
  that will never come, in either direction.
- **A reviewer's suggested patch is a hypothesis, not a spec — implementers
  verify it rather than apply it verbatim.** Observed directly: a
  blocking review on PR #5 shipped a real fix for a real bug, but the
  suggested patch itself had an uninitialized-variable defect that would
  have turned the fix into a 500 on every `leases`/`resides_at` creation —
  the most common dated relationship in this system. The implementer
  caught it by re-deriving the reasoning independently before coding
  rather than trusting the snippet, and the reviewer confirmed the defect
  and credited the catch in their re-review rather than treating it as
  friction. A review comment is the most authoritative-looking place to
  put a mistake precisely because it's a review — that authority doesn't
  make a suggested patch correct, and it isn't exempt from the same TDD
  discipline (write the failing test, prove the patch actually fixes it)
  as any other code. **Extends to a reviewer's offered alternative, not
  just their patch:** on the migration-consistency guard above, the same
  reviewer later offered a second, "equivalent" fix as an alternative to
  the one that shipped. Measured rather than assumed equivalent: it
  passed on the exact bug it was meant to catch. The two approaches
  differed in a way that mattered — one recorded what the schema looked
  like *before* the change, the other only checked the state *after*, and
  the bug in question is invisible to an after-only check by construction.
  An "I'd also consider X" is the same kind of unverified claim as a
  suggested patch; measure it the same way before treating it as a live
  option.
- **A verification attaches to a specific artifact, not to a branch name
  or PR number — the mirror image of the note above.** Observed directly:
  a reviewer verified a conflict resolution locally, the implementer then
  *rebased* (not merged) onto current `main` to apply it, and the
  resulting commit was pushed under the same branch/PR but was literally
  different bytes than what got verified — a rebase can drop or reshuffle
  a hunk silently. The reviewer re-checked the actual pushed commit rather
  than trusting the branch name carried the verification forward, which
  cost two minutes and was the right call given what was at stake (an open
  disclosure path). Skipping a redundant *third* review pass on unchanged
  work is correct economy; skipping re-confirmation after a rebase,
  squash, or force-push is trusting a different artifact than the one
  that was actually checked. When in doubt about which situation you're
  in, re-check — it's cheap next to being wrong about a security fix.
- **Retracting a claim doesn't recall the copies already made of it.**
  Observed directly: a reviewer conflated two bugs, corrected themselves
  a few messages later — but the implementor was already writing a PR
  description from the uncorrected version, and the correction landed on
  the PR and in the tech lead's todo split without reaching the artifact
  someone was actively drafting from. The fix (two factual one-string
  edits) was trivial once caught, but it needed a direct message to the
  specific person still working from the stale version, not just a public
  correction posted elsewhere on the assumption it would propagate. When
  you correct something you said earlier, think about who might be
  mid-task on the old version and tell them directly rather than trusting
  they'll see the retraction before they finish.
- **A plausible-sounding claim about what a test covers needs measurement,
  not just reasoning — the third note in this trio.** Recurred three times
  in one round: a foreign-key test that would have passed vacuously if
  `PRAGMA foreign_keys` were off (it wasn't, but nothing in the test itself
  proved that); a todo's stated rationale for why a bug mattered, corrected
  after the person fixing it measured the actual locking behavior instead
  of trusting the write-up; and a new regression test justified as "closes
  a gap no existing test covers," where mutation-testing both code paths
  it supposedly guarded showed each was already independently covered —
  the test was still worth keeping, just for a different, truer reason
  than the one first given. Writing the extra test kept being the right
  call even when the stated justification for it didn't hold up — which is
  itself the argument for checking the justification: a test kept alive by
  a false premise gets deleted the day someone notices the premise is
  false, even though the test earns its keep on its own merits.

  Fourth instance, one layer down: **the verification tooling itself needs
  checking, not just the thing it's verifying.** A reviewer re-running a
  "confirm no other occurrences" grep wrote `--include=*.py` unquoted; the
  shell glob-expanded it, `grep` errored out, and a `cmd || echo "no
  occurrences found"` fallback fired on that error rather than on a
  genuine zero-match — producing output indistinguishable from a clean
  pass. Caught only because the message read as the fallback text rather
  than grep's own silence. `cmd || echo "all clear"` reports success
  whenever `cmd` fails for *any* reason, not just the expected one — the
  same shape as a test that passes without actually asserting anything.
  When a check's own output is what a claim rests on, look at why it
  passed, not just that it did.

  Fifth instance: **a stress test that never enters the branch it's meant
  to exercise is indistinguishable from one that enters it and passes.**
  Ten OS processes released on a shared wall-clock start still arrive tens
  of milliseconds apart (interpreter startup dominates the jitter) — so
  the first process finished bootstrapping before the others even checked
  readiness, and the losing-racer code path was never reached at all in
  10 of 10 rounds. The stress test's "150/150 passed" was real and proved
  something (end-state integrity under load) but zero evidence for the
  specific guard it was assumed to cover. Only a deterministic test that
  directly injects the failure condition (mutate the code, confirm the
  test now fails) can tell you whether a branch is being exercised and
  succeeding, or not being exercised at all. Prefer the deterministic
  injection test as the actual regression guard; treat a stress/load test
  as evidence for aggregate behavior, not as proof any specific branch
  ran.

  **The name for this shape, across three unrelated tools this session:**
  a mechanism that matches a pattern rather than reads meaning produces
  output indistinguishable from success even when it did the wrong thing.
  `cmd || echo "all clear"` fires the fallback on any error, not just the
  expected zero-match. A stress test that never enters a branch looks
  exactly like one that entered it and passed. GitHub's commit-message
  linkifier matches `close #12` as a substring and closes the PR even
  inside "don't close #12" — it doesn't parse the negation, it pattern-
  matches. Whenever a check, a test, or an integration is built on
  matching rather than understanding, its silence or its pass is not
  proof of the thing you actually care about — verify what the mechanism
  can and can't distinguish before trusting its output.

  **A related, narrower pattern, three instances on its own:** when a
  test's docstring or name states which bug it guards against, check that
  it actually fails when that exact bug is present — don't take the name
  as the proof. A foreign-key test that would pass vacuously if `PRAGMA
  foreign_keys` were off; a stress test whose "150/150 passed" meant the
  guarded branch was never reached; a migrations-consistency test whose
  docstring promised to catch "a table added to `schema.sql` without a
  migration for it" but only checked that a *fresh* install had no
  pending migrations — which is true whether or not the new table has
  one, since a fresh install stamps everything as applied regardless.
  Caught by deliberately reintroducing each bug and confirming the test
  goes red — the same technique as mutation testing, aimed specifically
  at the gap between what a test's name claims and what its assertions
  check. The name is exactly what stops a future reader from looking
  again, so it's the detail most worth distrusting until it's been
  proven true.

  **A related but distinct trap: an old test's *fixture* can encode a
  belief about the system that used to be true and quietly stopped
  being.** A test simulated "a database predating the migration
  mechanism" by dropping one table from an otherwise-current database —
  accurate when written, before a second migration existed. Once it did,
  that simulated state became impossible (a database predating the
  runner also predates everything the runner has since added), and the
  test started asking a later migration to create tables the fixture had
  deliberately left in place. It failed loudly, which is the good
  outcome, but the failure read at first like "my new change broke an
  old test" — and the tempting fix was to adjust the assertion. The
  simulation was wrong, not the code under test. When an old test fails
  against new work, check whether its fixture still describes a state
  that can actually occur before assuming the new code introduced the
  regression.

  **A third variant, this one caught before it ever failed rather than
  after:** a test can be correct today and calendar-dependent, passing
  now and guaranteed to fail later for a reason that has nothing to do
  with whatever anyone touches next. A `/trend` test asserted a
  hardcoded transaction date appeared within a rolling `date('now', '-N
  months')` window — true when written, and true for about two more
  weeks, after which the fixture ages out of the window and the test
  fails in whatever unrelated session happens to be running that day,
  reading as a regression in that session's own change. Caught by
  noticing the dependency on `date.today()` during authorship and
  anchoring the fixture to it instead, rather than to a fixed date.
  Anything that filters or buckets by a rolling window relative to "now"
  needs its test fixtures generated relative to "now" too, never hardcoded
  — the same principle as the other two variants, aimed at a failure that
  hasn't happened yet instead of one already in hand.
- **If the reviewer already has a worktree checked out to the PR's head
  branch** (e.g. it's the same worktree that produced the PR), reuse it —
  no need for `gh pr checkout`. Check `git branch --show-current` against
  the PR's `headRefName` first.
- **Stacked PRs:** if a task's branch depends on a file/interface another
  task's PR introduces and that PR hasn't merged yet (e.g. Task 4 needs
  `api/models.py`, which Task 2/3's still-open PR creates), branch off
  that PR's branch instead of `main` and say so prominently in the PR
  body — don't force a phantom conflict by branching from `main` early.
  Once the base PR merges, the tech lead retargets the stacked PR's base
  to `main` so the diff collapses to just that task's commit(s) against
  the now-updated `main`. **`gh pr edit` is unreliable on this repo for
  any field, not just `--base`** — a known `gh` CLI bug where it queries
  deprecated `Projects (classic)` fields as part of the same call and
  errors on that, unrelated to the actual edit. Confirmed on both
  `--base` (exits with a `Projects (classic)` GraphQL error, the base
  silently unchanged) and `--body` (same error, the description silently
  unchanged — caught only because the edit was re-read afterward rather
  than trusted). Always verify a `gh pr edit` actually took by reading
  the field back, and when it didn't, fall back to `gh api -X PATCH
  repos/<owner>/<repo>/pulls/<n> -f <field>=<value>`, which bypasses the
  bug entirely.
- **The retarget is not bookkeeping — it is what decides where the code
  goes. `gh pr merge` merges a PR into whatever its `base` is at that
  moment, and GitHub then reports it as "merged" either way.** The tech
  lead batch-merged two approved stacked PRs (`for pr in 35 37 36; do gh
  pr merge $pr`) without retargeting the two stacked ones first. Each
  merged cleanly — into its parent task branch, not `main`. GitHub showed
  both as MERGED; `main`'s tool module still had two of the ten tools it
  was supposed to have. Nothing was lost (the next PR in the stack, once
  retargeted, carried the whole chain), but the review teammate was
  reviewing that PR as one task's diff when it was three tasks wide, and
  the end-to-end verification task would have run against a `main`
  missing eight tools. Caught by the implementer checking `main`'s actual
  file contents rather than trusting the merged label. Two rules from it:
  (1) **before merging a PR, read its `baseRefName` back and confirm it is
  `main`** — the merge sequence for a stack is retarget → verify base →
  merge, one PR at a time, never a batch loop over PR numbers; (2) **after
  merging, verify the change is on `main`** (grep for the function, count
  the tools, whatever the artifact is) rather than reading "merged" as
  "landed." A PR number tells you what was approved; only `main` tells
  you what shipped.
- **Assign a stacked PR to the review teammate at creation time, same as
  any other PR — don't defer it to "after the retarget."** Observed
  directly: a stacked PR was dispatched with "stacked on #N, retarget
  later," which reads as "not yet actionable" rather than "yours to
  review now," and it sat unreviewed through several other review cycles
  as a result before anyone noticed. A stacked PR's code is exactly as
  reviewable as any other PR the moment it opens; only its `base` is
  provisional. Say "review this now" explicitly when you dispatch it, not
  just when you retarget it.

  **This recurred a second time in an unstacked, purely concurrent form —
  the underlying failure isn't specific to stacking.** A PR was mentioned
  to its implementer (as context in an unrelated reply) but never sent to
  the review teammate as its own dispatch, and it sat open and unreviewed
  for roughly an hour before the review teammate found it themselves by
  listing open PRs to check why a later PR number skipped ahead. Relying
  on every dispatch message arriving intact is relying on something that
  crosses in transit under exactly the conditions (several teammates,
  concurrent initiatives) this workflow exists for. **Standing fix: the
  review teammate starts each turn by running `gh pr list --state open`
  and reconciling against what they've already reviewed**, rather than
  waiting to be told. The open-PR list is the source of truth and can't
  cross in transit the way a message can — this makes the queue
  self-correcting instead of dependent on the tech lead remembering every
  dispatch, which doesn't scale past a handful of concurrent PRs.
- **A retargeted base is not automatically a re-review, but the test isn't
  "was the base changed" either — it's whether the commit SHAs changed.**
  Two real cases landed back to back with opposite answers. PR #12→#13
  (the GitHub auto-close incident) was a genuine rebase: new commit SHAs,
  so the prior review didn't transfer and got redone from scratch. A
  later stacked-PR retarget (base pointer moved from a task branch to
  `main`, commits untouched) had byte-identical SHAs before and after —
  same diff, same head, verified by re-checking the commit hashes rather
  than assuming a retarget is always safe or always unsafe. The review
  attaches to the artifact (the commits), never to the PR number or its
  base field — check the SHAs every time, don't pattern-match on "this
  looks like the same kind of operation as last time."

  **The full taxonomy, settled after a third case.** When a stacked PR's
  two predecessors had been merged into the wrong base (see the
  retarget-decides-the-merge-target entry), the successor PR — retargeted
  to `main` — suddenly carried all three tasks' commits. The reviewer
  expected to re-verify 700 lines and didn't have to: the earlier commits
  were the *identical SHAs* already reviewed, not rebased equivalents. A
  git SHA is content-addressed, so the same hash *is* the same tree by
  construction; `range-diff` answers "are these *different* commits
  equivalent?" and here they weren't different. Three cases, one question:
  - **rebase** → new SHAs, patches should be equivalent → `git range-diff`.
    Pair each commit against its own parent (`old^..old new^..new`) so
    each range holds exactly the commit being compared. **Qualifier:**
    `range-diff` compares *patches*, not resulting trees — `=` proves the
    change survived, not that it landed on the intended foundation. When
    changing the base *is the point* of the rebase (e.g. a stacked PR
    whose base branch got a fix after the PR was cut, where a plain
    retarget would replay the pre-fix version over the fixed one), also
    verify the composed tree: the fix present, the pre-fix text absent.
    Whenever an operation's intent is to change what surrounds the patch,
    checking the patch isn't enough.
  - **conflict resolution** → patches necessarily changed → exercise the
    merged result directly (`range-diff` can't return `=`)
  - **retarget / base-branch shuffle** → SHAs unchanged → confirm they
    match the reviewed heads and stop; there is nothing to re-read
  - **cherry-pick** → new SHA, same patch → `range-diff` the original
    against the pick, then confirm by *content* on `origin/main`.
    `git merge-base --is-ancestor <original> origin/main` will always
    say no — the original SHA is never on `main`, only its patch is — so
    that check reports a landed change as missing. (Learned landing a
    plan correction that had been pushed to a PR someone else had
    already merged, rebase-style, 77 seconds earlier: the correction was
    stranded on a closed PR's branch; the pick landed it; the
    ancestry check then "failed" on a change that was demonstrably there.)
  The distinguishing question is always "did the SHAs change?", never
  what the operation was called.
- **A value that's validated once but relied on in a second, unconnected
  place needs an explicit test tying the two together — not just a test
  of each place separately.** Jyra's ticket status vocabulary ended up
  written in three places with nothing enforcing agreement: the
  `ALL_STATUS_ORDER` list driving the board view's column grouping, the
  `TicketStatus` Pydantic literal (and `STATUSES_BY_TYPE`) validating
  writes, and a schema.sql comment with no `CHECK` constraint. Each place
  had its own passing tests. The gap only showed up by asking "what
  happens if a row's status exists in one list but not the other" and
  actually inserting one: `GET /boards/{id}` did `columns[row["status"]]`
  with no fallback, a bare `KeyError` (500) for any status outside
  `ALL_STATUS_ORDER` — not reachable through the API yet (no ticket
  write routes existed at review time), but about to become reachable the
  moment ticket CRUD landed. Same shape as `EXPECTED_TABLES` vs.
  migrations: two lists that must describe the same set, each maintained
  separately. Fix is a four-line test pinning `set(list_a) ==
  set(list_b)` directly, in whichever PR owns the second list — cheaper
  before there are two independent call sites to reconcile than after.
- **The tech lead is not exempt from the SHA-identity rule, and got caught
  by it.** Merged PR #19 off an old approval comment without checking
  whether the head it was reviewing still matched the head being merged —
  the branch had been rebased in between, landing a new commit. Caught
  after the fact, not before, when the review teammate's own
  queue-reconciliation habit surfaced the mismatch. The rule from the
  SHA-identity entry above applies to every merge action, not just to the
  reviewer's decision of whether to re-review: **before merging, check
  that the head being merged is the head that was actually reviewed** —
  an approval comment on a PR number is not the same claim as an approval
  of a specific commit. Reading the plan section on stacked-worktree
  staleness (below) generalizes the same failure mode one layer up: a
  worktree's local plan copy can be stale relative to `origin/main`, and
  a remembered "this PR was approved" can just as easily be stale
  relative to the PR's current head. **The concrete check that closes the
  gap:** `git diff <reviewed-sha> <merged-head-sha> -- <source dirs>`
  before merging a rebased PR — two seconds, and it turns "the rebase
  probably only picked up base changes" from an assumption into a fact.
  Used after the fact here (the #19 gap closed itself out only because
  the actual diff between the reviewed SHA and the merged SHA turned out
  to be someone else's already-reviewed fix landing via the rebase, not
  new work) — that outcome was luck, not verification, since nobody ran
  the diff before merging. Run it before, not after.
- **A plan file committed to the repo and read from a stacked worktree can
  be stale relative to `origin/main`, in exactly the way a local branch
  can be stale relative to its remote.** A tech-lead correction to Jyra's
  plan (`204` → `200 + body` for `delete_ticket`) landed on `main` in one
  PR; an implementer's worktree, branched several PRs deep in the stack,
  still had the plan's original pre-correction text, because the plan was
  committed before the correction and the worktree was never rebased past
  that point. Working from the local copy would have silently undone the
  correction. Caught by reading the plan section from `origin/main`
  directly and diffing it against the local copy, rather than trusting
  that a file already sitting in the worktree must be current. When work
  is stacked several branches deep and the plan lives in-repo, treat the
  plan file the same way you'd treat any other file that might have moved
  upstream: check `origin/main`'s version before starting a task, don't
  assume the copy you branched from is still the latest word.
- **Never chain a rebase with `&&`.** A `git rebase ... && <next command>`
  chain assumes the rebase either succeeds or exits nonzero — but a
  conflict is a normal, expected outcome of `git rebase`, not an error
  condition, so the shell's own exit-code guard doesn't hold the way it
  does for most commands. One instance: a rebase hit a real conflict, a
  later command in the chain (`tail -2`) happened to exit 0 regardless,
  and the chain kept going — running the test suite against a
  mid-conflict tree (dozens of meaningless failures) and then attempting
  a force-push while the rebase was still interrupted. No damage that
  time (during an interrupted rebase HEAD is detached and the branch ref
  hasn't moved, so the force-push was a verified no-op), but the
  near-miss is the lesson: run `git rebase` on its own line, check the
  result, then decide what runs next.
- **In a worktree, `.git` is a file, not a directory** — it contains a
  `gitdir:` pointer to the real git directory under
  `.git/worktrees/<name>/` in the main checkout. A check like `test -d
  .git/rebase-merge` to detect an in-progress rebase silently returns
  false in a worktree even mid-rebase, because `.git/rebase-merge` isn't
  where the worktree's actual state lives — the check just doesn't find
  what it's looking for and says nothing is wrong. `git status` reports
  the true state regardless of whether you're in the main checkout or a
  worktree and doesn't have this blind spot. Worth remembering specifically
  because this workflow puts nearly everyone in a worktree nearly all the
  time.
- **An id tiebreak on a sort is right for an arbitrary stable order and
  wrong for a chronological one where the order itself carries meaning.**
  A ticket's transition history was sorted `(created_at, id)`, mirroring a
  pattern used correctly elsewhere for listings that only need *some*
  fixed order (a board's ticket list doesn't care which of two same-rank
  tickets prints first). But `created_at` has one-second resolution,
  transitions on one ticket routinely land in the same second, and `id`
  is a random uuid4 — so the audit log's actual event order became
  effectively random whenever two events tied, silently reordering what
  is supposed to be the record of what happened. Fixed with `(created_at,
  rowid)` — monotonic in insertion order — instead. The general question
  to ask before reusing an id-tiebreak pattern on a new sort: does this
  listing's order mean something beyond "consistent between requests," or
  is any fixed order equally correct? Worth noting too that the plan's
  own test caught this one only by luck — three events in one second
  makes a random order correct 1 time in 6, so on another run it would
  have been flaky rather than reliably red; the fix included a
  seven-event version verified to fail reliably on revert.
- **A multi-task plan stacked across several open PRs goes stale in the
  tech lead's head faster than it goes stale on disk, once merges stop
  landing as fast as tasks get pushed.** A dispatch message written
  against "the last PR I merged" was two tasks behind the implementer's
  actual position twice in the same arc — once framing an already-merged
  fix as upcoming, once telling the implementer they'd move to a task
  they'd already finished and opened a PR for. No work was lost either
  time only because the implementer checked their own position before
  following the framing, which isn't something to rely on. Standing fix,
  adopted from the implementer's own proposal: **the tech lead runs `gh
  pr list --state open` immediately before writing a dispatch that
  references "the next task" or "the current stack,"** rather than
  reasoning from the thread history — the open-PR list is the same kind
  of authoritative, can't-cross-in-transit source of truth the review
  teammate's own reconciliation habit already relies on (see the
  reconciliation-habit entry above). Paired with the implementer leading
  every status report with an explicit current-stack table, so the
  latest position is legible even if a dispatch does go out before it's
  read.
- **A code comment that explains *why* something must be a certain way is
  making a testable claim, and should be pinned as a test, not left as
  prose.** Caught twice from the same implementer in one session, both
  times the code itself was already correct and only the stated reason
  was wrong: once on a length-cap's rationale, once on why an MCP tool
  omits absent fields from a partial update rather than sending explicit
  nulls (the comment claimed it avoided a 422 that doesn't actually
  exist — the real behavior is worse, a silent no-op, which makes the
  guard more justified, not less). Prose can drift from the behavior it
  describes with nothing to catch it; a reviewer or a future edit can
  make the comment wrong while the code stays right, or vice versa. The
  fix both times was the same: write a test that would fail if the
  claimed behavior stopped holding, so the explanation can't silently
  go stale the way the plain-English version already had twice.
- **A rebase preserves patches; a conflict resolution does not — and they
  need different verification.** `git range-diff` answers "did this PR's
  own diff actually change" by comparing patches, which is exactly the
  right tool when a branch was rebased onto a new base with no conflict:
  identical patches come back `=` and a prior approval carries mechanically,
  no re-reading needed (this is what settled the #19 question). But when a
  cascade hits a *real* conflict — two branches independently appending to
  the same file at the same point — resolving it necessarily changes both
  sides' patches, so `range-diff` won't and can't return `=`, and treating
  that like the rebase case would be exactly the wrong inference. The only
  real check there is exercising both things that collided: after a Jyra
  stack's cascade resolved a conflict with Phase 3's financial routes/models,
  verification was reading `api/main.py`'s router registrations directly
  (all three present), checking both schema sets landed, and running an
  end-to-end smoke call through each feature — not diffing patches, since
  there were no longer two patches to compare against what was reviewed.
  Rule of thumb: no conflict during the rebase → `range-diff`; a conflict
  that got resolved → re-verify by exercising the merged result directly.
- **For an append-only conflict (two branches adding new functions/items at
  the same point in a file), "the suite stays green" is not enough — count
  what should exist.** A shared `@server.tool(` decorator line sat directly
  above the conflict markers in two colliding branches; keeping both
  function bodies could easily have left a decorator orphaned or a whole
  tool silently unregistered, and the file would still *parse* and most
  tests would still *pass*, because nearly every test names the specific
  tool it exercises rather than asserting the full registered set. The
  check that actually rules this out is counting: how many decorators, how
  many registered names, do they match the expected list. This is the same
  shape as the earlier "did both sides survive the merge" checks (routers
  in `main.py`, schema classes in `models.py`) — after any append-only
  conflict resolution, count the things that were appended on both sides
  rather than trusting that a green suite means nothing was dropped.
- **A plan's own prose claiming "this doesn't need a test" or "this would
  be flaky" is itself a claim to distrust by default, same family as the
  reviewer's-offered-alternative-is-a-hypothesis lesson.** Two separate
  instances in the same plan: Task 5 asserted a route returned 400 when
  the settled design said 422 (an assertion, not an argument, but still
  something nobody had re-checked against the actual decision); Task 6
  said a threaded concurrency test "would be flaky without proving
  anything extra," and it was neither — five consecutive runs failed
  identically when the guard was removed, and the plan's own *sequential*
  test stayed green in that same broken state, because it only exercised
  the case where the second writer arrives after the first commits. Both
  times the implementer measured instead of complying, and both times the
  plan's confidence was wrong in the direction of *less* testing, which
  is the direction that's easy to rationalize accepting ("the plan author
  already thought about this") and expensive to be wrong about. When a
  plan states outright that some case isn't worth covering, that line is
  exactly the one to verify rather than skip — and after finding one
  instance, it's worth grepping the rest of the plan for the same phrasing
  rather than assuming it was a one-off.
- **A stub can't verify a claim about the thing it stubs out.** Third
  instance of this exact shape in one session: a claim that one MCP
  client survives reuse across separate event loops was "verified" using
  `MockTransport`, which opens no real sockets — so the test passed
  regardless of whether the claim was true. It wasn't: `httpx.AsyncClient`
  binds its connection pool to the loop that created it, and a real
  `uvicorn` run over a real socket died with `RuntimeError: Event loop is
  closed` on the second call. (The other two instances: the `ToolError`
  subclass requirement, and a leak-guard rationale — both also verified
  in isolation against something that couldn't exercise the real
  boundary.) Production code was unaffected each time, purely by luck of
  how it happened to call things — the bug was in the *test's* confidence,
  not (yet) in the shipped behavior. The general check: before trusting a
  test that verifies a claim about integration with a real system
  (network, event loop, filesystem, process boundary), ask what the test
  double actually replicates versus what it merely stands in for — a
  fake that never does the real thing can't tell you whether the real
  thing works. **Concrete rule for this codebase's MCP tests:
  `ASGITransport` tests the app, not the transport.** Both instances above
  used `ASGITransport` (or the equivalent in-process double) specifically:
  it drives real FastAPI routing and dependency injection in-process, so
  it's the right tool for testing the *app*, but it never opens a socket
  or spawns a separate event loop, so anything depending on connection
  pooling, loop affinity, or how an unhandled exception actually
  serializes across a real transport needs `MockTransport` or a live
  server instead — no exception, no shortcut.
- **A display value derived from untrusted input must never be usable as
  a path component, and that invariant has to hold at every layer that
  touches it, not just the one that wrote it down — and it covers every
  field carrying attacker-influenced content, not just the obvious one.**
  A ticket attachment stores an uploaded file's *display* filename
  literally, including a percent-encoded traversal string
  (`%2e%2e%2fetc%2fpasswd`) — correct, because decoding it would silently
  rename the user's file, and harmless in that endpoint specifically
  because the actual on-disk name is a server-generated UUID, never the
  display name. Separator-based attempts (`..\..\windows\system32\evil.dll`,
  `....//....//etc/shadow`) get properly reduced to a basename
  (`evil.dll`, `shadow`) — also correct. But the API also returns
  `file_path`, the absolute *server-internal* path, in the same response.
  Neither field is unsafe to store or return on its own; the danger is a
  future consumer's plausible next move: decode the display name (a UI
  "save under its original name" feature would do exactly that) or accept
  `file_path` back from a client (the obvious shape for a future download
  route) and the traversal the storage layer correctly declined to
  perform gets reconstructed one layer up. The rule that actually closes
  it, phrased around what a consumer must do rather than what each field
  contains: **`filename` is a display label, never a path component, and
  may contain separators in encoded form that decode to a traversal
  string; `file_path` is server-internal. A consumer needing to write an
  attachment to disk derives its own name from the attachment id and uses
  neither field for that purpose.** Not assumed to be inherited
  automatically by whatever boundary reads these fields next — restate it
  there. (See todo #24, filed to drop `file_path` from responses entirely
  before a download route makes the wrong design the easy one to write.)
- **A field built by concatenating a fixed-format piece with an
  attacker-controlled piece needs its own bound, even when the
  attacker-controlled piece is "just cosmetic."** A ticket attachment's
  on-disk filename is `{uuid}{client-supplied suffix}`; the suffix is
  unbounded and the filesystem's `NAME_MAX` (255 on the systems this runs
  on) is not, so a suffix past roughly 218 characters produced an
  unhandled `OSError: File name too long` from `open()`, escaping as a
  plain-text 500 with no error envelope — the same "uncaught exception
  breaks the shared envelope" class this repo has now hit three separate
  times (`DataIntegrityError`, `paginate`'s `RequestValidationError`
  backstop, `CorruptDatabaseError`). Not a security issue here — the file
  never escapes the target directory — but trivially triggered by any
  caller, security concern or not. The fix matches the general instinct:
  bound the untrusted piece before it reaches the OS call
  (`Path(filename).suffix[:MAX_SUFFIX]`) rather than add a catch for the
  OS error it can trigger. Truncating is safe precisely because the piece
  being bounded is cosmetic — the real display value lives in a separate
  column untouched by the truncation.
- **`project-management.json` is a shared file with a dense sequential id
  counter, edited concurrently by several sessions in one checkout — and
  that combination collided five times in a single day.** Each session
  assigned its next id from *its own branch's snapshot* of the file; two
  todos landing on `main` in between meant two branches each "correctly"
  claimed the same number. Once, a hand-resolved conflict silently deleted
  an entry (#29) — caught only because the author re-read the pushed
  branch instead of trusting their own "15 pure insertions" summary, which
  had been true two rebases earlier. What was settled from it:
  - **Never reuse a retired id.** The list has gaps (4–6, 8, 11–12, 29 —
    closed or deduplicated); a gap is not a free slot. "Max is N, so next
    is N+1" is the rule, not "no gaps below N+1" — the two diverge exactly
    when someone treats a gap as reusable, and reusing one would silently
    attach new work to an old todo's history. Same property the migration
    runner has by construction (a version is never reused); todo ids have
    it by convention only.
  - **Compute the id at write time, against the file as it is *then*,
    never from an earlier read** — and pass `ensure_ascii=False` to
    `json.dump`, or every em dash in every existing entry gets escaped and
    a 5-line append becomes a 14-line diff that hides the real change.
  - **After any hand-resolved conflict on this file, verify by count and
    id list, not by eye.** The last two resolutions each looked right and
    weren't. `python3 -c "import json; ids=[t['id'] for t in
    json.load(open('project-management.json'))['todos']]; print(sorted(ids),
    len(ids)==len(set(ids)))"` is the whole check for a branch in
    isolation. **For a PR that deletes a todo, compare id *sets* against
    `main`** — `removed: [...] / added: [...]` — because that is the one
    change the uniqueness test cannot see, and the eye cannot reliably
    tell a 5-line deletion from a 5-line deletion plus an accidental edit
    200 lines away. A PR closing todo #17 should print exactly
    `removed: [17] added: []`; anything else in either list is a finding.
  - **The sixth instance was the one that finished the argument.** A PR
    that had been cut before four todos were filed on `main` merged
    "cleanly" — `merge-tree` showed zero conflict markers, and the tech
    lead read that as "no rebase needed" — and its merge result would
    have deleted all four. A whole-file rewrite from a stale snapshot is
    *not a textual conflict*: the file is internally valid, the hunks
    don't overlap anything, so git has nothing to flag. `merge-tree`
    structurally cannot see it; **for that file, "no markers" is the
    dangerous outcome**, and only the id-set comparison of the merge
    result against `main` can catch it. Same shape as a query plan that
    reads `SEARCH ... USING INDEX` while using the wrong index: the check
    that looks like it covers the thing passes, and only the check that
    names the specific expectation catches it.
  - **Resolution (2026-09-19): the tracker moved to a Jyra board, over
    MCP.** Twenty-five open todos were ported as tickets titled
    `[todo #N]` (verified through the session's own MCP connection:
    count, ids, no descriptions lost), the file was frozen, and
    `CLAUDE.md` now points at the board. Jyra's ids are server-generated
    and every write goes through one API, so the entire collision class
    — snapshot-assigned ids, hand-resolved merges, silent deletions —
    disappears with the file rather than being guarded against. The
    uniqueness test and the id-set check retire with it. The general
    lesson stands for any shared, hand-edited file with a dense counter:
    the guards were real and they were still the wrong layer; the fix was
    to stop having the file.
  - **`tests/test_project_management.py` now catches duplicates
    mechanically — and only duplicates.** The failure that actually caused
    loss was a *deletion*, and a uniqueness assertion is blind to that by
    construction; it isn't cleanly coverable either, since closed todos are
    legitimately removed. So: duplicates guarded, deletions still rest
    entirely on resolution discipline, and the unguarded one is the one
    that has bitten. The test's own docstring deliberately does not claim
    the #29 lineage, so it won't get deleted later when someone checks the
    premise. (The load-bearing part of that PR was `testpaths` in
    `pyproject.toml`, not the test — without adding the repo-level `tests/`
    dir there, a bare `pytest` collected 0 of these tests: a committed,
    visible, never-executed guard, worse than none because it reads as
    coverage.)
- **A test fixture that omits a writable path doesn't fail — it writes to
  the real one.** `lib_mcp/tests/conftest.py` never set `jyra_dir`, so it
  defaulted to the real `data/jyra/`; an attachment round-trip test would
  have written into the actual data directory. `logs_dir` had the same
  shape, and by then the launchd agent was live, so the real
  `data/logs/api.log` was one forgotten `model_copy` away from a test
  appending to it. The API's conftest had always set these; the MCP one
  was never updated when Jyra landed — a second conftest is a second
  hand-maintained list. Two fixes worth copying: (1) a guard asserting
  every writable `Settings` path stays under `tmp_path`; (2) **a second
  test asserting the first guard's field list is complete**, so a field
  added to `Settings` later must be classified rather than silently
  skipped. The second immediately flagged an unclassified field, and that
  is the only reason `logs_dir` was found at all — with just the first
  guard, the author would have checked exactly the two fields they
  already knew about. And after the fix: confirm the real file is
  byte-for-byte untouched by a full run. A test about not writing outside
  the sandbox is worth little if nobody looks.

  **Where the exposure actually was, which bounds the blast radius:**
  `REPO_ROOT` derives from `api/config.py`'s `__file__`, so a suite run
  inside a detached worktree resolves `data/` to *that worktree* and
  sandboxes itself by accident — the reviewer's scratchpad checkouts were
  never the risk, and the mutation output showed the escape path as the
  worktree's own `data/logs`. The exposure was **running `pytest` in the
  main checkout**, which is exactly what the tech lead and any session
  working in the main checkout directly do — and the live launchd
  agent sharpened it by putting a real `api.log` at the default path.
  "It's fine in a worktree" is not evidence the main checkout is safe.
- **An artifact check that string-matches a guessed literal can return
  "missing" for a present artifact — and a zero `grep -c` exits non-zero,
  so it silently truncates an `&&` chain.** After merging the
  entity-vocabulary fix, the tech lead verified it with
  `grep -c '"project"'` on `main`'s tool module: 0. The literal in the
  file is `..., account, project"` — no quote before `project` — so the
  pattern was wrong, the artifact was right, and the 0 was
  indistinguishable from the fix not having landed. Worse, `grep -c`
  returning 0 exits 1, and the check sat in an `&&` chain ahead of the
  pull and the worktree cleanup, all of which silently never ran. The
  same wrong-pattern shape had already hit twice on `EXPECTED_TOOLS`
  regexes. Two rules: **verify an artifact the way it is consumed** —
  import the module and print the value, run the test that asserts on
  it, render the description the SDK reports — not by matching a string
  you guessed the source contains; and **never put a count or a grep in
  an `&&` chain ahead of steps that must run regardless** — separate
  verification from cleanup with `;`, and read the number rather than
  letting the exit code decide what happens next.

  **Three more instances landed within the hour, in three different
  hands, so this is a class and not a slip:**
  - The tech lead's check that a README rebase hadn't reintroduced stale
    vocabulary was `grep -c project` ≠ 0. The implementer had correctly
    *removed* the enumeration (a hand-maintained README list is a third
    copy with nothing checking it), so the count was 0 — and `project`
    also matches `project-management.json`, so the check couldn't have
    distinguished "vocabulary current" from "filename mentioned" anyway.
    It was a *proxy* for the real question; the direct check
    (`grep -c "pet or account"` = 0) had been passing all along. Ask what
    the check would say in the correct-but-different outcome before
    trusting it.
  - An implementer polled an in-progress test run with
    `grep -c "DatabaseError"`. Pytest truncates the assertion to
    `IncompleteDa...`, so the pattern could never match, returned 0, and
    "0 matches" was reported as "0 errors" — with a conclusion drawn from
    it (load *reduces* the failure rate) that was the exact opposite of
    the truth (load doubles it, 27%). **When a number is the evidence,
    confirm the mechanism can produce a non-zero before trusting a
    zero** — feed it one known positive first.
  - A **self-fulfilling test**: a draft that raised the exception it then
    asserted on, so it would have passed against any implementation
    including no implementation. Caught before pushing. The tell is a
    test whose setup already contains its expected outcome; the fix is
    making the thing under test the only thing that can produce it.
  - A **phantom gap**: verifying a cherry-picked plan correction, an
    implementer grepped for a phrase from it, got 0, and nearly reported
    the correction as incomplete. The phrase spans a line break in the
    wrapped Markdown file. Rather than report, they diffed `main`'s file
    against their commit's version: byte-identical. "A grep returned 0"
    is weak evidence about a wrapped text file — diff the artifact
    against its source.
  - **Understating a change is the same shape as overstating a test.** A
    22-insertion/10-deletion plan correction was described as "a one-line
    correction." A docstring that claims more than its assertions check
    and a summary that claims less than its diff contains both work the
    same way: they make the reader's own check feel unnecessary. Describe
    a change by what it is — the reader who waves through "one line"
    unread is the reader you were relying on to catch it.
- **Mutation testing needs its own verification that the mutation
  applied.** While mutation-testing a vocabulary constant, an edit to one
  value silently didn't take — the string spanned two concatenated source
  lines, so neither replacement pattern matched — and the suite stayed
  green, which is indistinguishable from "the guard works." The report
  would have read 4/4 caught. Fixed by asserting the file actually changed
  before running the suite. Same family as `cmd || echo "all clear"`: a
  green result after an edit that never happened proves nothing, and
  "I mutated it and the test failed" is only evidence if the mutation is
  itself checked.
- **The MCP SDK silently drops any argument a tool's signature doesn't
  declare, before the tool runs, with `is_error: false`.** So omitting a
  field from a tool's parameters does *not* make it unexpressible — it
  makes it invisible. `update_ticket` had no `status` parameter on exactly
  that reasoning; `update_ticket(status="done")` sent an empty PATCH and
  returned **200**, telling the model its update succeeded while nothing
  changed. Confirmed against the SDK directly. This invalidates every
  "the signature makes X unpatchable" claim in the plans and reviews,
  including an "enforced at three levels" verdict — level one doesn't
  reject, it drops, so level two (`extra="forbid"` on the API model)
  never sees the argument. The fix pattern: **accept the field solely to
  refuse it**, naming what is and isn't patchable and echoing the
  attempt, pinned by a *behaviour* test that the call raises. A
  description-content test would have passed — the author's description
  said "rejected rather than quietly ignored" while the code quietly
  ignored; only `DID NOT RAISE` caught it. Todo #38 tracks the audit of
  every write tool. Sits next to the ASGITransport rule for the same
  reason: a load-bearing fact about the layer that the tests can't
  reveal unless you know to ask.
- **An instrument can manufacture the exact signature it's hunting for.**
  Two instances from one investigation: (1) a probe for whether two
  facts commit atomically read them as *separate autocommitted
  statements*, so the writer's COMMIT could land between the two reads —
  it reported 15 "non-atomic observations" of a transaction that was
  atomic, and was nearly reported as a two-commits finding; reading both
  facts inside one snapshot showed zero mixed states across ~57,000
  samples. (2) A 400-iteration post-fix soak ran *while the author was
  editing `api/db.py` in the same working tree*; its 14 failures were
  entirely their own edit windows (contiguous runs 70–81). **Soak and
  edit can't share a checkout** — commit first, soak against a frozen
  tree. Both belong to the same class as the non-applying mutation and
  the truncated grep: before trusting what an instrument reports, ask
  what else could produce that reading.
- **In a read-before-write plan, seeding test data through the write tools
  is the default failure, not a slip.** It happened twice to the same
  implementer in one round — a read tool's round-trip called
  `create_ticket`/`transition_ticket` from tasks that didn't exist yet,
  so the test could not run at all, and the temptation was to reorder the
  plan around the test. The thing under test is the read tool, so its
  setup is allowed to be raw HTTP against the API: a `_seed` helper.
  Expect it in every plan where reads ship before writes.
- **A premise test can prove its own premise wrong.** The exactness test
  for integer-cents money first used 100 rows of `10.07` — and
  `sum([-10.07] * 100)` is *exactly* `-1007.0`; floats are fine for that
  value, so the test would have passed and "proved" the case for integers
  with an example where integers bought nothing. `20.15` genuinely drifts
  to `-2014.9999999999998`. The catch came from a test written
  specifically to be suspicious of its own fixture; pin the premise
  (this value *does* drift) so a future edit can't quietly repeat it.
- **A repeated value in a sequence fixture rules out more than ordering.**
  Seven distinct statuses in a history test would still be satisfied by
  an implementation that sorts; a repeated `in_progress` at positions 1
  and 6 rules out sorting, deduplication and set-coercion at once. Free,
  if the fixture data is chosen for it.
- **For a refusal, assert what was *sent*, not just that something was
  raised.** A `pytest.raises` test for "this tool refuses to change an
  immutable field" cannot distinguish two implementations: one that
  refuses *before* writing, and one that issues the PATCH and *then*
  objects. For a tool whose entire purpose is protecting imported records
  from modification, that difference is the point, not a detail. Record
  the request bodies the tool actually sent (or assert none were) and
  parametrize over every protected field — the same assertion also
  catches the half-fix that guards `amount` but not `txn_date`, where a
  raises-test only pins the field someone thought of. Both shapes were
  mutation-tested on `update_transaction`: the half-fix failed 3 tests,
  the post-write refusal failed all 3 on the recorded body. The
  implementer's original `calls == []` had covered the second case by
  accident of how it was written; the parametrized body assertion covers
  it on purpose — that's the version that survives the next edit.
- **A forward-reference test beats a todo for a known gap: it fires in the
  changer's face.** When Jyra-MCP Task 5 found that the API accepted an
  empty transition note (todo #37), the implementer wrote
  `test_an_empty_note_is_currently_accepted` — a test that *documents the
  current permissive behaviour* and states in its docstring that it must
  go red when the API is tightened, so whoever tightens it revisits the
  tool description in the same change. When #37 was fixed, that test
  failed on the first full run, exactly as designed, and the description
  was strengthened in the same PR. A todo waits to be looked up and can
  be closed without the linkage; a test that encodes its own trigger
  condition cannot be satisfied without it. Keep the todo for
  prioritisation; write the test for the linkage.
- **Before reporting a regression, run the same scenario against
  `origin/main`.** During the runner-author's read of the migration-race
  fix, the reader found a path where the fix's new re-read would serve an
  incomplete database held under an exclusive lock, hypothesised it was a
  regression introduced by the second sampling point, and *ran the
  identical scenario against pre-fix `main`* before writing it up. It
  reproduced there too — the original single sample already saw the
  lock. Pre-existing, by design, orthogonal to the change; filed as its
  own todo instead of a false finding against a correct PR. The check
  was worth more than the hypothesis, and it's cheap: a detached
  worktree at `origin/main` and the same probe.
- **`| tail -1` (or any pipe) replaces the exit code you wanted with the
  pipe's.** The tech lead ran `gh pr merge 54 --merge 2>&1 | tail -1;
  echo "#54 merge exit: $?"` — GraphQL printed "Pull Request has merge
  conflicts," and the next line printed `exit: 0`, because `$?` was
  `tail`'s. Read on its own that line says the merge succeeded. The
  artifact check further down is what caught it. Either don't pipe the
  command whose status matters, or use `${PIPESTATUS[0]}` — and treat any
  printed exit code next to a piped command as decoration until you've
  checked which process it belongs to.
- **Name the base you measured on.** Two people ran the same mutation
  (invert the sign at the INSERT) and reported 20 passed / 0 failed and
  21 passed / 1 failed. Both were right: one ran it in a worktree on an
  older `main` where those files held 20 tests; the other on current
  `origin/main`. The conclusion was identical either way, but a count
  without its base is a claim that can't be checked, and the disagreement
  cost a round trip to resolve. "N passed on `<sha>`" is the unit.
- **Existence is not use: an index test must assert the query plan.** The
  first draft of the dedup-index test asserted `idx_txn_dedup` appears in
  `sqlite_master`. That passes on an index SQLite never uses — a subtly
  wrong column order would sail through while every import still scanned
  the table. It now asserts `EXPLAIN QUERY PLAN` shows
  `SEARCH ... USING INDEX idx_txn_dedup` and no `SCAN`, confirmed against
  the real schema. Same family as the stub-verifies-nothing lesson: the
  thing being asserted has to be the thing that matters.
- **A rule that reads as obviously correct is only legible by mutation.**
  The account-scoped dedup probe *counts* existing `(date, description,
  cents)` matches and inserts only when the batch ordinal is `>=` that
  count. Replacing it with a boolean `existing > 0` reads as obviously
  right — and fails three tests, including todo #2's original in-batch
  tiebreak, because it silently drops the second of two genuinely
  identical same-day charges (two coffees become one). Dropping the
  account scoping fails the cross-account test separately. Neither is
  visible by reading the diff; both are one mutation away. Where a
  reviewer's instinct says "that could be simpler," the mutation is the
  answer, not the argument.
- **Announce a rewritten head in the same message as the new SHA — old →
  new, why, and whether the delta is reviewable or just a base move.**
  The implementer-side mirror of the SHA-identity rule. An approved PR's
  head was rewritten three times after approval (amend, rebase, amend
  again), each time reported only as the final SHA, as though it were a
  fresh statement of where things stood rather than a rewrite of
  something two people had already read. From the lead's side that is
  indistinguishable from a stable branch, right up until `gh pr merge`
  hits a commit that no longer exists — which is what happened. Rewriting
  after approval is fine when the base moved (it was the right call
  here); the rule is to *say so*, so the lead holds the merge and the
  reviewer knows the SHA they approved is stale. Where possible, do the
  rewriting before announcing readiness, so there's one head to approve
  rather than a sequence.
- **A guarantee wants pinning where it is *claimed*, not merely somewhere
  in the suite.** `attach_file`'s copy-not-move guarantee was caught by
  exactly one test — `test_round_trip_delete_attachment_removes_the_file`.
  A tool that consumed the caller's file *would* have failed the suite,
  but the failure would have sent the next reader to debug
  `delete_attachment` for a bug in `attach_file`. One line in the attach
  round trip asserting the original survives makes the failure name the
  real problem. "Is it covered?" and "does the failure point at the
  cause?" are different questions.
- **When two people measure opposite results, build the matrix — nobody
  concedes.** One implementer demonstrated an incomplete database held
  under `BEGIN EXCLUSIVE` classifying "ready" and being served; the
  reviewer probed incomplete+locked and found it refused loudly. Both
  were measured, both were right: a 2×3 matrix (journal mode × lock type)
  showed exactly one reproducing cell — rollback-journal mode *and*
  `BEGIN EXCLUSIVE`. Under WAL readers are never blocked (the reviewer's
  case); `BEGIN IMMEDIATE` takes RESERVED, which readers pass. The
  implementer's fixture had never gone through `get_connection`, which
  sets WAL. Same shape as "name your base": two correct measurements, one
  unstated condition. The todo that came out of it names the trigger
  instead of saying "sometimes" — which is the difference between a todo
  that gets fixed and one that gets deprioritised.
- **A structural pin on the runner cannot see a migration *file* that
  carries its own transaction control.** The atomicity test asserts no
  COMMIT the *runner* issues falls between a migration's DDL and its
  `schema_migrations` row. A migration file containing `COMMIT;` in the
  middle ends that span early: the DDL before it commits alone and the
  record lands in a different transaction — exactly the half-applied
  state the race fix's correctness argument rests on being impossible.
  The code comment anticipated this arriving as a change to
  `_apply_migrations`; it's likelier to arrive via a hand-written SQL
  file, where explicit `BEGIN`/`COMMIT` is ordinary. All shipped
  migrations are clean today by accident. Guard the file, not just the
  runner (todo #42): both guards exist because the runner has a
  constraint a migration author can't see from inside the file they're
  writing.
- **A probe against a URL you guessed reports the route, not the code.**
  The tech lead proved the money-as-cents code was live by POSTing a float
  to `/statements/import` and reading the 405 as a result — the real route
  is `/import_statement`, and the 405 proved only that the error envelope
  existed. Same family as the guessed grep literal, pointed at HTTP: get
  the route from `grep -n '@router.post' api/financial.py` (or the OpenAPI
  schema), then probe. The second probe got the 422 naming
  `amount_cents`, which was the evidence.
- **`python -m` puts the current directory first on `sys.path`, ahead of
  `PYTHONPATH` — so a worktree cwd shadows the main checkout.** The owner's
  first `/mcp` attempt died with `CONNECTION_CLOSED`. Claude Code's own
  MCP log showed why: the session's cwd was a `.claude/worktrees/…`
  checkout, `import api` resolved to *that* worktree's package, and
  `REPO_ROOT` (derived from `api/config.py`'s `__file__`) landed in a
  checkout with no `.env` — gitignored, only the main checkout has one —
  so `Settings()` failed on `api_token` and the process exited. Reproduced
  from that exact worktree (exit 1, `api_token Field required`); with
  `PYTHONSAFEPATH=1` in the server's env, the same command answers
  `initialize` (exit 0, empty stderr). The `REPO_ROOT`-from-`__file__`
  design that makes worktree test runs self-sandboxing is the same thing
  that makes a worktree unable to find the token. The structural fix is
  the HTTP-mounted MCP endpoint (no per-session Python import at all);
  `PYTHONSAFEPATH=1` is the bridge.
- **To diagnose another session's failure, read *that* session's log —
  don't reproduce from your own cwd and call it clean.** The tech lead
  first reproduced the failing `.mcp.json` command from `/tmp` and from
  the repo root, got a valid `initialize` both times, and concluded "cwd
  can't be the cause." `/tmp` had nothing to shadow; a worktree did.
  Claude Code writes MCP logs under
  `~/Library/Caches/claude-cli-nodejs/<cwd-keyed dir>/mcp-logs-<name>/`,
  keyed by the *session's* cwd, with the full traceback and the `cwd`
  field — that is where the answer was, one `find` away. Two "server
  started" lines in `data/logs/mcp.log` at the time of the failure were
  the lead's own probes, not the user's attempt; a log line proves a
  process ran, not whose.
- **An example that silently works is worse than no example — it vouches
  for the method.** The runbook fix for the cents contract first said
  `int(float("-10.50") * 100)` gives `-1049`. It gives exactly `-1050`.
  The bug is real for other amounts (`-0.29 → -28`, `1.15 → 114`,
  `-19.99 → -1998`; `round(Decimal * 100)` gets all of them), just not for
  the one the author reached for — and a reader who spot-checks the
  printed example would conclude the naive conversion is fine. Same
  family as the stale runbook it was fixing: a plausible specific nothing
  checks. Every number in a runbook example gets executed before it's
  written down, and the example should show the case that *fails*.
- **An assertion in an edit script that fails safe is cheap; make it the
  default for multi-anchor text edits.** Three times in one session an
  implementer's renumbering/insert script tripped its own precondition
  (a new `3.` colliding with an existing `3.`) and wrote *nothing*,
  instead of half-applying. Check every anchor before touching the file;
  a partial edit to a runbook is the hardest kind of damage to notice.
- **A probe that measures "no effect" has to prove the disturbance
  happened.** Measuring whether a `schema_migrations` read blocks during
  `VACUUM`: the VACUUM thread died on sqlite3's same-thread rule, the
  read hit an idle database, and the result was a clean 0.04 ms — on zero
  evidence. Re-run with the connection created inside the thread and an
  assertion that the VACUUM actually ran (361 ms) before trusting the
  number. Fifth instrument failure this session with the same shape:
  the thing under test silently didn't happen, and the instrument
  reported success. Every "it didn't block / didn't fail / didn't leak"
  result needs a positive check that the load was applied.
- **`claim_ticket` takes the next `agent_ready` ticket by position, not a
  named id.** An implementer told to "claim" a specific ticket read the
  endpoint first: calling it would have returned 204 (nothing ready) or
  claimed some *other* agent_ready ticket out from under whoever was on
  it. To take a named ticket, `transition_ticket` it to `in_progress` by
  hand with a note saying why. Dispatch messages should say
  "hand-transition", not "claim".
- **Documenting a caveat is often working around a defect.** The HTTP
  MCP mount shipped at `/mcp/` with a note that bare `/mcp` 307-redirects
  first. Written out plainly, the caveat was: an unauthenticated request
  to the configured URL gets a redirect *before* the auth wrapper runs,
  and the URL only works for clients that follow redirects on POST. Once
  the lead's spec said the bare URL, the implementer fixed it (a
  path-rewrite ahead of routing; the obvious `Route` delegation 500s
  because Starlette wraps it as request/response, measured before
  choosing). When a PR description contains "note that X behaves
  differently", ask whether X is a defect with a paragraph on it.
- **When a test count moves, diff the collected names, not the totals.**
  #64 reported 609 against a main at 614. `pytest --collect-only` on
  both, strip to the function names, `comm` them: −10 were all stdio-only
  (stdout discipline, `mcp.log` rotation) and +5 were the mount tests.
  Thirty seconds, and the reviewer didn't have to wonder. A bare delta
  can hide a deletion behind an addition.
- **GitHub's merge endpoint can 500; a local `--no-ff` merge of the
  approved head with the standard subject is the fallback, and GitHub
  flips the PR to MERGED once the head is reachable from main.** Three
  attempts (`gh pr merge`, then the REST `pulls/N/merge` twice) returned
  HTTP 500 with an empty body for #63 while the rate limit was fine. Same
  discipline as the API path: clean tree, local `main` == `origin/main`,
  merge the exact approved SHA, run the suite on the merged tree
  *before* pushing, then `merge-base --is-ancestor` on a detached
  `origin/main` checkout. Also: the lead typed a *guessed* full SHA into
  one of those REST calls. A wrong SHA is a 409, so it didn't cause the
  500 — but never type a SHA you didn't read back; `gh pr view --json
  headRefOid` is one call.
- **A ground rule with two clauses that can't both hold gets built from
  anyway — check the layer, not just the wording.** CLAUDE.md said
  account numbers are "never sent to any LLM" *and* that redaction
  happens "at the intake-skill level". If the skill is a model reading
  the PDF, the number is in context before redaction runs: the rule
  protected the database, not the transmission. Three people wrote docs
  and a plan from it before the owner's direct question ("is feeding my bank
  PDFs through a session safe?") exposed it. The fix is where the raw
  text lives, not how it travels: extract-and-scrub server-side, outside
  model context, and the skill consumes only scrubbed output — a tool
  result *is* model context, so an MCP tool is fine only if it scrubs
  before it returns. When a ground rule names a boundary, ask which
  process is on each side of it.
- **A check whose failure path and whose negative result look identical
  is not a check.** Three instances in one session, all the reviewer's
  and all self-caught: `grep --include=*.py` unquoted (globbed by the
  shell, matched nothing, "no occurrences"); a `|| echo "(none)"`
  fallback that fires on a *command error* as readily as on a real
  absence; `$TREE:lib_mcp/...` unbraced, where zsh ate `:l` as a
  modifier, `git show` failed, `grep -q` found nothing, and the script
  printed "**#63's fix is MISSING from the merged result**". The lead
  then did it a fourth time: `timeout 60 claude mcp list | grep app-server`
  on macOS, where `timeout` doesn't exist — "command not found" went to
  the grep and came out as an empty result, i.e. "the server isn't
  listed". Assert the command succeeded before interpreting its output
  (`set -o pipefail`, check `PIPESTATUS`, or print the raw output once
  before filtering it).
- **A 400 can look like a 421, and `TestClient`'s default `Host:
  testserver` *is* a non-loopback host.** Probing the MCP host check with
  a malformed `{}` body returned 400 from the transport, not 421 from the
  host check — re-running with a real `initialize` payload separated
  them. And a lifespan probe that "returned 421 twice" was `TestClient`'s
  default Host tripping the loopback rule; the implementer's fixture
  documents that requirement, which is how the reviewer found their own
  error instead of reporting "lifespan is broken". Read the body of an
  unexpected status before naming its cause.
- **Count before you substitute.** A scrubber prototype counted SSN
  matches *after* `re.sub` had replaced them: output correct, count
  zero. Any "N things redacted/removed/fixed" number should be computed
  from the input, and a test should assert the count equals the number of
  markers in the output so the two can't drift.
- **Two approved rules can deadlock; when they do, make them one rule.**
  "Don't eat amounts" plus "refuse the document if any 9+-digit run
  survives" met at `Balance 123456789.00`: a decimal exemption spared it,
  the post-condition then refused the document, and it would refuse on
  every retry. Resolution: drop the exemption so scrubber and
  post-condition share one definition and cannot disagree by
  construction (same argument as #54's atomicity). Measured cost: nothing
  — `999,999.99` is eight digits and commas break runs. Prefer one rule
  and an over-redaction to two rules and a permanent refusal.
- **A broken `&&` chain skips the step you cared about and runs the ones
  after `;`.** `rmdir mcp && git push … && verify …; pip …; launchctl
  kickstart …; curl …` — `rmdir` failed on a `__pycache__`-only
  directory, so the push and the verification never ran, while the
  restart and the live probes did (against the local checkout) and all
  passed. The lead then told two teammates "#64 merged" while
  `origin/main` still lacked it. Put the announcement *after* a read-back
  of the remote (`git rev-parse origin/main`, `gh pr view --json state`),
  and don't mix `&&` and `;` in one line — one chain, one outcome.
- **`${VAR}` in `.mcp.json` expands from the Claude Code process's
  environment, not from `.env`.** Measured: with `APP_API_TOKEN`
  unset, `claude mcp list` prints `Missing environment variables:
  APP_API_TOKEN` under the `.mcp.json` location; with it exported the
  warning is gone. So the HTTP-mounted MCP needs the token exported in
  the shell that launches Claude (e.g. `~/.zshrc`), which is the same
  plaintext exposure as `.env` on the same machine. A changed `.mcp.json`
  also puts the server back to "Pending approval" — a new interactive
  session in the repo (or `/mcp`) approves it; headless runs use
  `--mcp-config .mcp.json --strict-mcp-config` to skip that gate.
- **A single ancestry reading taken while someone else is pushing is not
  evidence; two readings that disagree mean "in flight".** The reviewer's
  first check during the lead's #64 push returned "`6884e0b` an ancestor
  of main? NO — 30 paths still under `mcp/`, 0 under `lib_mcp/`",
  one step from reporting #64 stranded (the #42 shape). The next command
  contradicted it within seconds, which is only possible if the fact is
  moving. Re-fetch and re-read before reporting anything missing or
  stranded. The asymmetry is the point: a stale positive gets corrected
  later; a stale negative sends someone hunting for work that was never
  lost.
- **A negative control is only as good as its positive setup — before
  reporting that something doesn't work, verify the thing you set up
  exists.** The reviewer's first longest-pattern-wins test "disproved"
  the claim: the second `POST /merchant_rules` had 422'd on a made-up
  category (`transport_fuel`), nobody asserted it, only one rule existed,
  so the short pattern "won". With every setup call asserted and two
  real category ids, longest-wins held. This is the general form of
  three lessons above (the unrun command, the mid-push reading, the
  unasserted setup): all produce a confident wrong negative. Assert
  every setup call's status before interpreting the result it enables.
- **A property beats examples.** "Three amounts convert wrong" invites
  "avoid those three"; "`int(float(v)*100)` is wrong on 18,348 of 400,002
  two-decimal values (4.6%), `round(...)` on 0" is a property of the
  method that survives someone adding a fourth example that happens to
  work. When a runbook argues from examples, sweep the domain once and
  print the rate.
- **A deletion that removes its own tests cannot fail the suite — count
  `def test_` against `HEAD`.** Replacing one test in
  `test_migrations.py`, an implementer's edit sliced to end-of-file and
  silently dropped three unrelated tests and a module constant. Green
  suite, no conflict markers. Caught only by `grep -c '^def test_'` on
  both sides (17 vs 14), then the file was reverted and every edit redone
  from a clean base rather than patched. Third instance today of the
  same shape (green suite, no markers, `SEARCH … USING INDEX`): the check
  that looks sufficient is structurally blind to the thing that went
  wrong, and only counting sees it. Any PR that edits a test file gets a
  collected-test-name diff against main before merge.
- **A test can assert the right thing for a stated reason that is false,
  and nothing catches it.** `create_merchant_rule`'s omit-when-None test
  asserted the correct body and its docstring explained *why* with a
  mechanism the API doesn't have (null vs absent distinction — measured
  identical at every branch). The usual docstring failure is claiming
  more coverage than the assertions give; this is the nastier inverse:
  correct assertion, fictional justification, and a reviewer asking
  "does the test test what it says?" answers yes. When a docstring or
  comment states a *mechanism*, measure the mechanism, not just the
  assertion.
- **The general form (review-1): the check most people reach for is
  incapable of observing that particular failure.** `merge-tree` cannot
  see a whole-file rewrite from a stale snapshot; a green suite cannot
  see a deletion that removed its own tests; a single ancestry reading
  cannot see a push in progress; `EXPLAIN` cannot see that an index
  exists but isn't chosen unless you name the index. Three tools, one
  shape. Before trusting a check, ask what failure it is *structurally
  blind* to, and add the counting or naming check that sees it.
- **A census that says "nothing anywhere" deserves distrust before
  belief.** The scrubber-floor census first reported zero label-context
  hits because it searched only the 40 characters *before* each digit
  run; bank layouts put the number before the label about as often as
  after. Searching both directions found several. Three of four measures
  returning zero is a prompt to check the instrument, not a result.
- **A security justification nobody re-checks is what gets deleted
  later when someone notices it's false.** The 16-digit ceiling was
  removed citing a long digit run in a sample document that "passed
  through silently"; re-imposing the ceiling to test the claim showed that run
  was already redacted via its parts. The change was still right; the
  reason was fiction, and the measuring regex that produced it had mixed
  separator classes. The shipped comment now states the constructed case
  that genuinely survives the old rule *and* records the retraction —
  which is worth more than a comment stating only the right reason.
- **Treating two separator classes as one made `ACME COFFEE 12.34
  2026-01-01` a twelve-digit number.** Dots and whitespace as
  simultaneous separators joined an amount and a date into a single run
  the fail-closed post-condition then refused — every genuine statement
  line would have been unprocessable. The tests caught it; inspection
  would not have. Require a uniform separator class per run, and keep
  the must-survive cases (amount, ISO date, comma-grouped total) in the
  suite as first-class assertions.
- **When two components are specified to agree, test the agreement as a
  property, not each side on examples.** The scrubber and its fail-closed
  post-condition each passed their own tests; the post-condition checked
  dot-separated digit runs the scrubber never scrubbed, so any letterhead
  phone number (`555.555.1234`) withheld the whole document forever. Both
  parts were correct; the composition was not, and the first review
  (scrubber on instances, endpoint on a happy path) could not see it. A
  476-shape property check — "whatever `scrub_text` returns must pass
  `assert_no_account_numbers`" — found 84 failures, all dotted. The fix
  derives the checker's classes and floors from the scrubber's so "at
  least as strict, over the same classes" holds by construction, and the
  property test stays anyway: deriving narrows drift, it doesn't close it.
- **A spec function must not read the implementation's constants, or the
  test is a tautology.** The property test encodes the floors (contiguous
  7+, label-context 7–8, separator-joined 9+) as its own function of
  (digit count × separator class × label present). If it imported the
  scrubber's tuples it would pass whatever the scrubber does — the same
  shape as asserting a vocabulary against itself. It is the most natural
  "cleanup" a later reader would make, so the file says not to.
- **Two instruments means two methods, not two copies.** The lead asked
  the reviewer to keep an untouched copy of the property test to re-run
  against the new head "so the PR's test and the re-check are
  independent". They aren't: the same code run twice agrees with itself
  by construction, including in whatever it is blind to. The reviewer's
  re-check instead goes end-to-end through `POST /documents/extract`
  (page joining, fail-closed path, response model — the property test
  never touches HTTP), reads the derivation structurally, and mutates it
  (drop a class from the scrubber's tuple; confirm something goes red).
  Running a guard never tests the guard; only breaking it does.
- **"677 passed" with the defect present.** The head that lowered the
  scrubber floor was green while a dotted phone number still withheld
  every document, because nothing in the suite covered the
  scrubber/post-condition composition. That is the structurally-blind
  heading in live form, and it argues for sequencing: land the test that
  can see the defect *first*, so the fix commit goes from red to green
  and names its own gap, instead of a reviewer finding it again by
  another route. When a fix is dispatched with a new test, the test
  lands in the first commit.
- **A test file that pytest never collects passes by never running.** The
  test proving the autouse settings fixture fires was first written in
  `conftest.py`, which pytest does not collect. Green. Caught because
  the suite count did not move (635 → 635); moved to `test_main.py`, 637.
  Third time in a day counting saw what green could not.
- **A traversal case that is lexically inside proves nothing about
  `.resolve()`.** `<root>/data/../data/x` starts with `<root>/data` as
  text, so the path guard matched with or without resolution and the
  test asserting the property caught nothing under mutation. The case
  has to be lexically *outside* and only inside after resolution:
  `<root>/elsewhere/../data/x`. Found only because the implementer
  mutation-tested a test they were confident in — drop the thing the
  test claims to protect and watch for red; zero reds means the test is
  a statement, not a check.
- **A deny-list must enumerate every location the real thing might be;
  an allow-list needs only the one place tests may touch.** The guard
  that stops a pytest process migrating the live database compared
  `db_path` against `REPO_ROOT / "data"` — *this checkout's* root. From
  a worktree with an explicit absolute `APP_DB_PATH` pointing at the
  real repo it did not fire ("RESULT: NOT refused"), and every
  implementer works in a worktree. Inverted: under pytest, refuse any
  path *not* under the pytest temp root — one rule that covers
  `db_path`, `documents_dir`, `jyra_dir` and `intake_dir` at their
  readers. When a guard is a list of things to refuse, ask what it takes
  to keep the list complete; the fail-closed direction is usually the
  list of things to allow.
- **Merge order is a safety decision when a hazard is live on main.**
  #69's guard was queued behind #68; the reviewer measured that on
  current main a `with TestClient(app)` in the real checkout runs
  startup migrations against the live database (the lifespan calls
  `get_settings()` directly, so `dependency_overrides` never reaches it)
  and recommended merging #69 first. It went in ahead. "Which PR was
  ready first" yields to "which PR closes the thing that can hurt us
  today".
- **A test that encodes a defect as intended behaviour is how the defect
  survives review.** The scrubber's post-condition checked a separator
  class the scrubber never scrubbed; the implementer's own test asserted
  that as a feature ("the post-condition is wider on purpose — a wider
  net catches detector gaps"). It wasn't a net, it was a permanent
  outage for any document containing a dotted phone number, and the
  test would have defended it. When a test's docstring justifies an
  asymmetry between two components, that asymmetry is the first thing
  to measure end-to-end.
- **The lexically-inside blind spot reproduces on the first try, one
  commit after reading about it.** `intake/../intake/statement.pdf`
  passed with `.resolve()` removed because pathlib leaves `..` in
  `parents`, so the root was still a lexical ancestor. Rerouted through
  a sibling directory; red without `.resolve()`, green with it. A runbook
  entry is a warning, not a vaccine — the mutation check is what
  actually catches it, every time.
- **When a library needs a fact only the test harness knows, the harness
  publishes it.** The allow-list guard needs pytest's real temp root;
  `tempfile.gettempdir()` is right by default and wrong under
  `--basetemp` (measured: `/private/tmp/bt/x` and a path inside the repo
  are both outside it), where it fails closed on every test — the
  failure that gets a guard deleted. `getbasetemp()` is authoritative
  but only reachable from pytest. So a root `conftest.py` exports it as
  `APP_TEST_TMP_ROOT` for every test package and the guard reads it,
  falling back to `gettempdir()` with a WARNING rather than to "allow
  everything".
- **A diff is only evidence if you know what it's measuring from.** The
  reviewer's scope check on #69 diffed `e997abd..03d7120` — main's tip
  against the branch tip, a cross-branch comparison — and it listed
  `runbooks/team-workflow.md`. That was written down as the implementer
  creeping onto the shared runbook. It was the lead's runbook commit
  being *absent from the branch*, not the branch editing it; diffing
  against the commit's actual parent (`fd58dfa`) settled it in one
  command. Two plausible bases were available and the one that made a
  story got picked. The failure isn't misreading the tool; it's not
  noticing the tool answered a different question than the one asked.
  For "what did this PR touch", diff the merge-base, not main's tip.
- **A sweep for digit runs must exclude machine-generated fields by
  name, or it flakes on ids.** `test_nothing_account_shaped_reaches_the_log`
  swept every log line for a 9+-digit run and failed about one suite
  run in three: the middleware's `request_id` is `uuid4().hex[:12]`, and
  0.35% of those are all digits with many more carrying a long digit
  prefix (`0123456789ab` holds a 10-digit run). The test was wrong, not
  the product. Fix: exclude exactly `request_id` and `timestamp` by
  field name, sweep every other field, assert the excluded set is
  exactly those two so it can't grow by a one-word edit, and keep the
  mutation (log an unscrubbed filename → red) as proof it's still a
  check. A soak loop that records only the run number and not the
  failing test's name has measured nothing — capture the name.
- **Six clean runs prove almost nothing against a 1-in-3 flake — compute
  the probability.** P(6 clean | 1/3 flake) ≈ 9%; P(30 clean) ≈ 2.4e-6.
  The reviewer's instinct was to stop at six. "It passed a few times" is
  not evidence about a probabilistic failure; state the base rate and
  the run count together, or the number is decoration.
- **A mutation that does not create the condition proves nothing, and a
  mutation that breaks the file is not a result.** Removing only the
  leading `\b` from a label pattern left `no\b`, which still can't match
  inside NOVEMBER — "70 passed, the test missed it" was a partial
  mutation, not a missed test; removing both went red on 4 cases.
  Separately, an inline comment dropped inside a dict literal commented
  out the closing brace and produced 13 *collection errors*, nearly read
  as "the mutation caused failures". Gate a mutation with `ast.parse`
  before running it, and confirm the mutated code actually exhibits the
  behaviour the test is supposed to catch.
- **Don't edit the tree a soak is running against.** Twice in one PR the
  implementer changed files mid-soak and had to discard the run. A soak
  measures one frozen head; push it, note the SHA, and run against that.
- **A label pattern without word boundaries silently collapses a
  per-class rule.** `no` matched inside NOVEMBER and NOTE, `card` inside
  DISCARDED, so "label context" fired on nearly every page and
  the separator-joined floor dropped from nine to seven everywhere — the
  carefully designed per-class split wasn't running. Safe direction, but
  a design that isn't executing is a design on paper. Bound label
  tokens (lookarounds, since `A/C` and `No.` end on non-word characters),
  add ordinary-word negatives (`ANOTHER 1234 567`, `ACME DOMINO 1234567`)
  to the property test, and re-measure any census the unbounded pattern
  produced before citing its number.
- **A fallback can mask the death of the thing it backs up — mutate the
  primary, not just the guard.** Removing the allow-list guard failed
  two tests; *deleting the publisher* (the root `conftest.py` that
  exports pytest's temp root) failed nothing, because the
  `gettempdir()` fallback gives the same answer in the default
  configuration. Green suite, guard quietly depending on a fallback
  that is wrong in exactly the `--basetemp` case the publisher exists
  for. The test that closed it ties the *published* value to *what the
  guard actually reads* — a published variable the guard ignored would
  satisfy a weaker test and protect nothing.
- **Under an allow-list you cannot fake production under `tmp_path`.**
  `tmp_path` is legitimately allowed, so the three refusal tests that
  simulated "the real database" with a fake repo under it had to move
  their production paths *outside* the allow root. That is a consequence
  of the guard's shape, not a weakening, and it looks like a weakening
  to anyone who doesn't know why — the docstring says so.
- **Tests were green for weeks while writing into the repository.** The
  first arming of the every-reader allow-list guard caught four
  hand-built `Settings` that omitted `jyra_dir`, so it defaulted to
  `REPO_ROOT/data/jyra` and every run of `test_db.py`/`test_migrations.py`
  created directories inside the checkout. Nothing asserted *where* they
  wrote, only that what they wrote was correct. Confirmed by deleting
  `data/` in the worktree, running the suite, and watching it not come
  back. A guard applied "only at the database" would never have seen
  it; apply isolation guards at every reader.
- **`immutable=1` makes `PRAGMA journal_mode` describe the connection,
  not the file.** On the live WAL database, `sqlite3
  "file:…?immutable=1" "PRAGMA journal_mode;"` prints `delete`; an
  implementer nearly reported "the live DB isn't WAL, so todo #40's
  precondition is wrong". The file header (bytes 18/19 = 2/2) is the
  authoritative check. Same family as the grep-across-a-line-break
  phantom: a tool artifact read as a fact about the thing.
- **A `cp` of a WAL database under a live server can silently miss
  committed rows.** They sit in `-wal` until checkpoint. A pre-import
  safety net taken that way lacks exactly the state you'd roll back to.
  Backups are `sqlite3 .backup` / `Connection.backup()` over a
  `mode=ro` source; never `cp`.
- **When a change is announced as "comment-only", check before applying
  the comment-only procedure.** The head sent for an AST glance also
  swapped the label pattern from `\b` to lookarounds — a real rule
  change differing on roughly a third of the probe inputs. The reviewer ran the AST
  comparison first, saw three files differ structurally, and reviewed it
  as behaviour instead of waving it through on the announced premise.
  The change was right for a reason neither party had named (`\b`
  treats digits as word characters, so `Account1234567` — the common
  pypdf shape — wasn't label context); it was found by testing the
  reviewer's reasoning rather than deferring to it.
- **"Refused after reading" is no protection — assert the file was never
  opened.** The extract-reader guard's refusal surfaces as a 500 through
  the app's catch-all, so a status code can't distinguish the guard from
  an ordinary bug. Each refusal test therefore asserts the refusal in
  the log *and* that the file was never opened; mutating the hook to
  read first and refuse second fails 2 tests. For a directory holding
  real statements, the order is the whole guarantee.
- **A guard keyed on `PYTEST_CURRENT_TEST` can only be verified from
  inside a test run.** An ad-hoc script outside pytest "proved" the
  guard let the file be read — because outside pytest it is correctly
  inert. The probe was wrong, not the guard. Verify test-only guards
  with tests.
- **Don't guess categories for real money.** impl-2's rule seeding left
  several ambiguous merchants (~$1,234) unmatched rather than mapping
  them: a vendor whose charges could belong to either of two assets
  changes one asset's `cost_of_ownership` or the other's, and a wrong
  rule silently miscategorizes every later charge beneath it. Unmatched
  is honest; the intake skill asks. Likewise a merchant class the
  taxonomy doesn't cover (a generic "Category X") lands in the null bucket with a logged recommendation rather than a
  category invented on the owner's behalf.
- **A test written to prove independence from X can itself depend on
  X.** `test_the_allow_list_root_comes_from_the_harness_not_from_tmpdir`
  deleted the published root and called `init_db`, so the guard fell
  back to `gettempdir()` — which only worked because the *default*
  pytest basetemp happens to live under `gettempdir()`. Under any
  `--basetemp` the setup itself was refused and the test died before its
  assertion. It passed on a normal run for a reason unrelated to what it
  checked. When a test asserts "we don't rely on X", run it in the
  configuration where X is wrong; that configuration is the test.
- **An authorization to read real data goes in the decision log at the
  moment it is given, with the exact fields.** impl-2's CSV read was
  authorized verbatim in a dispatch message; the log's D3 entry
  recorded the task and not the read path. impl-1, told "it's
  authorized in writing", grepped the log, found nothing, and held the
  import — correct. The fix was a log entry (D9), not a reprimand: the
  gap was the lead's. A teammate who cannot find the authorization in
  the log holds.
- **A review names the head it ran on, and the lead checks that head is
  current before acting on the verdict.** #70's "changes requested" ran
  on `c934bd7` after `1e70e4a` had already landed with the fix for
  finding 1 — the messages crossed. Neither party was wrong; the
  verdict was simply about a commit that no longer existed as the head.
  Reviewer: `gh pr view N --json headRefOid` first, quote it. Lead: compare
  it to the latest announced head before dispatching fixes.
- **A number changes meaning as it is relayed — count what you find.**
  "5 of 10 intake documents aren't PDFs" reached a NEVER clause in the
  intake skill; the truth is 3 CSVs and 7 PDFs. The origin was a count
  of 12 *files* (including `.DS_Store`) where the unit that mattered was
  10 *documents*; nobody was wrong about what they saw, and nobody
  re-derived it. Inside a NEVER clause a wrong specific undermines the
  rule it supports. The skill now says to count rather than repeat.
- **Verifying something adjacent to a claim, then stating the claim as
  verified.** impl-2 checked the MCP tool surface, found no
  `extract_document_text` wrapper in its session, and told impl-1 the
  *capability* didn't exist — the endpoint was live and enforcing. Same
  session, same agent: quoted a dispatch message as "the decision log"
  and sent a teammate to verify it there. Both self-reported. The check
  is: is the thing I measured the thing I'm about to assert? If a
  teammate is told to go verify, the source named must be the one that
  was actually read.
- **A passing result can vouch for the wrong rule.** impl-2's
  overlap check ("no pattern is a substring of another") returned zero
  hits, which made "refuse nesting" look like the right gate for the
  intake skill. It isn't: `ACME` + `ACME WEB SERVICES` is the
  legitimate shape longest-pattern-wins exists to support, and the
  hazard that actually loses money is nesting across *different*
  categories. A zero-hit check proves the corpus was clean, not that the
  gate is right; the skill treats a hit as a question.
- **A parity assertion passes while both sides are wrong in the same
  way.** The intake skill's dry run asserts `preview unmatched == API
  unmatched`. Before the matcher fix merged, the preview (already
  token-bounded) and the API (still bare substring) agreed on the
  synthetic corpus — the assertion was green and measured nothing. After
  the fix the number should go *up*, because some earlier matches were
  false positives. A green agreement test only means the two agree; run
  it against a case where they *should* differ before trusting it.
- **A skill is instructions for someone else to implement; an ambiguous
  sentence there is a latent defect in a way working code isn't.** The
  skill's code was filter-then-longest, but its prose said "find the
  matching rules and apply longest-pattern-wins", which reads just as
  naturally as longest-then-check — and that ordering lets `ACME
  PU` beat `PUB` on "ACME PUB". Fixed in prose with the example.
  When two implementations must agree, adopt one canonical function
  rather than two that agree on ten cases.
- **The scrubber's own `****0000` token is rejected by `last4`.** The
  attribute is length-limited to four; a skill deriving last4 from
  scrubbed text has exactly that string in hand and copying it across is
  the natural move (measured: 422). The entity's display name may carry
  the mask; the attribute takes the four digits.
- **Find-or-create must be tested on the second pass.** A version that
  always creates would quietly fragment one account across five entities
  over five imports, and every per-entity total would be wrong with
  nothing erroring. The dry run's second pass asserts it *finds*.
- **The merge announcement goes out after the read-back, never in
  parallel with it — second instance.** The lead sent "merging now" to
  the reviewer in the same tool batch as the merge command. The command
  read the head back (`801432a`, not the approved `e02504c`), refused
  the merge — correctly, that is what the check is for — and the
  message was already wrong. Same shape as the skipped-push
  announcement earlier in the day. Merges are two turns: run and read
  back, then announce what actually happened.
- **A head that moves after approval is not an incident when the merge
  gate catches it; it is an incident when it doesn't.** The gate
  `test "${H:0:7}" = <approved>` stopped a merge of unreviewed commits
  (a rebase plus a new test). Keep it exact-SHA; never loosen it to "the
  branch".
- **Inferring a measurement from a mechanism.** "Some of the 80
  matches were false positives, so expect the unmatched count to rise
  after the fix" — the collision *shapes* were real, but whether
  `ACE`/`PLACE` occurs in the stored descriptions is a fact about the
  data, and impl-2 had measured zero false positives. The inference
  inverted a check: on the actual data preview and API should now agree
  exactly, and a disagreement is a stop signal, not evidence the fix
  worked. Same family as `-10.50` and "5 of 10": reasoning toward a
  number instead of measuring it. Self-corrected by the author.
- **`response_model` silently drops a field the endpoint set.**
  `attachment_count` was computed in the route, asserted in the test,
  and absent from the wire until it was added to `TicketDetailResponse`
  — the field existed everywhere except where it mattered. Caught only
  because a test asserted it; a field meant for a human reader would
  have vanished quietly. Every new response field gets a test that reads
  it back through the client.
- **A combined test case can prove the weaker property.** `ZIPCAB` vs
  "ZIPCAB CO/ZIPCABEATS" only shows the check doesn't reject everything
  when one occurrence is bounded; it cannot show the buried occurrence
  isn't matched — an implementation that matches anywhere as long as
  *some* occurrence is bounded passes it. `ZIPCABEATS ANYTOWN` alone is
  the test of the property. Split cases so each proves one thing.
- **The announcement trigger is "did the SHA change after someone looked
  at it" — including a plain fast-forward.** impl-4 announced `af6bcd4`
  (a rewrite) but not `801432a` ("just adding the tests you asked for"),
  and the merge gate stopped on the mismatch. Whether history was
  rewritten is irrelevant to whoever is merging; only the SHA under
  review matters. Any push to a branch under review carries the old→new
  line. (impl-4's own restatement, adopted verbatim.)
- **A test that can pass on prose can fail on prose.** A guard against
  `SELECT *` grepped the source and matched the implementer's own
  comment explaining what the code avoids. Strip comments before a
  source-text check, and pair every negative assertion ("no `SELECT
  *`") with a positive one ("the columns are named") so the test cannot
  be satisfied or broken by a sentence.
- **Prove a mirror discriminates before trusting its "no change".**
  impl-2's coverage replay reported 80/20 under the new matcher —
  exactly the old number. "No change" is also what a harness silently
  still running the old logic would report, so before trusting it they
  ran seven cases where old and new must differ (both false positives
  rejected, `ACE1234` rejected, `re.escape` holding `Acme.ca`'s dot)
  and three differed. Only then is an unchanged number a result. The
  same discipline as the property test on #68: a check that agrees with
  itself is not a check.
- **A fix that is a no-op on today's data is still worth gating on when
  its failure persists on rows.** The bounded matcher changed nothing
  for the current descriptions (zero false positives measured
  beforehand). The gate cost an hour and bought the proof that it also
  *lost* nothing across `*` and `-` — the direction that would have
  written nulls onto real rows — and a harness that will catch the next
  regression.
- **Lead every report with a one-line status block.** After the fifth
  exchange in a day where the lead's dispatch and the reviewer's report
  crossed on work already delivered (`#71` reviewed at one head while
  the next was being announced; `[todo #7]` dispatched after its PR was
  open), the fix adopted is a first line of the form `#NN <sha>
  <verdict> · <other item> · <pending>` on every report, and `#NN <sha>
  -> you` on every dispatch. A crossed message is then obvious without
  re-reading the body, and the SHA in the first line is the one that
  gets compared to the merge gate.
- **Test the text people will follow, not a retyped copy of it.** The
  intake skill's parity test extracts the python fence from `SKILL.md`
  at test time and runs it against the real matcher, so a future edit to
  the skill is what gets tested. The first version exec'd only the
  `matches` expression and hardcoded the driver, so the fence's
  filter-then-longest lines weren't under test at all — it would have
  stayed green whatever the skill told the reader to do with the
  matches. Caught by mutation-testing the harness (three mutations; the
  longest-then-check inversion only went red after the fix). A parity
  harness is verified the same way as any guard: break the thing it
  claims to catch and watch for red.
- **Check that a field is optional before telling a skill to omit it.**
  "Leave `account_subtype` null when unclear" would have been a new bug
  if the attribute were required; impl-1 read the schema (`| None =
  None`) first. The same read found that the legal value is `checking`
  while the skill's own example said "Chequing" — a 422 waiting in the
  example. Examples in skills get executed against the real validator.
- **"Added a test" is a claim; `test X exists at <sha>` is checkable.**
  A differential parity test was described in a dispatch, cited in the
  decision log as the drift-catcher, and did not exist in the repo —
  it was a scratchpad script. The reviewer found it by counting
  collected tests at the PR head against main (equal; the PR was
  docs-only) and grepping every branch. Second described-but-absent
  artifact in a day (the first was #68's "five items" head carrying
  one). The status-block convention applies to artifacts: name the file
  and the SHA it exists at.
- **A zero count in a test's own output is a warning, not a pass.** The
  parity corpus produced zero ambiguous ties and that was reported as
  reassuring; a corpus with no ties cannot discriminate any tie-break
  rule from any other, so the harness stayed green whichever rule the
  implementation used. Mutation-testing the harness didn't see it
  either, because mutation testing only probes behaviour the corpus
  reaches. Check that the corpus exercises the case you claim coverage
  of — then a second defect appeared: the "deliberately different
  insertion order" comment sat over code that inserted in id order.
- **Nothing in the happy path reaches it.** Three finds in one hour
  share a shape: `chequing` is a 422 where the skill's own example said
  "Chequing"; `last4: "unknown"` is a 422 (`max_length=4`), a fallback
  that had been dormant since first draft and would fire only in the
  degraded branch; the tie path was uncovered by every corpus. Each
  survived several reviews because normal inputs never touch them. Walk
  the degraded branches on purpose — validate every literal a skill
  tells the reader to write.
- **A success response says the call succeeded, not that the content
  survived the path it travelled.** A ticket note posted through a
  shell double-quoted string had its backticked tokens executed and
  eaten: "it matched  inside NOVEMBER and  inside DISCARDED" — reads as
  complete prose, carries none of the information. The API returned
  200. Rule: anything going into a durable record is posted from a
  quoted heredoc (`<<'JSON'`) and read back afterwards.
- **A test for a bug is run against the unfixed code first; if it
  passes before the fix, it isn't testing the fix — however right the
  assertion looks.** Of three tie-break tests handed to the implementer
  of the fix, two passed on current main: "oldest rule wins" was green
  only because the unordered `SELECT` hands `max()` rows in insertion
  order, which in that test matched id order. It asserts exactly the
  right thing and would not have caught the bug. Only the
  flipped-insertion-order test discriminates (same ids, same patterns,
  same description; category flips coffee → fuel). Plain red-green,
  but the specific failure is a correct-looking assertion smuggling in
  a coincidence — three times in one day (uncovered tie path, the
  harness's insertion-order comment, this). Hand over a test labelled
  weak rather than one discovered weak after it vouched for a fix.
- **Check the value the sentence merely mentions, not just the one it
  argues about.** Reviewing the D12 section, the reviewer verified
  `last4='****1234'` is rejected (the case the text was arguing) and
  did not test `"unknown"`, the fallback the same sentence tells you to
  write — also a 422. Every literal a skill instructs the reader to
  store gets validated, including the ones in the fallback branch.
- **Opposite failures, opposite symptoms — say which is which.** A
  wrongly split account double-counts (both copies `created`); a
  wrongly merged pair silently drops (`created=0
  skipped_duplicates=1`, a missing row). The skill said "double-counts"
  for both. Someone reconciling after a merge would hunt for a
  duplicate, find none, and exonerate the merge. When a paragraph
  exists to tell a future reader what to look for, measure the symptom
  it names.
- **`rowid` is not a stable identity on a table without an INTEGER
  PRIMARY KEY — VACUUM renumbers it, and our backup path is `VACUUM
  INTO`.** The tie-break fix's obvious form (`ORDER BY length DESC,
  rowid ASC`, true oldest-wins) would have changed which category a
  re-import writes after a restore from backup — from an operation
  nobody would connect to merchant matching. `id ASC` on a uuid is
  arbitrary with respect to age but stable forever; the requirement was
  stability, and "oldest" was only ever a proxy for it. Name the actual
  requirement before choosing the mechanism, and check what else
  touches the column you're about to order by.
- **A decision's rationale can contradict its mechanism — check the
  column type.** D15 said "oldest rule wins" and specified `id ASC`;
  `merchant_rules.id` is uuid4, so on stored rules it could pick the
  *newer* rule in a tie group, and the one example named in the ticket
  (ACME CAFE/ACME GAS) agreed by luck. Two implementers caught it independently
  before code. When a rule says "oldest", "first", "latest", look at
  what the ordering key actually is.
- **Read-only opens of the live WAL database fail from the `sqlite3`
  CLI under the sandbox (error 14, the `-shm` write) — not from
  Python.** `sqlite3.connect("file:data/app.db?mode=ro",
  uri=True).backup(dst)` works, and is the skill's documented backup
  line; `sqlite3 -readonly` and `file:…?mode=ro` from the CLI do not.
  An implementer first reported this as "read-only opens fail", went to
  fix the skill, tested the documented line first, and found nothing
  wrong — the same test-before-you-change habit, pointing the other
  way: the check that stops you changing working code. Scope a failure
  report to the tool that failed.
- **Detectability, not repairability.** The skill first called a wrong
  account merge "unrecoverable". It isn't — split the entities and
  re-import the retained source. What is asymmetric is that a merge's
  symptom (a missing row, an inflated `skipped_duplicates`) is the one
  nobody looks for. State the asymmetry that's actually true.
- **A probe that fetches its inputs differently from the procedure it
  validates tests the predicate, not the procedure.** The parity probe
  pulled all 57 rules and found 0 disagreements; the skill it was
  validating called `list_merchant_rules` once and would have received
  50 (default page). So the probe proved the matching rule agreed and
  said nothing about what a real run would compare. Drive the probe
  through the procedure's own steps — its fetch, its paging, its
  filtering — or the green covers a different program.
- **A rule that relies on people noticing their own leaps has the same
  defect as a rule that relies on failure being loud.** Two implementers
  each made the mechanism-for-measurement leap three times in a day and
  each caught only the other's — none of their own. That is the case
  for review as structure rather than as courtesy: the safety property
  cannot live in the one place that is unreliable at the moment it's
  needed. "Fails loudly" in a NEVER-list justification is a reassurance
  someone can reason past; if it failed loudly you wouldn't need the
  rule.
- **Order a NEVER list by reversibility, not by which item was the
  better find.** Reading a receipt into context bypasses the only
  scrubber and cannot be unread; a filename-guessed `doc_type` is a
  wrong row you refile. Silent-and-irreversible goes first, and the
  list says why, or the ordering reads as arbitrary.
- **A truncated list yields a wrong answer shaped like a right one.**
  Every `list_*` tool pages at 50 by default and says nothing about it;
  57 merchant rules and 64 categories were both silently truncated for
  any single-call consumer. "This category doesn't exist" and "this
  merchant has no rule" are legitimate answers the skill is written to
  give, so the truncation produced them with no signal. Any consumer
  that reasons over a whole set pages until `len(items) == total`, and
  a tool that paginates says so in its first line.
- **A drain loop that advances by `len(items)` spins forever on an
  empty page against a stale total.** `total` is a separate count; a
  row deleted between the count and the page leaves `total` above what
  any offset can return, and the loop reads as obviously correct. An
  unattended run would hang silently rather than fail. Caught only
  because the termination test was written first and watched to fail
  against the unguarded loop. Empty page → stop; count mismatch → stop
  and report.
- **A check built for one property is not evidence about an adjacent
  one.** The reviewer's 12-case parity probe would have scored 0
  disagreements even against the 50-of-57 fetch: its cases were chosen
  to exercise the matching rule and were insensitive to the fetch in
  both directions. "The probe used the wrong fetch" understates it —
  the probe was blind to the class regardless. When a green result is
  offered as evidence for a claim, ask which property the cases were
  built to discriminate; if it's a different one, the green is about
  that.
- **Two defects that surface identically from opposite directions are
  the argument for an unconditional stop.** The matcher defect had the
  preview right and the import wrong; the pagination defect had the
  preview wrong and the import right. Both appear as "preview and
  import disagree". The skill therefore stops and reports rather than
  adjudicating which side is correct — it cannot know, and this pair
  proves it.
- **An iterating guard covers the setting nobody remembered.**
  `inbox_dir` was the first new path setting after the allow-list
  guard landed; pointing it at a real directory failed
  `test_every_data_bearing_path_in_the_fixture_is_under_tmp_path` with
  nobody having added it. An enumerating guard would have shipped the
  setting unprotected. That was the original argument for the
  inversion, and it paid off on the first new setting.
- **A precedence test that doesn't assert *which* candidate won tests
  that matching happened, not that precedence held.**
  `test_import_statement_applies_longest_matching_merchant_rule`
  asserted `created == 1` and `unmatched == []`; both fixture rules
  carried a category, so either winner emptied `unmatched`. Flipping
  `length DESC` to `ASC` — shortest-wins, the opposite of the repo's
  headline rule — left the whole suite green. Found only because the
  implementer mutation-tested a key they weren't changing. The test
  now asserts the category. The name will keep telling you otherwise;
  read the assertion.
- **`cat >` onto an existing test file destroyed 30 tests and the suite
  went green at 15 passed.** What was written passed; what was
  overwritten was simply gone. Caught by the collected-test count
  against main (768 vs 783), the same instrument that caught #57's
  stale snapshot and #70's slice-to-EOF. The count diff is a standing
  step in the implementer's pre-push list, not only the reviewer's.
- **A test can go red for a reason adjacent to the one you care about
  and look like proof.** Mutating the skill's `fetch_all` into the
  single-call bug turned the differential test red — on the count guard
  ("retrieved 50 of 57"), not on a category disagreement. That is an
  assertion about rule count wearing a differential's clothes. With the
  guard neutralised, the differential still caught it (15 of 100
  descriptions disagreed, every one the bug's signature) — so both
  layers work, proven separately. When a mutation goes red, read which
  assertion fired.
- **If a test can't tell you how many records each side saw, it can't
  see the truncation class at all.** A differential whose expectation
  and result are built from the same fetch is structurally blind to
  pagination; the fix is two genuinely different sources (the API's
  written result vs the procedure's own retrieval) and a record count
  on each side.
- **Each endpoint passed its own tests; the defect was in the
  intersection.** `/documents/extract` permitted `intake_dir` and
  `documents_dir`; `POST /documents` permitted `inbox_dir` and
  `intake_dir`; nothing permitted extracting from `inbox/` — the
  document-intake skill's entire territory — and its dry run died on
  step 2. The extract tests used `intake_dir`; the register tests never
  called extract. Same shape as the scrubber/post-condition separator
  gap: two parts correct, the pair unusable, and re-testing either part
  would never show it. A flow is a test subject in its own right; the
  fix's test asserts the composition (register from `inbox/`, then
  extract the stored copy), not the endpoint.
- **PR bodies describe the intended final state and get written before
  the last commit.** Third described-but-absent artifact in a day: the
  document-intake PR body said the NEVER list "is ordered by
  reversibility, and says so"; the file didn't say so. All three were
  small and all were caught by looking rather than by the suite. When
  the announcement names an artifact or a sentence, name the file and
  line it exists at.
- **A fixture where the candidate keys agree cannot discriminate
  them.** ACME CAFE/ACME GAS — the tie example named in the decision — is the
  pair where ACME CAFE is both the oldest rule *and* the lowest id, so the
  tie test stayed green under lowest-id, oldest-wins and scan order
  alike. The discriminating fixture is the live pair where they
  disagree (ACME GROCERY written on the 1st, EXAMPLE FUEL on the 5th, EXAMPLE
  FUEL's uuid sorts lower);
  inserted one way the first test goes red, the other way the second
  does, so the pair pins the answer regardless of scan order. Pick the
  example where the rules diverge, not the one that reads nicely.
- **When a collected-name diff shows a test "lost", verify the name,
  not the count.** #80's diff against main shows exactly one missing
  test: a rename folded in from the #75 cleanup. Checking the name is
  the version of the check that would have caught the `cat >` overwrite
  on its own.
- **`zip()` over parallel sequences truncates silently — it is the
  enumerate-vs-iterate hazard in another costume.** The extract
  reader's guard loop zipped three roots against two labels; the third
  root (`inbox/`, the one the PR existed to add) was never guarded, and
  nothing failed because the guard tests had no inbox case. Same
  function as #70's "applied to only half of it" comment, now at
  two-thirds. Pair data with its label in one structure so they cannot
  disagree, or `zip(..., strict=True)`; and every new root gets a guard
  test the day it's added.
- **Land the test that sees the defect red, then the fix.** The
  document-intake flow test was committed with 2 of 7 tests
  deliberately red against main — exactly the two naming the
  inbox-extraction gap — so #81 turns them green rather than arriving
  green with nothing showing what it changed. The dry run became a
  re-runnable end-to-end test (`tests/test_document_intake_flow.py`,
  real MCP tools, real API, synthetic files) instead of a prose
  transcript: it can't go stale silently.
- **`structured_content` exists and is `None` for some tools, so a
  `getattr` default never fires.** Two failures that looked like
  product bugs. Read the payload with an explicit fallback.
- **Record a soak that produced no measurement as no measurement.** A
  leftover watcher was waiting on a process that had died (exit 144)
  without writing its result line and would have spun forever; it was
  stopped and its absence is not treated as a clean result.
- **A PR body is an instrument, and it can be pointed at your intent
  instead of the tree.** All three described-but-absent artifacts had
  the same shape: the body was written from the state the branch was
  meant to reach, and the last commit didn't reach it. Same failure as
  the truncated grep and the non-applying mutation — not a testing
  problem, an instrument-pointed-at-the-wrong-thing problem. Before
  pushing a head, every claim that the file *says* something ("says
  so", "states", "names", "lists") gets grepped against the file; and
  when editing prose, assert the anchor is unique and the diff is
  non-empty before committing. (impl-4's rule, adopted.)
- **A test must fail for the reason you care about — read *why* it
  went red, not just that it did.** The general form of several lessons
  above (adjacent-reason reds, record counts on both sides, tests that
  pass before the fix). "If a test can't tell you how many records each
  side saw, it can't see this class" was too narrow: the count guard
  *did* report the number and still wasn't proof, because it fired for
  an adjacent reason. Run the test against the unfixed code and read
  the assertion that fired.
- **"Settled" is not "merged": a mirror matches shipped code, not the
  decision.** The skill's preview fence could have been updated to the
  decided tie-break key while #80 was still open; that would have put
  the preview in deliberate disagreement with the live API — exactly
  the state the skill's stop-and-report rule treats as a defect — and
  halted any import in that window for a reason that looks like a bug.
  The mirror lands in a small PR immediately after the API change
  merges.
- **The commit is the safety net.** `open(p, "w").write(open(p).read()
  .replace(...))` evaluates the write-open first, which truncates, so
  the read returned an empty file and 0 bytes went over the decision
  log — twenty minutes after the implementer had been warned about
  `cat >` doing the same thing. Caught in seconds because a verifying
  grep came back empty and the previous entry was already committed.
  The lesson that generalizes isn't the idiom: both near-misses were
  survived by having something to restore against, not by care.
  Read-once, write-once, and commit before editing a durable record.
- **A cheap idempotent re-run can be a stronger test than the one you
  designed.** Re-importing a source file to prove dedup returned
  exactly the predicted 0 created / N skipped — and incidentally
  proved count-the-excess against a case nobody had staged: several
  identical same-day charges that a boolean key check would have
  collapsed on the first import and that no repeat-free corpus would
  ever have revealed. When a proof is cheap and reversible, run it; the
  corpus may contain the case you couldn't construct.
- **Determinism becomes load-bearing the moment output joins a key.**
  Re-extraction was byte-identical, which is the only reason the
  re-import deduplicated; `description` is in the dedup key, so a
  scrubber that varied between runs would defeat dedup silently. Any
  transform whose output feeds an identity or dedup key gets a
  same-input-twice test the day it lands.
- **A referenced id you can't find is a check to run, not a conclusion
  to draw.** An id cited in a dispatch turned out to be the lead's own message id,
  cited as if it were a ticket. The implementer searched every board,
  confirmed the count was a real total rather than a truncated page,
  and reported the absence with both explanations open. Earlier in the
  day the same shape (D3's read-path authorization) had been a real
  unlogged decision. Look, then say which it was.
- **The `zip()` distinction is parallel data vs offset views of one
  sequence — and the fix for the first is not having two sequences.**
  After pairing each extract root with its label in one structure,
  zero functional `zip()` calls remain in production; the three in
  tests are all `zip(xs, xs[1:])`, where `strict=True` would *break*
  them (lengths n and n−1 by construction). A blanket strict rule or a
  lint on bare `zip` would have fired on three correct sites and not
  existed at the one that was wrong. Only parallel data that must
  correspond can disagree; pair it. (impl-4.) The same commit removed a
  twin: `roots[0]` as the relative-path base, which a reorder would have
  silently changed — now a named variable.
- **The comment warning about the mistake was the line directly above
  the mistake.** #70's "how a per-reader hook gets applied to only half
  of it" sat one line above the `zip()` that applied it to two-thirds.
  A comment that has already been walked past once is evidence it does
  no work; make it a structure.
- **Any red-side quote is a quote from a tree that no longer exists —
  it needs a SHA.** The flow test's red side said "path must be inside
  the intake or documents directory"; the fix changed that message to
  name inbox too, so a reader grepping the quote after the merge finds
  nothing. Red evidence is by construction from the pre-fix code, and
  the fix changes that code. Quote it as what the error said *at
  <sha>*.
- **A sort-key component whose declared order matches the order the
  data already arrives in tests nothing.** The `/due` same-day
  ordering test asserted "attribute before reminder" — which passes
  under a date-only sort because the sources are queried in exactly
  that order. The discriminating version uses two same-day items from
  one source whose names sort against insertion order (`Zed` inserted
  first, expect `Abe`). Sibling of the precedence lesson: a test that
  reads as thorough and cannot fail.
- **Two rules, not one (impl-1's split), because the detection
  differs.** (1) *A check that cannot fail while the bug is present
  proves nothing* — whether its expectation is derived from the
  implementation (the `/due` guard parametrized from
  `FORWARD_DATED_ATTRIBUTES` would follow a field to the wrong side and
  keep passing), or its fixture answers identically under every
  candidate rule (ACME CAFE/ACME GAS; single-length patterns for a tie-break;
  uuid ids that only sometimes draw the discriminating order). Detect
  by introducing the bug and watching for red. (2) *A check is evidence
  only for the property it can fail on* — a sound test for A is not
  evidence about B: the 12-case probe vs the fetch, the count guard vs
  the differential, #83's differential vs the tie-break (it passes with
  the tie direction inverted). Detect by reading *why* it went red, not
  whether. The second bit three times in one day, always with a good
  test doing honest work and someone citing it one property over.
- **A check derived from the thing it checks cannot discriminate it,
  and it reads as thorough either way (impl-3).** The consumer-side
  `/due` guard only works as a second, *independent, literal* statement
  of what the digest should show, with a separate drift test between the
  two statements. The natural implementation — parametrize from the
  partition — is worthless and looks like the guard that was asked for.
- **Tests proving a negative are where wrong-reason passes hide
  (impl-4).** "The original path is dead because the file moved" was
  green on a containment refusal that had nothing to do with moving —
  any failure looks like confirmation. `pytest.raises(Exception)` is the
  tell; assert the specific error (the repo's idiom is `raises(ToolError)
  as excinfo` + an assertion on `str(excinfo.value)`), and count the
  red set again: it went 2 → 3.
- **"You cannot forget one" is a different class of fix from "we
  remembered the third".** The reviewer simulated the exact future edit
  that caused the zip defect — add a root, omit its label — and the
  paired structure failed 12 tests loudly where `zip()` had reported
  nothing. When fixing a coupling bug, re-read the neighbourhood for
  its siblings (`roots[0]` was one line down) and prove the class is
  closed, not the instance.
- **`caplog` listens on the root logger, so asserting over
  `caplog.records` passes if the warning came from anywhere.**
  `at_level(logger=...)` sets a level; it does not filter the records.
  Measured: moving one `api.due` warning to `logging.getLogger("silenced")`
  left all 48 logging tests green. Filter on `record.name == "api.due"`
  and confirm each warning fails its own test when moved. (impl-3.)
- **The general form of four incidents (impl-3): a check that reads
  *through* the thing it is meant to discriminate cannot discriminate
  it — and the weak version always looked more thorough.** ACME CAFE/ACME GAS
  (fixture agrees under every rule), the source-ordering sort key
  (declared order equals arrival order), the `/due` guard parametrized
  from the partition (follows the field to the wrong side), `caplog`
  over the root logger (any logger satisfies it). In each case the fix
  was a second, independent statement of the expectation that could
  disagree with the code.
- **An endpoint that answers one of three sources still returns 200 —
  "nothing is due" becomes indistinguishable from "I didn't look".**
  Why `/due` is one query over all sources rather than a
  `/reminders/due` beside an attributes query: the failure mode of two
  endpoints isn't an error, it's a confident empty answer. Recorded in
  decisions-log as superseding the spec's endpoint.
- **Reconcile counts by running `--collect-only`, not by reasoning.**
  857 + 9 = 866 — but the implementer had assumed one of the two new
  test files was already on main and would have reported a two-test
  mystery that didn't exist. Same rule as the posting-date claim, one
  layer down.
- **Measure the proposed fix before shipping it — a fix to a
  non-discriminating fixture can itself not discriminate.** The
  suggested repair for #83's fixture (drop the space from the generated
  patterns so "MERCHANT999 NO BOUNDARY" separates bounded from
  bare-substring) was applied, the predicate mutated, and all four tests
  still passed: that description contains none of the 000..059 patterns
  under either spelling. The real gap was that every description
  separated the pattern with a space or a star — both token boundaries.
  Two shapes with an alphanumeric touching the pattern (`{p}9`, `X{p}`)
  made the mutation red on 120 of 242. A relayed fix is a hypothesis
  until its mutation goes red.
- **The single-call read-back inside the file that exists to catch
  single-call fetches.** Growing the corpus past 200 rows exposed that
  the API side read transactions back with one `limit=200` call
  (`MAX_LIMIT`) — 200 stored rows compared against 242 predictions. The
  implementer had written the drain for merchant rules and read
  transactions back with one call in the same function. Invisible while
  the fixture fit a page; wrong the moment it didn't. A sweep of the
  suites for single-call read-backs follows; where a fixture is
  provably small, a comment says so instead of a drain.
- **Announcements go on the PR as a comment at push time; the message
  is a pointer.** Three first-send announcements were lost in one day
  (each resend arrived). A lost message then costs a click, not a
  re-request, and the PR carries the old→new line with its content as
  the durable record.
- **A review can land on an orphaned SHA.** The lead's queue message
  named #85's head as `21f87c9` (read from GitHub minutes earlier); the
  branch was then rebased (`21f87c9` → `45cc972`) and a commit added
  (`b10f497`). The reviewer approved "at `21f87c9`" — a commit
  `git branch --contains` no longer returns — and the merge gate would
  have refused it. The implementer traced the chain and showed the
  rewritten tree differed only by a base-side addition. Rules: the
  reviewer reads the head with `gh pr view` at review *start*, never
  from the lead's message, and runs `git branch -r --contains <sha>`
  before spending time on it; the lead's queue messages name SHAs as
  "as of <time>", not as the thing to review.
- **Assert on `total`, not on the length of a page.** The read-back
  sweep (82 list read-backs, 18 files) found no other broken one, and
  the reason is instructive: no test asserts `len(items) == total`, and
  most default-limit reads assert on `["total"]`, which is
  pagination-independent by construction. The truncation class is
  client-side only — `api/` reads with `fetchall()` and sees every row;
  the preview broke because it called a paginated endpoint once.
- **A drain makes the test correct; an assertion that the page wasn't
  truncated makes the future failure legible.** `list_categories`
  reads a fixture that lives outside the test (`db/seed_categories.sql`,
  which can grow); past one page its membership assertions would fail
  for a reason that looks nothing like pagination. It now asserts
  `total <= 200` first, with a message naming the cause — verified to
  fire by lowering the threshold. Where a fixture is a literal list in
  the same function, a drain is ceremony; a comment says the pattern it
  models (a real audit log) must drain.
- **A robustness change can be unobservable to every existing test.**
  #85 replaced the preview's `max(hits, key=len)` with an explicit
  `(−len, id)` key. impl-3 swapped the pre-#85 fence back in and got
  full parity — because `max` ties toward the first element and the
  API returns `ORDER BY id`, the old fence was already lowest-id
  whenever the input arrived sorted. So no id-ordered probe, including
  the tie tests written for the change, could see it. The change is
  right (it removes a dependence on someone else's `ORDER BY`), but the
  test that proves it must hand the fence an *unsorted* list.
- **The control neither red-green rule covers: mutate to a state that
  should be *identical*, confirm green, then ask whether that green
  means anything.** Both existing lines are about mutating the thing
  under test and checking for red. impl-3 did the opposite — swapped
  the pre-#85 fence back in, got parity, and asked why — and that is
  the only control that detects "this check cannot see this change at
  all": the failure behind #83 vs the tie-break, the probe vs the
  mirror, and the 12 cases vs the fetch. Three instances in a day, one
  missing control. (impl-1's framing of impl-3's move.)
- **The most realistic test was the blind one, precisely because it
  was realistic.** Of #85's three tie tests, the only true end-to-end
  differential — drives `/import_statement`, reads back the stored
  category — was the one that couldn't see the mirror, because it fed
  the fence exactly what `list_merchant_rules` returns: id-ordered, the
  one arrangement under which old and new agree. Fixed by reversing
  that input (one line), which also models the real hazard: a client
  that re-sorts or pages out of order. A correct fence is
  order-independent, so the unmutated test still matches the import.
- **A test whose failure mode is a hang is barely a test.** The digest
  skill's drain test drives the stale-`total` shape; without the
  empty-page guard the unguarded loop would hang the suite — which
  reports nothing, blocks CI, and reads as infrastructure. It now has a
  20-call budget with an assertion message naming the missing line.
- **A mutation test's cleanup is itself unverified, and its failure
  mode is shipping the mutation.** `git checkout --` restored the
  tracked skill and silently skipped the untracked one, leaving the
  digest skill without its empty-page guard — with a green suite behind
  it, which is worse than the mutation test not existing. Re-grep both
  files after restoring; treat cleanup as a step with its own check.
- **A probe that feeds a component its natural input cannot observe a
  change to how it handles unnatural input.** review-1 ran the
  three-mutation tie matrix at two heads, reproduced the numbers, and
  reported the mirror verified — and none of those runs could have
  distinguished the mirror from the old fence, because every one fed
  it id-ordered input, the arrangement under which they agree. "My
  matrix was measuring someone else's `ORDER BY` in a different file."
  The sharpest instance of the adjacent-property lesson, on the
  reviewer's own work, found by a third party cross-checking a thing
  signed off twice.
- **Pins prove agreement, not correctness.** A byte-identity test
  between every skill's fence and a canonical copy says the copies
  agree; if the canonical copy loses the empty-page guard, every pin
  passes and every skill hangs — unanimous and wrong. The canonical
  text needs a behaviour test of its own, and the mutation that
  justifies both is: drop the guard from the canonical copy, behaviour
  test red, pins green. "Make sure the canonical copy is the one with
  the guard" was the same worry expressed as a wish.
- **A pin must discover, not enumerate.** A hand-written list of skills
  lets a new skill escape by not being added — the diff that introduces
  the gap is the diff that would have closed it. Glob the skill
  directory; require the fence for every skill that mentions a `list_`
  tool; state the heuristic's limit rather than let the test imply a
  guarantee it lacks.
- **A flag named `all=true` asserts completeness in its name, which is
  what stops the next check.** A capped result plus a `truncated`
  boolean is the 50-of-57 bug with a bigger number and a longer fuse —
  fine when false, fine when unread. So `all=true` is complete or
  refuse (never rows-plus-flag), and on single pages the marker is
  present only when true, computed from `total` rather than from the
  cap so an honest full set never cries wolf. Shape a marker so
  ignoring it is hard, not so it reads fine either way.
- **The bug was not a missing marker — a marker distributes the
  obligation to every caller forever; a refusal concentrates it on the
  one caller that hits the cap.** (impl-3, superseding the line above
  within the hour.) `total` was in every response of the 50-of-57 bug
  and nobody compared against it; adding a second field to not-check
  has a poor prior. And a codebase with two answers to "the result is
  incomplete" decided hours apart would have the weaker one newer. So
  the capped `all=true` fails closed exactly like the partial-extraction
  fix: a 422 that withholds the rows, an explicit opt-in that returns
  them flagged, the tool omitting the flag when false. The earlier
  marker design is kept above as the record of what looked right first.
- **Pin what a field *means*, not that it exists — removal is loud,
  redefinition under the same name is invisible.** `total` appears
  exactly once in the intake skill, in the fence's termination
  condition. Drop it: `KeyError`, immediate, harmless. Redefine it to
  "rows returned" while keeping the name: `len(items) >= total` is true
  after page one, always, and the helper written to prevent the
  50-of-57 bug silently reproduces it with no error anywhere. An API
  test asserts `total` counts all matching rows. (impl-1.)
- **One owner, one text, for anything a pin will assert is identical.**
  Two people rewording "Every list call is paginated" in two skills is
  the exact thing the byte-identity pin exists to prevent. The
  rewording *is* the canonical text: written once in the runbook by the
  ticket's owner, copied into each skill, enforced by the pin; the
  other skill's copy updates as a mechanical consequence, not an
  independent edit.
- **Wrong-reason passes were found three different ways — hunt the
  shape deliberately.** The ACME CAFE/ACME GAS fixture (rewriting a fixture),
  the id-ordered tie probes (cross-checking a mirror), and the
  document-intake "path is dead" test (tightening an assertion): three
  tests each observing a true fact that wasn't the fact it named. That
  they surfaced by three unrelated routes says the shape is common
  enough to look for on purpose: for each test, ask what *else* would
  satisfy this assertion.
- **A grep exclusion that matches nothing makes every hit look like a
  finding.** `^./api/` as the exclusion pattern matched nothing, so
  every occurrence appeared to be *outside* `api/`; caught because the
  result contradicted the file paths in its own output. Same family as
  the unrun `timeout` and the zsh `:l` modifier: an instrument that
  silently did something else.
- **A conclusion about the repo drawn from your own file is not a
  measurement.** "My fence depends on `total`, therefore nothing pins
  `total`" — one grep showed five tests pin it. A ticket saying "unpinned"
  would have been closed as already-covered and taken the real, narrower
  gap (a new path that computes its own count) with it. A wrong
  justification for a right concern is worse than no ticket.
- **Enumerate by the property, not by the name.** The paging test was
  specified as "tools named `list_*`"; counting showed 3 of 12 paged
  tools (`get_ticket_history`, `spending_summary`, `trend`) don't carry
  the name. A name-based test passes while those three keep
  truncating, and reports the rule enforced. "Takes a `limit`" is the
  property; the name is a proxy wrong 3 times in 12.
- **The balance chain is the sign convention.** A statement PDF with two
  unlabelled columns has no sign in the source; deriving direction from
  the running balance and checking `|delta| == amount` is what turned a
  split money token into a stop instead of a +100 deposit imported as
  −1,234.56. When a document carries its own redundancy, use it as the
  integrity check rather than assuming a convention measured on a
  different source.
- **Tests that mock the transport are blind to a redefinition in the
  real function — pin the contract at the source.** Redefining `total`
  to `len(rows)` in `paginate` failed 4 tests in the new API contract
  test and left all 13 mocked MCP paging tests green: they hand back a
  synthetic `total`, so the suite written to prevent this class of bug
  cannot see this instance of it. The contract is pinned at `paginate`
  as well as at the endpoint, so endpoints added later are covered
  without anyone remembering to add a case.
- **"Debit" means the opposite thing on two document types.** On one
  document type the debit column decreases the balance and is money
  leaving; on another, a column with the same name increases the balance
  owed.
  Anything keying off the word rather than the direction is exactly
  backwards on one of them. The document's own totals settle the
  convention per source; the skill keys off direction.
- **Amounts right, description garbage is the dangerous combination.**
  A page-header date matched as a row and swept the interest rate and
  credit limit into that row's description; it reconciled and nothing
  downstream objected. Anchor patterns so a description cannot contain
  a dollar sign, and say why in the pattern.
- **An opt-in exists only when there is a correct case for it.**
  Partial extraction has one (a blank cover page is a real document);
  a capped `all=true` has none — the caller needs the whole set or a
  narrower query — so an opt-in there would exist only to bypass the
  guard. Two refusals with different shapes are consistent when the
  cases differ; document the difference so it doesn't read as
  carelessness.
- **When a document has no period, don't invent one silently — derive
  it and say what it is.** A rolling-window web export is not a
  statement; the API needs a period; the honest candidate is the
  min/max transaction date, which is a query window. Import with it,
  record that it is a query window, and record that the next export
  will overlap (transactions dedup; statement rows proliferate). The
  implementer stopped rather than decide what a "statement" means —
  that was the lead's call and it was logged.
- **`_skill_files()[0]` — a test silently scoped to one subject by
  alphabetical luck.** The behaviour test of the drain helper indexed
  the first skill file, which meant statement-intake only because it
  sorted first among two. When document-intake merged, the index moved
  to a skill with no fence and the test died with `IndexError` — loud
  by luck; had the new skill carried a fence, the test would have
  quietly stopped covering the digest skill while its name said
  otherwise. Fixed to execute every copy it finds, assert it found at
  least one, and name the skill per failure. Any test that picks `[0]`
  from a discovered list has this shape.
- **Separate rebase from push; read the result before the remote sees
  it.** A rebase chained to a push put a red head on the remote for a
  few minutes because the push ran before the suite result was read.
  Two steps, one read in between.
- **A distribution can answer a different question than the one
  asked.** Two deposit accounts from one source showed a strong
  day-of-week skew — the textbook posting-date signature — and the implementer
  declined to conclude "that source posts": deposit-account rows are bank
  operations with no merchant-side date to lag, so the numbers say
  when bank operations happen, not which date convention is in use.
  Recorded as inapplicable rather than as the tempting answer; the
  question is tested on a card source instead.
- **A backwards justification invites the wrong fix.** "`rrulestr`
  accepts some rules only with a `dtstart`" was the opposite of true
  (a dtstart makes validation stricter). The decision was right for a
  better reason — `/due` expands with the same dtstart, so a rule that
  validates is one the digest can expand — and the wrong reason would
  have led the next reader to drop the dtstart and let in rules the
  digest silently skips. Fix the reason, not just the code.
- **A comment that states a rule the adjacent code breaks — twice in a
  day — is replaced by a guard, not a better comment.** `# Only
  reachable via allow_truncated` sat on a branch reachable without it (a
  server that stops early, a `total` that overstates); the "applied to
  only half of it" comment sat directly above the `zip()` that did it.
  Both correct, both load-bearing, both enforcing nothing. When a
  comment describes an invariant, ask what enforces it; if the answer
  is "the comment", write the check.
- **Measure the ticket's premise before building it.** The transfers
  ticket said cross-account totals double-count; in the stored data only
  one leg was categorized (the `EXAMPLE PAYMENT RECEIVED` inflows),
  every outflow twin is uncategorized, and shipping the exclusion as
  written would have moved the headline ~$1,234 the wrong way while the
  new field read as the fix working. The build changed shape (a sibling
  `uncategorized_cents`; a separate routing ticket; one case escalated
  as unsolvable from the description). A ticket is a hypothesis about
  the data until someone reads the data.
- **The check you get for free is the one that catches the silent
  defects.** One source prints a balance per period; that single fact
  exposed an en-dash header dropping a whole period, `Total` lines
  parsed as rows, and page-order misattributing 25 rows — three
  defects that produced plausible output and raised nothing. Before
  parsing a new document type, find what it prints that lets you
  verify the parse, and refuse to import a source that prints nothing.
- **A masked token is not a last4 until it identifies an account.**
  One source's only masked tokens were `****0001` / `****0002` — differing
  solely by page number, i.e. `accountKey=****000` + `1 / 2` — and a
  transfer *source* account. The skill left `last4` unset and flagged
  it, the rule written hours earlier for exactly this, firing on the
  first document that needed it.
- **A clean `range-diff` proves the commits didn't change, not that
  they still pass — run the suite on the composed tree before merging.**
  #89's four commits were content-identical across a rebase and the
  test file byte-identical, and the suite went red: the base had gained
  `document-intake/SKILL.md` (via #79), it sorted first, it defined no
  `fetch_all`, and an unguarded `[0]` blew up. "Green at 964" was true
  when reported and stopped being true without a line changing. The
  lead's merge gate now merges `origin/main` into a scratch worktree at
  the approved head and runs the full suite there *before* `gh merge`,
  not only after; and the guard-on-the-guard could not see this because
  it defended against the defining set shrinking, not the file set
  growing with a non-defining member.
- **A floor presented as an answer.** "Real spending, transfers
  excluded: −1,234.56" excluded the transfer *categories* — only the
  labelled inflow leg — while 12 genuinely uncategorized purchases
  (−2,345.67) sat in the null bucket. The implementer corrected their
  own headline in the unsafe direction and logged a range. When a
  number depends on classification coverage, state the coverage next
  to the number, or the number understates by whatever is unlabelled.
- **When two measurements disagree, fix the definition, not the
  winner.** 10 rows / −3,456.78 versus 20 / −4,567.89 for "the
  unlabelled leg" — same database, different "flow" predicates. Both
  recorded as a stop; neither quoted; one predicate agreed in writing
  and run over the same rows from both sessions, with the rows where
  the heuristics diverged reported. The implementer applied their own
  skill's stop rule to their own number rather than to the other
  person's.
- **Read the ticket before ranking it.** One deferred ticket said in its own text
  "revisit … not before" the backlog-import work is scoped, and its
  atomicity concern was lock *duration*, not atomicity — imports already
  run in one transaction. The implementer had described it as "a
  half-completed import cannot be reverted", inferred from its pairing
  with the undo ticket; only the undo half was real. Self-corrected
  before building.
- **`gh pr edit --title` fails silently on this repo** (a
  Projects-classic GraphQL deprecation); `gh api -X PATCH
  repos/…/pulls/N -f title=…` works. A retitle that "succeeded" had
  not, until checked — same family as the merge announcement sent
  before the read-back.
- **"Assert an absence without grepping" — caught by the same person
  who was caught by it.** About to log a taxonomy gap for a class of income
  rows, the implementer grepped first: matching `income_*` categories
  exist; it is a rules gap. The lesson from the
  `total` incident two hours earlier, applied to oneself.
- **"Is it one transaction?" is answered by counting what the database
  saw.** A sqlite-level trace of `import_statement` at N=10/25/50 gave
  BEGIN=1, COMMIT=1, ROLLBACK=0 at every size and 3n+3 SELECTs — dead
  linear. That settled an atomicity question the code's shape had left
  arguable, and quantified a deferred performance ticket with a number
  instead of an opinion. Trace the driver, not the source.
- **Under archive, refusing on hand-edited rows is too strong; the
  real cost is silent, so report it.** Under delete a refusal is
  necessary because the edit would be destroyed; under archive nothing
  is destroyed and the loss is that a re-import arrives without the
  hand categorization — nobody gets an error, a summary just looks thin
  weeks later. Return the count and the ids at the moment the person
  can act; don't block a safe operation.
- **The scrubber that protects the account number also destroys the
  evidence that a row is a transfer.** `ACME TRANSFER IN [REDACTED]` cannot
  satisfy a predicate that requires an own-account last4. The redaction
  is correct; the classification gap is its consequence, and the
  remedy is to define a transfer by its *mechanism*, not its
  counterparty.
- **Too narrow beats too generous for a "flow" predicate.** A flow
  miscounted as spending is visible (it inflates a bucket someone
  reads); spending miscounted as a flow is not (it vanishes from every
  total). So `SERVICE FEE`, `EXAMPLE CHARGE` and loan payments stay expenses even
  though they look flow-ish.
- **Stage the leak a well-meaning contributor would actually write.**
  To verify that a refusal withholds its payload, the reviewer threaded
  `pages` onto the exception and had the handler return `"text"` — the
  natural helpful edit — and confirmed exactly one test failed. A
  withholding test that only checks the happy path proves nothing about
  the edit that would break it.
- **An enumeration that feeds an `== []` assertion needs its own count
  pinned.** #90's `_paged_tools()` fed three tests asserting no
  offenders; replacing its body with `return []` left all three green.
  The guard is a literal `assert len(found) == N` — a new member makes
  someone open the file, an empty enumeration fails loudly. Same guard
  #89 was required to carry; it recurs because it is invisible from
  the green side.
- **Read the per-account output, not the classifier.** impl-2's flow
  regex missed the `ACME TRANSFER` / `EXAMPLE XFER` prefixes, so several transfers presented as
  merchant purchases. The miss was caught by reading the rows the
  classifier passed, per account, before drafting anything against
  them. A classifier's output is a claim about the data; the data is
  the check.
- **A grep that errors prints nothing, and nothing looks clean.** zsh
  rejected an unquoted `--include=*.py`; the sweep printed no matches
  and no error worth noticing. Quote the glob and run a positive
  control (a pattern you know is present) before trusting an empty
  result — the same trap as `$TREE:path` and macOS's missing
  `timeout`.
- **Defer rulings that belong to the owner.** Some classification
  questions carry consequences beyond categorization (Category X vs
  Category Y on the same charge); a consistent team ruling would
  compound an earlier unreviewed guess rather than correct it. Record the precedent, the rows,
  and the amounts, and leave the ruling to the owner.
- **State the predicate next to the number, every time.** A "20 vs
  8" flow disagreement consumed two rounds of messages before it
  turned out that 20 was the whole `category_id IS NULL` bucket at an
  earlier import point, described in a sentence about transfer legs.
  One denominator, two classifiers. A figure that outlives its
  definition gets compared against figures measuring something else,
  and the comparison reads as a disagreement. Name the predicate
  inline, in the log and in the message.
- **`NOT (x IN (...))` is NULL when `x` is NULL.** A bare negation in a
  financial filter silently dropped every uncategorized row — 20
  rows, −4,567.89 live — with a 200 and a smaller, plausible total.
  Write `x IS NULL OR x NOT IN (...)` and pin it with a fixture that
  has a NULL in the column. An existing float-precision test caught it
  by accident; the pin exists so the next one is caught on purpose.
- **A visibility field must not read zero in the healthy state.**
  `transfers_excluded_cents` cancels to 0 once both legs of every
  transfer are labelled — invisible exactly when it is working. A
  count cannot cancel. Before adding a field so an exclusion is "not
  silent", ask what it shows when everything is correct.
- **A fixture that builds "the old state" from the current schema
  needs a hand-written undo per migration.** Third time now, and the
  failure arrives as a duplicate-column error, not as "the fixture is
  stale". Say so in the fixture's docstring; the next person should
  meet an explanation, not a puzzle.
- **An empty result from a query on the wrong column looks like the
  feature working.** impl-3's `trend` fixture passed an account id as
  `entity_id`, got an empty series, and that read as "the exclusion
  works". Assert non-empty before asserting the filter.
- **When you cannot decide, pick the failure mode someone will
  notice.** The empty-page guard, complete-or-refuse and the flow
  predicate all turned on one asymmetry: under-narrow fails loudly,
  because it inflates a number someone questions; over-generous fails
  silently, because it leaves the total quietly smaller. (impl-1,
  after three tickets rediscovered it.)
- **The definition should be external to whoever writes the number.**
  A figure that moved twice before settling moved the same way both
  times, toward "the reports look more complete than they are". The
  first figure not revised was the one computed from a predicate
  agreed before anyone had a number to defend.
- **Reconcile the board against merged PRs at merge time, and claim
  before building.** Five stale statuses were found in one pass — one
  ticket sat `in_progress` for hours after its own PR merged, and the
  board showed nothing `in_progress` while three implementers were
  building. The lead moves tickets to `done` inside the merge routine
  (with the merge SHA in the note); the implementer claims and moves
  to `in_progress` when they start. A status nobody re-derives is a
  claim that was true when written.
- **Reconstructing a "before" state for a red-green measurement
  contaminates easily.** impl-4's first reconstruction spliced out
  neighbouring helpers with the target and reported 10 failed / 5
  passed — a plausible number for the wrong experiment. Replace only
  the unit under test, assert the neighbours are still present, and
  report the first attempt rather than quietly redoing it.
- **A digest is verification only with its recipe.** "sha256 matches"
  meant nothing until the capture (the regex group, unstripped,
  trailing newline, UTF-8 bytes) was published beside it; two people
  computed different hashes of "the same fence" for an hour because
  one included the fence markers. Publish the digest and the recipe
  together, wherever the digest lands.
- **A check is only as good as its subject, and the subject is the
  part nobody tests.** Three mechanisms, one hole: a mocked boundary
  supplies the thing under test; an empty discovery supplies no
  things under test; a figure quoted without its predicate is
  compared against something else. In each the guard runs, passes,
  and never touches what it claims to cover. Mutate the subject
  (`return []`, delete one member, swap the predicate) before
  trusting the guard.
- **A floor (`>= N`) stops discriminating once the population exceeds
  it.** `>= 2` skills carrying the fence was a correct guard with two
  skills and silently stopped being one at three — one skill dropped
  its fence, the identity test agreed over the survivors, 8 passed.
  Use a literal count, or require the property per member.
- **A guard whose coverage depends on something you are eliminating
  is weakest on the day it matters.** The stale-allow-list test
  covered the empty-discovery hole only while the allow-list was
  non-empty, and emptying it is the goal. Allow-lists, TODO counts,
  legacy sets and deprecation shims all have this shape; ask whether
  the guard survives the project succeeding. The inverse exists too:
  impl-1's pin *required* a fence from any `list_*(` call, so a skill
  correctly adopting `all=true` would have failed it, louder as the
  migration succeeded. The question that catches both directions:
  **what does this guard assume stays true, and is anyone working to
  change it?**
- **Commit, then mutate, then restore.** A `git checkout -- tests/`
  between mutation cases reverted uncommitted improvements; the next
  mutation failed and the code being debugged was not the code that
  ran. Third restore mishap in one session (the `open(p,"w")`
  truncation, an `rm -rf` whose `cp` backup had silently failed),
  each recoverable only because the work was committed.
- **Prefer an independent traversal to a literal count when the
  population is meant to grow.** A literal needs editing whenever a
  member lands and then fails for the wrong reason; a floor absorbs
  regressions past N. Discovering the same set two ways (glob vs
  directory walk, asserting equal sets) needs no maintenance and
  catches a broken helper immediately.
- **Recorded output is regenerated, never hand-edited.** A docstring
  carrying a mutation run's output named a test renamed in the
  previous commit. Output that names something that no longer exists
  reads as evidence and cannot be reproduced — a figure without its
  definition, one layer down. Re-run and paste; if it cannot be
  re-run, say so instead of recording it.
- **A literal count catches what merged underneath you.** #90's
  `== 12` tripped at 14 on rebase: two paged tools had landed from
  other PRs while it sat in review, carrying the defect it removes. A
  discovery-based guard without a pinned population would have
  reported the rule enforced over 12 of 14. When the population is
  meant to be closed, pin it; when it is meant to grow, cross-check
  two discoveries (see above) — but never leave it unpinned.
- **Filters ride every page; page selection belongs to the paging
  layer.** When a paged call takes a filter (`exclude_transfers`),
  the filter goes in `params` so an `all=true` drain sends it on every
  request; `limit`/`offset` stay in the helper. Backwards, the first
  page is right and later pages are not — correct exactly where
  someone would spot-check. Test with three pages, not one.
- **A ticket can be unreached without being superseded.** One ticket
  was conditional on a trigger that has not appeared; closing it
  would discard a measured trap (VACUUM renumbers rowids on a table
  with no INTEGER PRIMARY KEY). Backlog is for standing findings; a
  closed ticket is not read.
- **Never pipe a gate.** `merge_pr.sh … | tail -4 && next` continued
  past a refused merge because the pipeline's exit was `tail`'s, not
  the gate's. Each later merge happened to pass its own gate, so
  nothing wrong landed — but the chain was designed to stop and did
  not. Run a gate bare, or `set -o pipefail`, and read its exit
  before the next command; the same trap as `&&` mixed with `;`.
- **A guard that catches something underneath you is the guard
  working, not a flake.** #94's source-reading scope test went red
  on the composed tree because #93 added raw reads of `transactions`
  after #94 was written. The refusal at the gate is the cheapest
  place that could have happened; the alternative was an aggregate
  quietly counting archived rows. Rebase, route, re-review — do not
  loosen the guard.
- **A skip you did not write is an unread test result.** pytest turns
  an empty parametrize into a *skip*, and a conditional check over a
  discovered set skips what it cannot see. A skip reads as deliberate
  so nobody investigates it, which makes it quieter than a vacuous
  pass. Run `-rs`; every skip must be one you can name the reason
  for. Cross-check anything you discover against a second traversal.
- **Independence of mechanism is not independence of author.** A
  property test and a fixture written together from one mental model
  shared a blind spot (`writes` was a retyped subset of the docstring
  beside it; the fixture had no case for the missing member). Two
  checks by one person in one sitting are one check. The cold
  reviewer is the second mechanism.
- **A collected-test diff is meaningful only against a main fetched
  in the same breath.** "5 tests lost" was main gaining a file
  between fetch and collect. Re-fetch and re-diff before explaining a
  number away; a check that cries wolf is one people learn to skip.
- **A naming gap and a timing gap need different guards.** Three
  paged tools escaped a `list_*` enumeration (mis-specified subject:
  enumerate by property); two more merged underneath an open PR
  (world moved: pin the count). A name-based enumeration with a count
  bolted on catches neither.
- **Text read from two layers needs its claims qualified by layer.**
  "Compare `returned` against `total`" was true in the MCP layer
  (where the key is set, documented in fourteen descriptions, and
  tested) and false for the raw-HTTP caller the fence exists for,
  who never receives it. Nothing in the authoring context reveals the
  reader's position; the error appears only in the artefact that
  crosses the boundary. Say which layer each claim is true in.
- **Pin one SHA for the rebase and the name diff.** Worktrees share
  one `.git`, so another session's fetch moves `origin/main` under a
  check that reads it twice; "5 tests removed" was tests newer than
  the base. The instrument moved, not the thing measured.
- **Re-run the mutations after a rebase.** A rebase that compiles and
  passes can still have dropped the thing a test was written for,
  while the test keeps passing for some other reason.
- **A heuristic right about 11 of 14 cases reports the same green as
  one right about all 14.** (impl-4.) Which is why a pin's limits are
  written down beside it rather than left for a passing suite to
  imply.
- **"Apply it everywhere for consistency" ships guards and
  decorations that read the same.** Two identical transfer-exclusion
  clauses: one reachable (entity mode, found only when a fixture row
  made it so), one dead by construction (two predicates that cannot
  both hold). Only mutation told them apart. Remove the dead one
  with a comment; unverifiable code that reads as load-bearing is
  what the next person preserves.
- **Knowing the failure mode by name does not stop you repeating it
  a paragraph later.** (impl-3.) A false "derived, not retyped"
  docstring was written inside the commit fixing a literal that
  claimed to be derived. The check has to be mechanical — does this
  claim have a test? — not a matter of attention.
- **Assert ancestry, not a sequence.** "Fetch, rebase, collect as one
  sequence" was the first rule here and it is not sufficient: main
  merged twice *during* one sequence, giving a 14-test then an 8-test
  false "lost" alarm. The reliable check is a property of the branch,
  not a race against the clock: after the collect, run
  `git merge-base --is-ancestor origin/main HEAD` and rebase again on
  NO. A count diff is evidence about two snapshots; ancestry is
  evidence about the branch. (impl-3, correcting their own earlier
  rule.)
- **Every structural or text-reading guard ships with a behavioural
  partner.** Promoted from a per-PR finding to the default after
  three PRs in a row landed on exactly this: the source-reading scope
  guard is blind to indirection (#101's invariant test covers it),
  the statements guard was accepted only with #105's archiving test
  as its pair (#108), and the keyword contract check was open upward
  until an exact pin closed it (#107). A guard proves the rule; its
  partner proves the consequence.
- **Bump the source mtime (or clear `__pycache__`) after every
  mutation write.** (impl-1 found it; review-1 corrected the fix.)
  CPython invalidates a `.pyc` on source mtime and size, not
  contents; a loop that writes same-second, same-length variants
  runs the previous mutation's bytecode. The apply-assertion cannot
  see it — the bytes on disk are right and never read. **The first
  mitigation proposed here, `PYTHONDONTWRITEBYTECODE=1` (or `-B`), does
  NOT fix it** — those suppress *writing* a `.pyc`, not *reading* the
  stale one that already exists; measured: still stale. What works:
  `os.utime(path, (t+1, t+1))` after writing, inside the same helper
  that does the write and the apply-assertion, or
  `find . -name __pycache__ -type d -exec rm -rf {} +` before the run.
  A mitigation whose failure is indistinguishable from success is
  the day's defect shape, applied to the instrument. The merge
  gate's fresh worktree is unaffected. **An apply-assertion proves
  the file changed, not that the program did** (impl-4): between them
  sits a cache invisible to both the test and the assertion. An
  earlier version of this entry said every published mutation before
  the rule was sound by luck; **that was false** — #116's matrix had
  three same-size edits and one row was under-reported (10 failed
  published, 11 actual; conclusions held). #120's seven deltas were
  all distinct, so that table was checked and needed no amendment —
  check rather than assume, per matrix. A reassuring claim is the
  kind most worth checking. The condition is *exactly equal* size,
  not "close" — invalidation compares the integer — and only compiled
  Python is at risk (a markdown fence read at runtime has no `.pyc`).
  And the failed mitigation passed its own test because it was
  verified on a cleared cache: **verifying a fix on a clean slate
  tests the slate, not the fix.** Put the mtime bump in the mutation
  helper beside the write and the apply-assertion, so the
  classification is never needed. **A fix nobody measured is a
  claim**, likelier to be taken on trust when it comes from someone
  who was just right about something else.
- **Where a classification is a judgement, find a second source that
  isn't one.** (review-1, on #116.) Lists checked against models
  cannot catch a mistake in the lists, because the bucket was the
  error. A UNIQUE constraint in the schema is not a judgement;
  deriving the expectation from it lets the test disagree with its
  author. And a derived check asserts its catch was non-empty, or it
  can derive nothing and pass.
- **Assert the mutation applied before trusting its result.**
  `assert new != old, "MUTATION DID NOT APPLY -- anchor not found"`.
  Three non-applying mutations in one day, each reporting a clean
  green that read as "the test is weak". That is the dangerous
  direction: a correct test gets "strengthened" and the real gap
  stays. And when a mutation applies and still passes, ask why
  before concluding — one flipped an UPDATE guard whose write the
  test client then rolled back; the faithful mutation flips the
  commit guard too.
- **An anchor that matches in more than one place is not an
  anchor.** `replace(old, "", 1)` deleted the first of four identical
  blocks, in an unrelated fixture; the mutation "applied" (anchor
  found, file changed, `!= before` passed) and measured the wrong
  thing. Scope the edit to the function body and post-check that the
  target changed AND the other copies did not. `assert s != before`
  proves something changed, not that the right thing did. What
  caught it was reading the assertion text (`-105000 == -5000`), not
  the pass/fail.
- **Scope the restore to the file you mutated, never the directory.**
  `git checkout -- api/` reverted a newly added test alongside the
  mutation; `git checkout -- api/financial.py` would have been right
  every time. Fourth restore mishap of the day, and the narrowest
  rule that would have prevented all of them.
- **A conflict boundary can fall inside a function; markers give no
  warning.** A marker-based resolution spliced two test bodies and
  left a duplicate `def` that pytest silently shadowed — green with
  one test eaten. When a conflict touches a test file, rebuild it
  deterministically (take main's file whole, extract your functions
  by name, concatenate) and assert no duplicate defs
  (`pytest --collect-only -q | sort | uniq -d` must print nothing).
- **Diff the PR's file list against the ticket's done-list.** A
  runbook item was skipped and found only by comparing
  `git diff --name-only origin/main...HEAD` to the ticket, not by
  remembering.
- **An in-document check inherits the extraction's blindness.** A
  balance assertion whose opening and closing figures come from the
  same extraction that lost a page passes on exactly the import it
  exists to catch — and passes with a stored number behind it, which
  manufactures evidence of completeness. Independence means a second
  document (the previous statement's closing) or a second axis
  (period adjacency), not the same data asserted in a second place.
- **An allow-list is a claim; test the claim.** A guard that asserts
  "every writer is on this list" can be silenced by adding a writer
  to the list, after which the guard asserts the property it was
  used to defeat. Pair it with a test that every listed member
  actually has the property the list claims (calls the recorder;
  reads a single row by id), and pin the count.
- **Read every insertion of a scripted edit.** A script adding one
  field to nineteen call sites leaked state and added it to a
  twentieth of a different type; the failure surfaced three frames
  from the cause, and the pass count after the fix would have looked
  identical either way.
- **A source-reading guard is defeated by one level of indirection.**
  `FROM transactions` in the function is caught; `FROM {_SRC}` with
  `_SRC = "transactions"` one line up is not. Every text-reading
  check (scope guard, call detection, anchors, route parsing) gets a
  behavioural partner that fails on the outcome, not the text.
- **Read the argument in a docstring's trigger, not the event.** "Add
  this clause when #94 lands" meant "when deliberate nulls become
  possible"; #94 landed and did not make them possible. A ruling
  taken from the phrasing was retracted after measuring that the
  clause would have excluded unclassified rows touched by a no-op
  PATCH.
- **Registration is not reachability.** A literal route declared
  after a parameterised sibling (`/statements/coverage` after
  `/statements/{id}`) appears in the openapi listing and answers 404.
  Pin routes with a test that sends the request, not one that
  inspects the schema; declare literals above parameters with the
  reason inline.
- **Flag from the file, not from memory of the file.** A "still
  stale" report was itself stale: read hours earlier on a
  pre-merge worktree and carried forward. Before flagging anything as
  unfixed, `git show <head>:<path>` on the branch in question.
- **A row count alone can produce a wrong finding.** Audit rows going
  1→2 on a 500 read as an orphan until the rule was checked too:
  both had landed, and the 500 was a read-back after a successful
  commit. Check the pair, not one side of it.
- **When a ruling oscillates, settle it on reasons that do not
  depend on who argued what.** The `edited_at` clause went in, out,
  and was re-argued in within an hour across three people. The final
  ruling lists the conditions under which each answer is right and
  names the trigger for changing it; that survives the next person
  who has just been bitten by the other case.
- **A guard that wrongly refuses gets fixed; one that wrongly grants
  does not get noticed.** When a heuristic has a window (a `WHERE`
  within six lines of its `FROM`), state the limit and make the
  out-of-window case *fail*, so the false result is the loud one.
- **A shared constant makes claims agree with each other, not with
  the behaviour.** Interpolating `MATCHER_CONTRACT` into four
  descriptions would have prevented nothing — a constant goes stale
  beside its code exactly as prose does. Pin the constant to the
  behaviour with a test per clause, and the description to the
  constant; then no two of the three can disagree.
- **Assert rendered output, not source.** A description assembled
  from f-strings can be correct in the file and wrong once built
  (`NameError` at import, or a stale interpolation). Read what the
  SDK actually reports.
- **"Keep both sides" is right for appends and wrong for
  contradictions.** (impl-3.) If both sides of a conflict assert
  something about behaviour, at most one can survive a change to
  that behaviour; a conflict in prose or in a pinned constant is a
  contradiction until shown otherwise, while a conflict in two
  independent test functions is an append. Keeping both would have
  shipped a pinned contract that was false — and the pin would have
  kept passing, because it checks the constant matches its phrase,
  not that the phrase is true.
- **Verify "keep both" three ways.** After an append-collision
  rebase: no conflict markers; no duplicate `def test_` per file; no
  duplicate node ids suite-wide (`--collect-only -q | sort | uniq -d`
  empty). The third catches a function appended twice under one
  name, where pytest silently keeps the last and the count still
  looks plausible.
- **Interpolation makes consistency free, and therefore worthless as
  evidence.** (impl-4.) Once a description derives from a constant,
  "they agree" is guaranteed by construction. Every interpolated
  contract needs a separate assertion tying the constant to the
  thing it describes, or the mechanism that removes one class of
  drift manufactures the appearance of safety against another.
- **A fixture that does not assert its own setup blames the feature
  under test.** A required field added upstream turned a fixture's
  create into a swallowed 422; the failure surfaced three asserts
  later as `assert 0 == 2` and pointed at correct code. Fixtures
  assert the response of every request they make.
- **A keyword check is a lower bound; close the loop upward too.**
  "The contract must name these three properties" cannot tell three
  from three-plus-a-false-one, and an addition is the one edit that
  reaches every interpolated description without failing anything.
  Pin the contract text exactly beside its clause tests, so any
  reword is a deliberate update.
- **Do not decide a product question from zero examples.** Whether
  a shared cost covering two assets splits evenly or by weight has no data
  behind it today; report the overlap so the caller has the evidence,
  and leave the split to the owner with a real case in front of them.
- **A true allow-list entry can cover more than it earned.** One
  function legitimately on two exemption lists for two different
  reasons; a merged list would let either reason justify both reads.
  Keep per-subject lists and assert the reasons differ.
- **A guard whose name implies completeness is more dangerous than an
  obviously partial one.** `test_archive_scope` guarded one of two
  archived tables. State coverage in the module docstring, including
  what is not covered and where that is tracked.
- **A check with one bound fails in the direction nobody pictures.**
  (impl-4.) A floor stops discriminating as the population grows; a
  discovery that finds nothing passes; a "must name these three"
  test admits a fourth, false claim. Ask of every assertion which
  direction it does not bound, and whether an edit in that direction
  is the natural one.
- **A relayed prediction is not a measurement.** "Mutation 3 fails
  two tests" was the reviewer's expectation, relayed by the lead as
  fact; it failed one until the guard was broadened. Relay figures
  with their status (measured / expected) and their source.
- **A mutation count is comparable only when the mutation is
  character-identical.** Two people "reworded the contract" and got
  1 and 2 failures; one replacement happened to contain the word the
  stale-claim guard looked for. Quote the replacement string with the
  count, the way a diff is quoted with a base.
- **Write tests that predict their own obsolescence.** A test that
  pinned "explicit nulls silently change nothing" carried a
  docstring naming the future change that would invalidate it and
  what to do then; when the API started rejecting nulls it failed as
  an instruction, not a puzzle, and the implementer revisited the
  comment it pointed at instead of repointing the test. Afterwards,
  record in the test that it did its job once, so it does not read
  as a stale assertion.
- **A test's data is part of its logic.** (impl-4.) Names that sort
  identically under binary and NOCASE collation cannot detect a
  dropped `COLLATE NOCASE`; two rows written in the same second
  cannot detect a reversed `ORDER BY changed_at`. Data that cannot
  distinguish the answers makes the assertion decorative. Choose
  fixture values that would sort, match or tie *differently* under
  the mutation you intend to catch.
- **Check the PR is still open before pushing to its branch.** A
  commit pushed to a branch whose PR has merged reopens nothing and
  is reviewed by nobody. Cherry-pick onto a fresh branch from main
  and open a new PR (a new SHA, per the taxonomy).
- **A convention and its enforcement can disagree about form.** The
  fence convention produces `fetch_all(list_entities, …)`; the
  detector required `list_entities(`. Same author, same week, and the
  recommended usage defeated the check that requires it. When a
  check reads text, test it against the text the convention actually
  produces, not the text you pictured.
- **Read the line above the one you are writing.** An exemption's
  detection was shaped like the neighbouring rule's and inherited
  its blind spot, two hours after that blind spot was named. A new
  clause beside an old pattern copies the pattern's shape by
  default; check whether it copies the pattern's hole.
- **A mutation result belongs to the tree it was run on.** Quoting
  it after a rebase is a claim about something you did not measure;
  re-run on the tree you are announcing.
- **When a fix eliminates a behaviour, grep for prose that cites it —
  and keep the past tense.** (review-1, after the third instance:
  #96's header, #102's trigger sentence, #110's reapply docstring;
  refined by impl-1 after the grep found two more in a file two
  directories from the diff, connected only by a shared model.) The
  justification usually outlives the thing it justified, and the
  hardest version to notice is a conclusion that survives while its
  stated basis has been inverted by the very change being shipped.
  Grep the whole tree, not the diff. Then: prose describing *why
  something was done* survives ("an empty PATCH *was* a 200, which is
  why this omits"); prose describing *what the system does now* does
  not. Nine hits, two wrong — do not rewrite the seven.
- **A green result is evidence only once you have shown the code
  under test executed.** (review-1's umbrella over three of their own
  corrections: name your base, quote the replacement, check which
  branch you reached — a mutation on a dated relationship type never
  reached `_differing_fields`, so "the suite still passed" was
  indistinguishable from "the guard was never called".) And the
  converse, from impl-4: a mutation that misses its target produces
  a false negative about a working guard, and the natural response
  is to weaken something that already worked — worse than the false
  positive it resembles, because the fix goes the wrong way.
- **Choose probe values the implementation would treat differently,
  not values you expect to matter.** (impl-1.) Six inputs, none at
  midnight, reported as "422 in every case" with a table that looked
  thorough; the boundary a datetime-to-date coercion cares about is
  midnight, and nobody asked. A table of results is persuasive in a
  way a sentence is not, which makes an unrepresentative one worse.
  When two people measure different results, run both inputs rather
  than choose a winner — the fact was in the difference.
- **A boundary is only pinned from both directions.** (impl-1.)
  Pin `00:00:01` and `23:30` either side of midnight, not just the
  midnight case: a test on one side of a boundary proves the
  boundary is somewhere, not where. And a subclass slips an
  isinstance check (`datetime` is a `date`) — refuse it by its own
  branch with its own mutation.
- **Argue for a ticket by measured reachability on the live system,
  not by title.** (impl-4.) Of three security-shaped tickets, one was
  unreachable under the live configuration, one latent until a route
  exists, and one — titled as a memory concern — was a live redaction
  bypass. Measure before ranking; the title was written before the
  system it describes.
- **Name a path by the setting that defines it, never by convention.**
  (impl-4, fourth instance in one file.) `REPO_ROOT / "logs"` did not
  exist; the real logs were at `settings.logs_dir`, configurable, and
  covered only by accident. The three correct entries above it came
  from settings and looked identical to the typed one. A test
  written against the typed path would have pinned the defect —
  which is why writing the test is when it was found.
- **Derive a boundary from the thing you mean, not its neighbour.**
  (impl-4.) A data hole derived from `db_path.parent` was the whole
  root under test (refused everything) and would have been the home
  directory in production (a hole the size of the disk). Name the
  sensitive directories and identify the database by identity;
  a neighbour-derived boundary gives everything or nothing, decided
  by layout.
- **"Unknown" and "clean" both accept today and must still be
  distinguished.** A scanned PDF yielding no text passes
  `assert_no_account_numbers("")` trivially; a test asserting
  acceptance cannot tell the extractor from a mutant returning `""`.
  The distinction is invisible now and load-bearing the day
  containment is relaxed for verified text — hold it in a test, not
  a comment.
- **A default root is a deny-list in disguise unless it is a single
  positive entry.** "The working tree minus the sensitive things we
  thought of" exposed `.env` with the API token after the financial
  holes were carefully named. Default to one purpose-built directory;
  make widening an act of intent; and keep the holes anyway, because
  roots are configurable to `/`.
- **A count pin detects arrival, not verification.** (review-1 and
  impl-3, on #120/#121.) The pinned count fired on the first new
  conflict site after it was written — the success case — and the
  step that mattered was the next one: the new site's test asserted
  a status *range*, which would have passed at 400, 409 or 422 alike.
  When a count moves, check the new member's own behavioural
  assertion pins the property, not merely that the member exists.
- **A filtered grep turns an absent result into a silent one.**
  (impl-3.) A mutation that produced uncompilable code made pytest
  fail at collection; `grep -E "passed|failed"` matched nothing, and
  a missing line read as a pass. Two rules: `ast.parse` /
  `py_compile` before trusting a mutation; and every "grep the output
  for the answer" check asserts the filter matched something. An
  empty result is not a passing result.
- **A status-code move is a free census of which branches anyone is
  watching.** (impl-3.) Flipping one error's code fails exactly the
  tests that pin it; the difference between that set and the set of
  raise sites is a coverage gap, obtained for nothing. Take the
  census whenever a shared constant changes.
- **Agreeing with a process fix does not install it.** (impl-3.) The
  restore-scope rule was flagged to two people and violated by its
  author an hour later; the collected-test count caught it. The
  mechanical check is the installation; the agreement is not.
- **No directory is safe by location.** (impl-4.) The documents
  store holds unredacted originals by design; every sensitive
  directory resolves under the repo root. Containment bounds what a
  tool can read; only a content check certifies what it read. Put
  the content check first and state containment's limit.
- **Ask what prose cites the behaviour this PR changes, before
  merging.** (review-1.) A rebase conflict can be semantic — two
  descriptions asserting incompatible things about one call — and
  the worst part may be a shared constant in a file git does not
  flag. Grep the tree for the old wording; an exact pin will catch
  it at the gate, but as a red test on someone else's rebase, which
  is a worse place to learn it.
- **An exact pin protects the sentence, not its truth.** (review-1.)
  A pin catches a reword, not a sentence that stays the same while
  the world changes around it; #115's machinery would have held the
  old dedup contract green indefinitely while #114 made it false. The
  truth needs the behavioural test beside it — the pairing lesson one
  layer up — and a superseded contract's old text is recorded next
  to the reason so the pin update reads as deliberate.
- **Match the normalisation the code under test uses.** A probe
  `"cannot link to itself" in description` returned False because the
  text is in caps and the test lowercases first; a probe stricter
  than the assertion it stands in for reports a failure the suite
  correctly does not have.
- **A contract pin asserts the sentence appears, not that it appears
  anywhere coherent.** (impl-3.) A narrowed contract landed under a
  heading saying the call is safe, so the refusal sat beneath
  "SAFE". Only rendering the description and reading it finds that.
  After any change that moves interpolated text, render and read.
- **A count asserted from a pattern is not a measurement.**
  (review-1.) "Four descriptions carry a false claim" was inferred
  from how other contracts fan out; rendering the tool list gave one.
  The conclusion survived; the alarm was three times too large.
  Render, then count.
- **A property that holds because of a component you do not control
  is a coincidence you are relying on.** (review-1, on the websocket
  hole Starlette happened to close first.) Close latent holes while
  they are latent: the change that breaks the coincidence will be one
  nobody connects to the property.
- **Comments come first.** A first-match mutation of a string that
  appears in both a comment and the code it describes lands on the
  comment; the code is untouched and the green suite reads as "the
  test is blind". Replace every occurrence, or scope to the code, and
  post-check that no unmutated copy remains.
- **Pin by where the output lands, not by what the package is
  called.** (impl-1.) Loud versus silent: something read at request
  time shows its change the next time you look; something written
  into a row is permanent and nothing re-derives it. A transport
  library whose decoded filename is stored is key-bearing; a
  recurrence library whose expansion is only reported is not. And
  the classification must assert both directions — the rest keep
  their floor, because pinning everything stops security updates
  and looks like diligence. The operative question is not "would
  this fail loudly?" but **"is there a version of this change that
  fails silently?"** — the first is about the expected case, the
  second about the worst one, and only the second is a safety
  argument. ("Loud" was a property of pydantic 2.13.5's strictness,
  not of pydantic.) The two directions of a parser change are not
  symmetric: stricter rejects and shouts; more lenient accepts what
  it used to reject and returns 200 having written a different
  value. A floor permits exactly the quiet direction — ask *which
  direction of this change would be quiet?*
- **Verify the property, not the label.** `.annotation` strips
  `Annotated` metadata, so `StrictInt` printed as `int`; "I checked
  the annotation" read as verification and was not. Prove a type
  behaviourally (`2.0` and `"250"` rejected) — and choose the
  discriminating case: plain `int` still rejects `2.5`.
- **A static annotation describes the worst the tool can do.** A
  tool with `dry_run=True` by default is still DESTRUCTIVE if the
  other setting writes; labelling it by the safe default puts the
  honest label on the call that writes.
- **Mutate the way the workflow would, not the way sabotage would.**
  D25's required mutation edited only the canonical copy, and three
  tests went red — proving the pins work, not that the behaviour test
  is load-bearing. The documented workflow propagates an edit to every
  copy; under that mutation the pins stay green and only the
  behaviour test catches it. A mutation that looks like an accident
  nobody would make proves less than one that looks like Tuesday.
- **A comment that states what the code does competes with the code;
  one that states why does not.** Three stale comments in one day,
  all descriptions of behaviour. A why-comment can still rot when its
  premise changes ("because the API has no `all`" the day `all`
  ships), but that fails loudly when someone acts on it.
- **Record two disagreeing instructions as two instructions.** The
  lead approved a field in one message and said "out" in the next;
  the implementer flagged the discrepancy instead of choosing. The
  log's first draft said "misread", which was not checkable against
  the source — the same failure the day was about, in the log itself.

- **Prefixes are not ids — and anything retyped from memory is a place the
  memory can be wrong. The remedy is to derive it, not to concentrate
  harder.** Recurred in four
  different costumes before I saw it was one thing. (a) I guessed ticket
  uuids from their 8-character prefixes three times and got three 404s, so
  I built a `resolve()` helper and made it the only path to an id — then
  typed *that helper's own file path* from memory and broke it, which is
  the failure mode reappearing one level up in the tool built to prevent
  it. (b) I posted a commit SHA in a PR comment from memory; it was wrong
  and I corrected it a minute later, but a wrong SHA in a review thread is
  the kind of thing a future reader takes at face value. (c) On #116 the
  date-field classification lived as prose in the PR body, transcribed by
  hand, and its stated justification — "none reaches a key" — was false:
  `reminder_instances` has `UNIQUE(reminder_id, due_date)` and the
  completion path upserts on it. (d) `runbooks/INDEX.md` had drifted from
  the directory it indexes and was missing `skill-conventions.md`
  entirely, so a file whose whole purpose is to be findable wasn't.
  **In every case the correct value was mechanically available** — `git
  rev-parse`, a `resolve()` call, a walk of `model_fields`, a parse of
  `db/schema.sql`, a directory listing — and in every case I typed it
  instead because typing it felt faster than fetching it. It is faster.
  That's the trap: the cost of the shortcut lands later and on someone
  else, and it lands looking like a different bug than the one you caused.
  So: **if a value exists somewhere authoritative, read it from there.**
  A path, a SHA, an id, a field list, a filename — anything you could have
  looked up and instead recalled is a defect waiting for the day your
  recall is stale. This is why the fix for the #116 miss was not "classify
  more carefully next time" but a test that parses the `UNIQUE` constraints
  out of the schema: a more careful classification is still a
  classification, and would have failed the same way the day my attention
  slipped.
- **But a derived check has its own failure mode: it can derive nothing
  and pass.** The pair to the note above, and the reason "just derive it"
  isn't the whole rule. A discovery that finds zero things is green and
  silent, and it looks exactly like a discovery that found everything and
  approved of it — this repo has already been bitten by it twice (a
  differential harness that reported "zero ambiguous ties" when the corpus
  simply couldn't produce one; an empty `parametrize` that collected no
  tests at all). **So every derived check asserts its own catch was
  non-empty** — `assert key_columns, "parsed no dated UNIQUE columns"` in
  the #116 test, which fails loudly if the regex ever stops matching the
  schema rather than quietly approving every field in the codebase. Derive
  the value, then prove the derivation found something. A check that can
  only pass is not a check.
- **Test at the seam the claim names, not the seam you just built.** #122
  claimed "a file with both causes reports both"; its test called the
  message-formatting helper with two labels and watched two labels come
  out — true, and not the claim. The claim was about the *classifier*
  seeing one file, and the classifier collapsed per file, which only
  showed when the test was rewritten to hand one real migration file to
  the real entry point. The nearest seam to the change is the natural
  place to put a test, and it is exactly the place that cannot fail on
  the layer below it. Before writing the test, say the claim aloud and
  name the function the claim is about; if the test doesn't call that
  function, it tests something else. (impl-1's own line, adopted: "I
  tested the layer I had just written instead of the behaviour I
  claimed.")
- **A figure built from two measurements must be built from the same
  setup.** #123's first "8%" divided a cost measured on the live DB by a
  request measured on a fresh one. Each number was right; the ratio was
  of nothing. When a published figure is a ratio, name the setup once and
  take both halves from it, and say which half the residual uncertainty
  lives in (the corrected 12.2% is an upper bound, and the entry says why).
- **Wrong thing, wrong world: two ways a green suite lies, and mutation
  testing catches neither.** Within an hour impl-1 hit both halves. On
  #122 the test was pointed at the wrong *thing* (the message layer just
  written, not the classifier the claim named) and eight mutations
  "passed" over a broken classifier. On #120 the test was pointed at the
  right thing on the wrong *world* (a tree that no longer existed). Both
  produce a green suite and a true-sounding sentence. Mutation testing
  verifies that tests notice changes to what they watch; it cannot say
  they watch the right thing, or that the thing still exists. So a
  mutation table in a PR body proves sensitivity, and the body still has
  to say, separately, which function the test calls and which tree it
  ran on.
- **A rebase conflict can land inside a function body and leave no
  marker, no duplicate name and no syntax error.** #124's rebase spliced
  a new block between a #120 test's docstring and its body; the old body
  was absorbed as the new helper's body and ten tests failed with a
  `TypeError`. The duplicate-`def` check saw nothing because the damage
  was a *missing* `def`, not a repeated one. "Keep both sides" is wrong
  for contradictions (earlier bullet) and also wrong when the conflict is
  *inside* a definition — there the only safe move is to rebuild the
  file deterministically (main's copy whole, your block appended from
  your old head) and then verify the function *boundaries* survived:
  every `def` name from both sides present, `ast.parse` clean, and the
  collected-test diff equal to exactly your additions. And the lead
  asking "how did the `!` arise?" before naming a cause: I called that
  rebase "diff-alignment only" from the range-diff's shape and it was a
  conflict resolution — a range-diff shows the result, not the route.
- **A verification chain must stop at the first failure, and `;` does
  not.** `rebase; pytest; push` pushed when the rebase stopped on a
  conflict. It happened to publish a valid earlier commit (checked with
  `git ls-remote`, not assumed), which is luck. Chain with `&&`, and
  check the remote after any chain that could have half-run.
- **"Passed the content check" does not mean "is text".** The #119 check
  returns `None` for a binary, which means UNKNOWN, not clean — that
  distinction was the point of #119. impl-4 measured it before building
  a route on the opposite premise: a PNG and a `.log` both pass the
  check and neither extracts (`.log` is not in `TEXT_SUFFIXES`, and is
  the attach tool's own second example of what to attach). When a
  design brief states what a store contains, measure the store; the
  brief's author (me) had inferred it from the check's name.
- **A probe that fabricates the path it tests cannot discover that the
  path is wrong.** review-1's #119 probe did `mkdir REPO_ROOT/logs` and
  then confirmed the hole covered it — answering "does the hole cover
  this path" when the question was "does the hole cover the logs". The
  directory never existed; the real logs live at `settings.logs_dir`
  under `data/`, and being configurable they could have moved out from
  under the hole silently. impl-4 found it by writing the test against
  the setting (D103); the probe hid it by creating the thing it needed.
  Distinct from the stale-value instrument failure: here the instrument
  was fresh and pointed at a path the prober invented. Before probing a
  guard over a path, `ls` the path; if you had to create it, the probe
  is measuring your own fixture.
- **The skipped-fence shape closed on its own reader.** impl-1 copied the
  fetch_all fence into the work-the-board skill to satisfy the dispatch;
  `test_skill_conventions.py` *skipped* the skill ("names no list tool")
  because the heuristic matches `list_[a-z_]+` and the three paged tools
  the skill uses aren't named that. Green suite, skip count up one,
  fence checked by nothing — the exact under-fire case that file
  documents, reproduced within an hour of reading the warning. The right
  response was not "ship with a note" but making the fence earn its
  place (the skill now drains `get_ticket_history`, which the loop
  genuinely needs), so the skip disappeared and the fence is required.
  Watch the skip count the way you watch the failure count.
- **`ast.parse` proves a mutation compiles, not that it does what it
  says — and a count higher than published deserves the same suspicion
  as one lower.** Two of review-1's #121 mutations measured something
  else: one inserted at the wrong function's `return` (wrong scope, two
  unrelated 500s), one raising `HTTPException` in a module that doesn't
  import it. Both compiled; `NameError` is a runtime failure. They were
  caught only by reading the *names* of the failing tests when the count
  missed the published figure. So: read failure names on every miss, in
  either direction, and quote the replacement string in the table so the
  next person can re-run it (a "→ 4" row nobody could reproduce is the
  part of a mutation table taken on trust).
- **A ticket filed from a reviewer's sentence inherits the sentence's
  errors, and adds the filer's.** I turned review-1's "the `delete_board`
  situation" into a ticket's *what done looks like* — a fixture forcing
  an `IntegrityError` fall-through in `delete_board` — without opening
  `delete_board`, which has no `try`, no `except`, and no backstop (it's
  an explicit pre-check). impl-1 found it by classifying all nine sites
  with the enclosing `except` in view, after their own first pass
  misread one from a six-line context window. The underlying finding
  (one counted site answers to nothing) may still hold at a different
  function. Rule: before a ticket names a function and a branch, read
  the function; the ticket is the brief the next person builds from,
  and "what done looks like" written against a branch that isn't there
  sends them to build a fixture for nothing. impl-1's sharper form, after
  making the same error an hour later in the same file (a six-line
  window read `delete_entity:462` as a pre-check because the `except`
  sat above it behind a long comment): **which branch a `raise` sits in
  is derived from the enclosing block, never from a phrase or from what
  is nearby.** "Open the function first" is not enough — the second
  reader had opened it.
- **A conflict resolved inside a function body can empty a test while
  preserving every count you would use to check the resolution.** At
  #124's first rebase the spliced test had a docstring-only body and,
  run alone, *passed*. Test-def count, collected count and duplicate-name
  check were identical across the defect and its repair — the splice
  moved a body, it did not remove a `def`. It was noticed only because
  siblings that called the stolen helper failed with `TypeError`; had
  the stolen body broken nothing else, the emptied test would have
  merged green and asserted nothing forever. So after any in-function
  conflict, run the affected tests *against the mutation they guard*,
  not just the suite. And rebuild faithful to the base, not to what
  looks right: #124's rebuilt file left #121's four `== 409` lines
  byte-identical to their base, which is the only reason the later
  three-way merge resolved them in main's favour instead of silently
  reverting the tightening.
- **A mutation needs a post-condition about the thing it claims to
  remove.** review-1's first `apply_clear` no-op sliced by line offsets,
  kept the whole body and re-added the return: it parsed, compiled,
  produced a non-zero diff, and the suite went green — which reads
  exactly like "nothing covers this". The second attempt asserted the
  post-condition through the AST (body went from three statements to
  one) and two tests failed. "Mutation applied" (a diff exists) and "it
  compiles" are both satisfied by a mutation that did nothing; assert
  the shape of the result, not the fact of a change. Twice in one day a
  false negative was one paste away from publication.
- **Two approved PRs can auto-merge into two implementations of one
  convention.** #124 (inline value-and-clear refusal) and #126 (shared
  `apply_clear`) merged textually clean in `tools/entities.py` and
  semantically wrong: one tool kept its own copy. The derived guard
  (`update_* tools taking 'clear' without explaining it`) named it, so
  it could not merge silently — which is the reason those guards are
  derived over the tool registry rather than enumerated. When two open
  PRs touch one convention, merge the one that *defines* the convention
  first and rebase the other onto it as a deletion.
- **Test the production wiring, not a wiring that resembles it.**
  `attach_file` never worked over the deployed MCP server: `api/main.py`
  builds `build_server(_LazyClient())`, the proxy forwards only
  `request`, and the tool reads `client.settings` — `AttributeError`,
  which the SDK flattens to "Error executing tool". Every test builds
  `build_server(real AppClient)`, so #119's refusals were verified
  in tests and were dead code in production from the day they shipped.
  The difference between the two wirings *was* the bug, and nothing
  exercised it. Found by impl-3 driving the deployed surface over HTTP
  with an MCP client session rather than calling tool functions
  in-process. Rule: at least one test constructs the server exactly as
  the entry point does and calls a tool through it; and when a review
  says "verified live", ask which wiring was live.
- **A live exercise reports the clean list alongside the defects.** The
  eight tickets from impl-3's exercise came with what was tried and
  found correct (`get_board`'s four documented claims, every error
  envelope naming the thing and the valid values, `claim_ticket` on a
  drained queue, `update_entity`'s accept-only-to-refuse params, dedup
  on identical re-POST). Without that list the next person re-probes
  the same surface; with it, they start where this one stopped. Also
  from that exercise, two self-corrections caught before filing — an
  annotations probe reading camelCase off snake_case, and "epic" nearly
  filed as an unvalidated enum: *the check read through the thing it was
  meant to discriminate.* Before filing, ask what the probe would have
  reported if the surface were correct.
- **A generated inventory can be plausibly, completely wrong, and a pin
  will then defend the wrong thing.** #131's first route walk over
  `app.routes` returned `/health` and `/` — FastAPI hides included
  routers behind a private `_IncludedRouter` — and a two-endpoint API
  rendered as a perfectly formed table. No assertion caught it; impl-1
  noticed the output was too short. A derived check must carry a floor
  that the real answer clears by a wide margin *and* a vacuity assertion
  per section (an empty section raises, it does not render). And while
  probing it, `getattr(x, "routes", "<none>")` returned a six-character
  string that read as "an attribute holding six items": it was the
  probe's own default value coming back. When a probe's answer is the
  same for every attribute you try, you are reading your default.
- **A vacuity guard has to name what it needs, not count what it got.**
  #132's trigger check discovered SQL files by glob and asserted the
  list was non-empty — the rule from earlier in this file. impl-1's
  mutation broke the glob so `schema.sql` dropped out: six migration
  files remained, `assert files` passed, and the file most likely to
  hold a trigger was no longer being read. The catch was non-empty; it
  just no longer contained the thing that mattered. `assert files` and
  `assert key_columns` are the weak form — they catch total collapse,
  not the specific loss. The guard now asserts `schema.sql` is in the
  set, and both glob mutations go red. Found by the mutation, not by
  reading: the test was green, looked principled, and already carried
  the non-empty assertion that would make a reader move on. Corollary
  for the same PR: count write sites through the AST, not by line —
  prose that discusses a column counts as evidence about the code under
  a line search, and implicitly concatenated SQL splits its verb from
  its target across lines.
  **Amendment, after the rule's author broke it again the same evening
  (#131):** "name what it needs" felt satisfied by asserting each
  section heading existed, and the skills and migrations collectors
  could render zero rows under it. The operational form is mechanical:
  **every collector must be independently falsifiable — break each one
  alone and something must fail that names it.** Run that check
  literally, one collector at a time, before calling a derived guard
  done. And prefer an independent count (a second traversal sharing no
  code with the collector) over a chosen floor: a floor tolerates
  partial loss by design, an equality does not.
- **A justification written in the future tense has an expiry date, and
  nothing in the repo knows when it passed.** Fourth instance in a day
  (review-1, #129): a new test asserted `400 <= status < 500` with the
  comment "T-409 *moves* conflict 400 → 409" — T-409 was already
  in the tree, and the sibling test twelve lines above said the range
  was "too weak to keep once T-409 settled the code". Nobody forgot
  a rule; each author wrote theirs correctly and in the right place.
  What fails is re-reading: a comment about a change that is going to
  happen survives the change and keeps being copied forward because it
  still reads like a reason. The tense is the tell. Actionable form: a
  comment naming a ticket in the future tense is a comment to re-check
  the moment that ticket merges — grep for the ticket id when you close
  it, and rewrite every hit into the past tense or delete it. impl-1's
  sharper form: such a comment gets *more* persuasive as it ages — each
  copy looks like it is following settled practice rather than a note
  someone forgot to delete. So the generalising fix is not "check the
  tense" but **name the state, not the transition**: `ConflictError is
  409` is falsifiable on sight; "T-409 moves it" is not falsifiable
  without knowing whether T-409 landed.
- **A guard can do two jobs while its docstring names one.** #128's
  `ensure_wal_mode` runs only when `_database_state` is ready; the
  docstring reasons about incomplete/corrupt, but "missing" is also
  non-ready, and without the guard `sqlite3.connect` creates a 4096-byte
  database where none existed. A future reader narrowing the condition
  to `{"incomplete", "corrupt"}` would read as *more* precise, which is
  what makes it likely. When a mutation fails more tests than the
  docstring predicts, the extra failures are the jobs the docstring
  doesn't know about; write them in.
- **A deny-list keyed on names cannot protect a namespace the caller
  can extend.** `_redact_sensitive_inputs` masked values by field name
  against a set of known-sensitive names; an *unknown* key is by
  construction not on that list, so `{"ssn": "123-45-6789"}` on a
  person came back verbatim in the 422 — which travels through the MCP
  tool into model context. Found by impl-1 reading the path while
  fixing #134's message, not by any test. Lengthening the list fixes
  nothing; the mechanism has no answer for a field it has never heard
  of. The fix drops the echoed value wherever the name is not from a
  known schema and keeps the name (the name says what to fix, and a
  name the caller chose is not the secret). When you see a name-keyed
  allow- or deny-list guarding data, ask what it does with a name it
  doesn't recognise — and whether the caller can invent one.
- **Before writing a sentence that warns against a change, make the
  change and see what goes red.** #128's hold was one docstring
  sentence warning against narrowing `!= "ready"` to
  `in ("incomplete", "corrupt")`. impl-3 tried the narrowing first: all
  45 of `test_db.py` passed; the whole `api/` suite failed exactly one
  test, in `test_mcp_mount.py`, named "left the rest of the api alone".
  The invariant was held by accident, by a test whose name tells the
  reader nothing about what they broke — the kind of failure that gets
  dismissed as unrelated and worked around, which is how the narrowing
  would have survived. The sentence shipped with a test that fails first
  and says why. A prose warning with nothing enforcing it is a comment
  asserting a property; and a mutation count taken from one test file
  ("1 fails") is a scope error, not a measurement — the suite is the
  unit.
- **A concurrency test has to open the window it claims to test.** #133
  asserts `_LazyClient` constructs the real client exactly once under
  concurrent first calls. The natural test for an async server — two
  tasks racing the first call — *passes with the lock removed*, because
  `__getattr__` is synchronous and there is no `await` between the check
  and the assignment, so tasks cannot interleave there. It would have
  reported a clean number while measuring nothing. The discriminating
  test drives threads through a barrier with a delayed factory so the
  window is reliably open (lock removed: "built 8 clients, not 1"); the
  async version stays beside it as evidence about the wiring, and each
  docstring says which property it is evidence for. Before trusting a
  race test, remove the lock and watch it fail.
- **A mutation harness refuses a dirty tree for any reason, including
  another harness.** review-1 started mutations in a background script,
  concluded it had died, and ran one of the same mutations in the
  foreground against the same worktree while the script was still live.
  The result happened to match the true one and was unattributable —
  nobody could say which file was in which state when the suite ran. It
  was discarded, the tree restored to a verified-clean baseline, and the
  script's own sequential results used. "I think that finished" is not a
  measurement of whether it finished, and a background job whose output
  is piped through `tail` looks identical to a dead one until it
  flushes. Check the process, not the silence.
- **Harness files go in the session scratchpad, never in shared `/tmp`
  with generic names.** review-1 ran a day of probes as `/tmp/ours.py`,
  `/tmp/theirs.py`, `/tmp/a.txt` while three other sessions ran
  concurrently. Nothing collided, as far as anyone can tell — and "as
  far as anyone can tell" is the problem: a clobbered intermediate
  file reads as a wrong comparison with no error and nothing to
  attribute it to, which is strictly worse than the dirty-tree error,
  which at least leaves a mark. A shared resource with unqualified
  names and an agent that assumes it is alone. The environment already
  provides a per-session scratchpad; use it.
- **Every fix PR carries the revert mutation: put the pre-fix behaviour
  back and something must go red.** #150's conditional-CREATE fix
  reverted to pre-PR behaviour left 1861 passed, 0 failed — the fix was
  untested, and the test that said "pinned where it is implemented"
  asserted on a helper and a regex, never on the excluding function.
  A fix whose revert is green is a fix nobody can prove landed.
- **A test that retypes the production filter will diverge, and it
  diverges in the direction of the defect.** #150's `_columns_supplied_for`
  copied the production check as `table in conditional` where
  production does `table.lower() in conditional`; on `CREATE TABLE IF
  NOT EXISTS Thing` the copy says "supplies" and production says not,
  and the two tests pinning the rebuild decision ran against the copy —
  which is why they survived the revert. Tests call the production
  helper; a mirror is a second implementation, a checksum, not a
  witness.
- **Two anchor traps for mutation harnesses (review-2).** A call can be
  a substring of another — `glob("test_*.py")` occurs inside
  `rglob("test_*.py")`, so a count-equals-one anchor is the only thing
  that stops the wrong site being edited. And a replacement string can
  legitimately live elsewhere in the file — `"days": delta - 1,` is on
  both the gap and the overlap branch — so "absent after restore" is
  the wrong post-check there; byte-compare the file to its
  pre-mutation contents instead.
- **Two reviewers on one PR is not wasted when the second reads it
  cold.** review-2's parallel reviews of the already-merged #145 and
  #147 (a rebalance message crossed their work) produced five post-merge
  findings review-1 had not raised, including one where the merged
  guard cannot see its own package leave `testpaths`. When a duplicate
  review happens by accident, read it for what the first reviewer's
  context made invisible.
- **A description pin asserts the old claim is gone, not only that the
  new words are present.** #145's pins were keyword lower bounds, so
  reverting the description to its pre-PR text — including the sentence
  the PR called wrong — stayed green. When a change exists to remove a
  misleading sentence, the test names that sentence and asserts its
  absence, alongside the exact new one.
- **Parallel names promise parallel conventions.** #145 made overlap
  bounds *be* the overlap while gap bounds still *bracket* the gap, then
  named them `overlap_*` and `gap_*`; before, the shapes were obviously
  different and nobody generalised across them. If two fields are named
  as siblings they obey one rule, or they are not named as siblings.
- **A derived pin sequences unrelated work; say so where the pin is.**
  Every PR that adds a test or route now regenerates `docs/SYSTEM.md`
  (one command), and post-merge tickets that add tests wait behind the
  regeneration in flight. Accepted (D148) as the price of an inventory
  that cannot rot; the regeneration step is on the pre-PR checklist.
- **A mutation that changes what gets collected cannot be verified by
  a run that names the file explicitly.** review-1 mutated `testpaths`
  on #147 and ran `pytest tests/test_no_duplicate_definitions.py` — the
  explicit path forces collection of the very test whose collection
  was the thing at risk, so the run proved the assertion's logic and
  said nothing about whether it runs. Second reviewer, bare suite: 143
  tests gone, green. Same family as verifying a fix on a clean slate —
  the narrowing removed the condition under test. For anything about
  collection, configuration or discovery, the mutation run is the bare
  suite, exactly as the gate runs it. review-2's extension: the rule
  covers anything that decides whether a test runs at all — `skipif`,
  an autouse fixture that errors, a conftest that fails to import, a
  parametrize that collapses to a skip — not only `testpaths`. And a
  brief that asks "is the pin exact?" is what surfaced #145's unpinned
  description; keep the question in briefs rather than crediting or
  blaming a reviewer for it.
- **A guard that fails as an INTERNALERROR reads as a harness bug and
  gets deleted.** review-1 pre-validated the root-conftest fix for the
  `testpaths` hole: a bare `assert` in `pytest_configure` fires before
  collection and renders as `INTERNALERROR> AssertionError` with a
  traceback — loud, correct, and the reading most likely to get it
  "fixed" by removal. `raise pytest.UsageError(...)` renders the same
  condition as a deliberate refusal and exits 4 (checked with the
  pipeline removed, since a clean message with exit 0 would be worse
  than the traceback). And a check that lives in a hook is deliberately
  not a test — it cannot be deselected, which is the whole point — so
  the PR says so, or the next tidy moves it back into a test file.
- **When moving a guard, diff the assertions of the old and new
  versions, not just the behaviour.** #153 moved the coverage check into
  a conftest hook and the non-empty guard — which the old file's own
  comment said was "the only reason this comment exists rather than a
  silently vacuous check" — did not survive the move: two raises went
  in, three assertions came out, and a broken walk passed over an
  empty set. A rewrite silently drops the assertions that are not its
  subject, because the subject gets the attention and the rest is
  scenery. Count them before and after.
- **A guard that derives a set is not mergeable without a case that
  empties the set.** review-1's mechanical form after the third guard
  in one ticket's lineage needed its own catch asserted non-empty: the
  vacuity case is never the subject of the change, so it survives
  review by not being what anyone is looking at. Same move as the
  apply-assertion on a mutation — not a thing to remember, a thing the
  PR is refused without. And the act that catches it is not applying a
  reviewer's note about form but running the case the note describes:
  impl-1 checked whether what they had built actually had the
  non-empty check, and it did not. review-1's tightening of the
  moving-a-guard rule: diff the *set of conditions that can make it
  fail*, not the count of raises — a guard can keep its count and still
  lose a condition by merging two. And impl-1's line for why applying
  a note is not checking: reading a specification against your code
  tells you whether you agree with it, not whether the code does what
  it says.
- **`in` against a fragment, when you mean "exactly this and nothing
  more" — fifth time.** impl-3's tally: `"title"` in both refusals;
  camelCase on a snake_case object; a frozen clock sharing a month with
  the real one; the ambiguity substring the generic refusal also
  contains; and `"…scheduled date: <+7>" in message`, a prefix of
  `"…scheduled date: <+7>, <+14>."`, so re-adding the requested date
  passed. None found by reading; all found by mutation. The fix each
  time was a terminator, a negative assertion, or an anchor the
  superset cannot satisfy. When you write `in`, ask what superset
  would also pass.
- **A number that should have changed and didn't deserves the same
  suspicion as one that changed unexpectedly.** review-1 retracted half
  their own #131 reference list: every section count was identical
  after four merges while two of the three test-count rows had changed
  value — a matching summary over a set whose members changed, the
  diffstat rule in their own artifact on the day they filed it. Use a
  reference list for "did anything get missed" (membership), never for
  "are these the right numbers" (values); regenerate and diff.
- **A review bar sent before the build earns its keep even when it
  arrives after the push.** review-2 sent impl-3 the seven checks and
  the property stated implementation-independently; impl-3 ran them
  against their own tree and found two real gaps (a test that chose its
  own target date instead of reading it out of `/due`; an untested
  sibling case). State the bar in the brief when you can; when you
  can't, send it anyway.
- **Every clause of a compound condition is independently
  falsifiable.** review-2 mutated only the snoozed-away half of #136's
  two-clause gate and got a fully green suite while the R-F1 false
  refusal reproduced behaviourally — half the gate unpinned. The final
  head reds each half by name and both together by two. The standard
  usually met for collectors and usually missed for `and`/`or`. The
  operational form: **mutate each conjunct, not the condition** — the
  tell is that mutating the whole condition goes red convincingly, and
  that convincing red is what stops anyone mutating the halves.
  impl-3's collapse of their five surviving mutations into one rule:
  the check fires on a superset of what you mean, and the superset case
  is the one nobody constructs.
- **Independence of mechanism is not independence of author.** review-1
  withdrew their own claim that two reviewers on one PR had caught more
  than dividing them would: in both cases the lever was method (the
  bare suite; "is the pin exact?"), and two reviewers running the same
  narrowed invocation would have agreed and both been wrong. Duplication
  delivered the method difference by accident — an unreliable
  randomiser at twice the cost. Make the method explicit in the brief
  and the runbook so the accident is not needed.
- **A cross-check is a witness if the two sides can disagree, and stays
  one only if the condition that would collapse them is asserted.**
  review-1 had called #131's test-count check "closest to a checksum"
  twice, from its name and subject matter rather than its mechanism,
  and built an argument on it; measured, the generator's count skewed
  by one fails it by name — an AST walk against a line-anchored recount,
  with the collapsing condition (a test method inside a class) asserted
  in the check itself. Two derivations equivalent by coincidence are a
  mirror with extra steps; one that knows what would make it a mirror
  and guards it is a witness. And the lead relayed the label to the
  implementer as an instruction before the measurement landed: a
  reviewer's characterisation of a check is a claim about its
  mechanism, and gets read, not repeated. review-2's third measurement
  of the same check sets the bound: a witness's power is limited to
  the ways the two mechanisms can diverge *in this tree* — 4 of 6
  generator mutations red it, and the 2 that miss do so because the
  tree holds no nested test defs, no class methods and no `testfoo`
  names, so three divergence conditions are unexercised. Assert the
  equivalence conditions themselves (AST-walk count equals top-level
  count), not one of them with a docstring that reads as if all are
  guarded. And review-1's refinement, measured: adding those
  assertions does *not* make the two surviving mutations red — nothing
  can, on a corpus with no distinguishing case — it converts a silent
  future failure (a bare number mismatch when someone adds a nested
  test) into one that fails by name saying the recount is no longer
  equivalent. A witness's power is bounded by the corpus; guarding the
  corpus does not raise it, it makes the boundary loud. impl-1's
  docstring on the final commit is the rule the whole thread was an
  instance of, lifted verbatim: **"a cross-check whose equivalence
  conditions are unexercised is correct for reasons nothing pins."**
- **A range-diff shows the commit is *the* commit, not that its
  assertions fire.** Six `=` plus one on top says nothing about whether
  the new one works; review-1 ran the three assertions post-merge
  rather than assuming. For a hold commit that adds a check, the merge
  gate is the range-diff and the check is still run by someone.
- **Over MCP, a 404 and a 400 arrive as the same `ToolError`.** impl-4's
  live verification could only read the D17 distinction at the REST
  layer. Any live check phrased as "expect a refusal" is blind to which
  refusal; read the code where it exists, or make the message carry it
  (ticketed for the owner).
- **A printer that `.get()`s on an error dict masks a `ToolError`.**
  impl-4's live harness reported `trend` returning zero buckets; the
  response was an error dict for a missing required filter and the
  printer's `.get("items", [])` turned it into an empty list — nearly
  filed as the run's last finding. Print the raw response before
  interpreting it, and never default a missing key on a path that can
  carry an error.
- **Read the deployed `tools/list` schema before calling a tool.**
  Invented argument names for two tools until the schema was read —
  derive-don't-retype, inside the verification of derive-don't-retype.
- **Fixing half a symmetry creates a false one.** impl-1 on their own
  #145: making the overlap self-consistent while leaving the gap
  bracketing gave two entries parallel names and mismatched rules —
  worse than before, because an inconsistency that looks like a
  convention is more dangerous than one that looks like two unrelated
  things. When you regularise one of a pair, regularise the pair, or
  do not give them sibling names.
- **A check that the right thing was added is not a check that the
  wrong thing is gone.** Same shape as #116's prose classification and
  #135's past-tense comment; #154 pins both directions on the
  description and verifies both failure modes.
- **The run's one rule, in impl-1's closing words: when a check passes,
  ask what it would take for it to fail, and then do that.** Every
  entry above from 2026-09-19/20 is an instance: a `.pyc` whose absence
  meant "unchanged", a null meaning both "unset" and "absent", an
  annotation whose absence meant its own opposite, a deny-list over a
  namespace the caller could extend, a guard living inside the package
  it guarded, a repository that could not distinguish two behaviours of
  its own generator. Each passed, looked principled, and was wrong for
  a reason unrelated to the property it claimed. Nothing clever caught
  any of them; running the case did. And being wrong was cheap because
  the dispatches asked for measurements rather than conclusions, so a
  retraction was just another measurement — keep it that way.
- **How to read the entries above (review-1, standing down).** They
  come from someone who published a false test count, built three
  arguments on a test's name rather than its content, invalidated a
  mutation by naming the file, ran two harnesses on one tree, used
  generic filenames in shared `/tmp`, held three positions on one
  question before measurement settled it, and had five apply-failures
  produce clean greens. Every one was caught by a mechanism, not by
  attention — usually a post-condition written after the same class had
  caught them earlier. The entries are worth trusting because they were
  extracted from failures, not because their authors stopped making
  them. Read them as advice from people who were wrong often enough to
  find where the cheap checks go.
- **The one named gap without a mechanism: two correct things whose
  relationship is wrong.** Every check built in this run examines one
  artifact. The class the last PR closed — gap bounds and overlap
  bounds each right alone, obeying different rules under sibling
  names — needed someone to compute both spans by hand from a real
  response and notice, and it was looked at only because a brief asked
  a question pointing there. Until there is a mechanism, briefs carry
  discriminating questions ("do these two shapes obey one rule?", "is
  the pin exact against the old text?"), and the runbook records which
  question found what.
- **A sentence in a refusal that promises a next step is executed, not
  read.** "works again once only one occurrence is left on it" —
  review-2 took the message's advice in order and got 200 then 200. A
  message that names a remedy makes a factual claim, and the test
  walks it.
- **A mutation harness's failure paths need the same restore
  discipline as its success path.** review-2's harness left a file
  mutated when a post-condition failed, so the next mutation measured
  a doubly-mutated tree; caught by that mutation's `restored == before`
  assertion, both rows re-run clean. A bad post-condition is exactly
  when the tree is dirty and nobody is looking: restore before raising.
  (The fix's own patch then failed its uniqueness anchor because the
  anchor appeared in two functions — the anchor trap inside the fix
  for the anchor traps.)
- **A check whose verdict is printed but not wired to anything is not
  a check — the lead's turn.** The patch-identity comparison before a
  rebased merge was `diff … && echo IDENTICAL || echo DIFFERS` chained
  into the gate with `&&`; the `||` branch returns 0, so DIFFERS was
  printed and the merge ran. Sound by luck (context lines only). Now a
  script whose exit status is the gate, comparing added/removed lines
  only. If a verification prints a word, ask what reads the word;
  usually the answer is "nobody", and the exit status is what should
  have carried it.
- **A checker inside the thing it checks is not a check; it is a
  component of it.** impl-1's root cause for the `testpaths` hole: the
  guard was independent of the *list* but not of its own *execution* —
  it asked "can the list shrink without me noticing?" and never "what
  if I am not there to ask?" A guard over configuration, discovery or
  collection lives somewhere that cannot be deselected (a root
  conftest hook), and the PR states that it is therefore not a test.
  Corollary from the same PR: impl-1 fixed the recursion in one walk
  and then wrote the new check with the non-recursive assumption still
  in their head — a nested test directory pytest collects was reported
  as "NOT BEING RUN". After fixing an assumption in one place, grep the
  change for the same assumption before pushing.
- **"The class moved rather than closed."** review-2 on #136's second
  round: the F1 fix stopped the silent write and left the same
  disagreement between the resolver's candidate set (membership alone)
  and `/due`'s view (membership plus instance state), which now
  surfaces as a false refusal. Strictly better, and not the ruling,
  which was to close the class. When a fix for "these two views
  disagree" is measured, re-run the original disagreement in every
  instance-state combination, not only the one the ticket showed; a
  class is closed when the two views cannot differ, not when the
  reported symptom is gone. And a refusal that names an alternative
  must have that alternative measured to succeed — "+14" that refuses
  identically is #138's shape one endpoint over.
- **Mixed floors mask a small section's collapse.** #131's inventory
  test had a floor on all bullet rows and a floor on all table rows,
  spanning two sections each, plus a check that every heading exists.
  Breaking the skills collector or the migrations collector rendered
  zero rows with all three tests green: the large section carried the
  floor for the small one, and a heading with nothing under it is still
  a heading. A document could state the system has no skills and the
  suite would call it verified. One floor per section, each vacuity
  its own failure by name — a floor that spans sections is a floor on
  the wrong thing.
- **An advertised broken tool is worse than an absent one.** Under the
  `_LazyClient` gap all 53 tools still listed, because `build_server`
  succeeded; the deployed server advertised two tools that could only
  fail. A model routes around a tool that isn't there and *retries* one
  that is there and errors. So "the server starts and lists its tools"
  is not evidence any of them work; the production-wiring test drives a
  call through each one.
- **A lossy decode is not a hole when the strict decode gates what can
  be served — and that argument should be written next to the lossy
  call.** `_pages_of` keeps `errors="replace"` for known text suffixes;
  `read_attachment` decodes strictly. Anything the tool can serve
  decodes cleanly, and anything that decodes cleanly is byte-identical
  under `replace`, so the lossy path can only be more conservative.
  review-1 proved it rather than flagging it; the proof lives in the
  code comment so the next reader doesn't re-derive or re-flag it.
- **Checking a layer tells you nothing about the layers downstream of
  it, including whether they already handle what you found.** impl-1
  measured `validate_entity_attributes`'s error list, saw an ssn value
  in it, and reported that the 422 body carried it into model context —
  without reading `_error_detail` in `api/main.py`, which drops `input`
  wholesale and cites the rule by name. Escalated as a CLAUDE.md breach;
  retracted an hour later after posting the actual request (four
  cases, `leaked=False` each). The thirty-second check — send the real
  request, read the real response — comes *before* the escalation, not
  after. And the guard that saved us was one nobody in the room had
  read, which is its own finding: it is now pinned directly.
- **Absence read as a value, third variant.** `EXPECTED_TOOLS` read a
  tool's `destructive` through `bool(...)`, so an explicit `False` and a
  missing annotation were one value — while the MCP spec reads a
  missing hint as `true`. The table asserted "not destructive" about
  the tools a client would treat as most dangerous. Same distinction as
  `model_fields_set` for PATCH bodies and the missing-`.pyc` trap: when
  a check coerces `None`, ask what the *consumer* of that field does
  with `None`, because it is often the opposite of what `bool` does.
- **Withdraw a finding the moment you know, even if it has already
  reached a ticket.** impl-3's "one reminder listed twice" was two
  reminders made by a probe that ran twice. They had spotted the
  duplicate during cleanup and attributed it correctly, then reported
  the symptom anyway; it reached a ticket and a lead ruling before the
  withdrawal. The runbook rule for probes: when cleanup finds more
  rows than the script should have made, the probe is the suspect
  before the system is.
- **A test named more broadly than it measures, twice in one PR
  family.** #130's "no attachment response carries a path" checked the
  POST and `get_ticket`'s embed and not `GET /tickets/{id}/attachments`,
  which was `SELECT *` with no response model and still returned
  `file_path`. The replacement enumerates every attachment-bearing
  shape and asserts the enumeration is non-empty. When a test's name
  says "every" or "no", its body must derive the population, not pick
  two examples.
- **Before refusing an operation, find the test that says why it is
  allowed.** impl-3 built a refusal for "snooze resurrects a completed
  occurrence" and an existing test failed with the reason: snoozing a
  completed occurrence is the only way to undo a completion recorded by
  mistake. A behaviour that looks like a defect from a probe can be the
  escape hatch a prior decision kept on purpose; read the failing
  test's docstring before deciding the test is wrong.
- **When you scope a check by a category, the exclusion is where the
  hole is.** impl-4's first column-baseline guard covered "baseline
  tables", reasoning that columns on migration-created tables arrive
  with the table — true only of the columns a table is *created* with.
  A column added later to a migration-created table needs a migration
  just as much, and the exemption covered `ticket_attachments`, the
  table the ticket came from. Third time in one run a guard covered
  less than its name claimed (attachment responses, baseline tables,
  the list route). The exclusion is exactly what no test exercises,
  because its author wrote it believing it was safe — so the mutation
  goes *in the excluded category first*.
- **Two guards for one rule, neither aware of the other, and the second
  makes the first unobservable.** `_redact_sensitive_inputs` (name-keyed,
  inner) and `_error_detail` (drops `input` unconditionally, outer) both
  cite the same CLAUDE.md rule. Disabling the inner one entirely on
  main leaked nothing, because the outer one was there. That is why a
  test of the inner layer plus a docstring saying "this becomes the 422
  body" produced a confident false breach: the code and its test agreed
  with each other, and neither was measured against what ships. When
  you find a guard, look for its twin before deciding what it protects.
- **A rewritten SHA is merged on patch identity, not on the approval's
  SHA.** #133's retarget rewrote the reviewed commit; the gate compares
  the two patches modulo hunk headers before it runs, and merges only
  on "identical". Anything else is a re-review. And a matching diffstat
  is not a matching diff: #133's `api/main.py | 64 +++-` read the same
  on both SHAs with different content (the rebase had picked up #128's
  line). The hash comparison took two seconds and was the only thing
  that settled it. **And the mirror (review-1, #151): a differing patch
  is not a differing change.** A rebase makes four source patches
  *look* changed through hunk headers and context while the
  added/removed lines are identical. A reviewer who learns only the
  first lesson over-trusts a clean range-diff; one who learns only the
  second over-trusts a dirty one. Same remedy both ways — compare
  content, never its presentation.
- **A generated inventory can inflate itself, and that is worse than
  being incomplete.** #131's cross-checks disagreed on their first run,
  70 against 64: `api/main.py` exposes the app, whose route table
  carries FastAPI's `/docs`, `/redoc`, `/openapi.json` and
  `/docs/oauth2-redirect` — four routes nobody wrote, rendered as six
  rows under `main.py` against two real ones, every one plausible to a
  reader who doesn't know the framework's defaults. Second defect the
  document produced about itself. Filter to endpoints declared in the
  repo; and when two derivations of "the same thing" disagree, the
  generator is the suspect before the check is.
- **Compare things meant to be identical, not the sizes of things that
  merely correlate.** review-1's count form of the route cross-check
  failed (70 rendered vs 74 decorators, because the generator dedupes);
  the set form (decorators from the AST vs rendered paths) agreed
  exactly with nothing tuned. The floors lesson one level up.
- **"The check read through the distinction it existed to make" —
  third time.** impl-3's `update_board` test asserted `"title"` appeared
  in the refusal; both the unclearable refusal *and* the empty-update
  refusal contain it, so dropping `apply_clear` survived. Earlier the
  same day: a camelCase probe over snake_case fields, and a fixture
  whose two rules matched the same row. Before asserting a substring,
  ask which *other* message on this path also contains it; assert the
  distinguishing phrase and the absence of the other.
- **400 or 422: a reference to something absent, or a value outside its
  permitted set.** impl-3's form of D17: a 400 is a *reference* — an id
  or path naming something that is not there; a 422 is a *value* judged
  against a set the request itself defines. It predicts the enums,
  `period`'s pattern and `due_date` correctly. **It is a heuristic, not
  a law** (review-2, #136, measured through the real app): a 400 can
  name a permitted set (`/documents/extract` names its three
  directories), a 400 can have no referent at all (`/trend` with
  neither id), a 422 can sit over a non-enumerable set (snooze to the
  same day), and six `InvalidReferenceError` sites are value or state
  refusals. So "can the refusal list the permitted values?" is a good
  first question and not the rule; the rule is D17's two sentences, and
  the shape of the message follows the case. An earlier version of this
  bullet stated the universal form; it was wrong.
- **Before a migration ships, run it against the live database's
  shape — not its schema.sql — and read what is pending there.** The
  live DB is stamped to 6 with 0007 unapplied, and it has the
  post-rename column set; a 0008 written against the pre-rename shape
  fails at prepare time and the startup runner is fatal by design. The
  API would have refused to start over its existing rows. impl-4 measured it
  with a read-only copy before building. Rule: a migration PR's body
  carries the live `schema_migrations` state and `PRAGMA table_info`
  of every table it touches, taken from a `mode=ro` connection, and
  the migration is applied to a `.backup()` copy before the PR opens.
  "It applies to a fresh DB" is not the question; "it applies to
  *the owner's* DB" is.
- **A new mechanism is invisible to every guard built for the old
  one.** Teaching the migration runner Python would have been contained
  and correct, and every migration guard in the repo parses SQL — so
  the first `.py` migration would have been the exclusion where the
  hole is. When a fix needs a new *class* of thing, list the guards
  that would not see it before deciding; usually that list is the
  argument against.
- **A window that opens mid-period and groups by period mislabels its
  first bucket.** `trend` used `date('now','-N months')` then grouped
  by month, so the leading month was partial and labelled whole, and
  the same calendar month read 3.5× differently depending on N. Any
  time-bucketed query opens its window on a bucket boundary, and its
  test runs with the clock at the 3rd and the 28th against the same
  rows.
- **An empty page is not an error message.** Seven of twelve
  id-filtered reads answer a ghost id with `{"items": [], "total": 0}`
  — a confident "there are none" indistinguishable from the true
  answer — while five siblings refuse. Readers refuse what writers
  refuse, by the same 400/422 test; a read surface that accepts an
  input its writer rejects will be believed.
- **Deriving a model's fields answers what the model exposes, not what
  the endpoint returns.** review-1 approved #130 having derived
  `AttachmentResponse`'s fields from the AST and checked the content
  route — and never asked *which routes return attachment shapes*. The
  list route had no `response_model` and bypassed the model entirely.
  The question for a response-shape claim is "which endpoints produce
  this shape", answered from the router, and each is asserted
  non-empty before it is checked.
- **The literal text of a message is not evidence about what it
  splices.** #142's redaction pin failed on its first run against
  correct code: it substring-searched the f-string for `"value"`, and
  the message read "The value is deliberately not quoted here." Read
  interpolated *expressions*, not the string. Same distinction as
  `input` vs `msg`, one level down.
- **A false claim in a code comment is where a belief gets acquired.**
  impl-1's retracted breach traced to a pre-existing comment in
  `api/models.py` saying the error list "becomes the 422 body — which
  reaches the MCP client". They read it, measured the layer it
  described, and escalated on a claim nobody had checked against what
  ships; the comment is why two people could agree. When a comment
  asserts what happens downstream, treat it as a claim to measure, not
  context to inherit.
- **A comment in the past tense four lines above the line that still
  does it.** #135's table comment said the old test "could not tell an
  explicit False from a missing annotation" — and the test below it
  still read both hints through `bool(...)`. Same family as the
  future-tense trap: name the state ("compares with `is`; `None` means
  unannotated"), and put the assertion that proves it beside the
  sentence.
- **Don't reimplement the thing under test to measure it.** Two people
  an hour apart applied migration 0007 to a backup copy with an ad-hoc
  `split(';')` and got a bogus syntax error from the comment block;
  the runner's own `_statements` gave two clean statements. Measure
  through the code path that will run in production — import it — or
  the measurement is of your splitter, not the migration.
- **A check placed only where "something is pending" misses the stuck
  case.** #144's refusal of a pre-rename database sits *before* the
  pending-migrations early return, because a database can be fully
  stamped and still stuck; guarding only the migration path would let
  exactly the case the guard exists for through. Ask what state the
  early return assumes, and whether the bad state satisfies it.
- **Reconstructing from memory, index edition.** impl-4 rewrote two of
  four `transactions` index definitions from memory in a table rebuild
  and got both wrong; the test comparing the rebuilt indexes against a
  fresh install caught it, not a reading. Same rule as retyped SHAs
  and retyped field lists: copy from the source, and derive the check.
- **A substring both refusals contain is not an assertion about which
  one fired — and two guards refusing one request for different reasons
  is the normal case here.** review-1's sharpening of impl-3's
  surviving mutation: `_refuse_unclearable` and `_require_at_least_one`
  both name the field, so `"title" in message` proves nothing. The
  trap is structural in this codebase, not a one-off. Assert the
  distinguishing phrase and the absence of the other guard's phrase.
- **"Which routes return this shape" is derived from "which functions
  read the table".** review-1's enumeration for #137: six functions
  SELECT from `ticket_attachments`; three return row shapes, three
  measured to return something else. The complete version of a
  response-shape list is not the routes you remember but the readers
  of the table, which is derivable.
- **A fixture that cannot distinguish the thing it asserts is the same
  vacuity as a corpus with no ambiguous ties.** #145's reversal
  mutation (swap `overlap_start`/`overlap_end`) caught nothing at first
  because the fixture's overlap was a single day, so start == end.
  Before trusting a mutation that survived, ask whether the fixture
  could ever have told the two apart.
- **A duplicated helper name in a test module is silently shadowed —
  third time this run.** pytest takes the later definition; eight
  unrelated tests failed with a `TypeError` that pointed nowhere, and
  the collision hid that the existing helper used a different path.
  The `--collect-only | uniq -d` check sees test ids, not helpers.
  Ticketed as a repo-wide AST guard; until it lands, grep for `def
  <name>` in the file before adding a helper.
- **The `&&` discipline does not survive a pipe.** `pytest ... | tail
  -1 && git push` pushed a branch with a failing test: a pipeline
  returns the *last* command's status, and `tail` succeeded. Same rule
  as "never pipe the gate", from the other end. Redirect to a file,
  check `$?`, grep the file for the passed line, then push.
- **Two sweeps of one surface disagreed, and the difference was
  checkable.** #142's guard matched secret-shaped *names* in the
  interpolated expression; #146's three leaking sites were named
  `value`, `exc` and `txn["description"]`, so #142 passed them by
  construction and concluded "nothing to fix" — the D119 line (a
  name-keyed deny-list cannot protect an extensible namespace) applied
  to the guard written in its wake. The replacement is an allow-list
  that forces every interpolation to be classified, keyed by *module*
  because a flat key let `value` be an id in one file and a raw string
  in another. And the strongest site echoed a value the caller never
  sent: `txn["description"]` is scrubbed bank text read back from the
  DB, so echoing it undoes the scrubber where it mattered. When a
  system already redacts a field somewhere, that field is
  secret-bearing everywhere.
- **"I patched the guard to accommodate the mechanism."** impl-4's own
  account of #143: when the column-baseline guard could not see the
  new `.py` migration, they widened the guard's glob and moved on. That
  was the mechanism failing its first contact with the safeguards,
  read as a detail to fix. Rule: when a change makes an existing guard
  need an edit *to keep passing*, stop and ask whether the guard is
  wrong or the change is; the guard usually wins, and the edit is the
  evidence.
- **A skip is not a neutral outcome for a guard — it is a green tick
  with nothing behind it.** Two independent sightings in one day: an
  empty `parametrize` SKIPs and reads as deliberate (#139, guarded by
  asserting the registry is non-empty); `_schema_at_runner_commit`
  uses `pytest.fail`, not `skip`, when git cannot resolve, with the
  reason in the message (#140). A guard that can skip can be made to
  skip; make its precondition failure a failure.
- **"Independent" overstates a check that reimplements the idea.** #131's
  route cross-check shared the generator's glob, skip rule, fallback,
  HEAD filter and module prefix; two implementations of one idea catch
  a typo in either and not an error in the idea — which is what the
  built-ins bug was, caught only because the cross-check predated the
  filter. A genuinely independent derivation reads a *different kind of
  thing*: `@router.<verb>` decorators from source syntax rather than
  imported router objects, immune to framework built-ins by
  construction. When you write a cross-check, name what it would NOT
  catch; if the answer is "the same mistakes as the original", it is a
  checksum, and label it as one. impl-1's proof, which is better than
  the argument: remove the built-ins filter from the generator *and*
  the router-walk check together — the mistake made consistently, which
  is how it actually arrived — and the decorator check goes red while
  the router walk agrees with the bug. **A second implementation of the
  same idea is a checksum, not a witness**; independence has to be
  independent of the idea, not the code. And the earlier catch was
  luck with the shape of a result: the cross-check predated the
  filter, so they briefly disagreed; a day later the same guard would
  have been silent on the same bug.
- **The evidence was on the screen with the wrong question in front of
  it.** review-1 had printed `/openapi.json`, `/docs`, `/redoc` in their
  own output while investigating the route trap and read them as
  evidence about the trap, never asking whether they belonged in the
  inventory. Output you produce for one question answers others; when
  you print a list, read it once more for the question you did not ask.
- **A check fed by the thing it checks cannot see that thing shrink.**
  #147's dropped-package check looped over `_test_packages()` and
  asserted each contributed a module — it validated whatever list it
  was handed, and truncating `testpaths` failed nothing. The
  replacement walks the repo independently, and found the worse fact
  underneath: a package dropped from `testpaths` silently stops being
  run. That walk's first run returned an empty set — it filtered
  absolute paths containing "worktrees" and the checkout itself lives
  under `.claude/worktrees/` — and only the non-empty assertion caught
  it. Third time in a day a guard was saved by its own vacuity check.
- **A method can be structurally unable to produce a finding.** impl-1
  classified interpolations by "is this field secret-bearing?", which
  assumes the value is the caller's own; `txn["description"]` is
  scrubbed bank text read back from the DB, so the question never
  reached it. When a sweep's classification rests on an assumption
  about where values come from, list the sites where that assumption
  is false before trusting "nothing to fix".
- **Do not pin behaviour the API does not have because the brief said
  so.** The lead's brief for #148 asked for "the apportioned total";
  the API reports a shared policy at full value per entity with
  `shared_with`, and apportioning is an open decision for the owner (D66).
  impl-4 asserted the real sum plus the two single-leg totals it must
  not equal. A test written to the brief instead of the code would
  have been red, or worse, would have driven a "fix" of behaviour that
  was decided on purpose.
- **A third-party exception is untrusted text for redaction purposes.**
  dateutil quotes the caller's RRULE fragment in its own message, so
  `f"invalid rule: {exc}"` echoes input at one remove. Interpolating an
  exception is interpolating whatever the library chose to quote; name
  the field and the expected format instead.
- **A conditional counted as unconditional, second time.** #143's
  `_tables_created_by` would have promised a table a conditional
  migration might not create; #140's column guard, built after it,
  counts `CREATE TABLE IF NOT EXISTS` as supplying a column — a no-op on
  the existing database, silently green under simulation. Versioned
  run-once migrations must not carry conditional DDL; the guard refuses
  it rather than reasoning about it.
- **Mutating against the wrong test file reads as uncovered.** review-1
  mutated #144's ROLLBACK fix and ran `test_migrations.py`: 49 passed,
  which would have been reported as "nothing covers this". The tests
  live in `test_migration_error_surfacing.py`. Run the mutation against
  the whole suite, or first find the test that names the behaviour and
  run that file *and* the suite.
- **"Handled by X" is what stops the next person checking X.** #144's
  docstring said the neither-column case was handled by the
  `EXPECTED_TABLES` check; that check compares table names and the
  table is present. If the honest answer is "out of scope", say that —
  it is stronger than naming a check that does not cover it.
- **A regression test's rows go where the OLD behaviour differs.**
  #149's 3rd-vs-28th test had to place rows in the month the old
  day-precision cutoff truncated (N back from the anchor), not the
  fixed version's leading bucket; two drafts landed the cutoff in an
  empty month and were green against the bug. Before writing the
  fixture, name the exact rows on which old and new disagree, and put
  those rows in.
- **An injected clock is proven to reach the query by anchoring in a
  different year.** Replacing `_now_anchor()` with a hardcoded `'now'`
  passed #149's whole test file, because the real clock shared a month
  with every anchor the tests chose — they would have started failing
  in a later month for a reason no message would name. One test now
  anchors in another year, so the real clock cannot produce its
  answer. Any test that freezes time needs one case the real time
  cannot satisfy.
- **Commit immediately before each mutation run, not before the
  batch.** `git checkout -- file` after a mutation discarded an
  uncommitted change made after the wip commit; the suite then showed
  two failures briefly mistaken for a regression. Second time in a day
  for the same person. Restore by `git checkout` only what the last
  commit contains — which means the last commit must contain
  everything you meant to keep.
- **The criticism you level at another guard applies to your own
  selector one level up.** #146's walk decided which raises to inspect
  from a curated list of error class names; it missed five classes
  raised with an f-string, including `UnscrubbedDigitsError`, so the
  sweep never looked at `redaction.py` — while its author was
  (correctly) faulting #142 for a name-keyed list. Fixed by putting
  every `raise <anything>(f"...")` in scope, eleven more rows
  classified. Any time a guard *selects what to look at* by a list,
  ask what an unlisted case would look like, and whether the guard
  would report it or simply not see it. impl-1's sharpening: **a
  narrowed classifier lies; a narrowed selector is silent.** #142
  produced a wrong verdict on sites it examined, checkable by anyone
  who looked; #146 produced no row at all for `redaction.py`, which
  reads identically to a clean file. And neither author could see it
  from inside their own sweep — each found the other's. So the lesson
  from two sweeps of one surface is *not* "don't duplicate": the
  collision is what surfaced both holes, and suppressing the
  duplication next time suppresses the detection with it. When two
  people independently sweep the same thing, compare the sweeps
  before closing either.
- **A warning can be true and inert.** #144's exemption note explained
  the constraint accurately and still skimmed as TODO; the rewrite
  addresses the reader ("IF YOU ARE ABOUT TO WRITE 0008: it was
  written, and measured…"), then the measurement, then the consequence,
  then forecloses the next idea. A warning attached to an exemption has
  one job — stop someone acting in good faith — and its test is not
  accuracy but whether it survives a skim by a reader who has half
  decided.
- **A reviewer grepping for the test name they remember gets a
  clean-looking miss when the comparison has moved.** review-1 looked
  for `test_exactly_the_expected_tools_are_registered` in #135's
  failures, did not see it, and began writing "still doesn't catch it";
  the comparison had moved into
  `test_every_tool_carries_the_annotations_its_risk_implies`. Caught
  only because a direct probe and the test result disagreed. When two
  measurements disagree, chase it; and search for the *assertion*, not
  the name.
- **A mutation result is only evidence once the mutation is proven to
  have landed.** Four attempts to land one status mutation on #127 —
  regex missed, a reference not a literal, two arguments into
  `frozenset()` — each read `13 passed` and each would have been
  published as "the pin does not fire"; every one was caught by the
  post-condition and none by the test result. The apply-assertion is
  not tidiness; it is the difference between a measurement and a
  guess.
- **When a hold-fix grows into behaviour, say "behaviour".** #144's
  one-sentence hold came back as a new refusal branch with 80 lines of
  tests — the right call, and a re-review, not a range-diff merge. The
  gate refused on HEAD MOVED, as designed; the push message is where
  the author says which kind of change it is.
- **A repro that goes red for an unrelated reason looks identical to a
  guard working.** A ticket's one-line `CREATE TABLE IF NOT EXISTS`
  repro went red because the block regex wants the closing paren on
  its own line — it was never parsed at all — and impl-4 nearly
  reported "cannot reproduce". The multi-line form, which is what real
  migrations look like, reproduced the hole exactly. When a repro
  fails, read *why* it failed before crediting the guard.
- **"Refuse outright" met two shipped migrations that already do it.**
  0001 needs the conditional form structurally (the runner creates
  `schema_migrations` before applying anything) and 0006 has shipped.
  Frozen exemptions with a size test, and the narrowing flagged rather
  than buried. A rule stated as absolute is checked against the
  existing tree before it is enforced; the exceptions it finds are
  either evidence against the rule or a frozen list with reasons.
- **The ticket's premise about which pattern 0008 used was wrong.**
  Measured against the closed branch, 0008 renamed the old table aside
  and created the real name — the order the guard reads fine. The
  ticket (written by the lead from review-1's sentence) claimed the
  other order. Third ticket this run whose "what done looks like" was
  written against something not in the tree; the same rule as
  the `delete_board` ticket — open the thing before naming it.
- **Agreement between two things you built is not evidence;
  disagreement with something you didn't is.** review-1's rule after
  three sightings in one evening: #131 (a checksum agreeing with the
  generator it copied), #135 (a table agreeing with the code about the
  opposite of what ships), #146 (a sweep reporting "nothing to fix"
  beside a file it never selected). Each time the check and the thing
  checked shared an assumption, and each was caught by a measurement
  from outside the pair — a real request, a direct probe, a different
  derivation. When a check passes, name the thing it does not share
  with its subject; if there is nothing, it is not a check.
- **Contingent safety is written down as contingent.** `main.py:name`
  is a safe interpolation because `__getattr__` is reached only from
  code asking for a fixed attribute, never caller input — a property
  of today's callers, not of the code. Same family as `edited_at`'s
  single-writer premise. A classification that rests on a contingency
  says so where the classification is, so a future dynamic dispatch is
  noticed rather than inheriting "safe".
- **Comments come first, second sighting.** review-1's day-precision
  apply-assertion matched `'start of month'` in the comment four lines
  above the SQL and reported `120 passed` as "the window is untested".
  The lesson from the morning had not stuck; what saved it both times
  was asserting on the mutated *file*, not trusting the diff. The
  working form asserts about the line being mutated (contains both
  `start of month` and `date(`), never about the string alone.
- **Three confirmations that a shortcut is safe is how a shortcut stops
  being checked.** review-1 had examined three runbook conflicts, found
  each safely resolvable toward `main`, and said so; the fourth (#144's
  decisions-log) carried 66 lines `main` did not have, and `--ours`
  would have dropped them silently. Every conflict is diffed both ways
  before a side is chosen; the previous three being append collisions
  is not evidence about this one. The concrete trap, from impl-4's
  first attempt at the union: during a *rebase*, `--theirs` is the
  commit being applied — your own side — so "take theirs and append
  mine" took their own file and dropped main's entry while duplicating
  theirs. `git diff --numstat main -- <file>` showed 35 removed lines;
  without that check it would have pushed as a clean-looking append.
  After any conflict in an append-only file the diff against main must
  show zero removed lines. **And the reviewer-side mirror (review-1,
  #145): a union that only appends is a resolution that silently
  reverts edits.** #145 modified a test that also exists on main;
  appending only the *new* defs kept main's pre-change body and failed
  one test that looked like a real regression. The rule for a
  conflicted file is union the additions *and* prefer the PR's version
  of anything it edited — and verify by diffing the result against
  each side for exactly what that side changed, never by reading the
  merged file. That one comparison is the remedy for both traps: it
  shows an append-only union reverting the PR's edits and a `--theirs`
  resolve dropping main's, neither of which is visible in the merged
  file. And the reviewer checks one more thing on a resolution: that
  the merged bodies are byte-identical to the *reviewed* versions, not
  reconstructed — the #124 splice was a rebuild that read as a move.
- **A fixture whose values are symmetric under the bug cannot test for
  the bug.** #145's reversal mutation was invisible on every one-day
  fixture (start == end) and caught by exactly the multi-day one. Same
  family as review-2's F3 and the regression-rows rule: before trusting
  a green mutation, ask whether the fixture could ever have told the
  two apart.
- **zsh: `"$VAR:path"` triggers the `:a` modifier.** `git show
  "$B:api/tests/x.py"` in zsh expanded to `...pi/tests/x.py`, the base
  file came back empty, and a comparison went silently vacuous — three
  times for one reviewer in one day, which makes it environmental. Use
  `"${B}:api/tests/x.py"`.
- **The size of the fix decides what it needs, not the size of the
  hold.** impl-4's account of #144: a one-line hold grew into a type
  change plus 55 lines and a new test file, announced as "the docstring
  hold addressed" — and the person who grew it is least able to notice,
  because to them it is still "the docstring thing". Before pushing a
  hold-fix, diffstat it; if it is not the size of the hold, say so.
- **A test's name is not its rationale.** review-2 found
  `test_snoozing_after_completing_overwrites_the_status` has no
  docstring; the reason snooze-after-complete is the undo lives in the
  commit message that introduced it (`e2882db`). impl-3's revert was
  right and could not have been justified from the test alone. A test
  that encodes a decision carries the decision in its docstring, with
  the commit or entry it came from.
- **A pin on the constant is not a pin on what ships.** #138 pinned the
  new paging clause as a substring of `PAGING_NOTE`; a tool rendering
  the note without the clause passed, because nothing looked at a
  description. The artifact is the rendered description per tool (and
  the constant gets an exact pin, as `ATTACHMENT_CONTRACT` has). Same
  family as "the message is what the model acts on".
- **A reviewer told "same thing, rebased" reads for drift; one told
  "this is new" reads for correctness.** Different passes, and only the
  author knows which is needed. impl-4 flagging #144's third commit as
  BEHAVIOUR in the handoff changed how review-1 read it. The push
  message names the kind of change; "rebased" is a claim the reviewer
  will act on.
- **A guard earns its keep on the first unrelated PR.** #146's
  interpolation allow-list, merged hours earlier, refused #144's new
  refusal messages until someone answered "could this echo something?"
  for `AMOUNT_CENTS_CONVERSION` and `db_file` — both benign, both now
  classified with a reason. That is stronger evidence for the guard
  than any mutation run on #146 itself, and it is the composed-suite
  gate doing what a range-diff cannot.
- **"It was asserting nothing" is measured, not conceded.** impl-3
  restored the old `not getattr(..., None)` assertion *and* removed the
  annotation: 18/18 passed. When a reviewer says a test is vacuous,
  reproduce the vacuity before rewriting the test; the reproduction is
  what goes in the commit.
- **A test can survive a mutation that makes its target structurally
  unreachable, when the generic path names a list containing the values
  it asserts.** review-2's F3 on #136, as the general form: the
  ambiguity test asserted that +7 and +14 appear in the refusal; the
  generic refusal names the eight nearest occurrences, which include
  both, so deleting the entire ambiguity branch left it green. Two
  narrower rules earlier in this file (shared substrings; the
  ACME CAFE/ACME GAS fixture) are instances. Assert the phrase only the
  targeted branch produces.
- **A refactor that relocates a message re-opens its classification.**
  `_require_reference` moved from `financial.py` to `db.py`; #146's
  module-keyed allow-list reported the old rows stale and the new ones
  unclassified — the same expressions, asked about again. Nobody
  designed for that and it is right: the same name in a different
  module can mean something else.
- **Disagreeing with a ruling by naming the test it breaks is the form
  that should always win.** impl-3 overturned the lead's literal
  merchant-history 404 by showing it reddens
  `test_a_deleted_rules_history_still_reads`; review-1 endorsed the
  form, not just the outcome. A ruling is a claim about behaviour, the
  test is the measurement, and when they disagree the measurement is
  the argument.
- **A tool refusal and an operator refusal follow opposite conventions,
  and what distinguishes them is the destination, not the content.**
  The attachment refusals quote neither a path nor the digits they
  found, because they render into a model's context. The pre-rename
  startup refusal names the database path, because it fires only in
  the lifespan with no handler — its firing is precisely the condition
  under which no request is served — and the operator converting a
  database by hand needs to know which one. Both are right. The
  classification carries its contingency ("startup-only; revisit if
  ever rendered into a response") so that adding a handler meets the
  condition rather than inheriting the verdict. And keep the two guards
  straight: #146's covers *authoring* (what a message may interpolate),
  #139's covers *rendering* (`_error_detail` drops `input`); neither
  implies the other.
- **An edit that looks like housekeeping can remove the only sentence
  explaining a rule.** impl-4's #152 tidy replaced two bespoke
  allow-list reasons with house-style rows — and deleted the
  startup-vs-model audience distinction that is *why* those messages
  may carry a path at all. Reversed by its author before review, with
  the commit message recording the reversal. When a tidy removes
  prose, ask what the prose was load-bearing for; scannability is real
  but cheap.
- **A withdrawal can be right about its evidence and wrong as a general
  claim.** impl-3 withdrew "one reminder listed twice" because their
  probe had made two reminders — true — and added "nothing to test",
  which was false: a recurring reminder legitimately yields two rows at
  one date, and that was F1. Withdraw the observation, not the
  question; say what the evidence covered and what it did not.
- **Prose restating a number a test owns is a second copy waiting to
  drift.** `skill-conventions.md` said "fourteen paged tools" and had
  gone stale twice; the count lives in `PAGED_TOOL_COUNT`, which a test
  asserts, so the prose now names the examples and points at the
  constant. Numbers in runbooks are derived or absent.
- **Amending the reviewed commit hides the fix's shape.** #138's two
  hold-fixes were squashed into the approved commit, so the range-diff
  read `!` instead of `= + one commit`, and the lead had to interdiff
  the two patches to see that the delta was exactly the holds. Push
  hold-fixes as commits on top; squash is for the merge, not the
  review.
- **A fixture proves the predicate; a backup copy proves the predicate
  about this database.** #144 shipped a startup refusal that reads the
  real database; its `test_the_deployed_shape_is_not_refused` builds
  the shape from `schema.sql`, which is the right unit test and not the
  same claim — the live file holds real history no fixture
  reconstructs. review-1 ran the predicate against a `.backup()` copy
  (never the live handle): verdict `None`, would serve. **Gate step,
  adopted:** for any PR that can refuse at startup, run its predicate
  against a `.backup()` copy of the live DB before merging. The restart
  is the expensive place to discover the answer.
- **Verify the reason you are handed, not just the verdict.** review-1
  argued the startup refusal cannot reach model context because its
  exception "has no handler"; impl-4 read `api/errors.py:169` —
  `_envelope_response` matches its parent `DatabaseNotUsableError`. The
  verdict survived and got stronger (the handler substitutes a fixed
  message rather than echoing `str(exc)`, two barriers not one), but
  the *revisit trigger* changed from "someone adds a handler", which
  could never fire, to "someone makes the handler echo". A wrong reason
  under a right verdict leaves a contingency nobody can meet. And when
  the implementer writes the reasoning down, the reviewer measures the
  new factual claims rather than reading them (#152: three SQLite
  claims, all checked) and says where the text improved on the
  argument — here, that the durable barrier is the handler substituting
  a fixed message, not reachability, which is contingent; the reviewer
  had the weaker barrier doing the load-bearing work.
- **Five apply-failures in one day, all caught by the post-condition
  and none by the test result.** review-1's running tally, reported
  because it kept happening while they were actively watching for it:
  a regex miss, a reference not a literal, two arguments into
  `frozenset()`, a comment matched instead of the SQL, a dangling
  indent `ast.parse` refused — each followed by a clean green on
  unmutated code. The rule is not "be careful"; it is that the
  apply-assertion runs every time, because attention did not catch any
  of the five.
- **Write PR bodies and comments through a quoted heredoc to a file,
  never an inline string.** Shell backtick substitution silently
  removed `_error_detail` from a comment three times in one evening
  before it was noticed; `gh pr edit` is also broken on this repo (a
  Projects-classic GraphQL deprecation), so bodies go through
  `gh api -X PATCH` from a file.

## Why this instead of subagent-driven-development

`subagent-driven-development` spins a fresh subagent per task and kills it
after review — no memory of prior tasks in the same plan, no ambient
judgment building up about this codebase's conventions. A persistent team
keeps that context across tasks, at the cost of needing real git isolation
(worktrees) and real review gates (PRs) instead of an in-process SDD
ledger, since multiple teammates are now genuinely concurrent instead of
sequential.

## When to spin the ad hoc 5th

Only for a bounded, specific question that doesn't warrant occupying one
of the 3 implementation slots — e.g. "does approach A or B avoid the
SQLite locking issue," not "implement task 4." Kill it as soon as it's
answered.
