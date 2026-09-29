---
name: review-response
description: Triage a factory PR review, verify or refute findings, implement scoped fixes, record evidence and resolve verified threads before incremental re-review. Use for responding to a posted factory review.
---

# Factory review response

## Never — read first

- **Process safety.** Never use pkill, killall or any other pattern-matched
  kill. Stop only processes you started, by their recorded PID or your own
  process group, and never touch system services or other users' processes.
  Hosts such as the server are shared with production and other agents.
- Never paste private documents, credentials or raw financial/log content into
  a reply to prove a point. Use non-private evidence or synthetic reproductions.
- Never mark a finding fixed just because code changed, resolve a disputed
  thread to make the PR look green, or defer a blocker without accepted scope.
- Never invent the user's answer to a product ambiguity. Name the decision and
  escalate to the tech lead, tagging the verified user login when requested.
- Never treat a resolved GitHub conversation as review approval, or claim another
  ticket while still owning this task.
- Never merge, deploy or complete tickets solely because the findings were
  addressed. Those operations require the session's actual authority.

Read `runbooks/code-review-protocol.md` completely, then project instructions and
current ticket/epic criteria. Receive the PR review URL from the tech lead and
read the full review, candidate evidence and prior replies from GitHub. Verify
its exact commit and your task worktree identity before editing.

For every finding, reproduce or inspect the claim before deciding. Reply in its
thread with its stable finding ID and one evidence-backed disposition:

- `fixed`: implement the bounded fix, run relevant checks and identify its commit
  and result. Resolve the thread only after verifying the reported behavior.
- `refuted`: show concrete counterevidence. A disagreement stays open until the
  review lead accepts the reasoning or the tech lead resolves the dispute.
- `deferred`: create a real Jyra follow-up on the correct project board, name its
  owner and obtain the review lead's non-blocking disposition before resolving.

Reply to GitHub review comments using their actual comment IDs, and resolve
threads using their actual thread IDs; review IDs and comment IDs are not
interchangeable. Read API results before assuming the reply/resolution succeeded.
Use structured arguments or JSON files, not shell interpolation. Do not silently
edit the original reviewer's verdict or renumber findings.

Preserve independent implementer ownership. A feedback cycle continues the
original task in its task worktree; it is not a new global board claim. When
needed, move the ticket back to implementation through an authorized transition
with evidence and current preconditions. Reserve `blocked` for an actual missing
input/decision, not ordinary fixable review feedback.

After committing and pushing fixes, report the current head and disposition
links to the tech lead. Request one incremental review over all commits since
last review, plus unresolved findings and affected acceptance criteria. Preserve
settled findings unless new evidence invalidates them. After two fix rounds with
no reduction in blockers or new verification evidence, escalate instead of
requesting another identical review. Changed history/base/spec needs the explicit
full-reset rule in the protocol.

Run `factory-reconcile` for the linked work when authorized. A merged PR does not
by itself close the ticket: acceptance, other required PRs and parent project
pointer integration still matter. No external receiving-review plugin is required;
this procedure carries the complete triage contract.

## Reading lists

Read every relevant review/thread/history entry. Prefer complete responses;
refusals stop the operation rather than becoming partial evidence. Attachments
are read by ID through the public API/MCP tools, never private filesystem paths.

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
