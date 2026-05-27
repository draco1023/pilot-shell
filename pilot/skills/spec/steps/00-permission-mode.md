## Step 0: Permission Mode Pre-Flight Check

<!-- CC-ONLY -->
**Before proceeding, check if the spec_mode_guard hook injected a permission mode note.** If you see a system-reminder containing "Current permission mode is", briefly warn the user:

> "Your current permission mode is **{mode}**. For uninterrupted `/spec` execution, **Bypass Permissions** mode is recommended (Shift+Tab to cycle). Proceeding — the workflow may pause for permission prompts."

**Then continue with the workflow.** Do not stop or wait for the user to switch. The user's mode choice is respected — bypass permissions is recommended, not required.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Skip** — permission mode checks are not applicable in Codex CLI. Proceed directly to Step 1.
CODEX-END -->
