## Step 3: Collect Review Results & Re-Verify

<!-- CC-ONLY -->
**⛔ If `PILOT_CHANGES_REVIEW_ENABLED` is `"false"` (from Step 0 — Step 1 was skipped),** skip this step entirely and proceed to Step 4 (Phase B). There are no findings to collect.
<!-- /CC-ONLY -->

<!-- CC-ONLY -->
**When enabled — mandatory. Never skip** — even if you're confident, context is high, or tests pass.

**⛔ NEVER use `TaskOutput`** to retrieve results — it dumps the full agent transcript into context, wasting thousands of tokens.

**Wait for Claude reviewer results (bash polling — NOT Read loop):**

```bash
OUTPUT_PATH="<findings-path>"
for i in $(seq 1 250); do [ -f "$OUTPUT_PATH" ] && echo "READY" && break; sleep 2; done
```

Then Read the file once. If not READY after ~8 min, re-launch synchronously.

**⛔ Validate findings:** After reading the JSON, verify that the `plan_file` field matches the current plan path. If it doesn't match, the findings are stale from a previous `/spec` — delete the file, re-launch the reviewer, and wait again.

#### Fix Claude Reviewer Findings

**Fix automatically — no user permission needed.**

1. **must_fix** → Fix immediately (security, crashes, TDD violations)
2. **should_fix** → Fix immediately (spec deviations, missing tests, error handling)
3. **suggestions** → Implement if quick

For each fix: implement → run relevant tests → log "Fixed: [title]"

#### Collect Codex Results (if launched)

**⛔ MANDATORY — NEVER skip or defer the Codex review.** If Codex was launched in Step 1, you MUST collect and act on its results before proceeding past Step 3. The Codex review runs as a `Bash(run_in_background=true)` — you will be automatically notified when it completes.

**⛔ The completion notification is the ONLY valid signal.** Do NOT read the output file to check if the review is done. The file may contain partial output from an in-progress review — reading it before the notification arrives leads to false conclusions ("no findings" when the review is still running). This is the #1 cause of premature Codex skip.

**⛔ If the notification hasn't arrived yet:** STOP. Do NOT proceed to Phase B, do NOT say "still running, moving on", do NOT read the output file, do NOT conclude the review failed. Wait for the `<task-notification>` with `<status>completed</status>`. If you are tempted to check the file — that is the exact mistake this rule prevents.

**Wait for completion via bash polling**, NOT by reading the state file directly. The polling bash returns when the `task` job's status flips to `completed` or `failed`, triggering the completion notification.

```bash
JOB_ID="<captured-task-id from Step 1>"
for i in $(seq 1 250); do
  STATE=$(node "$CODEX_COMPANION" status "$JOB_ID" --json 2>/dev/null \
    | uv run --no-project python -c "import json,sys
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

   Severity → action map for the parsed findings:
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
### Goal Achievement: N/M truths verified
### Must Fix (N) | Should Fix (N) | Suggestions (N)
```

#### Re-verification (Only for Structural Fixes)

**Skip** when fixes were localized (terminology, error handling, test updates, minor bugs). Run tests + lint to confirm, proceed to Phase B.

**Re-verify** when fixes required new functionality, changed APIs, or significant new code paths: re-launch changes-review, fix new findings. Max 2 iterations before adding remaining issues to plan.
<!-- /CC-ONLY -->
<!-- CODEX-START
**⛔ If `PILOT_CHANGES_REVIEW_ENABLED` is `"false"` (from Step 0 — Step 1 was skipped),** skip this step entirely and proceed to Step 4 (Phase B).

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
