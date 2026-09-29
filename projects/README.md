# Managed projects

Each `projects/<slug>/` entry is a Git submodule with an independent
repository, branches, pull requests and releases. Use lowercase slugs with
letters, digits and single hyphens. This directory's README belongs to
q-factory; project source belongs to each project's repository.

q-factory records an accepted commit for each project. `.gitmodules` owns
the repository URL and path; the gitlink owns the pinned commit. Entries
are added when an actual project is onboarded, never as placeholders.
Project entities identify those paths and boards belong to those entities.
The live Jyra board remains the work-status authority.

This copy of q-factory ships `.gitmodules` entries for `projects/chadmux`
and `projects/q-core` but no gitlinks, so no project commit is pinned yet.
Add a project's submodule (and so its pinned commit) with, for example,
`git submodule add -b main git@github.com:Ascinocco/q-core-clean.git projects/q-core`.

## Checkouts and task worktrees

A plain q-factory clone works without fetching every project. Initialize
only the project you need with `git submodule update --init -- projects/<slug>`.
This checks out the recorded commit, often detached. Do not implement on
that detached checkout or use `update --remote` as routine initialization.

Create named task branches in the project's repository, with isolated
checkouts under the chosen q-factory workspace's ignored
`.worktrees/<project>/<task>/`. Keep the submodule checkout stable while
workers use their own task worktrees. Project code changes and PRs belong
to the project remote. A later q-factory PR records the accepted project
commit after it is pushed and retrievable from that remote.

## Workspace identity

The factory root is an explicit q-factory checkout, including a linked
q-factory worktree. Resolve its absolute root with `git -C <factory-root>
rev-parse --show-toplevel`; never infer it from a worker's current directory
or a machine-specific path. Resolve project paths relative to that root.
A linked q-factory worktree may have uninitialized submodules; report that
state instead of silently substituting the canonical checkout. Pass the
factory root explicitly when working from a project task worktree.

Each project supplies its technical setup and checks in its own
instructions. Shared factory procedures come from q-factory and must be
provided explicitly to worker sessions, which may not inherit parent
directory instructions.

q-factory's test discovery excludes this directory and `.worktrees/`.
Project tests run separately from their own checkouts; project dependencies,
secrets and generated artifacts are governed by each project's repository.
