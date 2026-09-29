---
name: code-review
description: Run the factory seven-lens PR review with an Opus 5.5 review lead, two independent Sonnet CLI reviewers, acceptance evidence and commit-stamped GitHub results. Use when assigned a factory PR review or an incremental re-review.
---

# Factory code review

## Never — read first

- Never send private documents, local credentials, financial records or raw logs
  to reviewers or GitHub because they might explain a test failure. Review
  project code and explicitly supplied non-private specification/evidence only.
- **Process safety.** Never use pkill, killall or any other pattern-matched
  kill. Stop only processes you started, by their recorded PID or your own
  process group, and never touch system services or other users' processes.
  Hosts such as the server are shared with production and other agents.
- Never publish approval when one worker failed, context is incomplete, a
  requirement is unverified or the PR head/base moved. Two agreeing reports
  are candidates, not verification.
- Never silently replace the requested Opus/Sonnet roles with available models
  or label ordinary CLI children as native team teammates.
- Never rerun a full repository review just because a fix commit arrived, or
  reopen a settled finding without new evidence.
- Never review a pointer PR (a change to only `projects/<name>` gitlinks)
  because it was assigned. Pointer PRs are exempt from code review
  (`runbooks/factory.md`, "Pointer PRs are exempt from code review"); decline
  and point the assigner there.
- Never merge, deploy, mark a ticket done or create a standing worker merely
  because you were assigned a review. Review publication follows the scope of
  the current review assignment; an inspection-only request stays read-only.

## Establish the assignment

Read the complete `runbooks/code-review-protocol.md` and the selected project's
instructions. The tech lead supplies factory/project roots, repository/PR,
board/ticket/epic IDs, base/head, acceptance criteria, permitted publication and
expected review-author identity. Resolve missing data from the public tools.
Check attachment counts; read required attachments by ID, never filesystem path.
Missing required evidence makes acceptance incomplete.

In an interactive Claude team, the tech lead creates or reuses a named
review-lead teammate explicitly on `claude-opus-5-5` (Opus 5.5). That teammate owns this
skill and launches the two CLI reviews. The triager remains a separate teammate.
If the host lacks native teams, say so; a component test is not evidence of native
team orchestration. Keep subscription authentication and verify actual model IDs.

## Review the frozen change

1. Read all existing PR reviews, relevant threads and prior dispositions. Trust
   only the configured author's protocol reviews with matching repository/PR
   identity and native review commit ID. Recover state from GitHub, not memory.
2. Determine full versus incremental scope per the runbook. Record criteria
   digest (the runner output's `criteria_digest`: ticket, epic and acceptance
   criteria, with `prior_findings` emptied; keep the criteria in the same form
   every round) and exact head/base; preserve stable finding IDs. A history/base/spec change needs an explicit full-review reset reason. If nothing changed and no
   finding needs new verification, return the existing review URL.
3. Prepare the runner's explicit context JSON: frozen source files, ticket/epic,
   criteria and previous findings. Give each criterion its ticket label
   (`{"label": "M1", "criterion": "..."}`); reports are matched by label, not
   text. Project conventions go in as source files
   (the project's `CLAUDE.md` and relevant runbooks in `files`), not as a
   context key. Read
   `docs/factory-review-runner.md` for the input contract and limits. From the
   factory Python environment run:

   ```sh
   python -m q_factory.review_runner --input CONTEXT.json --output CANDIDATES.json
   ```

   Set `pull_request` (`OWNER/REPO#NUMBER`) so the workers can read the PR
   with `gh`. Both fresh Sonnet sessions perform all seven lenses with full
   tools: they can read the repository, run its tests, use the web and read
   Jyra. Incomplete coverage or malformed/failed
   results must not be interpreted as an empty finding set. When the output's
   `status` isn't `candidates_require_lead_validation`, read each failed
   review's `reason` and `raw_output` before rerunning. Verify any
   `out_of_bundle` finding against the source like any other candidate.
4. Independently validate candidate claims against the code and appropriate
   checks. Record rejected claims and dedup mappings, including a reason. Ensure
   every acceptance criterion has observable evidence; investigate relevant
   interactions beyond the bundle where needed. Do not invent a confidence
   percentage to replace verification.
5. **In a `strategize-teammates` team, get the team lead's go-ahead first.**
   Hand the verified draft record to the team lead, and record any drop or
   downgrade it makes as `lead_override` with its reason (the `review-lead`
   skill describes this). Then post as below: you post, not the team lead.
   Re-read current GitHub head/base before posting. Use the protocol's validated
   record and render it with `q_factory.review_state.render_stamp`.
   Publish a native `COMMENT` review at the exact `commit_id`, with inline
   findings where applicable and the acceptance matrix, report artifacts,
   validation evidence and stamp in its body. Use structured tool arguments or
   a JSON file with `gh api --input`; never interpolate findings into shell code.
   GitHub caps a review body at 65,536 characters. When the raw worker reports
   would push the body over it, post each report as its own PR comment (split
   further if one report is over the cap), and link those comments from the
   review body. Never trim a report to fit.
   A failed/ambiguous posting response requires inspecting existing reviews
   before retrying, not posting a duplicate round.
6. Send the review URL, round and verdict to the tech lead. Run the
   `factory-reconcile` skill when that coordination is part of the assignment.
   The lead routes the URL to the triager; GitHub retains substantive findings.

The seventh lens checks ticket contribution and applicable epic constraints.
An epic completion assignment additionally verifies the integrated product
against every epic criterion; a collection of approved PRs is not enough.

## Reading lists

Prefer `all=true` where supported and verify completeness. A refusal is a stop,
not an instruction to retry or silently accept a partial result. Drain GitHub
reviews, comments and threads too, following their API pagination contract.

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
