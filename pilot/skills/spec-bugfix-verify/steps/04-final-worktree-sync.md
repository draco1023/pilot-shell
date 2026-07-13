## Step 4: Worktree Sync (if worktree active)

1. Detect: `~/.pilot/bin/pilot worktree detect --json <plan_slug>`
2. If no worktree: skip to Step 5 (the annotation check — it runs BEFORE the review gate regardless of worktree mode; never collapse Step 5 → Step 6).
3. Save plan to project root (only if gitignored):
   `git -C <project_root> check-ignore -q docs/plans/<plan_filename>` — if exit 0: `cp <worktree_plan> <project_root>/docs/plans/`; if exit 1 (tracked): skip — squash merge brings the updated plan.
4. Show diff: `~/.pilot/bin/pilot worktree diff --json <plan_slug>`
5. Notify + AskUserQuestion: "Yes, squash merge" | "No, keep" | "Discard"
6. Handle:
   - **Squash:** `worktree sync && cleanup --force + cd` — ALL in ONE Bash call chained with `&&`. Cleanup MUST NOT run if sync fails.
   - **Keep:** Report path
   - **Discard:** `cleanup --discard` + `cd` in SAME bash call (no sync needed — `--discard` explicitly allows deleting unmerged work)

   ⛔ NEVER split sync, cleanup, or cd into separate Bash calls — compaction between them can cause work loss.
7. **Post-merge verification — MANDATORY after a successful squash merge** (parity with `spec-verify` §8.2): the base branch may have diverged, so re-run the full test suite and type check on the merged base-branch tree. Any failure means the merge broke something — fix on the base branch before reporting the bugfix verified.
