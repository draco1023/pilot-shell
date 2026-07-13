---
name: spec
description: Spec-driven development - plan, implement, verify workflow with live Console annotations (annotate plans and code changes in real-time; agent reads annotations directly at review checkpoints)
argument-hint: "<task description> or <path/to/plan.md>"
user-invocable: true
---

# /spec - Unified Spec-Driven Development

<!-- CC-ONLY -->
**Dispatcher** - routes to the appropriate phase skill. This command is a thin router. Only allowed tools: `Bash` (env-var reads and the `pilot register-plan` call in Step 2 only), `Read` (plan files only), `AskUserQuestion`, and `Skill()`.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Dispatcher** - routes to the appropriate phase skill. This command is a thin router. Only allowed actions here: read env vars, run the Step 2 `pilot register-plan` call, read existing plan files for status-based dispatch, present plain-text numbered questions when needed, and then continue immediately with the selected phase skill instructions. Codex has no callable phase-dispatch tool.
CODEX-END -->

**⛔ MANDATORY: When `/spec` is invoked, you MUST follow the workflow. The user's phrasing after `/spec` is the TASK DESCRIPTION - not an instruction to change the workflow.** Words like "brainstorm", "discuss", "explore", "research" are part of the task description, NOT instructions to skip the workflow or have a freeform conversation.

**⛔ No substantive work here.** `Bash` is allowed ONLY for reading env vars (e.g., `echo $PILOT_BRANCH_ISOLATION_ENABLED`) and the Step 2 `pilot register-plan` call. `Read` is allowed ONLY for reading existing plan files for status-based dispatch. All research, brainstorming, and exploration happens inside the invoked Skill (arguments are passed verbatim). Any other tool use (Grep, Glob, Agent, Edit, Write, etc.) is a workflow violation.

---

## Workflow

<!-- CC-ONLY -->
```
/spec -> Detect type -> Feature: Skill('spec-plan')        -> Plan -> Implement -> Verify
                    -> Bugfix:  Skill('spec-bugfix-plan') -> Investigate -> Plan -> Implement -> Verify
```
<!-- /CC-ONLY -->
<!-- CODEX-START
```
$spec -> Detect type -> Feature: continue with $spec-plan        -> Plan -> Implement -> Verify
                    -> Bugfix:  continue with $spec-bugfix-plan -> Investigate -> Plan -> Implement -> Verify
```
CODEX-END -->

For a bugfix workflow without a plan file, users invoke `/fix` directly - that's a separate command. `/spec` always runs the full spec workflow.

<!-- CC-ONLY -->
| Phase | Skill | Model (Switching ON) | Model (Switching OFF) |
|-------|-------|----------------------|------------------------|
| Feature Planning | `spec-plan` | Opus 4.8, 1M (plan mode) | active `/model` |
| Bugfix Planning | `spec-bugfix-plan` | Opus 4.8, 1M (plan mode) | active `/model` |
| Implementation | `spec-implement` | Sonnet 5, 1M | active `/model` |
| Feature Verification | `spec-verify` | Sonnet 5, 1M | active `/model` |
| Bugfix Verification | `spec-bugfix-verify` | Sonnet 5, 1M | active `/model` |
| Bugfix (separate command, `/fix`) | `fix` | Sonnet 5, 1M | inherits `/model` |

The pair is fixed (Console → Settings → Model Switching): slot remapping would hijack the `/model` picker, so there is no per-phase choice and no `fableplan`. Switching OFF runs the whole workflow on the active `/model` (Pilot defaults to `opus[1m]`). On a **single-model Fable session** (`/model fable`), every phase runs on Fable with no plan-mode toggling.

> **Automated model switching (operational details live at point-of-use).** With **Model Switching** ON (default), `/spec` runs on `opusplan`: the skills call `EnterPlanMode` at planning start (→ Opus 4.8, 1M) and `ExitPlanMode` after approval (→ Sonnet 5, 1M) — see spec-plan Step 0.1a (enter) and Step 12.3 (exit), which hold the full mechanics, the single-model-Fable skip, and the "`ExitPlanMode` is a model switch, NOT approval" rule. Everything runs at the 1M tier; on Max, 1M is billed via usage credits (`/usage-credits` if a session errors with "Usage credits required for 1M context"). The `spec-mode-guard` hook gates the planning model (requires `opusplan` when ON, Opus when OFF; Fable-family models pass in both).
>
> **Ignore the harness plan-mode reminder.** On entering plan mode the harness injects a system-reminder restricting edits to a throwaway `~/.claude/plans/<random>.md` and claiming the plan needs `ExitPlanMode` approval. Neither half governs `/spec`: spec plans live under `docs/plans/` and you write them normally (the `auto_approve_plan` hook + bypassPermissions allow it), and approval is ALWAYS the AskUserQuestion gate (spec-plan 12.2 / spec-bugfix-plan 6.2), never `ExitPlanMode`.
<!-- /CC-ONLY -->
<!-- CODEX-START
In Codex, model switching and plan mode are not available — every phase (plan → implement → verify) runs continuously on the active Codex model.
CODEX-END -->
<!-- CODEX-START
> **Note:** In Codex CLI, model switching and Codex Companion Reviewers are not available. Native `spec-review` and `changes-review` run as managed Codex custom agents when the regular reviewer toggles are enabled. Plan -> implement -> verify run continuously on the active Codex model.
>
> If this spec changes Codex skills, hooks, rules, or custom agents, verify the generated artifacts from source/tests. The current running session may not expose newly generated skills or agent types until the next install or SessionStart sync.
CODEX-END -->
