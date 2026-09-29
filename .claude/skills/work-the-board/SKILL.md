---
name: work-the-board
description: Work a selected q-factory or managed-project Jyra board — resolve its repository and instructions, claim ready work, implement in an isolated worktree, and hand back review evidence or a named blocker. Use when asked to work a project board or its ready queue.
---

# Work the board

## Never — read this before anything else

These are ordered by how hard the damage is to undo, not by how likely
you are to hit them.

**Never run this loop as a service, a daemon, a cron job, or against a
Claude API key.** `CLAUDE.md` makes this a ground rule, not a preference:
this runs on the interactive subscription, as Claude Code, with one human
present per run. The temptation is specific and will sound like
efficiency — "the queue has eleven tickets, I could just leave this
running overnight." That is the thing the rule forbids. A standing loop
on an API key is a different system with a different cost model and no
human in it, and nobody has agreed to run one.

**Process safety.** Never use pkill, killall or any other
pattern-matched kill. Stop only processes you started, by their recorded
PID or your own process group, and never touch system services or other
users' processes. Hosts such as the server are shared with production and
other agents.

**Never transition a ticket to `done`.** `review` is where your work
stops. `done` is a human's word for "I looked at this and accepted it",
and an agent moving a ticket there erases the only checkpoint between
work and merged work. It reads as progress and is the opposite: the
board now says something was reviewed that nobody read.

**Never leave a ticket in `agent_coding`.** You claimed it, so it is
invisible to the queue — no other caller will take it — and it is also
invisible to a human reading the board for things that need attention. A
ticket stalled there is the one failure nothing reports. If you stop
working on a ticket for any reason, including running out of context or
deciding it was a mistake to claim, move it: to `review` if the work
stands, to `blocked` with a note if it does not.

**Never move a ticket out of `blocked` yourself.** Blocked is deliberately
outside the claim query — `POST /tickets/claim` only ever returns
`agent_ready` — so a ticket you could not finish is not handed back to
you on the next pass. Returning it to `agent_ready` because "the blocker
might be resolved now" rebuilds the retry-forever loop the status exists
to prevent, and it does so quietly: the ticket looks like it is
progressing. A human unblocks.

**Never read an attachment by file path.** Ask for it by id with
`read_attachment`. Attachment responses do not carry a path to open
(D107), and reconstructing one from the store's layout is the shortcut
that sounds harmless — it reads the same bytes today and breaks silently
when the store moves, with the symptom appearing in whatever you built on
the contents rather than at the read. Two uploads are both called
`screenshot.png`; only the id is unambiguous.

**Never claim a second ticket while you are holding one.** The claim is
atomic so you will succeed, and then two tickets are stamped with your
actor and one of them is not being worked. Finish or hand back the one
you have first.

**Never invent the work.** If the description does not say what is
wanted, that is a `blocked` with a note naming the decision you need —
not a best guess implemented confidently. A guessed ticket costs more to
unpick than an unworked one, because someone has to read the diff to
find out it answered a different question.

## The loop

### Resolve the project before claiming

Read `runbooks/factory.md`. Keep the coordinating session in q-factory and
establish its absolute factory root. For q-factory development itself, use
the q-factory board and checkout named in `CLAUDE.md`; it is not a submodule.
For a managed project, fetch the project entities with the pagination fence
below, select by exact ID or unambiguous name, and read its
`attributes.repository_path`. Read the boards for that entity; when several
exist, use the board the user selected, never the first result.

Verify the path names the initialized submodule registered in this factory
checkout, with the expected origin. Missing registration, an uninitialized
checkout, duplicate project names/paths or unclear board selection means
report the missing choice before taking work. Never fall back to the
q-factory board or the current directory's repository. A plain non-software
project without a repository path does not become a coding project by guess.

Load the project's `AGENTS.md`/`CLAUDE.md` and the technical instructions they
reference. Shared procedures come from the explicit q-factory root; project
commands come from the project. Filesystem nesting does not distribute skills.
Use `templates/worker-handoff.md` when assigning a worker: include project,
board and ticket IDs, both roots, branch/base, instruction paths, acceptance
criteria, permitted actions and checks. Workers verify actual Git identity.

Inspect ready-ticket prerequisites before dispatch. Ticket ordering expresses
priority, not an enforced dependency graph. Do not promote prerequisite work
to accepted just because its dependent ticket is ready. If a prerequisite
becomes uncertain after claiming, hand back a named blocker.

One pass, repeated until the queue is empty. Each pass handles exactly
one ticket from claim to hand-back.

1. **Claim.** `claim_ticket(actor="<your agent name>", board_id="<selected board id>")`.
   Always supply the resolved `board_id`; an unscoped claim can take another
   project's work. It returns
   `{"claimed": true, "ticket": {...}}` when it took one, and
   `{"claimed": false, ...}` when the queue is empty.

   **An empty queue is success.** It means there is nothing to do. It is
   not a failure, not something to retry in a tight loop, and not
   something to report as a problem. Stop and say the board is drained.

   The claim moves the ticket `agent_ready` → `agent_coding` in one
   conditional write, so if a human is working the board at the same time
   only one of you gets it. You never need to check first and then claim.

2. **Read it.** `get_ticket(ticket_id)` returns the description, the
   parent, refs to child tickets, and the attachments.

   **Compare `attachment_count` against the number of attachments you
   actually received.** The list is capped; `attachment_count` is the
   true total. If it is larger, you are missing attachments — say so and
   treat it as a stop, not as a list to work from. A ticket worked
   without the attachment that mattered looks exactly like a ticket
   worked correctly.

   Read each attachment with `read_attachment(attachment_id)`, using the
   id from the ticket. Child refs carry only id, type, title and status —
   call `get_ticket` on a child when you need its description.

   **A `ToolError` from `read_attachment` is a stop-and-report on that
   attachment, never a reason to reach the file another way.** The tool
   refuses anything that is not UTF-8 text and names the media type and
   size rather than a path — deliberately, because a path in an error is
   still a path in a response. The temptation at that moment is specific:
   you have an id, you know the store is on disk, and finding the bytes
   yourself looks like resourcefulness. It is the same shortcut the NEVER
   list above forbids, arriving in the one situation that makes it feel
   justified. Say the attachment could not be read, say what the refusal
   said, and work the ticket without it or block it.

3. **Do the work**, following whatever the repo's own conventions
   require for that kind of change. Nothing about being an agent
   loosens them.

   For a managed project, use a named task branch and isolated worktree:

   ```sh
   python -m q_factory --root /absolute/factory worktree start \
     --project PROJECT_ID --board BOARD_ID --ticket TICKET_ID \
     --task TASK_SLUG --base BASE_COMMIT --owner WORKER_NAME
   ```

   For a ticket on an initiative board (a board whose entity isn't the
   repository's project, such as an initiative's board on q-core), pass
   `--ticket-board BOARD_ID` instead of `--board`; see "Initiative boards" in
   `runbooks/factory.md`.

   Run from the factory's Python environment. The helper checks the ticket
   belongs to this board and project before touching Git. It records the
   owner, ticket and base, and resumes an identical existing checkout;
   mismatched ownership is a refusal. Keep the submodule checkout stable.
   q-factory's own implementation uses its normal task worktrees too.

   Implement against the ticket's acceptance criteria and run the project's
   checks in that task checkout. Do not restart q-core because a managed
   project's code changed. A shared factory improvement is a separate
   q-factory ticket and PR.

4. **Validate before the PR.** Passing tests are not validation. Exercise
   the change the way it will actually be used, with every tool available:

   - run the app, CLI or server. Anything that creates or changes data uses
     isolated fixtures. Start it with the project's own launch skill where it
     has one, otherwise the `run` skill. Where the real environment is shared
     (a tmux server, a host), use fixtures you name and own, touch nothing
     else, and remove them afterwards;
   - drive UIs with the browser, Playwright or chrome-devtools MCPs;
   - call APIs and MCP tools end to end;
   - exercise concurrency and failure paths where the change touches them.

   Read-only checks against a live service are allowed where the ticket or
   the session's authorization calls for them; never read, print or store
   private data. Write to a live service only through the ticket's own
   authorized paths (such as its Jyra transitions), never as test data.

   For a documentation or skill change, follow the new instructions once as
   written, and confirm every file, skill, command, link and ID they cite.

   Record each command or action and what you observed, plus anything you
   couldn't check and why: a platform you don't have, a service you must not
   touch. Where you can approximate a missing platform, do so and say how.
   Then open the PR in the project's repository.

5. **Hand it back.** `transition_ticket` with `to_status`, `actor` and a
   `note`. The note is required in content, not merely in presence: an
   empty string is refused, because a history row that explains nothing
   satisfies the rule and defeats it.

   - **`review`** when the work stands. The note says what you did and
     what a reviewer should look at first. Include repository identity,
     branch/worktree, PR URL, exact commit, checks and results, acceptance
     evidence and limitations. List the step 4 validation: each command or
     action and what was observed, and what couldn't be checked and why.
     "Tests pass" alone isn't a handoff. Explain whether project merge and
     the separate q-factory pointer update are pending; a PR being open is
     not integration.
   - **`blocked`** when it does not. The note names **the decision you
     need**, not that you are stuck. "Blocked" with no named decision
     moves the ticket out of the queue and gives the human nothing to act
     on, which is the same stall as leaving it in `agent_coding` with
     extra steps.

   Retain the worktree while someone uses it or review is pending. Resume by
   reading ticket history, PR state and the ownership record, not from a
   remembered branch name. Cleanup requires the owner to be inactive and
   commits contained in the explicit accepted revision; the helper retains
   the branch and refuses local files. It does not itself attest that a PR
   was reviewed or that a revision was accepted remotely.

### Integration and authority

Project merge/push and q-factory submodule pointer changes are separate
operations. The project change is reviewed; the pointer PR is exempt from code
review and passes the mechanical gate in `runbooks/factory.md` instead. Record
evidence for each. Never pin
an unpublished local commit or update every project to its latest remote.
Human acceptance and unblocking remain the defaults above. Explicit authority
already given in the current session takes precedence; do not ask again for
an already authorized operation. A historical autonomous run grants nothing
to this session. Nothing here authorizes a deployment or standing worker.

`to_status` is one of `backlog`, `in_progress`, `agent_ready`,
`agent_coding`, `review`, `blocked`, `done` — and of those you write only
`review` and `blocked`, per the NEVER list above.

## Reading the history before you redo someone's work

A ticket that reaches `agent_ready` may have been worked before — claimed,
blocked, unblocked by a human, and put back. `get_ticket_history` tells
you that, and it is worth one call before you start on anything whose
description mentions a prior attempt or a reversal. Redoing work that was
already rejected is expensive in the one way the board cannot show you:
the diff looks like progress.

**`get_ticket_history` is paginated and is not named `list_*`.** Neither
are `spending_summary` and `trend`. That matters here because the habit
"drain the ones called `list_`" reads as the whole rule and is not — a
long-lived ticket easily exceeds the default `limit=50`, and the oldest
transitions are the ones that say why it was blocked the first time.
Drain it with the fence below, exactly as you would `list_tickets` when
asked to survey the board rather than work a single ticket.

## Reading lists

Fourteen tools are paginated and each defaults to `limit=50`, so one call
is not the whole set. When you page a list, drain it:

```python
def fetch_all(list_tool, **kwargs):
    items, offset = [], 0
    while True:
        page = list_tool(limit=200, offset=offset, **kwargs)
        if not page["items"]:
            return items          # empty page: stop, never spin
        items += page["items"]
        if len(items) >= page["total"]:
            return items
        offset += len(page["items"])
```

**The empty-page guard is load-bearing, not defensive habit.** `total` is
counted in a separate query from the page, so a row deleted between the
two leaves `total` permanently above what any offset can return. Without
the guard the loop advances by zero and spins forever — an unattended run
hanging silently rather than failing.

Prefer `all=true` where the tool offers it. It returns the complete set
or refuses; it never returns a partial one. **A refusal is a STOP, not a
retry** — read as transient and retried it fails identically, making the
tool look flaky rather than the query look too broad.

## Why attachments are read by id and not by path

The original design for this skill said to "read the ticket description
and its attachments' absolute paths", and `get_ticket` used to return an
absolute `file_path` for each attachment, meant to be opened straight off
disk.

That changed (D107). A path in a response is an instruction to read a
file the API has not checked you should read, and it makes the attachment
store's on-disk layout part of the public contract — so it cannot be
reorganised without breaking callers who never asked for the guarantee.
Reading by id keeps one gate: the API decides what you get, and a caller
who cannot read the ticket cannot read its attachments by guessing at
filenames.

The practical tell that the old shape was wrong: two uploads are both
called `screenshot.png`, and the store disambiguates them by id
internally. A caller holding a path was already relying on a detail the
store considered its own.

## This is a Claude Code skill, not a runtime

Nothing here polls on a timer or runs unattended. A pass happens because
a human asked for one, in an interactive session, on the subscription. If
you find yourself wanting a loop that keeps claiming after the human
stops watching, that is the ground rule in `CLAUDE.md` — a Claude API key
is for deliberate one-off batch jobs, not for a standing service, and
this skill is not one of those jobs.
