## Step 10: Plan Verification

### 10.0: No-Placeholders Self-Check (always — before launching reviewers)

Walk the plan file once, fresh-eyed, and grep for the patterns below. **Every match is a plan failure** — fix inline before sending the plan to a reviewer or asking for approval.

**Forbidden placeholder patterns:**

- `TBD`, `TODO`, `FIXME`, "implement later", "fill in details", "details below"
- "add appropriate error handling", "add validation", "handle edge cases" — without specifying which cases
- "write tests for the above" — tasks must specify the actual test cases, not a meta-instruction
- "similar to Task N" — implementers may read tasks out of order; repeat the relevant content
- Steps that describe *what* to do without showing *how* (code blocks required for code steps)
- References to types, functions, methods, files, or env vars not defined in any task
- Bracketed angle-brackets like `<your-code-here>`, `<insert-X>` outside of header literal placeholders
- Goal Verification truths that are not falsifiable ("works correctly", "is fast enough")

```bash
# Quick grep (run in worktree or repo root):
grep -nEi "TBD|TODO|FIXME|implement later|fill in details|appropriate error handling|similar to Task" "<plan_path>"
```

If anything matches, fix it inline (no new round-trip needed). Then proceed to spec-review launch below.

---

<!-- CC-ONLY -->
**If `PILOT_SPEC_REVIEW_ENABLED` is `"false"` (from Step 0),** skip the Claude reviewer launch below and proceed straight to the Codex section.

**Auto-skip the Claude reviewer for small plans.** If the plan has **task count ≤ 2** AND it does NOT touch security, authentication, data integrity, or destructive operations, skip the Claude reviewer launch — reviewer overhead exceeds value for a change the implementer can audit by inspection. Continue to the Codex section below; Codex still runs **only** when the user has explicitly opted in via `PILOT_CODEX_SPEC_REVIEW_ENABLED`.

⛔ **Auto-skip scope is the reviewer agent only.** Skipping the Claude reviewer does NOT skip Step 11 (annotation check) or Step 12 (user approval) — those steps always run regardless of plan size. After completing this step (reviewer skipped or not), you MUST continue to Step 11.

For 3+ task plans, OR any plan touching sensitive surfaces regardless of task count, run the Claude reviewer below in full.

**Derive plan slug** from the plan filename: strip the date prefix (`YYYY-MM-DD-`) and `.md` extension. Example: `2026-03-02-sku-builder-modal-cleanup.md` → `sku-builder-modal-cleanup`.

**Delete stale findings before launching** (a previous run of the same plan may have left a file) — assign the path and remove it in one block:

```bash
SESS_ID="${PILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-default}}}"
OUTPUT_PATH="$HOME/.pilot/sessions/$SESS_ID/findings-spec-review-<plan-slug>.json"
rm -f "$OUTPUT_PATH"
```

```
Agent(
  subagent_type="spec-review",
  run_in_background=true,
  prompt="""
  **Plan file:** <plan-path>
  **User request:** <original task description>
  **Clarifications:** <any Q&A>
  **Output path:** <absolute path to findings JSON>

  Review for alignment with requirements AND adversarial risks.
  Write findings JSON to output_path using Write tool.
  IMPORTANT: Include the plan file path in your output JSON as the "plan_file" field.
  """
)
```

**⛔ NEVER use `TaskOutput`** to retrieve results — it dumps the full agent transcript into context, wasting thousands of tokens.

#### Codex Adversarial Review (Optional — launch immediately after Claude reviewer)

**If `PILOT_CODEX_SPEC_REVIEW_ENABLED` is `"true"` (from Step 0):**

Launch Codex review NOW — it runs in parallel with the Claude reviewer above.

**Codex-once rule.** Codex runs at most once per `/spec` invocation. Before launching, check the sentinel file. If it exists, the review already ran in this session — skip the launch and the collection sub-step below. Plan iterations (annotation feedback, plan edits, fixing prior findings) do NOT trigger another Codex run.

```bash
SESS_ID="${PILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-default}}}"
CODEX_FLAG="$HOME/.pilot/sessions/$SESS_ID/codex-spec-review-ran-<plan-slug>.flag"
if [ -f "$CODEX_FLAG" ]; then
  echo "Codex already reviewed this plan in this session — skipping (codex-once)."
  # Skip the launch and the Codex collection sub-step. Continue with Claude reviewer results only.
fi
```

**⛔ DO NOT use `adversarial-review --base` or `adversarial-review --scope branch` for plans.** Those subcommands bundle a git diff and feed it to Codex as the review target. Plan files in `pilot-shell` are gitignored (see `.gitignore` line ~271 — `docs/plans` is excluded), so the bundled diff is empty, and Codex returns a meta-finding ("no implementation diff was provided") with zero substantive findings on the actual plan content. Use the `task` subcommand with `--prompt-file` instead — it lets Codex Read the plan file directly via its own tools, with no diff dependency. (The `adversarial-review` path remains correct for `spec-verify`, where there is real working-tree code to scan.)

1. Detect companion path and project root:
```bash
CODEX_COMPANION=$(ls ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)
PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
```

2. Build the review prompt file by rendering the **template at `$HOME/.claude/agents/spec-review-codex.md`**. The template is the single source of truth for plan-review semantics — do NOT re-state the prompt inline in this skill. Substitute three placeholders:
   - `{{PLAN_PATH}}` — absolute path to the plan file
   - `{{PLAN_GOAL}}` — the 1–2 sentence Goal sentence from the plan's `## Summary`
   - `{{CONTEXT_FILES}}` — newline-separated absolute paths to source/reference files the plan ports from or extends (use the files referenced in `## Context for Implementer`)

```bash
PROMPT_TEMPLATE="$HOME/.claude/agents/spec-review-codex.md"
SESS_DIR="$HOME/.pilot/sessions/${PILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-default}}}"; mkdir -p "$SESS_DIR"
PROMPT_FILE="$SESS_DIR/codex-spec-review-<plan-slug>.md"

# Set these before rendering:
PLAN_PATH="/absolute/path/to/docs/plans/YYYY-MM-DD-<slug>.md"
PLAN_GOAL="<one or two sentences from the plan Summary>"
# CONTEXT_FILES is a newline-separated list — use printf to build it:
CONTEXT_FILES=$(printf -- '- %s\n' \
  /absolute/path/to/source-or-pattern-file-1 \
  /absolute/path/to/source-or-pattern-file-2)

PLAN_PATH="$PLAN_PATH" PLAN_GOAL="$PLAN_GOAL" CONTEXT_FILES="$CONTEXT_FILES" \
PROMPT_TEMPLATE="$PROMPT_TEMPLATE" PROMPT_FILE="$PROMPT_FILE" \
node -e '
const fs = require("fs");
let text = fs.readFileSync(process.env.PROMPT_TEMPLATE, "utf8");
for (const key of ["PLAN_PATH", "PLAN_GOAL", "CONTEXT_FILES"])
  text = text.split("{{" + key + "}}").join(process.env[key] ?? "");
fs.writeFileSync(process.env.PROMPT_FILE, text);
'
```

Render with `node` (guaranteed present wherever the companion runs; no `uv` dependency on this path). `split/join` instead of `replace` avoids JS `$`-pattern expansion if a substitution value contains `$&`.

3. Launch the task in background. **For `task`, the companion's `--background` flag IS supported** (unlike `review`/`adversarial-review`, where only Claude Code's `Bash(run_in_background=true)` detaches). Use the companion's own background mode here — the launch command returns the job ID immediately on stdout. Capture the job ID for collection.

   **Resolve the review effort first (fail-closed to `medium`).** A plan review is a bounded read-only audit — it does not need the user's interactive reasoning default (often `xhigh`, ~2× slower for equivalent material findings; verified live). Users override via `PILOT_CODEX_REVIEW_EFFORT`. ⛔ Do NOT pass `--model` — fast-model aliases (e.g. `spark`) are rejected on ChatGPT-plan auth; the user's default model always stays.

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

   If the launch itself errors on the effort value (a model that rejects the requested `reasoning.effort` fails within seconds with a `400`), re-launch once WITHOUT `--effort` — inheriting the user's Codex default — before falling back to the Claude-reviewer-only path.

   The stdout looks like: `Codex Task started in the background as task-<id>. Check /codex:status task-<id> for progress.` Extract the `task-…` token and store as `JOB_ID`.

   **Verify registration before polling** — fail-fast guard against synthetic-ID launches:

   ```bash
   node "$CODEX_COMPANION" status "$JOB_ID" --json 2>/dev/null | grep -q '"status":' \
     || { echo "Codex launch did not register with broker — JOB_ID is synthetic. Skipping Codex this run."; JOB_ID=""; }
   ```

   If `$JOB_ID` is empty, skip the Codex polling section and proceed with Claude reviewer only.

**Do NOT wait** — proceed to collect the Claude reviewer results first.

#### Collect Review Results

**Wait for Claude reviewer results (bash polling — NOT Read loop):**

```bash
OUTPUT_PATH="<findings-path>"
for i in $(seq 1 150); do [ -f "$OUTPUT_PATH" ] && echo "READY" && break; sleep 2; done
```

Then Read the file once. If not READY after 5 min, re-launch synchronously.

**Validate findings:** After reading the JSON, verify that the `plan_file` field matches the current plan path. If it doesn't match, the findings are stale from a previous `/spec` — delete the file, re-launch the reviewer, and wait again.

**Fix Claude reviewer findings immediately** — must_fix → should_fix. Suggestions if reasonable.

#### Collect Codex Results (if launched)

**⛔ Never skip or defer the Codex review.** If Codex was launched above, collect and act on its results before proceeding. The Codex review runs as `Bash(run_in_background=true)` — you will be automatically notified when it completes.

**⛔ The completion notification is the ONLY valid signal.** Do NOT read the output file to check if the review is done. The file may contain partial output from an in-progress review — reading it before the notification arrives leads to false conclusions ("no findings" when the review is still running). This is the #1 cause of premature Codex skip.

**⛔ If the notification hasn't arrived yet:** Do NOT proceed to Step 11 or approval. Do NOT read the output file. Do NOT conclude the review failed. Wait for the `<task-notification>` with `<status>completed</status>`. If you are tempted to check the file — that is the exact mistake this rule prevents.

**⛔ "Wait" does NOT mean "end your turn."** Ending the conversation turn lets the user think the workflow is finished and triggers a stop hook that pulls you out. Do not output a closing text message ("Waiting for codex…", "Holding for completion…"), do not call `ScheduleWakeup` as a substitute for staying engaged. Stay in-turn until the `<task-notification>` arrives. While waiting, do something productive in the same turn:
- Re-read the plan file once and pre-emptively spot any gaps you would fix anyway.
- If the user has queued a related request (e.g. a second bug to bundle), investigate / draft plan text for it now so you are ready to act when Codex completes.
- Run sanity-check Bash one-liners that don't fork long-running processes (path checks, file existence, small `git log` queries).
- As an absolute last resort with no other useful work, call `AskUserQuestion` to ask a short clarifying question — `AskUserQuestion` is the only tool whitelisted for a legitimate session-pause while a background task is in flight.

The completion notification arrives automatically as a mid-turn tool-result-style event; you do not need to poll for it.

**Wait for completion via the active stall monitor** (NOT a status-only poll, and NOT by reading the state file directly while waiting). Broker `status` alone is not a liveness signal — a silent job keeps reporting `running`/`verifying` and a status-only loop burns its whole timeout. The monitor watches `job.logFile` mtime and returns the moment the job finishes OR stalls, triggering the completion notification.

```bash
JOB_ID="<captured-task-id>"
STALL=90 CEILING=480 node -e '
const { execFileSync } = require("child_process");
const fs = require("fs");
const [companion, jobId] = process.argv.slice(1);
const stallMs = (Number(process.env.STALL) || 90) * 1000;
const ceilingMs = (Number(process.env.CEILING) || 480) * 1000;
const start = Date.now();
let lastChange = Date.now(), lastMtime = 0, logFile = null;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  while (true) {
    let job = {};
    try {
      job = JSON.parse(execFileSync(process.execPath, [companion, "status", jobId, "--json"], { encoding: "utf8", timeout: 30000 })).job ?? {};
    } catch { console.log("FAIL state=status_error"); return; }
    const st = job.status ?? "unknown";
    if (st === "completed") { console.log(`READY elapsed=${Math.round((Date.now() - start) / 1000)}s`); return; }
    if (st === "failed" || st === "cancelled" || st === "unknown") { console.log(`FAIL state=${st}`); return; }
    if (!logFile) logFile = job.logFile ?? null;
    let m = 0;
    try { if (logFile) m = fs.statSync(logFile).mtimeMs; } catch {}
    if (m > lastMtime) { lastMtime = m; lastChange = Date.now(); }
    if (Date.now() - lastChange >= stallMs) { console.log(`STALLED no_log_growth=${Math.round((Date.now() - lastChange) / 1000)}s`); return; }
    if (Date.now() - start >= ceilingMs) { console.log(`CEILING elapsed=${Math.round((Date.now() - start) / 1000)}s`); return; }
    await sleep(5000);
  }
})();
' "$CODEX_COMPANION" "$JOB_ID"
```

Run this as `Bash(run_in_background=true, timeout=600000)` (the CEILING exits before the bash timeout). One node process replaces the old bash loop — no per-poll `uv`/`python` spawns, no zsh traps (read-only `status` variable, unquoted word-splitting), no `stat -f`/`stat -c` platform juggling — and the 5s poll detects completion up to 10s sooner. Output contract unchanged: `READY` / `FAIL state=…` / `STALLED no_log_growth=…` / `CEILING`. A missing `logFile` degrades the monitor to status + CEILING only. Plan reviews at the default `medium` effort typically take under 2 minutes (no diff context to load; xhigh runs ~2× longer).

**Outcome handling:**
- `READY` → fetch and act on the result below.
- `FAIL` → genuine launch/broker failure; re-launch once synchronously per step 3 below.
- `STALLED` / `CEILING` → the job went silent. Cancel it, then re-launch ONCE under the same monitor — **without the `--effort` override** (inherit the user's Codex default), so the one retry has no configuration variable in play:
  ```bash
  node "$CODEX_COMPANION" cancel "$JOB_ID" --json 2>/dev/null || true
  node "$CODEX_COMPANION" task --background --prompt-file "$PROMPT_FILE"   # retry: NO --effort
  ```
  If the re-launch also returns `STALLED`/`CEILING`/`FAIL`, do NOT spin again and do NOT silently skip: proceed with the Claude reviewer results only and note the missing Codex pass before requesting approval.

1. **When (and ONLY when) the completion notification arrives**, fetch the result via the companion's public interface:

   ```bash
   SESS_DIR="$HOME/.pilot/sessions/${PILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-default}}}"
   node "$CODEX_COMPANION" result "$JOB_ID" --json > "$SESS_DIR/codex-task-result-<plan-slug>.json"
   ```

   Read `$SESS_DIR/codex-task-result-<plan-slug>.json` with the `Read` tool. (Deterministic name, not `$$` — each Bash tool call is a new shell with a new PID, so a PID-based path cannot be reconstructed by a later step.) The relevant fields:
   - `storedJob.status` — must be `"completed"`. If not, treat as a re-launch trigger; do not silently proceed.
   - `storedJob.result.rawOutput` — a string containing Codex's response. With our prompt, this is JSON matching the schema above.
   - `storedJob.rendered` — same content rendered for display; useful as a fallback if `rawOutput` is malformed.

2. **Parse `rawOutput` as JSON.** Extract `verdict`, `summary`, `findings`, `next_steps`. If `JSON.parse` fails (Codex deviated from the schema), fall back to `storedJob.rendered` — surface the rendered text to the user as a suggestion-level finding and continue. Do NOT re-launch on a parse failure; one Codex run per `/spec` is the rule.

   Severity → action map for the parsed findings:
   - `critical` / `high` → must_fix
   - `medium` / `low` → should_fix
   - `info` → suggestion

   Fix every must_fix and should_fix inline before requesting plan approval. Codex findings frequently surface architectural gaps (chained-command bypasses, fail-open paths, encoding edge cases) that the Claude reviewer misses — treat them with at least equal weight.

3. **If `storedJob.status` is `"failed"`** (genuine launch failure, not a timeout): re-launch synchronously and wait. If the second attempt also fails, escalate to the user with the captured error — do not silently proceed.

4. **Mark Codex as ran** so re-iterations of this plan within the same session do not re-run it:
```bash
mkdir -p "$(dirname "$CODEX_FLAG")" && touch "$CODEX_FLAG"
```

5. **Cleanup:** delete the temp prompt and result files:
```bash
SESS_DIR="$HOME/.pilot/sessions/${PILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-default}}}"
rm -f "$SESS_DIR/codex-spec-review-<plan-slug>.md" "$SESS_DIR/codex-task-result-<plan-slug>.json"
```

**If Codex was NOT launched**, proceed after all Claude reviewer must_fix/should_fix resolved.
<!-- /CC-ONLY -->
<!-- CODEX-START
**If `PILOT_SPEC_REVIEW_ENABLED` is `"false"` (from Step 0),** skip native Codex plan review and proceed to the task-card format check below.

**When enabled:** launch the managed Codex custom agent and wait for its final JSON response before requesting approval.

1. Spawn the review agent:

```python
review = multi_agent_v1.spawn_agent(
    agent_type="spec-review",
    message="""
    Plan file: <plan-path>
    User request: <original task description>
    Clarifications: <any Q&A>

    Review for alignment with requirements and adversarial risks.
    Return ONLY valid JSON matching the spec-review schema.
    Include the plan file path in the `plan_file` field.
    """,
)
```

2. Wait for the result:

```python
result = multi_agent_v1.wait_agent(targets=[review.agent_id], timeout_ms=600000)
```

3. Parse the agent's final message as JSON. If parsing fails, treat the raw final message as one `suggestion` finding and continue; do not launch a second reviewer.

4. Validate `plan_file` matches the current plan. If it does not, discard the stale result and self-review instead of applying mismatched findings.

5. Severity mapping:
   - `must_fix` → fix immediately
   - `should_fix` → fix immediately
   - `suggestion` → implement if quick

Fix every `must_fix` and `should_fix` inline, then re-run the no-placeholders and task-card checks before approval.

Before Step 11, run this task-card format check on the plan:

```bash
grep -nE '^### Task [0-9]+:|^\*\*(Objective|Files|Key Decisions / Notes|Definition of Done):\*\*' "<plan_path>"
```

Every `### Task N:` block under `## Implementation Tasks` must contain all four bold labels: `**Objective:**`, `**Files:**`, `**Key Decisions / Notes:**`, and `**Definition of Done:**`. Fix any plain labels such as `Files:`, `Key Decisions:`, `Definition of Done:`, or `Verification:` before asking for approval.

Self-review the plan for obvious issues before requesting approval: missing edge cases, unclear DoD criteria, placeholder text, wrong task-card label format, and unresolved ambiguities.
CODEX-END -->
