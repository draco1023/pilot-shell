## Phase A — Finalize the Code

## Step 1: Early Background Review Launch

### 1a: Clean Up Stale Review Findings (always run, before any launch)

**Always run this first** — regardless of whether changes-review is enabled. Spec-review findings are stale artifacts from the planning phase that were already addressed during implementation; changes-review findings files are the previous run's output (agent mode writes a fresh one below — a stale file left behind would be read as if it reviewed THIS iteration's diff). The cleanup runs strictly BEFORE any launch in this step:

```bash
SESS_DIR="$HOME/.pilot/sessions/${PILOT_SESSION_ID:-default}"
FIND_BIN="/usr/bin/find"
[ -x "$FIND_BIN" ] || FIND_BIN="$(command -v find)"
test -d "$SESS_DIR" && "$FIND_BIN" "$SESS_DIR" -maxdepth 1 -name 'findings-spec-review-*.json' -delete
test -d "$SESS_DIR" && "$FIND_BIN" "$SESS_DIR" -maxdepth 1 -name 'findings-changes-review-*.json' -delete
```

Use the absolute `FIND_BIN` form above. In Pilot Shell sessions the shell hook may rewrite plain `find` to RTK, and RTK rejects the `-delete` predicate shape this cleanup needs.

### 1b: Resolve the review diff scope and stage (before ANY reviewer launches)

**Resolve `DIFF_SCOPE` once — every reviewer launch below AND every Step 2 audit uses exactly this scope.** It depends on the plan's `Worktree:` mode, because that determines whether the change is committed:

- **Non-worktree mode (`Worktree: No`, the default):** the implementation phase does NOT commit, so the work sits in the WORKING TREE (modified files plus brand-new untracked ones). Stage the change's own files (below), then **`DIFF_SCOPE` = `git diff HEAD -- <changed files>`** — which now includes the staged additions.
- **Worktree mode (`Worktree: Yes`):** the implementation phase per-task-commits (`spec-implement` TDD loop), so the work is already committed on the worktree branch. Do NOT stage. Resolve the base ref (`~/.pilot/bin/pilot worktree status --json <slug>` → `base_branch`, default `main`) and **`DIFF_SCOPE` = `git diff <base_ref>..HEAD -- <changed files>`**. A plain `git diff HEAD` here would review an EMPTY diff.

A review of the unstaged tree (non-worktree) misfires both ways: a reviewer reading `git status --untracked-files=all` reports a spurious `critical` ("deliverable depends on untracked files"), while one reading only `git diff HEAD` silently OMITS new files. Staging fixes both:

```bash
# Non-worktree mode ONLY — stage the plan's files (paths from each task's `Files:` block)
# plus documented deviations — NOT unrelated dirty or untracked files.
git add <path/from/plan/Files-block-1> <path/from/plan/Files-block-2> ...
git status --short --untracked-files=all | grep '^??' || true   # anything still untracked must NOT be part of this change
```

A bare `git add -N` (intent-to-add) is NOT enough — `git status` still treats the path as untracked and a later `git commit` can record empty content. Use a real `git add`. **Staging is not committing** — the commit still waits for the review, doc-sync, and (Phase B) the worktree sync; `git add` is pre-authorized, the push is not. All reviewers below and all Step 2 audits scope to `DIFF_SCOPE` as resolved above.

**Reviewable file preflight:** the `Files:` block must contain at least one non-ignored repository artifact for implementation plans. `docs/plans/...` is workflow state and may be gitignored in Pilot Shell itself, so it cannot be the sole review target. Do NOT use `git add -f` to force ignored plan files into review. If every planned file is ignored, outside the repo, or only the plan file itself, set `Status: PENDING`, add a fix task for a reviewable non-production artifact (for smoke/no-production specs), and return to implementation before launching any reviewer.

---

<!-- CC-ONLY -->
**Resolve the changes-review mode** (fail-closed to `agent` — never pass the raw env var through):

```bash
SPEC_MODE="${PILOT_SPEC_CODE_REVIEW_MODE:-agent}"
case "$SPEC_MODE" in medium|high|xhigh) ;; *) SPEC_MODE=agent ;; esac
echo "$SPEC_MODE"
```

#### Agent mode (`SPEC_MODE=agent`) — launch the changes-review sub-agent NOW, in the background

**Only when `PILOT_CHANGES_REVIEW_ENABLED` is not `"false"`.** The single `changes-review` sub-agent is the low-token review mechanism; it works in the background while you run the Step 2 automated checks, and Step 3 collects its findings file.

**Derive plan slug** from the plan filename (strip `YYYY-MM-DD-` prefix and `.md`). Output path: `$SESS_DIR/findings-changes-review-<plan-slug>.json` (the 1a cleanup already removed any stale file).

```
Agent(
  subagent_type="changes-review",
  run_in_background=true,
  prompt="""
  **Plan file:** <plan-path>
  **Changed files:** <paths from the plan's Files: blocks + documented deviations>
  **Runtime environment:** <plan's Runtime Environment section, if present>
  **Output path:** <absolute findings path above>

  Review the diff (DIFF_SCOPE resolved in Step 1b — `git diff HEAD -- <changed files>` in non-worktree mode, `git diff <base_ref>..HEAD -- <changed files>` in worktree mode) against the plan: compliance, quality, goal achievement.
  Write findings JSON to output_path using the Write tool.
  IMPORTANT: Include the plan file path in your output JSON as the "plan_file" field.
  """
)
```

**⛔ NEVER use `TaskOutput`** to retrieve results — Step 3 polls the findings file.

#### Skill mode (`SPEC_MODE` = `medium`/`high`/`xhigh`) — no reviewer launch here

The code review runs INLINE in Step 3 via the built-in `/code-review` skill at effort `$SPEC_MODE` — there is no subagent to launch early and no findings file to derive. The only launch in this step is the optional Codex companion below.

#### Codex Adversarial Review (Optional — launch NOW, in the background)

**If `PILOT_CODEX_CHANGES_REVIEW_ENABLED` is `"true"` (from Step 0):**

Launch Codex review NOW — it works in the background while you run the Step 2 automated checks and the Step 3 inline review.

**Derive plan slug** from the plan filename: strip the date prefix (`YYYY-MM-DD-`) and `.md` extension. Example: `2026-03-02-sku-builder-modal-cleanup.md` → `sku-builder-modal-cleanup`.

**Codex-once rule.** Codex runs at most once per `/spec` invocation. Before launching, check the sentinel file. If it exists, the review already ran in this session — skip the launch and the collection sub-step in Step 3. Verify-phase iterations (re-verify after fixing findings, code-review-gate annotation fixes) do NOT trigger another Codex run.

```bash
SESS_ID="${PILOT_SESSION_ID:-default}"
CODEX_FLAG="$HOME/.pilot/sessions/$SESS_ID/codex-changes-review-ran-<plan-slug>.flag"
if [ -f "$CODEX_FLAG" ]; then
  echo "Codex already reviewed this plan in this session — skipping (codex-once)."
  # Skip the launch below and the Codex collection sub-step in Step 3.
fi
```

1. Detect companion path and ensure project root:
```bash
CODEX_COMPANION=$(ls ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)
PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
```

2. Build the review prompt file by rendering the **template at `$HOME/.claude/agents/changes-review-codex.md`**. The template is the single source of truth for code-review semantics — do NOT re-state the prompt inline in this skill. Substitute four placeholders:
   - `{{PLAN_PATH}}` — absolute path to the plan file
   - `{{PLAN_GOAL}}` — the 1–2 sentence Goal sentence from the plan's `## Summary`
   - `{{BASE_REF}}` — consistent with the Step 1b `DIFF_SCOPE`: **`HEAD` in non-worktree mode** (the change is uncommitted/staged, so the template's `git diff <BASE_REF>..HEAD` is empty and it falls back to `git diff HEAD` — the staged implementation; a `main` base would instead review prior branch commits on a dirty branch ahead of main), and the **worktree base branch** (`pilot worktree status --json` → `base_branch`) in worktree mode.
   - `{{CHANGED_FILES}}` — newline-separated paths to the files the plan said it would touch (extracted from each task's `Files:` block)

```bash
PROMPT_TEMPLATE="$HOME/.claude/agents/changes-review-codex.md"
PROMPT_FILE="/tmp/codex-changes-review-${PILOT_SESSION_ID:-default}-<plan-slug>.md"

PLAN_PATH="/absolute/path/to/docs/plans/YYYY-MM-DD-<slug>.md"
PLAN_GOAL="<one or two sentences from the plan Summary>"
BASE_REF="HEAD"   # non-worktree: HEAD → template falls back to `git diff HEAD` (the staged change). Worktree: set to the base_branch from `pilot worktree status --json`.
CHANGED_FILES=$(printf -- '- %s\n' \
  path/to/changed/file-1 \
  path/to/changed/file-2)

PLAN_PATH="$PLAN_PATH" PLAN_GOAL="$PLAN_GOAL" BASE_REF="$BASE_REF" CHANGED_FILES="$CHANGED_FILES" \
PROMPT_TEMPLATE="$PROMPT_TEMPLATE" PROMPT_FILE="$PROMPT_FILE" \
node -e '
const fs = require("fs");
let text = fs.readFileSync(process.env.PROMPT_TEMPLATE, "utf8");
for (const key of ["PLAN_PATH", "PLAN_GOAL", "BASE_REF", "CHANGED_FILES"])
  text = text.split("{{" + key + "}}").join(process.env[key] ?? "");
fs.writeFileSync(process.env.PROMPT_FILE, text);
'
```

Render with `node` (guaranteed present wherever the companion runs — the companion itself is node; no `uv` dependency on this path). `split/join` instead of `replace` avoids JS `$`-pattern expansion if a substitution value contains `$&`.

3. Launch the task in background. **For `task`, the companion's `--background` flag IS supported** (unlike `review`/`adversarial-review`). Use the companion's own background mode — the launch command returns the job ID immediately on stdout. Capture the job ID for collection in Step 3.

   **Resolve the review effort first (fail-closed to `medium`).** A changes review is a bounded read-only audit — it does not need the user's interactive reasoning default (often `xhigh`, which runs ~2× slower for equivalent material findings on review-scale diffs; verified live). `medium` is the default; users override via `PILOT_CODEX_REVIEW_EFFORT`. ⛔ Do NOT pass `--model` — fast-model aliases (e.g. `spark`) are rejected on ChatGPT-plan auth (`400 invalid_request_error`); the user's default model always stays.

   ```bash
   CODEX_EFFORT="${PILOT_CODEX_REVIEW_EFFORT:-medium}"
   case "$CODEX_EFFORT" in none|minimal|low|medium|high|xhigh) ;; *) CODEX_EFFORT=medium ;; esac
   ```

   ⛔ **Launch the companion via Bash from the MAIN conversation — NEVER through a subagent** (`codex:codex-rescue` included): a subagent-launched job's ID is unreachable afterwards (no findings file, no `TaskOutput`, no `SendMessage`).

   ```
   Bash(
     command="cd $PROJECT_ROOT && node $CODEX_COMPANION task --background --effort \"$CODEX_EFFORT\" --prompt-file \"$PROMPT_FILE\"",
     run_in_background=false,
     timeout=60000
   )
   ```

   If the launch itself errors on the effort value (a model that rejects the requested `reasoning.effort` fails within seconds with a `400`), re-launch once WITHOUT `--effort` — inheriting the user's Codex default — before falling back to the no-Codex path.

   The stdout looks like: `Codex Task started in the background as task-<id>. Check /codex:status task-<id> for progress.` Extract the `task-…` token and store as `JOB_ID`.

   **Verify registration before letting Step 3 poll** — fail-fast guard against synthetic-ID launches:

   ```bash
   node "$CODEX_COMPANION" status "$JOB_ID" --json 2>/dev/null | grep -q '"status":' \
     || { echo "Codex launch did not register with broker — JOB_ID is synthetic. Skipping Codex this run."; JOB_ID=""; }
   ```

   If `$JOB_ID` is empty after this check, skip Step 3's Codex collection and rely on the Step 3 changes review alone (agent findings or inline `/code-review`, per the resolved mode). If Changes Review is disabled too, no automated review runs this iteration — record that gap explicitly in the verification report.

**Do NOT wait** — proceed to Step 2 immediately. You'll be notified when the polling bash (Step 3) completes.
<!-- /CC-ONLY -->
<!-- CODEX-START
**If `PILOT_CHANGES_REVIEW_ENABLED` is `"false"` (from Step 0),** skip the rest of this step and proceed directly to Step 2 (Automated Checks).

**When enabled:** launch the managed Codex custom agent immediately. It runs while automated checks execute in Step 2.

Gather context first:

```bash
git status --short
```

Collect: changed files list, runtime environment info, test framework constraints, and plan risks section. Derive the plan slug from the plan filename by stripping the date prefix and `.md`.

Persist the returned agent id so Step 3 can survive long checks or compaction. Use a deterministic session file:

```bash
SESS_DIR="$HOME/.pilot/sessions/${PILOT_SESSION_ID:-default}"
AGENT_ID_FILE="$SESS_DIR/changes-review-agent-id-<plan-slug>.txt"
mkdir -p "$SESS_DIR"
```

```python
review = multi_agent_v1.spawn_agent(
    agent_type="changes-review",
    message="""
    Plan file: <plan-path>
    User request: <original task description that invoked $spec>
    Changed files: [file list]
    Runtime environment: [how to start, port, deploy path]
    Test framework constraints: [what it can/cannot test]

    Review implementation: compliance, quality, and goal achievement.
    Return ONLY valid JSON matching the changes-review schema.
    Include the plan file path in the `plan_file` field.
    """,
)
CHANGES_REVIEW_AGENT_ID = review.agent_id
```

After spawning, write `CHANGES_REVIEW_AGENT_ID` to `$AGENT_ID_FILE`.

Do NOT wait here. Proceed directly to Step 2.

Self-review the implementation diff before proceeding: `git diff --stat` to verify scope matches the plan, and spot-check changed files for obvious issues (security, missing error handling, dead code).
CODEX-END -->
