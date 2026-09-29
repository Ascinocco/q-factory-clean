---
name: factory-reconcile
description: Reconcile an explicit set of linked GitHub PRs with a selected Jyra ticket through local preview and guarded apply. Use after factory PR actions or to resume interrupted project work; no webhook or background polling.
---

# Local factory reconciliation

## Never — read first

- **Process safety.** Never use pkill, killall or any other pattern-matched
  kill. Stop only processes you started, by their recorded PID or your own
  process group, and never touch system services or other users' processes.
  Hosts such as the server are shared with production and other agents.
- Never expose q-core through a tunnel or webhook to synchronize tickets, or
  copy private ticket context/credentials into GitHub. Use outbound GitHub reads
  and the public local API; keep the service loopback-only.
- Never treat a commit mentioning a UUID, a closed PR, or one merged PR in a
  multi-PR task as proof that the ticket is complete.
- Never overwrite a human status decision, unblock a ticket automatically or
  retry a stale apply with refreshed preconditions without inspecting the change.
- Never claim GitHub and Jyra mutate atomically. Inspect durable receipts after a
  failure and resume the unfinished operation without duplicate transitions.
- Never use this command as a timer, daemon, global board sweep or new source of
  product acceptance. An inspection-only request authorizes preview only.

Read `runbooks/code-review-protocol.md` and
`docs/factory-reconciliation.md` before executing. Select the factory root,
project/board/ticket and explicit PR URLs. For q-factory itself use the
`--self` mode (identity from `q-factory.toml`); managed projects resolve their
registered repository. GitHub
owns PR state; Jyra owns backlog and acceptance.

Every participating PR body and its relevant commits carry canonical
`Jyra-Ticket: UUID` references. Verify the exact selected ticket and repository,
not a UUID mentioned incidentally in quoted prose. Keep links to all required
PRs in the ticket history; include every previously linked PR when reconciling.
New or ambiguous links require inspection rather than guessing the first match.

Use the documented command in preview mode. Inspect proposed evidence/status,
current transition ID, GitHub snapshot receipt and any attention/unknown state.
A publication or merge already authorized by the current factory task also
permits its associated bookkeeping; do not ask again for that same authority.
Apply only the reviewed snapshot with both explicit preconditions. If it changed,
inspect the new GitHub/Jyra state and decide again. The command's default records
evidence without moving work; optional owned-status advancement never transfers
human ownership to the synchronizer.

Invoke reconciliation after PR open/review/fix/merge and at a cold session's
resume. It does not continuously watch GitHub; an action outside the factory is
observed at the next invocation. A successful write whose response was lost must
be discoverable as already applied on retry.

After all required PRs merge, the coordinator checks the current exact review
records, acceptance evidence, target integration and any separate q-factory
submodule pointer PR. Only then perform an explicitly authorized Jyra completion
transition. An epic additionally needs product-level acceptance across its
children. The reconciliation helper never automatically declares either done.

## Reading lists

Prefer `all=true` for complete public reads when supported. Verify completeness
against the reported total; stop on refusal. GitHub paginated reviews, commits
and thread responses also require complete traversal. Do not read the DB or
private attachment paths to recover missing evidence.

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
