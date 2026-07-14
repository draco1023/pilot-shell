## Step 0: Permission Mode + Model Switching Pre-Flight

<!-- CC-ONLY -->
**0a. Permission mode.** Check if the spec_mode_guard hook injected a permission mode note. If you see a system-reminder containing "Current permission mode is", briefly warn the user:

> "Your current permission mode is **{mode}**. For uninterrupted `/spec` execution, **Bypass Permissions** mode is recommended (Shift+Tab to cycle). Proceeding — the workflow may pause for permission prompts."

Do not stop or wait for the user to switch. The user's mode choice is respected — bypass permissions is recommended, not required.

**0b. Automated model switching info (show this verbatim to the user).** Read the toggle and the configured model pair, then show the matching message:

```bash
echo "MODEL_SWITCH=${PILOT_MODEL_SWITCH_ENABLED:-true} PLAN_MODEL=${PILOT_PLAN_MODEL:-opus} EXEC_MODEL=${PILOT_EXEC_MODEL:-sonnet}"
```

Render the model names from those values: `PLAN_MODEL` `opus` → **Opus 4.8 (1M)**, `fable` → **Fable 5 (1M)**; `EXEC_MODEL` `sonnet` → **Sonnet 5 (1M)**, `opus` → **Opus 4.8 (1M)**.

- **If `MODEL_SWITCH` is `true` (default):**

  > ℹ️ Automated model switching is ON — planning runs on **{Plan Model}**, implementation & verification on **{Execution Model}**, automatically. This requires the **Opus Plan** model: if your status bar isn't already on it, run `/model opusplan` now (future sessions set this automatically). A **Fable 5** plan model is applied only during plan-mode windows, and an **Opus 4.8** execution model only during a running /spec — configure both in Pilot Console → Settings → Model Switching. On a single-model **Fable 5** session (`/model fable`), `/spec` runs the whole workflow on Fable instead. Prefer one model for everything? Disable **Model Switching** in the Console.

- **If `MODEL_SWITCH` is `false`:**

  > ℹ️ Model Switching is OFF — `/spec` runs entirely on your active `/model` choice (Pilot defaults it to **Opus 4.8 (1M)**; a saved **Fable 5** model is preserved).

We can only see the resolved execution-leg model — not whether it's really Opus Plan — so this is guidance, not a hard check. After showing the message, continue with the workflow.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Skip** — permission mode and model switching are not applicable in Codex CLI. Proceed directly to Step 1.
CODEX-END -->
