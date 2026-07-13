## Step 2: Create Plan File Header (FIRST)

1. **Parse flags** from arguments: `--worktree=yes|no` or `--new-branch` (default: `No`). Strip the flag from task description.

2a. **Create new branch (if `--new-branch`) — run as ONE Bash call.** Shell state (`$STASHED`, `$?`) does not persist across separate Bash invocations, so the stash/detect/checkout/restore sequence must live in a single call:

   ```bash
   STASH_MSG="pilot-spec-$(date +%s)"
   git stash push -m "$STASH_MSG" --include-untracked 2>/dev/null
   # git stash push exits 0 even when there is nothing to stash — detect a real stash by its message:
   STASHED=no; git stash list | grep -q "$STASH_MSG" && STASHED=yes

   # Detect the default branch. `git fetch` IS a network call; fall back to a local guess if offline.
   git fetch origin 2>/dev/null
   DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
   if [ -z "$DEFAULT_BRANCH" ]; then
     for b in main master; do git rev-parse --verify "origin/$b" >/dev/null 2>&1 && { DEFAULT_BRANCH="$b"; break; }; done
   fi
   DEFAULT_BRANCH=${DEFAULT_BRANCH:-main}

   BRANCH_NAME="feat/<plan_slug>"
   git rev-parse --verify "$BRANCH_NAME" >/dev/null 2>&1 && BRANCH_NAME="feat/<plan_slug>-$(date +%m%d-%H%M)"

   if git checkout -b "$BRANCH_NAME" "origin/$DEFAULT_BRANCH"; then
     # Bring the user's stashed working changes onto the new branch (new branch = latest origin base + their work).
     if [ "$STASHED" = yes ]; then
       git stash pop 2>/dev/null \
         && echo "on $BRANCH_NAME — restored your working changes" \
         || echo "on $BRANCH_NAME — stash '$STASH_MSG' did NOT auto-apply (conflict with origin/$DEFAULT_BRANCH); recover with: git stash pop"
     else
       echo "on $BRANCH_NAME"
     fi
   else
     # checkout failed (e.g. no origin remote) — restore the stash onto the current branch so no work is lost
     [ "$STASHED" = yes ] && git stash pop 2>/dev/null
     echo "checkout failed — restored stash, staying on current branch"
   fi
   ```

   `<plan_slug>` is derived from the task description (same slug used for the plan filename). The new branch starts from the latest `origin/$DEFAULT_BRANCH` and the user's uncommitted working changes are re-applied on top (a clean base + their work). On a pop conflict the stash is preserved for manual recovery; on checkout failure the stash is restored onto the current branch. After successful branch creation, continue with `Worktree: No` semantics (work directly on the new branch).

2b. **Create worktree early (if `--worktree=yes`):**

   ```bash
   ~/.pilot/bin/pilot worktree detect --json <plan_slug>
   # If not found:
   ~/.pilot/bin/pilot worktree create --json <plan_slug>
   # Returns: {"path": "...", "branch": "spec/<slug>", "base_branch": "main"}
   ```

   All file writes use the worktree path as base. If creation fails (old git): continue without worktree, set to `No`.

3. **Generate filename:** (for both worktree and new-branch paths) `docs/plans/YYYY-MM-DD-<feature-slug>.md` — slug from first 3-4 words (lowercase, hyphens). If worktree active, use worktree path as base directory.

4. **Fetch author email** (best-effort, do not fail if unavailable):

   ```bash
   ~/.pilot/bin/pilot status --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('email',''))" 2>/dev/null
   ```

   If the command returns a non-empty email, include `Author: <email>` in the header. If empty or fails, omit the Author line entirely.

<!-- CC-ONLY -->
4b. **Detect agent:** If `$CLAUDE_CODE_ENTRYPOINT` is set, agent is `Claude Code`. Otherwise, agent is `Codex`.
<!-- /CC-ONLY -->
<!-- CODEX-START
4b. **Set agent:** Use `Codex`.
CODEX-END -->

5. **Write initial header:**

   ```markdown
   # [Feature Name] Implementation Plan

   Created: [Date]
   Author: [email if available]
   <!-- CC-ONLY -->
   Agent: [Claude Code|Codex]
   <!-- /CC-ONLY -->
   <!-- CODEX-START
   Agent: Codex
   CODEX-END -->
   Status: PENDING
   Approved: No
   Iterations: 0
   Worktree: [Yes|No]
   Type: Feature

   > Planning in progress...

   ## Summary

   **Goal:** [Task description from user]

   ---

   _Exploring codebase and gathering requirements..._
   ```

   **`Status:` is a closed set** — only `PENDING` | `COMPLETE` | `VERIFIED`, written as the bare keyword with no trailing prose or parentheticals (see `task-and-workflow.md` → *Status values*). At creation it is always `PENDING`; never invent a custom status (no `RESOLVED`/`DONE`/`CLOSED`).

6. **Register plan:** `~/.pilot/bin/pilot register-plan "<plan_path>" "PENDING" 2>/dev/null || true`

**Do this FIRST** — before any exploration or questions. Status bar shows progress immediately.
