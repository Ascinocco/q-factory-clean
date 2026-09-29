# Start or resume a factory review

Start in the q-factory checkout. Read the
[review protocol](../runbooks/code-review-protocol.md) before assigning review
work; this page is an entry point, not a second specification.

## Start an interactive team

For an installed Claude CLI supporting native teams, enable them for this
session only:

```sh
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude --model claude-opus-5-5
```

Ask the interactive tech lead to create or reuse a named review-lead teammate
explicitly on `claude-opus-5-5`, plus a separate triager (normally the implementer).
Provide the factory/project roots, repository/PR, Jyra board/ticket/epic and
current authority. Do not change global settings. The native teammate's runtime
metadata is evidence of its role and model: Claude Code CLI `2.1.280`, observed
2026-09-22, reports `taskKind=in_process_teammate`, a `session-*` team name and
`claude-opus-5`, and requires no separate `TeamCreate` command. Those field
names belong to the CLI, not to this repository, so a later release may rename
them: verify the metadata the installed CLI actually reports, and treat a
mismatch as unverified rather than as a failure. A model's self-description
does not establish this.

A `claude -p` process is not a native team teammate, even with the environment
flag. If the host cannot run the requested team/models, report that limit;
do not silently substitute a different model or label a CLI rehearsal as a team.

## Route the work

| Assignment | Read the complete skill |
| --- | --- |
| Initial or incremental PR review | [code-review](../.claude/skills/code-review/SKILL.md) |
| Verify, fix or refute findings | [review-response](../.claude/skills/review-response/SKILL.md) |
| Link or resume GitHub/Jyra state | [factory-reconcile](../.claude/skills/factory-reconcile/SKILL.md) |

The Opus review lead launches **two independent Sonnet CLI reviewers** using
[the isolated runner](factory-review-runner.md), with identical frozen context
and distinct sessions. Each applies all seven lenses: correctness,
contract-coherence, convention-drift, test-integrity, silent-failure,
scope-simplification and acceptance-specification. The lead validates evidence,
deduplicates candidates and checks ticket/epic acceptance before publishing.
Two reports agreeing does not establish correctness or approval.

Keep subscription authentication; the runner's command reference explains why
`--bare` is unsuitable. Use the runner's actual model/session metadata and its
coverage limitations. The CLI workers are separate from the interactive native
team's review-lead and triager roles.

## Resume from durable evidence

Read GitHub's existing native review records, threads and exact head/base; use
[the protocol's review stamp](../runbooks/code-review-protocol.md) to recover
stable findings, dispositions and acceptance evidence. GitHub owns review state;
agent memory only points to the procedure. Route the review URL through the tech
lead to the triager, then request one incremental round over the accumulated
delta, unresolved findings and affected acceptance. History/base/specification
changes require the protocol's explicit full-review reset.

Each participating PR body and relevant commit uses `Jyra-Ticket: UUID` as the
canonical linkage. Use [reconciliation preview and guarded apply](factory-reconciliation.md)
after PR actions and at resume; no webhook, tunnel or standing poller is needed.
A merge does not automatically accept a ticket. Verify all required PRs,
acceptance evidence and any parent submodule pointer update before an authorized
completion transition. Epic completion additionally requires integrated product
acceptance. Review, user acceptance, merge and deployment remain separate.
