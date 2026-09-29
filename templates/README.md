# Project guidance templates

`project/PROJECT.md` is a stack-neutral starting point for project-owned
technical instructions. `AGENTS.md` routes agents to it; `CLAUDE.md` routes
Claude to the same guidance. Commands have one canonical home.

During onboarding, inspect existing guidance first. Preserve it and adapt the
entry points to reference its existing authoritative document. Do not overwrite
an existing AGENTS.md, CLAUDE.md or PROJECT.md merely to match this layout.
For a new project, copy the templates, resolve their angle-bracket prompts and
record unavailable capabilities honestly. Do not copy machine-specific paths,
credentials or q-core private data into a project repository.

`worker-handoff.md` is a session brief template, not project source. Resolve its
absolute paths, Git identity, instructions, task IDs, acceptance criteria and
commands for each assignment. It supports cold-start workers in worktrees
outside the submodule directory without embedding factory dependencies in the
standalone project's source.
