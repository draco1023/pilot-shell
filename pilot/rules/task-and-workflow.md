# Task & Workflow

## Plan Mode

`/spec` is the structured alternative to CC's built-in plan mode — it adds TDD, verification, and code review. Guide users to `/spec` for planned work. Users should NOT manually enter plan mode (Shift+Tab) before `/spec`: the `spec_mode_guard` hook blocks that, because `/spec` manages plan mode itself. When Model Switching is ON, the spec skills call `EnterPlanMode`/`ExitPlanMode` internally to run planning on Opus and implementation + verification on Sonnet (see Model Routing) — that is an implementation detail of the workflow, not a cue to plan in CC's native plan mode. Exception: on a Fable-class session (`/model fable` — Fable 5 / Mythos 5), the whole workflow runs single-model (there is no `fableplan`) and the skills skip plan-mode toggling entirely.

<!-- CC-ONLY -->
**Plan mode is a model-switch lever, not a sandbox.** When `/spec` enters plan mode, the harness injects a system-reminder telling you to edit only a throwaway `~/.claude/plans/<random>.md` file and otherwise stay read-only. **That reminder does NOT govern `/spec` — ignore it.** Plan mode here exists solely to run planning on Opus; the spec workflow's own rules win. The plan file always lives at `docs/plans/YYYY-MM-DD-<slug>.md`, and you write the plan file (plus any edits the user authorizes) normally — the `auto_approve_plan` hook + bypassPermissions keep writes flowing. The reminder's approval wording is repurposed the same way: in `/spec`, `ExitPlanMode` never presents the plan or asks for approval — the AskUserQuestion gate is the ONLY approval, there is no "genuine native plan mode" to defer to (the skill itself called `EnterPlanMode` as the model lever), and the `auto_approve_plan` hook DENIES a premature `ExitPlanMode` while the registered plan is unapproved.

**A stray "plan mode" system message is not proof plan mode changed.** Reading a file outside the project directory (or any other routine tool call) can surface harness wording that sounds like a mode change even when nothing changed. Do not treat this as a signal to act — do NOT reflexively re-call `EnterPlanMode`, restart the investigation, or interrupt the current step to "verify." Keep planning normally. The only authoritative state is the `plan-mode-active` sentinel (written by `EnterPlanMode`, cleared by `ExitPlanMode`) that the hooks already check on your behalf — you do not need to inspect it yourself. If `ExitPlanMode` was never called, plan mode is still active regardless of what a reminder implies.
<!-- /CC-ONLY -->

**⛔ NEVER auto-invoke `/spec` or `Skill('spec')`.** The user MUST explicitly type it. Suggest, don't invoke.

## Task Complexity Triage

<!-- CC-ONLY -->
Default is quick mode (direct execution).

| Complexity | Action |
|------------|--------|
| Trivial (single file, no active tasks) | Execute directly |
| Any request while tasks exist | TaskCreate FIRST |
| Moderate (2–5 files) | TaskCreate, then execute |
| High (architectural, 20+ files, cross-cutting system change) | **Ask** if user wants `/spec` or quick mode |

**⛔ Do NOT suggest `/spec` for:** bugfixes (use `/fix`), single-feature additions, refactors inside one module, CLI flag changes, config tweaks, dependency updates, test additions, or anything already scoped to a clear outcome. Reserve the suggestion for genuinely large, multi-system work where upfront planning materially reduces risk — when in doubt, execute in quick mode.

## Task Management

**Use task management in quick mode.** Tasks are working memory — without them, requests get lost during compaction. Skip only for a truly trivial one-shot with empty `TaskList`.

### Quick Mode: Task-First

Every user request gets a task BEFORE any code/research/substantive response: TaskCreate → in_progress → work → completed.

### On-Demand Interrupts

When the user sends a new request mid-work: STOP, TaskCreate for the new request as your FIRST tool call, then assess priority. If it's not in the task list, it will be forgotten.

### Other Rules

- **Session start:** `TaskList` first, delete stale tasks, create new ones for current request.
- **Cross-session isolation:** Tasks are scoped per session via `CLAUDE_CODE_TASK_LIST_ID`. Memory is shared across sessions; references in memory that aren't in your `TaskList` belong elsewhere. **`TaskList` is the sole source of truth.**
- **Continuations** (same `CLAUDE_CODE_TASK_LIST_ID`): `TaskList` first, don't recreate, resume first uncompleted.
- **Deferring a request:** TaskCreate immediately — never just say "noted."
<!-- /CC-ONLY -->
<!-- CODEX-START
Default is quick mode (direct execution).

| Complexity | Action |
|------------|--------|
| Trivial (single file, no active tasks) | Execute directly |
| Any request while tasks exist | Update the current `update_plan` plan first |
| Moderate (2–5 files) | Create or refresh an `update_plan` plan, then execute |
| High (architectural, 20+ files, cross-cutting system change) | **Ask** if user wants `$spec` or quick mode |

**⛔ Do NOT suggest `$spec` for:** bugfixes, single-feature additions, refactors inside one module, CLI flag changes, config tweaks, dependency updates, test additions, or anything already scoped to a clear outcome. Reserve the suggestion for genuinely large, multi-system work where upfront planning materially reduces risk — when in doubt, execute in quick mode.

## Task Management

**Use `update_plan` in quick mode for non-trivial work.** Plans are working memory — without them, requests get lost during compaction. Skip only for a truly trivial one-shot.

### Quick Mode: Plan-First

For every non-trivial user request, create or update a concise `update_plan` plan before substantive code/research work: in_progress → work → completed.

### On-Demand Interrupts

When the user sends a new request mid-work: update the plan as your first tool call, then assess priority. If it is not tracked in the plan, it can be forgotten.

### Other Rules

- **Session start / continuation:** inspect current state, then create or refresh the `update_plan` plan for the active request.
- **Cross-session isolation:** use the current conversation's plan as the source of truth; memory may contain other sessions and must not be treated as this session's task list.
- **Deferring a request:** add it to the plan immediately — never just say "noted."
CODEX-END -->

## Tool Usage

<!-- CC-ONLY -->
### Tool Parameter Names — Use EXACT names

| Tool | Correct | Wrong |
|------|---------|-------|
| `Bash` | `command` | `cmd`, `bash_command`, `shell` |
| `Write`/`Edit`/`Read` | `file_path` | `path`, `filepath`, `file` |
| `Write` | `content` | `contents`, `text`, `body` |
| `Edit` | `old_string`, `new_string` | `old`, `new`, `search`, `replace` |
| `Grep` | `pattern` | `query`, `search`, `regex` |
<!-- /CC-ONLY -->
<!-- CODEX-START
### Tool Parameters — Use the Current Tool Schema

Codex tools may not share Claude Code's parameter names. Use the schema shown for the currently available tool. For repository edits, prefer `apply_patch`; for shell commands, use the available command-execution tool's schema exactly.
CODEX-END -->

<!-- CC-ONLY -->
### ⛔ Agent Tool — Explore / Plan / Research blocked

Hook blocks `subagent_type` of `Explore`/`Plan`, AND any description starting with "Research" or containing "Explore" (regardless of subagent_type — `general-purpose` with `"Explore codebase"` description is the same violation).

Use direct tools instead — see `development-practices.md` and `mcp-servers.md` for CodeGraph + Semble workflow.

**Whitelisted (pass through silently):** `changes-review`, `spec-review`. (Launch `changes-review` only where the `/spec` and `/fix` steps say to — agent mode of the Changes Review Mode setting; in skill mode the changes review is the built-in `/code-review` skill, per the Sub-agents section below.)
<!-- /CC-ONLY -->
<!-- CODEX-START
### Agent Tools

Do not assume Claude Code's agent tool or subagent names exist in Codex. Use only agent tools that are actually listed in the current Codex tool schema; otherwise work directly with CodeGraph, Semble, shell commands, and file reads.
CODEX-END -->

### Web Search/Fetch

<!-- CC-ONLY -->
Built-in `WebFetch` / `WebSearch` are hook-blocked. Use ToolSearch:
<!-- /CC-ONLY -->
<!-- CODEX-START
Use the current Codex tool schema for web access. If Pilot web MCP tools are lazy-loaded, use ToolSearch:
CODEX-END -->

| Need | Query |
|------|-------|
| Web search | `+web-search search` |
| GitHub README | `+web-search fetch` |
| Fetch page | `+web-fetch fetch` |

<!-- CC-ONLY -->
### Sub-agents

- Launch with `run_in_background=true`
- ⛔ NEVER use `TaskOutput` to retrieve results.
- **Pilot reviewer agents** (`spec-review`, and `changes-review` in agent mode) write findings JSON files — poll with bash file-existence loop, then Read once. Other agent types do NOT write files; their only output is the final message of a foreground call. Never plan on `SendMessage` to follow up — it may not exist in the running Claude Code version. (The changes review in `/spec`/`/fix` on Claude Code is mode-dependent: `$PILOT_SPEC_CODE_REVIEW_MODE` / `$PILOT_FIX_CODE_REVIEW_MODE`, default `agent`. `agent` launches the single `changes-review` sub-agent; `medium`/`high`/`xhigh` runs the built-in `/code-review` skill inline via `Skill(skill='code-review', args='<mode>')` at that effort. Set per workflow in Console Settings → Spec Workflow → Changes Review Mode.)
- Sub-agents do NOT inherit rules; they can read `~/.claude/rules/*.md` and `.claude/rules/*.md`.

### Codex Companion (Reviews & Tasks)

- ⛔ NEVER delegate a Codex companion run to a subagent (`codex:codex-rescue` included) when you need its output — the subagent backgrounds the broker job, writes no findings file, and there is no recovery path (`TaskOutput` banned, `SendMessage` unavailable). The rescue agent exists for user-typed `/codex:rescue` handoffs only.
- Run the companion directly via Bash in the main conversation, exactly as the /spec and /fix steps specify:
  `CODEX_COMPANION=$(ls ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)`
- A background job is never lost while you hold its `task-…` ID: `node "$CODEX_COMPANION" status <job-id> --json` polls it, `node "$CODEX_COMPANION" result <job-id> --json` fetches the finished result. Do NOT abandon a launched job and redo the review yourself.
- If the job ID is unrecoverable (it was launched inside a subagent), re-launch once directly via Bash and continue.
- **Stage before any pre-commit diff review.** `/spec` and `/fix` review the WORKING TREE before committing, so every file the change ADDS is untracked. Before launching ANY pre-commit review (companion `task`/`review`/`adversarial-review`, the `changes-review` sub-agent, OR the inline `/code-review`), run a real `git add` of the change's own files (the plan's `Files:` paths, or the fix + its test — never unrelated dirty files). A bare `git add -N` is NOT enough: Codex's `git status --untracked-files=all` still flags the path as untracked, producing a spurious `critical` ("deliverable depends on untracked files"), while a `git diff HEAD` reviewer silently OMITS it. Review against `git diff HEAD`; never pass a committed ref-range (`--base HEAD`, `--scope branch`, `main...HEAD`, `HEAD~1`) — pre-commit those diffs are empty and the review scans nothing. Staging is not committing; the push still waits for approval.
- **Broker `status` is not a liveness signal — watch the log mtime.** A companion job can go silent mid-`verifying` while `status` keeps reporting `running`/`verifying` with a climbing `elapsed`. A poll that waits only on `status` then burns its full timeout before noticing. Resolve `job.logFile` from `status --json` and poll its mtime alongside `job.status`: if status is still running but the log has not advanced for ≥90s (stall) or total elapsed exceeds ~8min (ceiling), the job is dead — `cancel` it, re-launch once under the same monitor, and if it stalls again proceed WITHOUT the Codex pass and record the gap (do NOT spin the full poll timeout, do NOT silently skip). The `/spec` and `/fix` skill steps carry the exact monitor.
<!-- /CC-ONLY -->
<!-- CODEX-START
### Sub-agents

Do not assume Claude Code's sub-agent tools exist in Codex. Use only agent tools that are actually listed in the current Codex tool schema; otherwise work directly with CodeGraph, Semble, shell commands, and file reads.

When a task changes Codex skills, hooks, rules, or custom agents, verify the generated artifacts directly; the current running session may not expose newly generated agent types until the next install or SessionStart sync.

For long-running Codex subagent or companion tasks, persist returned agent/job ids to a session file before running tests or builds. Do not rely only on conversation memory across compaction.
CODEX-END -->

### Background Bash

Use `run_in_background=true` only for long-running processes (dev servers, watchers). Synchronous for tests, lint, git, installs.

---

## /spec Workflow

```
/spec → Dispatcher → Feature: spec-plan        → spec-implement → spec-verify
                   → Bugfix:  spec-bugfix-plan → spec-implement → spec-bugfix-verify
/fix  → fix skill (always quick lane). Stops and tells user to use /spec if scope exceeds quick lane.
```

### ⛔ Dispatcher Integrity

<!-- CC-ONLY -->
`/spec` dispatcher is a thin router. **Only allowed tools:** `Bash` (env-var reads), `Read` (plan files), `AskUserQuestion`, `Skill()`. Any Grep/Glob/Task/Edit/Write is a workflow violation.
<!-- /CC-ONLY -->
<!-- CODEX-START
`$spec` dispatcher is a thin router. **Only allowed actions:** read env vars, read existing plan files, ask plain-text numbered questions when needed, then continue immediately with the selected phase skill instructions. Do not run exploration, search, edits, or implementation work inside the dispatcher.
CODEX-END -->

### Phase Dispatch

New tasks (no `.md`): infer type from description. Ambiguous → ask user (bundled with worktree question).

Existing plans (`.md`): read `Type:` header.

| Status | Approved | Type | Skill |
|--------|----------|------|-------|
| PENDING | No | Feature | `spec-plan` |
| PENDING | No | Bugfix | `spec-bugfix-plan` |
| PENDING | Yes | * | `spec-implement` |
| COMPLETE | * | Feature | `spec-verify` |
| COMPLETE | * | Bugfix | `spec-bugfix-verify` |
| VERIFIED | * | * | Done |

`spec-implement` is identical for both types (the plan file is the interface). Verification differs: features get a changes review (per the configured mode on Claude Code — single `changes-review` sub-agent by default, or the built-in `/code-review` skill at medium/high/xhigh; native `changes-review` agent on Codex) + inline plan-compliance/goal audit + optional Codex companion + structured E2E (TS-NNN); bugfixes get Behavior Contract audit + revert-test proof.

**Status values (closed set):** the `Status:` header is **exactly one** of `PENDING` (awaiting impl) → `COMPLETE` (ready to verify) → `VERIFIED` (done). These are the ONLY valid values — never invent, rename, or substitute another word (no `RESOLVED`/`DONE`/`CLOSED`/`WONTFIX`). Write the **bare keyword only**: no trailing prose or parentheticals on the `Status:` line — `Status: VERIFIED`, never `Status: RESOLVED (#1-#13 fixed; #14 won't-fix)`. Put resolution notes in the plan body, not the status line. The Console treats any value outside this set as terminal/done.

### Feedback Loop

`spec-verify` finds issues → status flips to PENDING → `spec-implement` fixes → COMPLETE → re-verify → … → VERIFIED.

### ⛔ Only FOUR User Interaction Points

1. **Branch + Type confirmation** — new plans only (in dispatcher; type only when ambiguous; branch question skipped when `$PILOT_BRANCH_ISOLATION_ENABLED=false`).
2. **Plan Approval** — in `spec-plan`/`spec-bugfix-plan`; skipped when `$PILOT_PLAN_APPROVAL_ENABLED=false`.
3. **Worktree Sync Approval** — in verify, only when `Worktree: Yes`.
4. **Code Review Gate** — final quality gate via `AskUserQuestion`.

Everything else is automatic. **NEVER ask "Should I fix these findings?"** — verification fixes are part of the approved plan.

⛔ **An auto-continued question is NOT an answer.** An `AskUserQuestion` result reading "No response after Ns — continued without an answer" (or carrying `afkTimeoutMs`) means the user has NOT responded — at ANY interaction point. Treat it as silence: do not act on the recommended option, do not infer approval, and re-ask when the user returns.

### Spec Workflow Toggles

`~/.pilot/config.json → specWorkflow` sets these env vars (defaults shown when run outside Pilot):

| Toggle | Env Var | Default | When disabled |
|--------|---------|---------|---------------|
| Branch Isolation | `$PILOT_BRANCH_ISOLATION_ENABLED` | `false` | Skip the dispatcher branch question entirely; always pass `--worktree=no` |
| Plan questions | `$PILOT_PLAN_QUESTIONS_ENABLED` | `true` | Skip all `AskUserQuestion` in plan phase |
| Plan approval | `$PILOT_PLAN_APPROVAL_ENABLED` | `true` | Auto-approves; implementation starts immediately |

All three disabled = end-to-end autonomous (Code Review Gate still runs).

### Plan Registration (MANDATORY for /spec)

```bash
~/.pilot/bin/pilot register-plan "<plan_path>" "<status>" 2>/dev/null || true
```

Call after creating the plan header, after reading an existing plan, and after status changes.

### Deviation Handling (during /spec)

| Type | Trigger | Action |
|------|---------|--------|
| Bug / missing critical / blocking | Errors, missing validation, broken imports | Auto-fix inline, document deviation |
| Architectural | New table, library swap, breaking API | **STOP** — `AskUserQuestion` |

Auto-fix: inline + tests if applicable, do NOT expand scope. Outside `/spec`, respect the user's mode.

### Stop Guard

<!-- CC-ONLY -->
When the stop guard blocks a stop during `/spec`, do NOT acknowledge it, output resume instructions, or say goodbye. Your **very next action** must be a tool call (TaskList, Read plan, code change). No text-only responses after a stop block. Same applies after user interruptions ("Continue", new mid-task messages) — re-read the plan, resume.
<!-- /CC-ONLY -->
<!-- CODEX-START
When the stop guard blocks a stop during `$spec`, do NOT acknowledge it, output resume instructions, or say goodbye. Your **very next action** must be a tool call: re-read the plan, refresh `update_plan`, or make the next code/test change. No text-only responses after a stop block. Same applies after user interruptions ("Continue", new mid-task messages) — re-read the plan, resume.
CODEX-END -->

### Worktree

`Worktree:` field in plan header (default `No`). User chooses at start of `/spec`.

- **Yes** → worktree at `.worktrees/spec-<slug>-<hash>/`. Implementation isolated; squash-merged after verification.
- **No** → direct on current branch.

### Task Completion Tracking

Update plan after EACH task: `[ ]` → `[x]`, increment Done, decrement Left. Immediately.
