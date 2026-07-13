## Step 6: Finalise

### 6.1 Automated changes review (when enabled)

⛔ **Before running any reviewer, you MUST have completed Step 4 (Verify End-to-End) with concrete evidence.** Reviewers audit the fix; they are not a substitute for running the program.

The same two Console Settings toggles that drive `/spec`'s post-implementation review also govern `/fix`. Run whichever are enabled, and **auto-fix findings before** the worktree commit (6.2) and the approval gate (6.3) — so any review-driven change lands in the single bundled commit.

<!-- CC-ONLY -->
```bash
echo "CHANGES_REVIEW=$PILOT_CHANGES_REVIEW_ENABLED"          # changes review — runs unless explicitly "false" (mechanism per FIX_MODE below)
echo "FIX_MODE=$PILOT_FIX_CODE_REVIEW_MODE"                  # CC mechanism: agent = single changes-review sub-agent; medium/high/xhigh = /code-review at that effort
echo "CODEX_REVIEW=$PILOT_CODEX_CHANGES_REVIEW_ENABLED"      # Codex companion review — runs only when "true"
```

**Skip this sub-step entirely (proceed to 6.2) ONLY when `PILOT_CHANGES_REVIEW_ENABLED` IS `"false"` AND `PILOT_CODEX_CHANGES_REVIEW_ENABLED` is not `"true"`.** Otherwise at least one reviewer runs (changes-review is on by default — an unset `PILOT_CHANGES_REVIEW_ENABLED` runs it).
<!-- /CC-ONLY -->
<!-- CODEX-START
```bash
echo "CHANGES_REVIEW=$PILOT_CHANGES_REVIEW_ENABLED"          # native changes-review agent — runs unless explicitly "false"
```

`FIX_MODE` and the Codex companion (`PILOT_CODEX_CHANGES_REVIEW_ENABLED`) do NOT apply in Codex. **Skip this sub-step (proceed to 6.2) ONLY when `PILOT_CHANGES_REVIEW_ENABLED` IS `"false"`;** otherwise the native `changes-review` agent runs (an unset value runs it).
CODEX-END -->

#### 6.1.pre Instrumentation gate + stage the bugfix files (always run when any reviewer is enabled, before launching it)

**⛔ Leftover-instrumentation gate — runs BEFORE staging and the 6.2 commit** (the earlier Step 3.5 scan is the primary gate; this is the last pre-commit backstop, so a `SPEC-DEBUG`/`console` line can NEVER be committed — the 6.5 checklist's `git show HEAD` variant would only catch it after the worktree commit, too late):

```bash
# Scan the UNSTAGED working tree before anything is staged or committed:
git diff | grep -nE "SPEC-DEBUG|^\+.*\b(console\.log|console\.error|print\()" && \
  { echo "Leftover instrumentation — remove before staging/commit"; } || echo "instrumentation clean"
```

Remove any match and re-run before proceeding. Then stage the change's own files.

The fix and its new test sit UNSTAGED in the working tree — and a brand-new test file is untracked. A pre-commit review of that unstaged tree misfires both ways: a reviewer that reads `git status --untracked-files=all` flags the new test as a spurious `critical` ("untracked deliverable"), while a reviewer that reads only `git diff HEAD` silently OMITS it, so the test goes unreviewed. Stage the change's own files with a **real `git add`** (NOT `git add -N`) before launching any reviewer below:

```bash
git add <fix_file> <test_file>   # only the bugfix's own files — never unrelated dirty paths
git status --short --untracked-files=all | grep '^??' || true   # should list only files NOT part of this fix
```

Staging is not committing — the commit (6.2) still waits for the review and the approval gate. All reviewers scope to `git diff HEAD` (which now includes the staged additions); never narrow to a committed ref-range, which is empty pre-commit.

<!-- CC-ONLY -->
#### 6.1.0 Shared bugfix summary (Codex companion AND agent mode)

For `/fix` the "plan" is the conversation, not a file. Resolve `FIX_MODE` first (the 6.1.b block below shows the exact resolution — do it here, once). Build the one-page summary temp file whenever a reviewer that anchors on a plan artifact will run: the Codex companion (enabled), or the agent-mode changes-review sub-agent (`FIX_MODE=agent` with Changes Review enabled). Skill mode without the companion needs no artifact — `/code-review` reads the diff directly.

```bash
SESS_ID="${PILOT_SESSION_ID:-default}"
# Deterministic path (no $$): later Bash invocations, the agent-mode reviewer prompt,
# and the 6.1.d cleanup all need to reconstruct it outside this shell.
FIX_PLAN_FILE="/tmp/fix-review-plan-$SESS_ID.md"
cat > "$FIX_PLAN_FILE" <<'PLAN_EOF'
# /fix Bugfix Summary
Bug: <one-line bug>
Root cause: <file>:<line> — <what>
Fix: <one-line fix description>
Reproducing test: <test file>::<test name> (added in Step 2 RED)
PLAN_EOF
CHANGED_FILES=$(git status --short --untracked-files=all | awk '{print "- " $2}')
```

#### 6.1.a Codex companion changes review (only when `PILOT_CODEX_CHANGES_REVIEW_ENABLED == "true"`) — launch FIRST

Independent second opinion via the Codex plugin companion. **Codex-once rule:** Codex runs at most once per `/fix` invocation. Before launching, check the sentinel; if it exists (a prior approval-gate loop already ran it), skip the launch and the Codex part of 6.1.c.

```bash
SESS_DIR="$HOME/.pilot/sessions/${PILOT_SESSION_ID:-default}"
mkdir -p "$SESS_DIR"
CODEX_FLAG="$SESS_DIR/codex-changes-review-ran-fix.flag"
[ -f "$CODEX_FLAG" ] && echo "Codex already reviewed this fix in this session — skipping (codex-once)."
```

1. **Locate the companion.** If missing, tell the user "Codex companion not found — install the openai-codex plugin or disable Codex Companion Changes Review in Console Settings" and continue with the 6.1.b changes-review results (agent findings or inline `/code-review`, per the resolved mode) when Changes Review is enabled — otherwise proceed without automated review and say so in the 6.6 report.

   ```bash
   CODEX_COMPANION=$(ls ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)
   PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
   [ -z "$CODEX_COMPANION" ] && echo "MISSING"
   ```

2. **Build the review prompt file** by rendering the **template at `$HOME/.claude/agents/changes-review-codex.md`** (the same template `spec-verify` uses — single source of truth for code-review semantics). Reuse `$FIX_PLAN_FILE` from 6.1.0 as `{{PLAN_PATH}}` so the template's substitution points at a real artifact:

   ```bash
   PROMPT_TEMPLATE="$HOME/.claude/agents/changes-review-codex.md"
   PROMPT_FILE="/tmp/codex-fix-review-$SESS_ID.md"

   PLAN_GOAL="Bugfix for: <one-line bug>. Root cause at <file>:<line>. The reproducing test must reliably fail before the fix and pass after."
   # The fix + test are UNCOMMITTED at review time (staged in 6.1.pre), so review the working tree, not a committed range:
   BASE_REF="HEAD"

   PLAN_PATH="$FIX_PLAN_FILE" PLAN_GOAL="$PLAN_GOAL" BASE_REF="$BASE_REF" CHANGED_FILES="$CHANGED_FILES" \
   PROMPT_TEMPLATE="$PROMPT_TEMPLATE" PROMPT_FILE="$PROMPT_FILE" \
   node -e '
   const fs = require("fs");
   let text = fs.readFileSync(process.env.PROMPT_TEMPLATE, "utf8");
   for (const key of ["PLAN_PATH", "PLAN_GOAL", "BASE_REF", "CHANGED_FILES"])
     text = text.split("{{" + key + "}}").join(process.env[key] ?? "");
   fs.writeFileSync(process.env.PROMPT_FILE, text);
   '
   ```

   Render with `node` (guaranteed present wherever the companion runs; no `uv` dependency on this path). `split/join` instead of `replace` avoids JS `$`-pattern expansion if a substitution value contains `$&`.

3. **Launch the task in background.** Use `task --background --prompt-file` (the companion's own background mode is supported for `task` — unlike `review`/`adversarial-review`).

   **Resolve the review effort first (fail-closed to `medium`).** A changes review is a bounded read-only audit — it does not need the user's interactive reasoning default (often `xhigh`, ~2× slower for equivalent material findings; verified live). Users override via `PILOT_CODEX_REVIEW_EFFORT`. ⛔ Do NOT pass `--model` — fast-model aliases (e.g. `spark`) are rejected on ChatGPT-plan auth; the user's default model always stays.

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

   Capture the job ID from stdout (`task-…` token). **Verify registration before polling** — fail-fast guard against synthetic-ID launches:

   ```bash
   node "$CODEX_COMPANION" status "$JOB_ID" --json 2>/dev/null | grep -q '"status":' \
     || { echo "Codex launch did not register with broker (synthetic task id?). Skipping Codex this run."; JOB_ID=""; }
   ```

   If `$JOB_ID` is empty, skip the Codex part of 6.1.c. Otherwise run the **active stall monitor** — broker `status` alone is not a liveness signal (a silent job keeps reporting `running`/`verifying` and a status-only loop burns its whole timeout). It watches `job.logFile` mtime and returns the moment the job finishes OR stalls:

   ```bash
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

   Run the monitor as `Bash(run_in_background=true, timeout=600000)` (the CEILING exits before the bash timeout). One node process replaces the old bash loop — no per-poll `uv`/`python` spawns, no zsh traps (read-only `status` variable, unquoted word-splitting), no `stat -f`/`stat -c` platform juggling — and the 5s poll detects completion up to 10s sooner. Output contract unchanged: `READY` / `FAIL state=…` / `STALLED no_log_growth=…` / `CEILING`. A missing `logFile` degrades the monitor to status + CEILING only. ⛔ **Wait for the completion notification** — do NOT read the result file before the `<task-notification>` arrives. The inline review (6.1.b) runs while Codex churns.

   **Outcome handling.** `READY` → fetch the result in 6.1.c. `FAIL` → treat as a failed run (6.1.d launch-failure handling). `STALLED`/`CEILING` → the job went silent: cancel it and re-launch ONCE under the same monitor — **without the `--effort` override** (inherit the user's Codex default), so the one retry has no configuration variable in play:

   ```bash
   node "$CODEX_COMPANION" cancel "$JOB_ID" --json 2>/dev/null || true
   node "$CODEX_COMPANION" task --background --prompt-file "$PROMPT_FILE"   # retry: NO --effort
   ```

   If it stalls again, do NOT spin a third time and do NOT silently skip — proceed without the Codex pass, note the gap in the 6.6 report, and rely on the 6.1.b changes-review results.

#### 6.1.b Changes review (only when `PILOT_CHANGES_REVIEW_ENABLED` is not `"false"`)

Run AFTER launching Codex (6.1.a) so the companion works in parallel. Resolve the configured mechanism first, fail-closed to `agent` for an unset/invalid value (never pass the raw env var straight through):

```bash
FIX_MODE="${PILOT_FIX_CODE_REVIEW_MODE:-agent}"
case "$FIX_MODE" in medium|high|xhigh) ;; *) FIX_MODE=agent ;; esac
echo "$FIX_MODE"
```

**Agent mode (`FIX_MODE=agent`) — launch the single changes-review sub-agent:**

Build `$FIX_PLAN_FILE` per 6.1.0 (if not already built for the Codex companion), delete any stale findings file, then launch in the background:

```bash
SESS_DIR="$HOME/.pilot/sessions/${PILOT_SESSION_ID:-default}"
FINDINGS_PATH="$SESS_DIR/findings-changes-review-fix.json"
rm -f "$SESS_DIR"/findings-changes-review-fix*.json   # incl. -rN re-launch files from prior runs
```

```
Agent(
  subagent_type="changes-review",
  run_in_background=true,
  prompt="""
  **Plan file:** <$FIX_PLAN_FILE path>
  **Changed files:** <fix file> <test file>
  **Output path:** <$FINDINGS_PATH>

  Review the diff (git diff HEAD -- <fix file> <test file>) against the bugfix summary: root-cause fix quality, test quality, regressions.
  Write findings JSON to output_path using the Write tool.
  IMPORTANT: Include the plan file path in your output JSON as the "plan_file" field.
  """
)
```

Wait via bash file polling (⛔ NEVER `TaskOutput`): `for i in $(seq 1 150); do [ -f "$FINDINGS_PATH" ] && echo READY && break; sleep 2; done` — run the poll as `Bash(run_in_background=true, timeout=330000)` (the 5-min loop exceeds the default foreground Bash timeout; `sleep` is allowed in background, and you are notified when it exits). Then Read the file once and apply its findings in 6.1.c. If not READY after the poll completes, the first agent may be slow rather than dead — re-launch ONCE with a fresh output path (`findings-changes-review-fix-r2.json`; never reuse the in-flight path, a late write from the superseded agent must not be collected) and poll the new path.

**Skill mode (`FIX_MODE` = `medium`/`high`/`xhigh`) — run the built-in code review inline at that effort** (substitute the resolved `<FIX_MODE>`):

```
Skill(skill='code-review', args='<FIX_MODE>')
```

- Execute the loaded review protocol fully. Do NOT pass `--fix` — findings are applied by this orchestrator (6.1.c), not by the review.
- The default scope (uncommitted working-tree changes + commits ahead of upstream) covers the `/fix` diff in a clean tree. **If the tree carries unrelated dirty files, pass the bugfix lineage AS THE TARGET in the Skill args** — `Skill(skill='code-review', args='<FIX_MODE> <fix file> <test file>')` — covering BOTH the fix AND the Step 2 reproducing test (never review the fix without its test, or weak test assertions go unaudited); prose-level scoping outside the args does not bind the review. A ref-range target only covers committed work and misses the uncommitted fix.
- `/code-review` does not know the bug — root-cause-vs-symptom judgment stays with this orchestrator (Step 1.3 trace + 6.5 checklist); the agent-mode sub-agent and the Codex companion (6.1.a) are the reviewers that receive the bug summary.
- Output: a ranked JSON array of findings `{file, line, summary, failure_scenario}` — most severe first, no severity labels.

#### 6.1.c Apply findings + collect Codex

**Changes-review findings (if run in 6.1.b — agent findings file or inline `/code-review` output):** classify each finding and act. Agent-mode findings carry explicit severities — map them through the same lineage-first rule (`must_fix` → row 2 handling, `should_fix` → row 3, `suggestion` → mention/summarise). **Lineage is evaluated FIRST:** a finding on a file outside the bug's lineage (the fix file, its test, and files the fix legitimately touched) is mention-only regardless of severity — out-of-lineage crashes are reported to the user, never auto-fixed. Only in-lineage findings are classified by the remaining rows:

| Finding class | Action |
|---------------|--------|
| Finding on a file outside the bug's lineage (CHECK FIRST — overrides all rows below) | Mention in one line; do not auto-apply |
| `failure_scenario` names a concrete crash, wrong output, security, or data-integrity problem | **must_fix** — fix immediately, then re-run the targeted test from Step 3.4 + the full suite from Step 5.2 |
| Cleanup / efficiency finding, single-site and within the bug's lineage | **should_fix** — fix |
| Finding that would expand scope (3+ files, architectural) | Summarise to the user; let them decide whether to fix here or open a `/spec` follow-up |

**Codex reviewer (if launched in 6.1.a):** on the completion notification, fetch via the public interface:

```bash
node "$CODEX_COMPANION" result "$JOB_ID" --json > /tmp/codex-fix-result-$SESS_ID.json
```

Read `/tmp/codex-fix-result-$SESS_ID.json`. Verify `storedJob.status === "completed"`, then parse `storedJob.result.rawOutput` as JSON (`{verdict, summary, findings, next_steps}`). If JSON parse fails, fall back to `storedJob.rendered` and surface as a suggestion-level finding.

**Act on Codex findings — same action map as the inline table above, keyed by Codex severity:** `critical`/`high` → must_fix; `medium`/`low` → should_fix (single-site, in-lineage) or summarise; `info` → mention only.

If a reviewer returns no blocking findings (Codex verdict `approve`, `/code-review` empty findings array): report "Review: no blocking findings" in one line and proceed.

#### 6.1.d Mark + cleanup

```bash
[ -n "$JOB_ID" ] && touch "$CODEX_FLAG"   # codex-once
rm -f "$PROMPT_FILE" "$FIX_PLAN_FILE" /tmp/codex-fix-result-$SESS_ID.json
```

**Launch failure handling.** If the Codex job ended `failed` (genuine launch failure, not timeout): surface the captured stderr to the user, do **not** silently mark the bugfix done. Continue with the 6.1.b changes-review results.
<!-- /CC-ONLY -->
<!-- CODEX-START
When `PILOT_CHANGES_REVIEW_ENABLED` is not `"false"`, run the managed Codex `changes-review` custom agent on the bugfix diff before finalising. (The Codex *companion* review — `PILOT_CODEX_CHANGES_REVIEW_ENABLED` — is a Claude-Code-only plugin path and does not run here.)

1. Build a one-page bugfix summary in a temp file as the review anchor:

```bash
FIX_PLAN_FILE="/tmp/fix-review-plan-${PILOT_SESSION_ID:-default}.md"
cat > "$FIX_PLAN_FILE" <<'PLAN_EOF'
# /fix Bugfix Summary
Bug: <one-line bug>
Root cause: <file>:<line> — <what>
Fix: <one-line fix description>
Reproducing test: <test file>::<test name>
PLAN_EOF
```

2. Spawn the review agent and wait for its final JSON response:

```python
review = multi_agent_v1.spawn_agent(
    agent_type="changes-review",
    message="""
    Plan file: <FIX_PLAN_FILE path>
    User request: Bugfix — <one-line bug>
    Changed files: [git status --short list]

    Review the bugfix diff: quality and goal achievement. The "plan" is a one-page bugfix
    summary, not a multi-task spec — judge compliance against the bug, not absent feature tasks.
    Return ONLY valid JSON matching the changes-review schema. Include the plan file path in `plan_file`.
    """,
)
result = multi_agent_v1.wait_agent(targets=[review.agent_id], timeout_ms=600000)
```

3. Parse the agent's final message as JSON. If parsing fails, treat the raw final message as one `suggestion` finding and continue. Validate `plan_file` matches `$FIX_PLAN_FILE`; if not, discard the stale result and self-review instead.

4. Severity → action map: `must_fix` → fix now; `should_fix` → fix if single-site and within the bug's lineage (else summarise and let the user decide); `suggestion` → mention. After any fix, re-run the targeted test + full suite. Then `rm -f "$FIX_PLAN_FILE"`.
CODEX-END -->

### 6.2 Worktree mode — single commit

If a worktree was created: bundle test + fix (and any review-driven fixes from 6.1) into one commit.

```bash
git add <test_file> <fix_file>
git commit -m "fix: <one-line description>" -m "Root cause: <file>:<line> — <what was wrong and why>"
```

The conventional `fix:` prefix triggers a patch release if/when this branch ships. Do not split into multiple commits in the quick lane. The body placeholder is the Step 1.5 statement with its `Confidence` tail dropped — the template already carries the `Root cause:` prefix, so don't repeat it inside the placeholder. It gives the next debugger the confirmed cause in `git log`.

### 6.3 Approval gate (only when enabled)

⛔ **Before showing the approval question, you MUST have completed Step 4 (Verify End-to-End) with evidence.** "Tests pass" is not enough — the approval summary must include what you actually ran and what you observed. If you cannot fill in `**E2E:**` below with concrete evidence, you have not finished Step 4 — go back, do not ask for approval.

Read `PILOT_PLAN_APPROVAL_ENABLED`. If `"false"` → skip 6.3 entirely, mark done.

When approval is enabled, summarise + ask:

1. `"Approve — done"`
2. `"Request changes"`
3. `"Explain the fix in more detail"` — present in the initial ask (dropped from the re-ask list, per 6.3 below, to avoid loops).

```
AskUserQuestion(
  question="Bugfix complete.\n\nBug: <one line>\nRoot cause: <file>:<line> — <what>\nFix: <one-line description of the change>\nTests: reproducing test added (<test_name>), full suite green.\nReview: <none | changes-review sub-agent or /code-review (configured mode): N findings, all resolved | Codex: approve | ...>\nE2E: <command/URL you ran and the concrete observation that proves the fix — e.g. 'curl /search -d {} → 200 with [results]', 'opened /tasks page, saved end_date=2026-05-15, list shows 2026-05-15', 'ran pilot register-plan ./foo.md PENDING → exit 0, plan visible in console'>\n\nReview the diff in the Console's Changes tab. Approve when ready.",
  options=[<see list above>]
)
```

Handle:

- **Approve** → done.
- **Request changes** → user describes problem in free-form. Treat as a new investigation: re-run Step 1.3 (re-trace) → Step 2 onward. The 6.1 reviews re-run on the new fix, scoped to the files changed since the previous review — not the whole diff again.
<!-- CC-ONLY -->
  Re-run mechanics (same resolved `FIX_MODE` as 6.1.b): the codex-once flag keeps the Codex companion to a single run per invocation. Agent mode: rebuild `$FIX_PLAN_FILE` per 6.1.0 first (6.1.d deleted it), delete the findings file, and re-launch with `Changed files:` = the files changed since the previous review. Skill mode: pass them as the target — `Skill(skill='code-review', args='<FIX_MODE> <changed files>')`.
<!-- /CC-ONLY -->
<!-- CODEX-START
  Re-run mechanics: spawn the managed `changes-review` custom agent again on the updated diff (rebuild the one-page bugfix summary first so its `Plan file:` anchor exists), listing only the files changed since the previous review.
CODEX-END -->
- **Explain the fix in more detail** → write a fuller walkthrough (causal chain from trigger → root cause; why the boundary you fixed at is correct; line-by-line meaning of the diff; alternatives considered and rejected). Do NOT modify code. Then re-ask 6.3 — drop the "Explain" option from the new list to avoid loops.

### 6.4 Console notification (always, when binary present)

```bash
~/.pilot/bin/pilot notify plan_approval "Bugfix complete" "<one-line bug>" 2>/dev/null || true
```

Best-effort — don't block on failure.

### 6.5 Pre-report verification checklist

Walk every box before writing the report. **Missing any one = not done** — return to the relevant step.

- [ ] Reproducing test passes (Step 3.3 fresh run, this message).
- [ ] Full anti-regression suite green (Step 5.2 fresh run).
- [ ] E2E executed against the actual program with concrete evidence captured (Step 4).
- [ ] Enabled reviewers (6.1) ran; all `must_fix` / `should_fix` resolved or escalated.
- [ ] No leftover instrumentation. Instrumentation was already gated at Step 3.5 and again pre-commit at 6.1.pre (before staging/6.2 commit), so this is a final backstop only. Confirm on the staged/committed content: `git diff HEAD | grep -nE "SPEC-DEBUG|^\\+.*\\b(console\\.log|console\\.error|print\\()"` returns nothing (in worktree mode, where 6.2 already committed, use `git show HEAD | grep -nE "SPEC-DEBUG|console\\.log|console\\.error|print\\("` — if this fires, amend/revert the commit).
- [ ] Diff is small and every changed line traces to the bug (lineage rule).
- [ ] Worktree mode: single bundled `fix:` commit. Non-worktree: changes ready, no commit yet.

If any box is unchecked, do not write the report and do not ask for approval — fix the gap first.

### 6.6 Report

```
Bugfix complete — <bug>.
Root cause: <file>:<line>.
Tests: 1 new reproducing test, full suite green.
Review: <none enabled | changes-review sub-agent or /code-review (configured mode) / native changes-review + Codex, no blocking findings | N findings resolved>.
E2E: <command/URL run> → <observation that proves the symptom is gone>.

Run /clear before starting new work — this resets context while keeping project rules loaded.
```

The `E2E:` line is **mandatory** — it documents that the actual program was exercised, not just the unit tests.

### 6.7 Post-mortem flag (optional, one line)

Ask once, now that you have more information than when you started: **what would have prevented this bug?** If the answer is architectural — no clean test seam, hidden coupling between modules, validation absent at the boundary the bad data crossed, repeated near-miss in the same area — name it as a `/spec` follow-up candidate in one line:

```
Follow-up (architectural): <one-line description> — candidate for /spec.
```

Skip when the answer is "nothing structural, it was a one-line typo / off-by-one / wrong default." Don't manufacture follow-ups.

ARGUMENTS: $ARGUMENTS
