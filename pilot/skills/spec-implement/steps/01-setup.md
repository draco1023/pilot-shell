## Step 1: Setup — Read Plan, Detect Worktree, Set Up Task List

<!-- CC-ONLY -->
### 1.0 Plan Mode Exit Guard (MANDATORY safety net)

**⛔ This is the very first action — before reading the plan or doing any other work.**

`spec-plan` should have called `ExitPlanMode` before invoking this skill. If it didn't (model skip, approval edge case, etc.), you are still on Opus in plan mode and implementation will run on the wrong model. Exit now.

```bash
echo "MODEL_SWITCH=${PILOT_MODEL_SWITCH_ENABLED:-true}"
SPEC_SESS="${PILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-default}}}"
[ -f "$HOME/.pilot/sessions/$SPEC_SESS/plan-mode-skipped-fable" ] && echo "ON_FABLE=true" || echo "ON_FABLE=false"
```

**If `ON_FABLE=true`:** skip this guard entirely even when `MODEL_SWITCH=true` — the planning leg ran on a single-model Fable session (a saved `/model fable`), `EnterPlanMode` was never called, and there is no plan mode to exit. Proceed to 1.1.

**Otherwise, if `MODEL_SWITCH=true`:**
```
ToolSearch(query="select:ExitPlanMode")   # deferred — load schema first
ExitPlanMode(...)                          # safe to call even if already exited; exits plan mode → Sonnet
```

- If `ToolSearch` returns no tool: emit one visible line ("ExitPlanMode unavailable — implementation will run on current model") and continue.
- If `MODEL_SWITCH=false`: skip entirely — no plan mode was entered. (Unset defaults to `true`, matching the plan-side default, so the ExitPlanMode safety net still fires.)

**Do NOT skip this step to save tokens. An extra ExitPlanMode call costs nothing; running the entire implementation leg on Opus is expensive and wrong.**
<!-- /CC-ONLY -->

### 1.0b Open the execution model window (best-effort)

When the Execution Model is Opus (Console → Settings → Model Switching, requires a Fable plan model), the sonnet-slot pin must apply for the implementation + verification legs. `ExitPlanMode` above already opened this window via the plan-mode hook, but a resumed session (`/spec <plan.md>` that skips plan mode) never fires that hook, so open it explicitly here. Idempotent and no-op unless config + the registered plan call for it:

```bash
~/.pilot/bin/pilot model-pin exec-enter --session "${PILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-default}}}" 2>/dev/null || true
```

The window closes automatically when `spec-verify` registers the plan `VERIFIED` (or at session end / by the PID sweep) — no manual close needed here.

### 1.1 Read Plan & Gather Context

1. **Read the COMPLETE plan** — understand architecture and design
2. **Summarize understanding** — demonstrate comprehension
3. **Check current state:** `git status --short`, `git diff --name-only`, plan progress (`[x]` vs `[ ]`)

<!-- CC-ONLY -->
**Research tools during implementation:** CodeGraph (`codegraph_explore(query=...)` — one call orients on the task, returns deep source, and gives callers + blast radius before you modify a shared or non-trivial function), Context7 (library docs), Semble `semble search` or `mcp__semble__search` (find patterns by intent), `semble find-related` (discover parallel implementations), grep-mcp (production examples).

**Before modifying a shared or non-trivial function:** run `codegraph_explore(query="<fn> callers and impact")` — its response includes the call path and blast radius, catching callers you'd otherwise miss. A self-contained local function the plan already isolated doesn't need it.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Research tools during implementation:** Use CodeGraph for structural runtime-code questions (`codegraph_explore(query=...)` — one call orients, returns known-symbol source, and gives callers + blast radius before a non-local change), Context7 for library docs, Semble for intent/pattern discovery, and grep-mcp for production examples.

**Codex proportionality:** Skip CodeGraph for docs, rules, markdown, config, UI copy, test-only edits, or named-path local changes unless the call graph itself is the uncertainty. Before modifying a runtime function with non-local effects, run `codegraph_explore(query="<fn> callers")`; for a local function already isolated by the plan and targeted reads, do not add graph calls just to satisfy a checklist.
CODEX-END -->

### 1.2 Detect or Resume Worktree (Conditional)

**Read `Worktree:` header from plan.** If `No` or missing: skip to 1.3.

**If `Worktree: Yes`:**

1. Extract plan slug: `docs/plans/2026-02-09-add-auth.md` → `add-auth`
2. Detect: `~/.pilot/bin/pilot worktree detect --json <plan_slug>`
3. **If found:** `cd` to the worktree `path`
4. **If not found:** Create as fallback:
   ```bash
   ~/.pilot/bin/pilot worktree create --json <plan_slug>
   ```
   Copy plan file into worktree if needed. `cd` to worktree path.
5. If creation fails (old git): continue without worktree.
6. Verify: `git branch --show-current` should show `spec/<plan_slug>`

All subsequent work happens inside the worktree directory.

### 1.3 Set Up Task List (MANDATORY)

<!-- CC-ONLY -->
1. **Check existing:** `TaskList` — if tasks exist from prior session, resume (don't recreate)
2. **If empty:** Create one task per uncompleted `[ ]` plan task:
   ```
   TaskCreate(subject="Task N: <title>", description="<objective>", activeForm="Implementing <desc>")
   ```
   Set dependencies: `TaskUpdate(taskId="...", addBlockedBy=["..."])`
3. Skip `[x]` (already completed) tasks
<!-- /CC-ONLY -->
<!-- CODEX-START
1. List uncompleted `[ ]` plan tasks — these are your work items.
2. Track progress by updating plan checkboxes (`[ ]` → `[x]`) after each task.
3. Skip `[x]` (already completed) tasks.
CODEX-END -->
