---
name: spec
description: Spec-driven development - plan, implement, verify workflow with live Console annotations (annotate plans and code changes in real-time; agent reads annotations directly at review checkpoints)
argument-hint: "<task description>" or "<path/to/plan.md>"
user-invocable: true
---

# /spec - Unified Spec-Driven Development

<!-- CC-ONLY -->
**Dispatcher** — routes to the appropriate phase skill. This command is a thin router. Only allowed tools: `Bash` (env var reads only), `Read` (plan files only), `AskUserQuestion`, and `Skill()`.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Dispatcher** — routes to the appropriate phase skill. This command is a thin router. Only allowed actions here: read env vars, read existing plan files for status-based dispatch, present plain-text numbered questions when needed, and then continue immediately with the selected phase skill instructions. Codex has no callable phase-dispatch tool.
CODEX-END -->

**⛔ MANDATORY: When `/spec` is invoked, you MUST follow the workflow. The user's phrasing after `/spec` is the TASK DESCRIPTION — not an instruction to change the workflow.** Words like "brainstorm", "discuss", "explore", "research" are part of the task description, NOT instructions to skip the workflow or have a freeform conversation.

**⛔ No substantive work here.** `Bash` is allowed ONLY for reading env vars (e.g., `echo $PILOT_BRANCH_ISOLATION_ENABLED`). `Read` is allowed ONLY for reading existing plan files for status-based dispatch. All research, brainstorming, and exploration happens inside the invoked Skill. Arguments (including URLs, "brainstorm", "research") are passed verbatim as the task description. Any other tool use (Grep, Glob, Task, Edit, Write, etc.) is a workflow violation.

---

## Workflow

<!-- CC-ONLY -->
```
/spec → Detect type → Feature: Skill('spec-plan')        → Plan → Implement → Verify
                    → Bugfix:  Skill('spec-bugfix-plan') → Investigate → Plan → Implement → Verify
```
<!-- /CC-ONLY -->
<!-- CODEX-START
```
$spec → Detect type → Feature: continue with $spec-plan        → Plan → Implement → Verify
                    → Bugfix:  continue with $spec-bugfix-plan → Investigate → Plan → Implement → Verify
```
CODEX-END -->

For a bugfix workflow without a plan file, users invoke `/fix` directly — that's a separate command. `/spec` always runs the full spec workflow.

| Phase | Skill | Model |
|-------|-------|-------|
| Feature Planning | `spec-plan` | inherits `/model` (recommend Opus) |
| Bugfix Planning | `spec-bugfix-plan` | inherits `/model` (recommend Opus) |
| Implementation | `spec-implement` | inherits `/model` |
| Feature Verification | `spec-verify` | inherits `/model` |
| Bugfix Verification | `spec-bugfix-verify` | inherits `/model` |
| Bugfix (separate command, `/fix`) | `fix` | inherits `/model` |

<!-- CC-ONLY -->
> **Note:** Every phase runs on the model the user has currently selected via Claude Code's `/model` command. The `spec-mode-guard` hook blocks `/spec` invocations when the active model is not Opus (planning's reasoning hop benefits most from Opus). With the **Model Switching** toggle ON (default), the planner stops after approval so you can run `/model <sonnet|sonnet[1m]|opus|opus[1m]>` and then type any prompt (e.g. `continue`) to resume — the `spec_handoff_resume` hook routes the next prompt directly to `spec-implement`, with no `/clear` and no `/spec <plan-path>` re-invocation. With it OFF, plan → implement → verify run continuously on whichever model is active. Sub-agents (`spec-review`, `changes-review`, `web-search-agent`) are hard-coded to Sonnet because sub-agents do not support 1M context.
<!-- /CC-ONLY -->
<!-- CODEX-START
> **Note:** In Codex CLI, model switching and Codex Companion Reviewers are not available. Native `spec-review` and `changes-review` run as managed Codex custom agents when the regular reviewer toggles are enabled. Plan → implement → verify run continuously on the active Codex model.
>
> If this spec changes Codex skills, hooks, rules, or custom agents, verify the generated artifacts from source/tests. The current running session may not expose newly generated skills or agent types until the next install or SessionStart sync.
CODEX-END -->
