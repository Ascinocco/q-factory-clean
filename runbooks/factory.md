# Software factory

q-factory is the coordinating home for independent software repositories at
`projects/<slug>`. Each is a Git submodule with its own history, PRs and
releases. Keep the root session in q-factory; execute task work in isolated
project worktrees under `.worktrees/<project>/<task>/`.

## Route the request and resolve the project

- Operating q-core (personal services) uses its MCP tools and the domain skills
  from the q-core plugin; that is not factory work.
- Building q-factory itself uses this repository's board, engineering checks and
  architecture decisions in [decisions-log.md](decisions-log.md).
- Building a managed project uses its project entity, associated board,
  checkout and technical instructions. Do not substitute the q-factory board
  when a project has no board or the target is ambiguous: establish the
  missing association before claiming its work.

The project entity's `repository_path` identifies its checkout relative to
the q-factory root. Git owns repository URLs (`.gitmodules`) and recorded commits
(gitlinks); Jyra owns backlog status and board relationships. The target
repository owns setup, architecture, test/build commands and deployment
instructions. Shared factory procedures live in q-factory. Avoid duplicate
registries of these facts.

Registered projects: `projects/chadmux` and `projects/q-core` (added
2026-09-25 so q-core is worked from here after the split). In this copy
`.gitmodules` records their URLs but no gitlinks are committed; see
`projects/README.md`. q-factory itself is the root checkout, not a submodule: `status`
reports its entity (`projects/q-factory`, the earlier registration) as
unmatched, and its own tickets use the root worktree flow and
`reconcile --self`.

**Initiative boards.** Some work is tracked on its own entity and board but
has no repository (an initiative entity with its own board). Their code lives in a managed project's repository, and each
ticket names it (for example `projects/q-core`). Resolve the project from the
ticket, never from the initiative entity, which has no `repository_path`.
Start the task checkout with `worktree start --project <that project>
--ticket-board <initiative board>` in place of `--board`. Don't fall back to a
plain `git worktree add`: it skips the ownership record and its ticket check. The helper
checks that the ticket is on that board and records the project, the ticket's
board and that board's entity. PRs, review and merge follow the project's rules.

Before editing, confirm the resolved checkout is the expected Git submodule,
inspect its status, and read its `AGENTS.md`, `CLAUDE.md` and applicable skills.
An absent or uninitialized checkout must be set up before execution; never
silently fall back to editing q-factory. Keep unrelated dirty work intact.

For onboarding an existing or requested new repository, use the complete
[project-onboarding skill](../.claude/skills/project-onboarding/SKILL.md). It
includes empty-remote initialization and recovery across Git and Jyra.

## Define work and choose execution

The coordinator turns the requested outcome into tickets with acceptance
criteria, scope, dependencies and a validation plan. Link work to its project
board. Separate changes to the factory itself onto the q-factory board. Read
existing tickets and decisions before creating duplicates.

Use a single implementer for a small or tightly coupled change. When parallel
agent work is authorized and useful, assign nonoverlapping files or independent
repositories, retain an explicit integration order, and reuse workers where
practical. The coordinator owns sequencing and integration; each implementer
owns one claimed ticket and worktree at a time; a reviewer assesses the actual
change and its evidence. See [team-workflow.md](team-workflow.md) for collision,
review and composed-test lessons.

For a team build, the root session acts as **team lead** with the
`strategize-teammates` skill: it sizes a team of **2–4 implementation and 1–2
review-lead teammates** (full Opus 5.5 sessions in tmux panes, long-lived
across tasks), coordinates and verifies, gates review content, and never
implements. Review leads use the `review-lead` skill; implementers use
`work-the-board` and `review-response`.

Authorization comes from the current session. Historical autonomous runs do
not grant permission to merge, deploy, accept tickets or spawn a team in a new
session. Apply the user's existing authorization without repeatedly asking.
The ordinary `work-the-board` skill hands back to `review` or `blocked`;
broader completion authority must come from the current user request.

## Start and hand off a task

Use the full [.claude/skills/work-the-board/SKILL.md](../.claude/skills/work-the-board/SKILL.md)
for claiming and handback. Claims, status history and attachments go through
MCP; never read the live database or attachment storage directly.

A submodule can be detached at its recorded commit. Select an explicit task
base and create a named branch in a task worktree belonging to that project's
repository. Do not switch branches in the shared submodule checkout to give a
worker somewhere to work. One task has one branch, worktree and PR.

Use the [project guidance templates](../templates/README.md) when adopting a
project, preserving existing instructions. Fill the
[worker handoff template](../templates/worker-handoff.md) for each assignment.

Every worker brief must include:

- Absolute q-factory root, target repository and assigned task worktree paths.
- Project entity, board and ticket IDs; requested outcome and acceptance criteria.
- Exact task base, branch, owned files and prerequisites.
- Shared factory instructions and the project's instructions to read in full.
- Required checks, review handoff and the current limits of authorization.

Workers verify their actual working directory, Git root and branch before
writing. A harness can inherit another worker's directory. Treat a mismatched
checkout as read-only and use the assigned worktree explicitly. MCP tools and
directory nesting do not distribute skills or guarantee inherited context.

## Observe and debug

Instrument project software with OpenTelemetry and send it to the shared
stack on the server. Query it while debugging (traces, logs, metrics) before
guessing. See [observability.md](observability.md) and the
project template's "Observability" section.

## Verify, review and integrate

Run the target project's documented checks appropriate to the change. Use
isolated fixtures for stateful tests. Record commands, results and material
limitations, and ensure tests exercise the failure being fixed rather than
merely repeating implementation details. A successful command is not proof
that a report's evaluation passed: inspect the result.

Tests are not the whole check. Before opening a PR, the implementer exercises
the change the way it will be used, with the tools available: the app, CLI or
server on isolated fixture data (the project's launch skill, otherwise the
`run` skill), UIs through the browser, Playwright or chrome-devtools MCPs, APIs
and MCP tools end to end, and concurrency and failure paths where relevant.
Runs that create or change data use isolated fixtures; in a shared
environment, fixtures you own, removed afterwards. Read-only live checks are
allowed where the ticket or session authorizes them, never reading, printing
or storing private data. Live writes go only through the ticket's own
authorized paths, never as test data. The handoff and the Jyra `review`
note list each command or action and what was observed, plus anything that
couldn't be checked and why; "tests pass" alone isn't a handoff. The procedure
is step 4 of the `work-the-board` skill.

Push the project branch and open its PR in the project's repository. Review
uses [the seven-lens protocol](code-review-protocol.md) and the
`code-review` skill; feedback uses `review-response`. Include canonical
`Jyra-Ticket: UUID` references in the PR body and relevant commit trailers.
Reconcile the linked PR set through `factory-reconcile` after workflow events
and on session resume. Review must identify the commit examined and resolve
findings. If code changes after
review, identify the new commit and obtain the needed re-review. Before an
authorized merge, validate the proposed change composed with the current base,
including checks for interacting changes. Record the PR and evidence on the
ticket. Do not equate a PR's existence with acceptance.

**Every managed project merges this way; there are no exceptions by project**
(the owner's decision). chadmux follows it exactly as q-core does:
- merge only a head that carries a valid approved review stamp;
- check that the merge tree equals that head;
- pin through a separate pointer PR, which is **exempt from code review** (below).

A session's authority to do the work or to deploy doesn't cover skipping
review. An unreviewed merge needs the owner's explicit say-so for that specific
change, recorded on its ticket. This was written down after several
project PRs and their pin PRs were found merged without review
(q-factory #7, correction comment). The owner accepted those merges as they are,
with no retroactive review.

Follow the [integration procedure](factory-integration.md) for the explicit `pin`
command, exact commit evidence, clean-clone proof and concurrent-update recovery.
After the project change lands, update the q-factory submodule pointer as a
separate parent-repository change. Select the accepted commit and verify it is
available from the project's remote so a fresh clone can retrieve it. Review
the parent diff: it should contain only intended project registration or
pointer changes, not project source files or unrelated pins. A pointer update
is not a project deployment. Deployment follows the project's instructions and
current authorization; managed-project work never implies a q-core restart.

**Pointer PRs are exempt from code review** (the owner's decision, 2026-09-26). A
pointer PR only records a commit that was already reviewed, or explicitly
fast-tracked, in its own repository, so reviewing it again finds nothing. Don't
queue it for `code-review` or a review lead, and don't wait for a stamp. The
gate is mechanical instead. The PR author merges it once all of these hold:
- the diff changes only `projects/<name>` gitlinks: no other files, and no
  gitlink change hidden in a merge commit;
- `q_factory pin` staged it with `remote_verified: true`, so the new commit is
  on the project's remote and descends from `--expected-old`;
- every commit it brings in reached the project's `main` under the rules above
  (stamped, or fast-tracked by the owner for that change);
- a clean-clone check shows the initialized submodule `HEAD` equals the gitlink.

If any of those fails, stop and fix it or ask the owner. Don't fall back to a review.

## Recover and finish

On interruption, record what exists, its branch/PR and the remaining decision
or work; hand the claimed ticket to `review` or `blocked` rather than leaving
it in `agent_coding`. Inspect existing work and history before resuming.

Remove a worktree only after its owner and any other occupants are clear,
its changes and untracked files have been checked, and work is preserved.
Do not force-remove a dirty worktree or reset someone else's checkout. A
project and parent pointer can be at different stages after interruption:
inspect both repositories and remote availability before continuing.

Completion evidence includes the accepted project commit, PR/review, relevant
check results, and any corresponding q-factory pointer update. Transition status
according to the current session's authority; do not invent human acceptance.

## Current capabilities and boundaries

Git supplies submodules and worktrees. Jyra supplies project-associated boards,
tickets, claim concurrency and transition history. This guide supplies the
shared procedure; it does not introduce a background dispatcher. Consult shipped
skill files and command help before invoking helpers.

Review-protocol provenance and adoption are tracked in Jyra.

The current procedure is [the review protocol](code-review-protocol.md), with
the `code-review`, `review-response` and `factory-reconcile` skills. It requires
ticket-level evidence and a separate integrated-product review before epic
completion. Review, merge, accepted project pointer and ticket completion are
distinct events; reconciliation does not infer acceptance from a commit mention.

Financial intake, privacy extraction, database backup and service
procedures belong to q-core and its data. Read the applicable domain
skill before touching those workflows. Tests of a managed project neither
authorize live ledger changes nor require private q-core documents. General
secret handling and the prohibition on exposing private documents still apply.

For native iOS project builds, paired-device installation and Simulator testing,
read [local iOS development](ios-development.md), then the target project’s adapter.
