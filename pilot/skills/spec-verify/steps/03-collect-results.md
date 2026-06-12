## Step 3: Code Review & Re-Verify

<!-- CC-ONLY -->
**If `PILOT_CHANGES_REVIEW_ENABLED` is `"false"` (from Step 0),** skip the inline `/code-review` below. If the Codex companion was launched in Step 1, still run its collection sub-step — then proceed to Step 4 (Phase B). If neither reviewer is enabled, skip this step entirely.

**When enabled — mandatory. Never skip** — even if you're confident, context is high, or tests pass.

#### Run /code-review (inline — AFTER the Step 2 automated checks are green)

Invoke the built-in code review skill at xhigh effort:

```
Skill(skill='code-review', args='xhigh')
```

- Execute the loaded review protocol fully (finder angles → verify → sweep). Do NOT pass `--fix` — findings are applied by this orchestrator (below), not by the review.
- The default scope (branch commits ahead of upstream + uncommitted changes) is correct for a clean worktree or branch. **If the working tree carries unrelated dirty files, pass the plan's files AS THE TARGET in the Skill args** — `Skill(skill='code-review', args='xhigh <file1> <file2> …')` with the paths from the plan's `Files:` blocks — so the review protocol itself scopes its diff (`git diff HEAD -- <those paths>`); prose-level scoping outside the args does NOT bind the review and risks spending the capped findings on unrelated files. ⛔ Do NOT use a bare ref-range like `main...HEAD` to narrow a dirty tree — ref-ranges cover committed work only and would scope AWAY the spec's uncommitted changes.
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

**⛔ Never skip or defer the Codex review.** If Codex was launched in Step 1, collect and act on its results before proceeding past Step 3. The Codex review runs as a `Bash(run_in_background=true)` — you will be automatically notified when it completes.

**⛔ The completion notification is the ONLY valid signal.** Do NOT read the output file to check if the review is done. The file may contain partial output from an in-progress review — reading it before the notification arrives leads to false conclusions ("no findings" when the review is still running). This is the #1 cause of premature Codex skip.

**⛔ If the notification hasn't arrived yet:** STOP. Do NOT proceed to Phase B, do NOT say "still running, moving on", do NOT read the output file, do NOT conclude the review failed. Wait for the `<task-notification>` with `<status>completed</status>`. If you are tempted to check the file — that is the exact mistake this rule prevents.

**Wait for completion via bash polling**, NOT by reading the state file directly. The polling bash returns when the `task` job's status flips to `completed` or `failed`, triggering the completion notification.

```bash
JOB_ID="<captured-task-id from Step 1>"
for i in $(seq 1 250); do
  STATE=$(node "$CODEX_COMPANION" status "$JOB_ID" --json 2>/dev/null \
    | uv run --no-project --python python3 python -c "import json,sys
try: print((json.load(sys.stdin).get('job') or {}).get('status') or 'unknown')
except Exception: print('parse_error')" 2>/dev/null)
  case "$STATE" in
    completed)                  echo "READY @ iter=$i"; break ;;
    failed|parse_error|unknown) echo "FAIL state=$STATE iter=$i"; break ;;
  esac
  sleep 4
done
```

Treat `parse_error`/`unknown` as failure (job vanished or broker unreachable) — do NOT continue spinning.
Run this as `Bash(run_in_background=true, timeout=600000)`. Code reviews typically take 2–6 minutes; the 10-minute ceiling is the safety margin.

1. **When (and ONLY when) the completion notification arrives**, fetch the findings via the companion's public interface:

   ```bash
   node "$CODEX_COMPANION" result "$JOB_ID" --json > /tmp/codex-task-result-$$.json
   ```

   Read `/tmp/codex-task-result-$$.json` with the `Read` tool. The relevant fields:
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
rm -f "/tmp/codex-changes-review-${PILOT_SESSION_ID:-default}-<plan-slug>.md"
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

**Re-verify** when fixes required new functionality, changed APIs, or significant new code paths: re-run the Step 2.2 Plan Compliance & Goal-Truth Audit on the post-fix diff (fixes can break mitigations or truths), then re-run the inline review SCOPED to the files the fixes touched — pass them as the target: `Skill(skill='code-review', args='xhigh <fixed files>')` — rather than the whole spec diff. Max 2 iterations before adding remaining issues to plan.
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

For each fix: implement → run relevant tests → log `Fixed: [title]`.

After all findings are handled, re-run the relevant automated checks from Step 2 before proceeding to Step 4.
CODEX-END -->
