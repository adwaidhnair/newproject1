---
name: merge
description: >-
  Merge the requested changes for the Northstar ERP Operations Intelligence
  project into the intended destination. Invoke this skill only when the user
  has explicitly requested merging, such as by choosing Merge Change or
  invoking /merge. Do not invoke it for review, preparation, passing checks, or
  skill installation alone.
disable-model-invocation: true
metadata:
  delta-action: land
---

# Merge Northstar changes

Carry the user's explicit merge request through to a completed merge into the
intended destination. The request that invoked this skill is sufficient
authorization to perform the merge: do not ask whether the user wants to merge
again. Do not claim success if the changes have not reached the destination.

## Repository workflow and verified checks

- The observed GitHub repository is `adwaidhnair/newproject1`, with `main` as
  its default branch. Recheck the live default branch and remotes at execution
  time; do not assume the checkout or remote is unchanged.
- There is no repository contribution guide, PR template, CI workflow, backend
  test configuration, or established merge strategy in the inspected project.
  Recheck current project instructions and contribution policy before acting.
- The frontend's verified production check is `npm run build` from `frontend/`
  (`frontend/package.json`). The README also lists Python 3.10+ and Node.js 18+
  with npm (`README.md`). There is no configured backend test command.
- Do not invent checks, review requirements, signing requirements, changelog
  obligations, or merge conventions. Apply any requirements discovered in
  current repository policy and destination settings, including their stated
  conditions and exceptions.

## Procedure

1. **Confirm scope and safeguard work.** Identify the requested change and
   intended destination from the user's request and current project context.
   Inspect the repository root, applicable `AGENTS.md`/`AGENT.md` instructions,
   Git status, current branch, remotes, recent history, and the complete change
   diff, including staged, unstaged, and untracked files. Do not include
   unrelated changes, overwrite other work, or discard files. If the requested
   change cannot be distinguished safely from unrelated work, stop and ask the
   user to identify its scope.

2. **Establish destination and requirements.** Verify the destination's live
   default branch and whether the relevant change is already on that branch or
   on a separate source branch. Inspect applicable branch rules, protections,
   required reviews, checks, merge queue, and enabled merge methods through
   available authoritative GitHub UI/API or repository tooling. Distinguish
   confirmed absence from inaccessible or incomplete settings. A 401, 403,
   unexplained 404, unavailable tool, or other incomplete view is not proof
   that no requirements exist. Do not proceed with a direct push or choose a
   different route to evade a requirement. If required settings cannot be
   established, stop and tell the user what needs inspection or access.

3. **Prepare only the requested change.** If the requested work is uncommitted,
   review it, run the checks below, and create a commit only from files and
   hunks that clearly belong to the request. Preserve all other staged,
   unstaged, and untracked work. If commits are needed, use a concise message
   describing the actual change; do not invent an issue reference or claim
   human authorship. Do not rewrite shared history or use an interactive
   editor/rebase. If the change is already committed, retain its existing
   history unless the user specifically requested a permitted transformation.

4. **Run local verification.** For changes affecting the frontend, run
   `npm run build` from `frontend/`. Use installed dependencies when available;
   if dependencies are unavailable, report that fact rather than installing
   tools or dependencies without authorization. For backend changes, inspect
   for newly added project-defined tests or validation commands and run those
   verified commands; there is no established backend test command in the
   inspected repository. Run any additional applicable checks required by
   current project policy or destination rules. A local build does not replace
   required remote checks.

5. **Choose the safe merge route.** Prefer a pull request into the live default
   branch when the requested change is on a separate source branch and the
   destination supports that route. Prepare an accurate title and description
   based on the actual diff. If policy requires human-authored text, obtain it
   from the user rather than writing text and treating approval as authorship.
   Publish only the intended source branch to the verified remote; never force
   push. Use the repository's configured merge method, reviews, and merge queue
   behavior. If the change is already on the default branch, a pull request
   cannot compare that branch to itself: do not push directly or fabricate a
   workaround. Stop and explain the available safe options, including moving
   the change onto a separate branch or having the user clarify the desired
   route.

6. **Handle conflicts and blockers.** Conflict preference: pause and ask the
   user to decide. Do not resolve conflicts automatically. If a merge attempt
   encounters conflicts, leave unrelated work intact, avoid committing a
   conflict resolution, and clearly report that the change was not merged.
   Stop for failing or incomplete checks, missing required reviews, merge
   queue blockers, policy uncertainty, insufficient permissions, unavailable
   credentials/tools, or any request to bypass a safeguard. Never use an
   administrator bypass, force push, or rule change to get around a blocker.

7. **Require checks for the exact change.** Before merging, verify every
   required check has completed successfully for the exact commit or merge
   candidate the destination rules require. Recheck the source/head SHA after
   checks and reviews; if it changed, verify requirements again for the updated
   change. Pending, failing, missing, stale, skipped without confirmation that
   policy accepts it, or unverifiable required checks are not proof of success.
   When checks are required but cannot be inspected, stop and request the
   necessary access or a user-provided verifiable result. Do not treat a
   started check or local build as sufficient.

8. **Merge and verify.** Once all applicable requirements are satisfied, use
   the supported, configured merge mechanism and method. Do not open an
   interactive editor. Verify through the hosting service or remote Git
   history that the intended destination now contains the requested change and
   that the pull request, if used, is merged. If a merge queue was required,
   verify it completed rather than merely accepting or queueing the change.
   Report the destination and resulting commit or merged pull request. If
   verification fails or cannot be performed, state that the merge is
   unconfirmed and do not report it as complete.
