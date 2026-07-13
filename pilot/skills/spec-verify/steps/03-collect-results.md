## Step 3: Code Review & Re-Verify

<!-- CC-ONLY -->
**If `PILOT_CHANGES_REVIEW_ENABLED` is `"false"` (from Step 0),** skip the review collection below. If the Codex companion was launched in Step 1, still run its collection sub-step — then proceed to Step 4 (Phase B). If neither reviewer is enabled, skip this step entirely.

**When enabled — mandatory. Never skip** — even if you're confident, context is high, or tests pass.

Re-resolve the mode exactly as in Step 1 (fail-closed to `agent`), then run the matching branch:

```bash
SPEC_MODE="${PILOT_SPEC_CODE_REVIEW_MODE:-agent}"
case "$SPEC_MODE" in medium|high|xhigh) ;; *) SPEC_MODE=agent ;; esac
echo "$SPEC_MODE"
```

#### Agent mode (`SPEC_MODE=agent`) — collect the changes-review findings launched in Step 1

**Stale-snapshot guard first:** the Step 1 launch reviewed the tree as it stood BEFORE the Step 2 automated checks. If Step 2 fixes modified ANY file after that launch, the findings are against stale code — re-launch the sub-agent now (same Step 1 prompt, current diff) and collect the re-launch instead. ⛔ The original agent may still be running and will eventually write to its own path — every launch MUST get a FRESH `output_path` (append a `-r2`, `-r3`, … suffix to the filename) so a late write from a superseded agent can never be collected as the fresh run. If Step 2 changed nothing, collect the Step 1 run as-is.

**Wait for the findings file (bash polling — NOT a Read loop, ⛔ NEVER `TaskOutput`):**

```bash
# Poll the path of the launch you are collecting (the Step 1 path, or the -rN re-launch path)
OUTPUT_PATH="$HOME/.pilot/sessions/${PILOT_SESSION_ID:-default}/findings-changes-review-<plan-slug>.json"
for i in $(seq 1 150); do [ -f "$OUTPUT_PATH" ] && echo "READY" && break; sleep 2; done
```

Run the poll as `Bash(run_in_background=true, timeout=330000)` — the loop can wait up to 5 min, which exceeds the default foreground Bash timeout, and `sleep` is allowed in background; you are notified when it exits. Then Read the file once. If not READY after the poll completes, the first agent may be slow rather than dead — re-launch ONCE with a fresh `-rN` output path (never reuse the in-flight path) and poll the new path.

**Validate findings:** the JSON's `plan_file` field must match the current plan path. A mismatch means stale findings from another plan — delete the file, re-launch, wait again.

**Apply agent findings (severity → action) — lineage first,** using the same lineage rule as the table below (out-of-lineage findings are mention-only regardless of severity): `must_fix` → fix immediately; `should_fix` → fix immediately; `suggestion` → implement if quick, else mention in the report. The agent's `truths` array feeds the Goal Achievement line of the report. Then skip the skill-mode sub-step and continue at "Collect Codex Results".

#### Skill mode (`SPEC_MODE` = `medium`/`high`/`xhigh`) — run /code-review (inline — AFTER the Step 2 automated checks are green)

Invoke the built-in code review skill at that effort (substitute the resolved `<SPEC_MODE>`):

```
Skill(skill='code-review', args='<SPEC_MODE>')
```

- Execute the loaded review protocol fully (finder angles → verify → sweep). Do NOT pass `--fix` — findings are applied by this orchestrator (below), not by the review.
- The default scope (branch commits ahead of upstream + uncommitted changes) is correct for a clean worktree or branch. **If the working tree carries unrelated dirty files, pass the plan's files AS THE TARGET in the Skill args** — `Skill(skill='code-review', args='<SPEC_MODE> <file1> <file2> …')` with the paths from the plan's `Files:` blocks — so the review protocol itself scopes its diff (`git diff HEAD -- <those paths>`); prose-level scoping outside the args does NOT bind the review and risks spending the capped findings on unrelated files. ⛔ Do NOT use a bare ref-range like `main...HEAD` to narrow a dirty tree — ref-ranges cover committed work only and would scope AWAY the spec's uncommitted changes.
- Output: a ranked JSON array of findings `{file, line, summary, failure_scenario}` — most severe first, no severity labels.
- **If the `code-review` skill is unavailable (older Claude Code version) or the invocation errors:** do NOT silently proceed as if reviewed. Record the gap explicitly in the Step 3 report and the Step 6.2 Not-Verified table, and rely on the Step 2.2 audit results for this iteration.

#### Apply /code-review Findings (severity → action)

**Fix automatically — no user permission needed.** **Lineage is evaluated FIRST:** a finding on a file outside the spec's lineage — the plan's `Files:` blocks plus files legitimately touched as documented deviations — is mention-only regardless of severity (out-of-lineage crashes are reported, never auto-fixed). Only in-lineage findings are classified by the remaining rows:

| Finding class | Action |
|---------------|--------|
| Finding on a file OUTSIDE the spec's lineage (CHECK FIRST — overrides all rows below) | **Mention-only — do NOT fix** (mirrors the pre-existing-issue rule) |
| `failure_scenario` names a concrete crash, wrong output, security, or data-integrity problem | **must_fix** — fix immediately |
| Cleanup / efficiency / altitude finding (duplication, wasted work, maintainability), single-site | **should_fix** — fix immediately |
| Cleanup finding that would expand scope (3+ files, architectural) | **suggestion** — implement if quick, else mention in the report |

Rank order is the tiebreaker within a class. For each fix: implement → run relevant tests → log "Fixed: [title]"

#### Collect Codex Results (if launched)

**⛔ Never skip or defer the Codex review.** If Codex was launched in Step 1, collect and act on its results before proceeding past Step 3. Its completion signal is the **exit of the Step 3 stall monitor below** (run as a background `Bash`), which watches `job.logFile` mtime and returns the moment the job finishes OR stalls. Do NOT poll broker `status` alone (a silent job keeps reporting `running`/`verifying` and a status-only loop burns its whole timeout before noticing), and do NOT read the result file while the monitor is running (partial output reads as a false "no findings" — the #1 cause of premature Codex skip). Wait for the monitor to exit, then branch on its `READY` / `FAIL` / `STALLED` output.

```bash
JOB_ID="<captured-task-id from Step 1>"
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

Run this as `Bash(run_in_background=true, timeout=600000)` (the CEILING exits well before the bash timeout). One node process replaces the old bash loop — no per-poll `uv`/`python` spawns, no zsh traps (read-only `status` variable, unquoted word-splitting), no `stat -f`/`stat -c` platform juggling — and the 5s poll detects completion up to 10s sooner. Output contract unchanged: `READY` / `FAIL state=…` / `STALLED no_log_growth=…` / `CEILING`. A missing `logFile` in the status JSON degrades the monitor to status + CEILING only — still better than spinning blind. Code reviews at the default `medium` effort typically take 1–3 minutes (xhigh runs ~2× longer).

**Outcome handling:**
- `READY` → completion notification fired; fetch and act on the result below.
- `FAIL` (`failed`/`cancelled`/`parse_error`/`unknown`) → genuine launch/broker failure; re-launch once synchronously per step 3 below.
- `STALLED` / `CEILING` → the job went silent. Cancel it, then re-launch ONCE under the same monitor — **without the `--effort` override** (inherit the user's Codex default), so the one retry has no configuration variable in play:
  ```bash
  node "$CODEX_COMPANION" cancel "$JOB_ID" --json 2>/dev/null || true
  node "$CODEX_COMPANION" task --background --prompt-file "$PROMPT_FILE"   # retry: NO --effort
  ```
  If the re-launch also returns `STALLED`/`CEILING`/`FAIL`, do NOT spin a third time and do NOT silently skip: proceed WITHOUT the Codex pass and record the gap explicitly in the verification report and the Step 6.2 Not-Verified table (note how long it ran and when the log last advanced). Continue with this iteration's changes-review results (agent findings or inline `/code-review`, per the resolved mode).

1. **When (and ONLY when) the completion notification arrives**, fetch the findings via the companion's public interface:

   ```bash
   node "$CODEX_COMPANION" result "$JOB_ID" --json > "/tmp/codex-task-result-${PILOT_SESSION_ID:-default}-<plan-slug>.json"
   ```

   Read `/tmp/codex-task-result-${PILOT_SESSION_ID:-default}-<plan-slug>.json` with the `Read` tool. (Deterministic name, not `$$` — each Bash tool call is a new shell with a new PID, so a PID-based path cannot be reconstructed by a later step.) The relevant fields:
   - `storedJob.status` — must be `"completed"`. If `"failed"`, treat as a re-launch trigger; do not silently proceed.
   - `storedJob.result.rawOutput` — a string containing Codex's response. With our prompt template, this is JSON matching the `{verdict, summary, findings, next_steps}` schema.
   - `storedJob.rendered` — same content rendered for display; useful as a fallback if `rawOutput` is malformed.

2. **Parse `rawOutput` as JSON.** Extract `verdict`, `summary`, `findings`, and `next_steps`. If `JSON.parse` fails (Codex deviated from the schema), fall back to `storedJob.rendered` — surface the rendered text to the user as a suggestion-level finding and continue. Do NOT re-launch on a parse failure; one Codex run per `/spec` is the rule.

   Severity → action map for the parsed findings (the same lineage-first rule as the inline table above applies — out-of-lineage Codex findings are mention-only regardless of severity):
   - `critical` / `high` → must_fix — fix immediately
   - `medium` / `low` → should_fix — fix immediately
   - `info` → suggestion — implement if quick

3. **If `storedJob.status` is `"failed"`** (genuine launch failure, not a timeout): re-launch synchronously (foreground `Bash(timeout=600000)`) and wait for results. If the second attempt also fails, escalate to the user with the captured error — do not silently proceed.

4. **Mark Codex as ran** so re-verify iterations within the same session do not re-run it:
```bash
SESS_ID="${PILOT_SESSION_ID:-default}"
CODEX_FLAG="$HOME/.pilot/sessions/$SESS_ID/codex-changes-review-ran-<plan-slug>.flag"
mkdir -p "$(dirname "$CODEX_FLAG")" && touch "$CODEX_FLAG"
```

5. **Cleanup:** delete the temp prompt file. `$PROMPT_FILE` from Step 1 is not in scope here (different bash invocation), so re-derive the path from the same template Step 1 used:
```bash
rm -f "/tmp/codex-changes-review-${PILOT_SESSION_ID:-default}-<plan-slug>.md" "/tmp/codex-task-result-${PILOT_SESSION_ID:-default}-<plan-slug>.json"
```

**Report:**
```
## Code Verification Complete
**Issues Found:** X
### Goal Achievement: N/M truths verified   (from the Step 2.2 Plan Compliance & Goal-Truth Audit)
### Must Fix (N) | Should Fix (N) | Suggestions (N) | Out-of-lineage mentions (N)
```

#### Re-verification (Only for Structural Fixes)

**Skip** when fixes were localized (terminology, error handling, test updates, minor bugs). Run tests + lint to confirm, proceed to Phase B.

**Re-verify** when fixes required new functionality, changed APIs, or significant new code paths: re-run the Step 2.2 Plan Compliance & Goal-Truth Audit on the post-fix diff (fixes can break mitigations or truths), then re-run the review SCOPED to the files the fixes touched rather than the whole spec diff. Agent mode: re-launch the Step 1 `changes-review` sub-agent with a FRESH `-rN` output path (never delete or reuse the in-flight path — a late write from the superseded agent must never be collected as the fresh run) and `Changed files:` = the fixed files, then poll the new path and apply as above. Skill mode: pass the fixed files as the target — `Skill(skill='code-review', args='<SPEC_MODE> <fixed files>')` (same resolved `<SPEC_MODE>` as the first run). Max 2 iterations before adding remaining issues to plan.
<!-- /CC-ONLY -->
<!-- CODEX-START
**If `PILOT_CHANGES_REVIEW_ENABLED` is `"false"` (from Step 0 — Step 1 was skipped),** skip this step entirely and proceed to Step 4 (Phase B).

**When enabled — mandatory. Never skip.** Read the `changes-review` agent id captured in Step 1 from working notes or the session file:

```bash
AGENT_ID_FILE="$HOME/.pilot/sessions/${PILOT_SESSION_ID:-default}/changes-review-agent-id-<plan-slug>.txt"
```

If `CHANGES_REVIEW_AGENT_ID` is missing and the file exists, read the file and use its trimmed contents. If both are missing or empty, re-launch `changes-review` once using the Step 1 prompt, persist the new id to the file, then continue. Do not silently skip review while `PILOT_CHANGES_REVIEW_ENABLED` is enabled.

Wait for the final result:

```python
result = multi_agent_v1.wait_agent(targets=[CHANGES_REVIEW_AGENT_ID], timeout_ms=600000)
```

Parse the agent's final message as JSON. If parsing fails, treat the raw final message as one `suggestion` finding and continue; do not re-launch on parse failure.

Validate `plan_file` matches the current plan. If it does not, discard the stale result and self-review the diff before proceeding.

Severity mapping:
- `must_fix` → fix immediately
- `should_fix` → fix immediately
- `suggestion` → implement if quick

Final-status-only findings are not implementation fixes. If a finding only says the plan still reads `Status: COMPLETE` instead of `Status: VERIFIED`, record it as pending Step 11 finalization and do not loop back to implementation. Step 11 is responsible for writing `VERIFIED` after the user review gate and re-checking final-status truths.

For each fix: implement → run relevant tests → log `Fixed: [title]`.

After all findings are handled, re-run the relevant automated checks from Step 2 before proceeding to Step 4.
CODEX-END -->
