# q-factory agent entry point

Read `CLAUDE.md` before building a managed project or q-factory itself. It is
the shared source for mode boundaries, backlog and workflow routing. Read
`runbooks/INDEX.md` to locate the maintained procedures, and `runbooks/factory.md`
before any managed-project work.

Skills are in `.claude/skills/*/SKILL.md`; read the complete applicable skill
before acting:

- Project onboarding or registration: `.claude/skills/project-onboarding/SKILL.md`.
- Leading a team build: `.claude/skills/strategize-teammates/SKILL.md`;
  review-lead teammates: `.claude/skills/review-lead/SKILL.md`.
- Working a board: `.claude/skills/work-the-board/SKILL.md`.
- Factory PR reviews: `.claude/skills/code-review/SKILL.md`; responses:
  `.claude/skills/review-response/SKILL.md`; PR/ticket reconciliation:
  `.claude/skills/factory-reconcile/SKILL.md`. Shared contract:
  `runbooks/code-review-protocol.md`.

Workers need explicit paths and instructions; neither submodule nesting nor MCP
access guarantees inherited factory context. Report actual host/model
capabilities; ordinary CLI subprocesses are not native Claude team teammates.
