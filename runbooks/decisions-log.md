# q-factory decisions log

Architecture calls for the factory itself. Pre-split history is in the earlier
repository's decisions log.

## Review workers get full tools, gh and Jyra (2026-09-26)

- **The owner's decision.** Reviewers get every tool and resource they need to
  review and validate a PR. The tool-free runner (`a795a5c`, 2026-09-22) was
  a design choice carried over from the earlier repository, never a recorded decision. This
  replaces the read-only `Read`/`Grep`/`Glob` rule from earlier the same day.
- **What changed.**
  - Each worker gets the full default toolset with Bash (tests, scripts,
    dependency installs, web) in its own snapshot of the frozen head, with
    permissions bypassed.
  - `gh` uses the owner's login; the optional `pull_request` input names the PR.
  - The q-core MCP uses the factory's own full-scope token. On the server that's
    the `server-q-factory` client token in the root `.env`. No narrower scope
    was added.
  - `--safe-mode` is dropped, because it also disables `--mcp-config` servers.
  - The per-worker timeout defaults to 3600 seconds with no upper bound.
- **Guardrails that remain.**
  - Private paths and the token stay out of the snapshot, and the token
    never appears on a command line.
  - Workers are instructed not to write to Jyra or GitHub, not to use q-core's
    financial, document or inventory tools, and not to read outside their
    snapshot. With Bash running as the owner, that's instruction, not enforcement.
  - Sonnet-only model evidence, pair semantics and lead verification are
    unchanged.

## Reviewers read the repository; failed workers keep their reports (2026-09-26)

- **The owner's decision.** Review workers should pull in broader context, and one
  bad worker result must not throw away the pair. PR #33's round 2 was refused
  twice ("Finding cites a file outside the supplied review scope"), losing four
  Sonnet reports without anyone seeing what was cited.
- **What changed.** Each worker runs in a `git archive` snapshot of the frozen
  head with private paths removed, with read-only `Read`, `Grep` and `Glob`
  (confined there by `--restricted`). This replaces the tool-free,
  bundle-only rule. A finding citing a file outside the bundle is kept and
  flagged `out_of_bundle`. A failed worker is recorded with its reason and raw
  output, and the runner always writes its output once the workers have started.
- **What stays.** A pair is only `candidates_require_lead_validation` when both
  workers are complete, and the review record still requires two complete
  reviewers, so a partial pair can't be approved. No write, command, network or
  MCP tools; the same private-path rules apply to the snapshot as to the bundle.

## No size cap on review bundles (2026-09-26)

- **The owner's decision.** The review runner has no size limit. The old
  300,000-byte cap (per source and per bundle) refused incremental rounds on
  modest PRs: three snapshots of a few ~30 KB files outgrew it (q-core#17
  round 2), and the change could not be split.
- **Why it's safe.** The bundle reaches each Sonnet reviewer on stdin, not
  argv, so no OS limit applies. A bundle too large for the reviewer's context
  makes the CLI fail, and the runner refuses the pair, so nothing is truncated
  silently. Binary, non-UTF-8, symlink, submodule and private-path refusals are
  unchanged.

## Pointer PRs skip code review (2026-09-26)

- **The owner's decision.** Pin (pointer) PRs are exempt from code review
  permanently. In the owner's words: "They're basically just stamps … I don't want
  other agents wasting cycles." Recorded on Jyra (q-factory board).
- **Why it's safe.** A pointer PR adds no code: it records a project commit
  that was already reviewed, or explicitly fast-tracked, in its own
  repository. What review used to catch here is mechanical, and `q_factory pin`
  plus a clean clone check it: exactly one gitlink, remote retrievability,
  ancestry from the expected old pin, and submodule `HEAD` equal to the
  gitlink. A gitlink changed inside a merge commit (an earlier review finding) still
  fails the gate.
- **What changed.** `runbooks/factory.md` gained the gate. The integration
  procedure, `work-the-board`, `strategize-teammates`, `code-review`,
  `review-lead` and the review protocol now say not to review or queue pointer
  PRs. The project-merge rule (stamped head, merge tree equal to it) is
  unchanged.

## Staying current and carrying claude-tmux (2026-09-25)

- **The clone updates itself at session start.** Epic 3 of the split requires
  every machine to stay current with no manual step. A SessionStart hook runs
  `scripts/session-sync.sh`, which only ever fast-forwards `main` and otherwise
  skips with a one-line reason (git's own first error line, URL credentials
  stripped). It never merges, rebases, stashes or discards, never recurses
  into `projects/` (`submodule.recurse=false` as well), and always exits 0
  (q-factory PR #2). The life skills keep themselves current separately,
  through the q-core plugin's own hook; this hook is repo-only by design
  (a spike).
- **claude-tmux syncs before launching Claude** (2026-09-25). Claude Code
  reads `CLAUDE.md`, settings and skills before any SessionStart hook runs, so
  a hook-only pull always arrives one session late. claude-tmux `new`/`create`
  run `session-sync.sh` before starting `claude` in a q-factory checkout (top
  level has `q-factory.toml`), and the hook stays as the backstop for sessions
  started any other way. A `clear` matcher was not added.
- **claude-tmux lives here** (from the earlier repository, q-factory PR #4). q-factory is
  the one repository on every machine, so the script Chadmux depends on
  survives the earlier repository's retirement and reaches every host at its next session
  start. Re-linking each machine's `~/.claude/scripts/claude-tmux.sh` to its
  main q-factory clone is a cutover step.
- **Registered projects:** chadmux and q-core, pinned at the earlier
  repository's commits (q-factory PR #3).

## Split from the earlier repository (2026-09-25)

q-factory was created from an earlier repository's history with `git filter-repo`, keeping the
factory CLI, factory skills and runbooks, templates and the managed-project
submodules.

- **Own settings, no q-core import.** `q_factory/settings.py` reads the committed
  `q-factory.toml` (q-core origin, own Jyra identity) and the token from
  `Q_CORE_API_TOKEN`, from the
  environment or root `.env`. The factory reaches q-core only over HTTP.
- **API origins.** Loopback HTTP(S) with an explicit port, or
  `https://<machine>.<tailnet>` on port 443 for the tailnet pinned in
  `q-factory.toml` (q-core's Tailscale Serve origin). Not any `*.ts.net`:
  another tailnet's machine, possibly public through Funnel, would match, so
  a typo could send the token outside the tailnet (review R1-F1). No pinned
  tailnet means loopback only. Plain HTTP stays loopback-only; credentials,
  paths, queries and fragments are refused.
- **`reconcile --self`** replaces an older hard-coded flag: the factory's own project, board
  and repository come from `q-factory.toml` rather than hard-coded ids.
- **Contract with q-core.** Pins that used to test factory skills against the
  API now test them against `contracts/q-core-factory-contract.json`, q-core's
  published surface. The reconcile contract test that drives the factory
  through q-core's real routes is an opt-in integration test (`Q_CORE_ROOT`),
  skipped, never passed, when q-core is absent.
- **Dependencies declared.** `jsonschema` (used by the review runner) was only
  a transitive install in the earlier repository; q-factory pins it explicitly.
