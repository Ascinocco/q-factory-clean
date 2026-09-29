# Reviewed project integration and parent pointers

A project merge and the q-factory pointer update are separate reviewed changes.
Git helpers verify repository properties; they do not certify review or grant
permission to merge or deploy. Follow the current [team review procedure](team-workflow.md)
and the [factory guide](factory.md), with the session's actual authorization.

1. Record the originating ticket, project PR, exact reviewed head SHA, target
   branch SHA and relevant checks. Test the project change composed with the
   intended target branch; another target change or substantive head change
   requires refreshed evidence. Use the existing exact-commit review gate.
2. Merge and push only within the user's authorization. Record the actual accepted
   commit, which may differ from the PR head after a merge or squash. Verify the
   resulting accepted tree and checks; do not substitute an arbitrary newer HEAD.
3. In a named, clean q-factory branch/worktree, read its recorded gitlink as
   `EXPECTED_OLD`. Select the registered project and run the explicit pointer
   command from [CLI documentation](../docs/factory-cli.md):

   ```sh
   python -m q_factory --root /path/to/q-factory pin \
     --project PROJECT_ID --board BOARD_ID \
     --commit ACCEPTED_COMMIT_SHA --expected-old EXPECTED_OLD_SHA
   ```

   The command retrieves the exact commit from the configured project remote into
   an empty disposable repository and proves it descends from `EXPECTED_OLD`.
   It refuses dirty project files, unrelated parent changes, a different staged
   pointer, unexpected checkout revisions and detached parent HEADs. Ignored files
   that a checkout would overwrite are protected too. It then checks out that
   exact project revision and stages only its gitlink. It does not commit, push,
   merge, initialize other projects or deploy anything.
4. Inspect `git diff --cached`: the change must contain only the intended project's
   gitlink. Commit and open the separate q-factory pointer PR. Its description links
   the project PR, accepted commit and originating ticket, states the old/new
   gitlinks, and includes the remote-retrieval result and relevant checks.
5. Validate the proposed parent revision using a clean clone and explicit
   initialization of the selected submodule. Verify the initialized `HEAD` equals
   the recorded gitlink. Use the project's normal remote/authentication; do not
   copy local object caches as a substitute for remote availability.
6. Merge the parent PR within authorization. It is **not code-reviewed**: the
   mechanical gate in `factory.md` ("Pointer PRs are exempt from code review")
   replaces review. Record both project and parent
   PRs/commits and the clone evidence on the originating ticket. Hand off for
   acceptance according to the session's permissions; a merge alone does not
   authorize deployment or automatically accept a ticket.

## Concurrent updates and interrupted runs

`--expected-old` is an optimistic guard. If the parent already records another
revision, inspect both accepted project histories and the new parent revision.
Do not blindly choose either side of a gitlink conflict. A desired descendant can
be reconsidered with the current recorded revision and fresh composed checks;
a divergence requires an explicit project integration decision. The helper will
not downgrade or force an unrelated history.

Repeated calls with the same target/expected-old recognize a completed checkout
awaiting staging, an already staged pointer, or an already recorded target. They
still verify remote retrieval and ancestry. A checkout/staging failure leaves
visible Git state; inspect it and repeat the same command only if it is still the
intended change. Do not reset unrelated work to make a retry pass. Ticket evidence
and existing PRs identify completed merge/push steps, so resume from the first
unfinished step rather than creating duplicate PRs or re-merging.
