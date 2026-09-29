---
name: project-onboarding
description: Bring an existing or explicitly requested new software repository into q-factory as a projects/ Git submodule, with project guidance and a Jyra board. Use for project onboarding or registration, not ordinary ticket implementation.
---

# Onboard a managed project

## Never — read first

- **Process safety.** Never use pkill, killall or any other pattern-matched
  kill. Stop only processes you started, by their recorded PID or your own
  process group, and never touch system services or other users' processes.
  Hosts such as the server are shared with production and other agents.
- **Never publish credentials because “the remote URL explains the failure.”**
  Use credential-free SSH/HTTPS repository addresses and local authentication.
  Do not print credential-bearing URLs, private configuration or tokens in
  reports, Git diffs, tickets or committed guidance.
- **Never overwrite existing instructions or force-reset a checkout because
  “the template is the standard.”** Preserve existing work and guidance. Stop
  on conflicting identity rather than replacing a repository or its records.
- **Never create an external repository or choose an application stack because
  “onboarding needs something to clone.”** Use the user's specified repository
  and authorized scaffold. Existing session authorization is sufficient; do
  not repeat an approval ceremony. Resolve only genuinely missing decisions.
- **Never repeat a create after an uncertain result because “it probably
  failed.”** Read Git and Jyra state first. There is no cross-system transaction
  or guaranteed uniqueness for entity names or board titles.
- **Never bypass MCP with live database writes because “registration is only
  metadata.”** Use entity and board tools, and drain their lists below.

## Resolve scope and existing state

Read `CLAUDE.md`, `runbooks/factory.md`, `templates/README.md` and the applicable
project instructions from the explicit q-factory root. Resolve the requested
repository, project identity, lowercase slug, starting revision and any new
repository visibility from the current session. Use `projects/<slug>`, with a
slug matching `[a-z0-9]+(?:-[a-z0-9]+)*`. Do not invent a stack or remote host.
Remote repository creation requires the user to request it; an already-created
empty remote needs initialization, not another repository.

Inspect q-factory Git status, `.gitmodules`, the index gitlink and the target
path before changing anything. A matching registered submodule is reused;
an uninitialized one may be initialized. An unrelated directory, conflicting
remote or different recorded identity is a stop to resolve, not a cleanup
opportunity. Preserve unrelated parent and project edits. Inspect URLs locally
without exposing embedded credentials; never register a credential-bearing URL.

Use `list_entities` for projects and drain the full response. Match an explicit
entity ID first; otherwise compare requested identity and `repository_path`.
If more than one candidate matches, or the chosen path belongs to another
project, resolve that conflict before writes. Do not choose the first name
match. Read the chosen entity with `get_entity` before changing attributes.

## Establish the project repository

For an existing nonempty remote, resolve the requested revision (or its
advertised default branch if no revision was specified), fetch it, and inspect
project instructions before running setup. Add it with Git's submodule command
under the canonical path, then check out the selected commit. Use explicitly
quoted arguments; never interpolate untrusted URLs or names into shell code.
Check the submodule belongs to the intended remote and the selected commit can
be retrieved from it. Avoid recursive initialization of unrelated projects.

For an empty remote, create a separate staging checkout outside `projects/`.
An empty remote has no commit that a parent gitlink can record. In that staging
checkout, initialize the requested default branch, adopt project guidance and
create only the authorized starting scaffold. Commit and push its initial
revision to the selected remote before adding it as a submodule. Verify the
branch is advertised and resolves to the pushed commit; use an explicit branch
when adding if the remote has not established its default HEAD yet. Do not
change global Git protocol settings to make a local fixture work.

Adopt the project-owned instructions from `templates/project/` without replacing
existing files. Keep one canonical technical guide and thin agent entry points;
resolve template prompts with known information, recording unconfigured
capabilities honestly. Shared q-factory paths and q-core private records do not belong
in the standalone repository. Scaffold changes to existing projects follow
that project's normal branch/review process and current authorization.

## Register or reuse Jyra identity

Once the submodule identity is established, create the project with
`create_entity(entity_type="project", name=..., attributes={...})`, including
`repository_path="projects/<slug>"`, or reuse the confirmed entity. To add the
path to an existing entity, get its current attributes and send the complete
object with the changed path using `update_entity`: attributes replace rather
than merge. Preserve descriptions and other attributes. If the running API
rejects `repository_path`, report that deployment prerequisite; do not silently
register a project lacking its required checkout association.

Read all `list_boards(entity_id=...)` results. Reuse the explicitly requested
board, or the single existing board when unambiguous. Multiple boards require
an explicit choice; titles are not unique identifiers. With no board, create
one with `create_board(entity_id=..., title=...)`, then record its returned ID.
Re-read entity and board to verify the association. A timeout after creation
requires inspection for a completed write before any retry; concurrent
onboarders must resolve duplicates rather than silently choose one.

## Validate and record completion

Verify project Git root, remote identity, chosen commit and the parent gitlink.
The gitlink must name a commit retrievable from the remote. Read and run the
project's documented setup/check commands within the authorized scope; inspect
commands before executing unfamiliar project code. Report absent toolchains or
credentials without inventing successful checks. Do not deploy or restart
q-core as part of managed-project registration.

Inspect the parent diff and stage `.gitmodules` and the specific project path
explicitly, plus only intentional factory changes. Do not use a blanket add
that captures unrelated submodule pins. Commit, push and review/integrate
according to session authority and the factory guide. Final evidence names the
project path, entity/board IDs, project commit, parent change, checks and any
remaining limitations; redact sensitive remote information.

## Partial failure and reruns

Git, the remote and Jyra can finish independently. Report completed steps and
remaining work, preserving repositories and records for recovery:

- Pushed initial commit but no submodule: reuse the now-nonempty remote.
- Submodule added but registration failed: inspect and reuse that submodule;
  complete entity/board association after resolving the failure.
- Entity exists but no board: verify its path and create only the missing board.
- Board creation response lost: re-list boards before considering a create.
- Registration complete but parent commit/push failed: preserve IDs, inspect
  the parent diff and finish that step; do not create a second project.

A disagreement between things that should agree is a stop. Do not automatically
delete external records or remove a dirty checkout to simulate rollback. Report
the specific unresolved identity or decision. A rerun that finds the expected
project, submodule and board reuses them and verifies the result.

## Reading lists

Prefer `all=true` where supported; it returns the complete set or refuses.
A refusal is a STOP, not a retry. Otherwise drain pages with this fence:

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

Derive reported counts from returned records. `total` is all matching rows;
a full first page is not proof of completeness. The empty-page guard prevents
an endless loop if records disappear between the count and page queries.
