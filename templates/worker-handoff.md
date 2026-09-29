# Worker handoff template

Fill every field for the assigned task. Absolute paths belong in this session
brief, not committed project guidance. Angle-bracket fields are deliberate
prompts and must be resolved before work starts. Send the brief to the worker
explicitly; do not depend on directory ancestry or automatic skill discovery.

## Identity and checkout

- Factory root (absolute): <q-factory checkout>
- Project name/entity ID: <name / entity UUID>
- Jyra board and ticket IDs: <board UUID / ticket UUID>
- Project repository (absolute): <canonical submodule checkout>
- Assigned task worktree (absolute): <worktree, which may be elsewhere>
- Expected Git common directory (absolute): <resolved common Git directory>
- Branch: <named task branch>
- Base commit: <full commit SHA>
- Owned files and dependencies: <scope; prerequisites; other active workers>

## Instructions to load

Read these actual files completely, using the explicit factory root above:

1. <factory root>/CLAUDE.md and <factory root>/AGENTS.md.
2. <factory root>/runbooks/factory.md.
3. <absolute paths to applicable shared SKILL.md files and referenced procedures>.
4. <task worktree>/AGENTS.md, <task worktree>/CLAUDE.md, and the project's
   canonical technical guide (normally PROJECT.md).
5. <applicable nested project instructions and project-local skills>.

List required external skills with their real available locations. If a listed
file or skill is missing, report it and resolve the missing context; never
pretend it loaded. Surface conflicts between instructions and the task, using
current user authorization rather than historical grants. Continue independent
work only where the missing decision is not required.

## Outcome and evidence

- Requested change: <concrete behavior>
- Acceptance criteria: <observable outcomes>
- Validation: <exact project-specific commands, working directories, fixtures,
  expected outcomes and platform constraints, resolved from the project guide>
- Real-use validation: <how to exercise this change as it will be used before
  the PR: the app, CLI or server on isolated fixtures (the project's launch
  skill, otherwise `run`), UIs through the browser MCPs, API and MCP calls end
  to end, failure and concurrency paths. Data-changing runs use isolated
  fixtures (owned by the worker in a shared environment); name any read-only
  live check the ticket or this session authorizes; no private data; live
  writes only through the ticket's own authorized paths.
  The handoff lists each command or action and what was observed, and what
  couldn't be checked and why. "Tests pass" alone isn't a handoff.>
- Review handoff: <PR destination, reviewer, required evidence>
- Authority: <what this session authorizes for commits, pushes, merges,
  ticket acceptance, deployment and further delegation>
- Stop/recovery: <where to report blockers; preserve work and hand ticket back>

## Verify before writing

From the assigned worktree, inspect `pwd`, `git rev-parse --show-toplevel`,
`git rev-parse --path-format=absolute --git-common-dir`,
`git branch --show-current`, `git status --short`, and
`git merge-base --is-ancestor <base-commit> HEAD`.
Resolve paths before comparing them (a platform may resolve `/tmp` differently).
Compare the root, common directory and branch with the brief; the common
directory must also match that of the canonical project repository. A worktree
outside `projects/` is valid when these identities agree. Do not infer identity
from folder names or a `.git` directory: worktrees typically have a `.git` file.

If identity does not match, treat that checkout as read-only and report the
mismatch. If unrelated work is present, preserve it and establish ownership.
On handback provide the commit/PR, check results, the real-use validation
record, remaining limitations and status transition evidence. Do not leave a
claimed ticket silently running.
