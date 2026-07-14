## Step 0: Setup, Process Overview, & Runtime Classification

### 0.1 Read Toggle Configuration

**Run first, before any other step.** Read the reviewer toggle env vars:

<!-- CC-ONLY -->
```bash
echo "REVIEWER=$PILOT_CHANGES_REVIEW_ENABLED CODEX_CHG=$PILOT_CODEX_CHANGES_REVIEW_ENABLED SPEC_MODE=$PILOT_SPEC_CODE_REVIEW_MODE"
```

Codex reviewers are controlled entirely by Console Settings — the env vars are authoritative. `SPEC_MODE` is the configured changes-review mechanism for `/spec` (`agent` = single `changes-review` sub-agent; `medium`/`high`/`xhigh` = built-in `/code-review` skill at that effort; default `agent` when unset/invalid — allow-listed at the points of use in Steps 1 and 3).

Reference these values in Steps 1 (agent-mode + Codex companion launch) and 3 (review collection).

**Open the execution model window (best-effort).** When the Execution Model is Opus (Console → Settings → Model Switching, requires a Fable plan model), the sonnet-slot pin must apply for the verification leg. A resumed `/spec <plan.md>` that skipped plan mode never fired the window-opening hook, so open it explicitly. Idempotent, no-op unless config + the registered plan call for it; it closes when this skill later registers the plan `VERIFIED`:

```bash
~/.pilot/bin/pilot model-pin exec-enter --session "${PILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-default}}}" 2>/dev/null || true
```
<!-- /CC-ONLY -->
<!-- CODEX-START
```bash
echo "REVIEWER=$PILOT_CHANGES_REVIEW_ENABLED"
```

Native Codex changes review is controlled by the regular reviewer toggle. Reference this value in Steps 1 and 3.
CODEX-END -->

### 0.2 Process Overview

<!-- CC-ONLY -->
```
Phase A — Finalize the code:
  Launch changes-review sub-agent (agent mode) + Codex companion (if enabled) → Automated Checks (tests + lint + verify commands + Plan Compliance & Goal-Truth Audit) → Feature Parity (if migration) → Collect review results (agent findings OR inline /code-review at the configured effort) + Collect Codex Results → Fix

Phase B — Verify the running program (depth depends on runtime profile):
  Build → Program Execution → Per-Task DoD Audit → E2E

Final:
  Regression check → Worktree sync → Post-merge verification → Update status
```
<!-- /CC-ONLY -->
<!-- CODEX-START
```
Phase A — Finalize the code:
  Launch Reviewer → Automated Checks (tests + lint + verify commands) → Feature Parity (if migration) → Collect Review Results → Fix

Phase B — Verify the running program (depth depends on runtime profile):
  Build → Program Execution → Per-Task DoD Audit → E2E

Final:
  Regression check → Worktree sync → Post-merge verification → Update status
```
CODEX-END -->

### 0.3 Classify Runtime Profile

**Determine verification depth based on what changed:**

| Profile | Criteria | Phase B Scope |
|---------|----------|---------------|
| **Minimal** | No server, no UI, no built artifacts (libraries, CLI tools, hooks, scripts) | Build check only |
| **API** | Server/API but no frontend changes | Build + program execution + DoD audit. Skip E2E. |
| **Full** | Frontend/UI changes or complex deployment | All Phase B steps |

Read the plan's Runtime Environment section (if present) and the changed file types to classify.
