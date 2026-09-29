# Lead coordination: one coordinator, many team leads

Procedure: [`coordinate-leads`](../.claude/skills/coordinate-leads/SKILL.md).
This page records why it is shaped the way it is and what was measured.

## Shape

The owner runs several team-lead Claude sessions in tmux on one machine (chadmux,
nixos, q-factory, …). Each lead runs its own Opus teammates. The coordinator is
one more session, and it takes that role **only when the owner names it** in so many
words: opening a session never starts it, and there is no hook. It asks leads for
status (each lead collects from its own teammates) and sends them scoped changes.

## Transport: native messaging, not tmux

`ListAgents` lists the other top-level Claude sessions on the machine, each with
its tmux pane (`tmux S:@W.%P`). `SendMessage` reaches them and they reply to the
message's `from` address. tmux is used only to label peers: pane id → session
name. `tmux send-keys` was rejected because it types into whatever state the pane
is in, has no delivery or reply channel, and competes with the owner's own typing.

A lead's teammates are not listed as peers, so the peer list is already the list
of leads.

## Measured 2026-09-25

- A round trip works: coordinator → nixos lead → coordinator, in its fixed format.
- **Busy leads** get the message at their next tool round. Both busy leads in the
  first sweep acked within minutes and replied after collecting from their teams.
- **The reply arrives before the idle notice**, and the notice sometimes didn't
  come during the sweep. `notify_when_idle` is a supplement. The ack-then-reply
  protocol is what distinguishes "collecting from my team" from "didn't answer".
- Incoming messages carry `from-name`, `from` (a socket address) and `from-mode`.
  A lead in a different permission mode holds messages for the owner's approval in its
  own pane, so silence can mean "waiting for approval" as well as "no reply".
- Peer names (`proj-xx`) are per session and change on restart, so the roster
  is rebuilt every time.

## Durability

Messages are lost if a lead compacts or restarts. A broadcast that changes work
is recorded in Jyra: either a ticket on each affected board, or a note the lead
records on the ticket it already owns. The first live broadcast was a
time-critical hold (the cutover gate had cleared a minute earlier). It went out
before its record, and the skill now names that as the one allowed exception.

## Where the skill path points

Messages give the skill's absolute path so that a lead started from any repo
(including one that predates this skill) reads the same protocol without a
restart. The coordinator uses its own checkout. Normally that's `~/Projects/q-factory`,
which `claude-tmux` links to.
