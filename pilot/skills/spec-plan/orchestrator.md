---
name: spec-plan
description: "Spec planning phase - explore codebase, design plan, get approval"
argument-hint: "<task description> or <path/to/plan.md>"
user-invocable: false
hooks:
  Stop:
    - command: uv run --no-project python "$HOME/.claude/hooks/spec_plan_validator.py"
---

# /spec-plan - Planning Phase

**Phase 1 of the /spec workflow.** Explores codebase, designs implementation plan, verifies it, gets user approval.

**Input:** Task description (new) or plan path (continue unapproved)
**Output:** Approved plan at `docs/plans/YYYY-MM-DD-<slug>.md`
<!-- CC-ONLY -->
**Next:** On approval → `Skill(skill='spec-implement', args='<plan-path>')`
<!-- /CC-ONLY -->
<!-- CODEX-START
**Next:** On approval → continue immediately with the `$spec-implement` skill instructions using arguments: `<plan-path>`.
CODEX-END -->

---

## ⛔ Critical Constraints

- **NO sub-agents during planning** except Step 10 (spec-review, when enabled in settings)
- **Run spec-review when enabled** — it runs for every feature spec when `$PILOT_SPEC_REVIEW_ENABLED` is not `"false"`. Context level is NOT a valid reason to skip. To disable, use Console Settings → Reviewers → Spec Review toggle.
- **NEVER write code during planning** — planning and implementation are separate phases
- **NEVER assume — verify by reading files**
- **ONLY stopping point is plan approval** — everything else is automatic. Never ask "Should I fix these?"
- **Re-read plan after user edits** — before asking for approval again
- **Plan file is source of truth** — survives across auto-compaction cycles
<!-- CC-ONLY -->
- **Quality over speed** — never rush due to context pressure
<!-- /CC-ONLY -->
<!-- CODEX-START
- **Bounded quality** — do enough verification to make the plan actionable, then draft it.
CODEX-END -->

<!-- CODEX-START

### Codex Planning Speed Contract

For Codex, quality means enough verified context to write an implementable plan, not exhaustive research. This block overrides broader "always" and "mandatory" exploration language in this skill and in the rules when they conflict.

- Reach a first complete plan draft before context reaches 35%.
- Use a bounded scan: at most one CodeGraph orientation call when runtime-code structure is unknown, plus one Semble intent search at most before asking or choosing. If either result is irrelevant, pivot immediately to direct file reads. Skip CodeGraph for docs, rules, markdown, config, UI copy, reviews of a known diff, or named paths.
- Ask at most one clarification/design batch before approval. If you can make a reversible assumption, document it under "Assumptions" or "Autonomous Decisions" and continue.
- Stop exploration once you can name the files, commands, tests, and user-visible checks for each task. Leave implementation-time details to task DoD.
- Do not wait for automated reviewer agents during Codex planning. Step 10 is self-review only until Codex-native review agents are available.
CODEX-END -->
