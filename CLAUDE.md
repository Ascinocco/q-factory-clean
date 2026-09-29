# q-factory

**q-factory** is the software factory: the coordinating home for independent
software repositories checked out as Git submodules at `projects/<slug>`, plus
the procedures, skills and CLI that build them. It was split from an
earlier repository with history preserved. Personal services (API, MCP, database, financial pipeline, Jyra's
data, Whisper) live in **q-core**; life-admin skills reach every machine as the
q-core Claude Code plugin, not from here.

Two modes of work happen here, and it matters which one a request implies:

- **Building a managed project** — work on a repository at `projects/<slug>`
  (Chadmux, q-core, ...). Start with `runbooks/factory.md`, resolve
  its project entity and Jyra board, and read the project's own instructions
  before editing. Keep the coordinating session here; give workers explicit
  factory and project context. Project work does not authorize q-core
  financial writes or service restarts.
- **Building q-factory** — the CLI in `q_factory/`, the skills, runbooks and
  templates. Normal engineering practice; check `runbooks/decisions-log.md`
  before re-litigating a decision.

## Orientation

- `runbooks/INDEX.md` — index of the factory runbooks.
- **The q-factory development backlog is a Jyra board** reached over the q-core
  MCP tools — board `00000000-0000-4000-8000-000000000002` on the `project`
  entity `q-factory` (`00000000-0000-4000-8000-000000000001`). Read it with
  `get_board` / `list_tickets`; file findings with `create_ticket`; move status
  only with `transition_ticket`, whose note must say why. Managed projects use
  their own project-associated boards; do not default their tickets here.
- `q_factory/` — the on-demand factory CLI (`python -m q_factory ...`,
  `python -m q_factory.reconcile`, `python -m q_factory.review_runner`). It
  talks to q-core only over HTTP; see `docs/factory-cli.md`.
- `q-factory.toml` — committed, secret-free configuration: the q-core API
  origin and this repository's own Jyra identity (`reconcile --self`). The
  token comes from `Q_CORE_API_TOKEN` in the
  environment or the untracked root `.env`.
- `contracts/q-core-factory-contract.json` — the q-core surface (ticket
  statuses, MCP tools) the skills depend on; `tests/test_q_core_contract.py`
  pins the skills against it. Copy it from q-core when q-core changes it.
- `.claude/skills/` — factory skills (strategize-teammates, review-lead,
  work-the-board, project-onboarding, code-review, review-response,
  factory-reconcile). They load when a session
  is opened in this repository.
- `projects/` — managed-project submodules; this repository records their URLs
  and pinned commits.
- `.worktrees/<project>/<task>/` — ignored task checkouts, one worker each.
- `templates/` — project guidance and the worker handoff.
- `.claude/settings.json` + `scripts/session-sync.sh` — at every session start,
  this checkout fast-forwards `main` from origin, or skips with one line saying
  why (another branch, uncommitted changes, offline, local commits). It never
  merges, rebases, stashes or touches `projects/`, and it always exits 0. Keep
  the main clone on `main` and clean so it stays current on every machine.
- `scripts/claude-tmux.sh` — the one definition of a Claude tmux session, used
  by terminals and by Chadmux over SSH; `scripts/install-claude-tmux.sh` links
  `~/.claude/scripts/claude-tmux.sh` to this clone (runbooks/claude-tmux.md).

## Managed-project onboarding

“Bring this repository into the factory”, “register a project” or an authorized
new project request → read `.claude/skills/project-onboarding/SKILL.md`.

## Team builds

Build a set of tickets, an epic or a board queue with a team →
`.claude/skills/strategize-teammates/SKILL.md`: the root session is the team
lead (2–4 implementers + 1–2 review leads, Opus 5.5 teammates in tmux panes),
coordinating and verifying but never implementing. Review teammates →
`.claude/skills/review-lead/SKILL.md`.

Coordinating the team leads in this machine's tmux sessions →
`.claude/skills/coordinate-leads/SKILL.md`. It's **opt-in**: a session is the
coordinator only when the owner names it so. A `[q-coord` message from the coordinator
means follow the skill's lead role.

## Factory review and PR coordination

Assigned PR review or re-review → `.claude/skills/code-review/SKILL.md` and
`runbooks/code-review-protocol.md`: two independent seven-lens Sonnet CLI
reviews, validated by the Opus review-lead teammate, including ticket/epic
acceptance. Responding to findings → `.claude/skills/review-response/SKILL.md`.
Linking or resuming PR/ticket state → `.claude/skills/factory-reconcile/SKILL.md`.
The procedure is local and on-demand; no webhook, tunnel or background worker.
Read actual GitHub review records and Jyra evidence when resuming, not
remembered verdicts. Native Claude teams require an interactive Claude session.

## Safety

- Nothing here uses a Claude API key for routine work; this runs on the
  interactive subscription, one human present per action.
- Never put raw statement text, the private redaction profile, email bodies,
  account/card/SIN values or copies of private logs into prompts, transcripts,
  Jyra tickets, commits, PR descriptions, screenshots or test snapshots.
  Committed fixtures must be invented. q-core's privacy rules still apply to
  any work that touches it.
- `intake/` is the owner's statement drop folder (the q-core plugin's `intake_dir`).
  Git tracks only its `.gitkeep`. Factory sessions and workers never list,
  read, bundle or commit its contents; only the plugin's statement-intake
  upload step touches it, streaming files to q-core without reading them.
- The q-core API is reached only at loopback or its Tailscale Serve HTTPS
  origin; the CLI refuses other origins. Never expose q-core another way.
