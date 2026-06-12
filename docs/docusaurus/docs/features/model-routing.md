---
sidebar_position: 5
title: Model Routing
description: Plan with Opus, implement with Sonnet - automatically, no manual switch.
---

# Model Routing

:::warning Claude Code only
Automated model switching is a Claude Code feature. It is not available in Codex CLI -- on Codex, set the model via `codex --model <name>` or in `~/.codex/config.toml`, and `/spec` runs on whatever model is active.
:::

Opus reasons better; Sonnet is faster and cheaper. The cost-saving move is to plan on Opus, then drop to Sonnet for the mechanical implementation and verification that follow. Pilot does this **automatically** during `/spec` -- no manual `/model` step.

## How It Works

Pilot relies on Claude Code's **Opus Plan** model (`opusplan`): Opus while in plan mode, Sonnet otherwise. With **Model Switching** ON (the default), `/spec`:

1. Calls **EnterPlanMode** at the start of planning -> you're on **Opus** for the reasoning-heavy planning leg.
2. After you approve the plan, calls **ExitPlanMode** -> you drop to **Sonnet** automatically.
3. Runs implementation and verification on **Sonnet**, continuously, in the same session.

There is no pause, no handoff message, and no `/clear` + re-invoke. You approve the plan and implementation begins.

## Set the Opus Plan Model

For automated switching to work, your session must be on the `opusplan` model:

```text
/model opusplan
```

Pilot writes this into `~/.claude/settings.json` during install and whenever Console settings change via `pilot sync-env`, so future sessions start on `opusplan` automatically.

`/spec` checks your model before planning and behaves differently per model:

- **On a wrong, identifiable model** (e.g. plain **Opus**): `/spec` **hard-blocks** and tells you to run `/model opusplan`. Before plan mode, `opusplan` resolves to Sonnet -- so being on Opus means you never switched.
- **On Sonnet**: allowed. Pilot can't tell `opusplan`'s Sonnet leg from plain Sonnet, so it presumes you're correct rather than false-block every valid user.
- **On Fable 5 / Mythos 5** (`fable`, `mythos`, `claude-fable-5`, `claude-mythos-5`, `best`): allowed in BOTH toggle states -- see [Fable 5](#fable-5) below.

With **Model Switching OFF**, the check flips: `/spec` requires **Opus** (only Opus may enter plan mode; Fable-family models also pass) and hard-blocks any other model. Resuming an existing plan (`/spec <path/to/plan.md>`) skips the check on any model.

## Fable 5

[Claude Fable 5](https://www.anthropic.com/news/claude-fable-5-mythos-5) is Anthropic's frontier model (`/model fable`, or `fable[1m]` for the 1M window). There is **no `fableplan`** -- no Fable equivalent of `opusplan` exists (for now), so automated model switching does not apply. Pilot is fully Fable-aware instead:

- **`/spec` runs single-model on Fable**, in both Model Switching states. The planning skills detect a Fable session and skip `EnterPlanMode`/`ExitPlanMode` entirely -- plan, implement, and verify all run on Fable with no model toggling and no `/model opusplan` block.
- **Your saved Fable model is preserved.** `ANTHROPIC_MODEL` (env) outranks the saved `model` field in `~/.claude/settings.json`, so Pilot removes its own `ANTHROPIC_MODEL` override instead of writing it when your saved model is Fable-family -- on installs, on Console settings changes (`pilot sync-env`), and healed on every `pilot` startup.
- **1M context stays available.** `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` removes 1M variants from the model picker, which would break `fable[1m]` -- Pilot forces it to `false` whenever a Fable-family model is selected, regardless of the Context Window settings below.
- **Statusline and Console Usage** display "Fable 5" / "Mythos 5" with the announced $10/$50 per-MTok pricing.

Note: Fable 5 ships with safety classifiers; flagged requests (mostly cybersecurity/biology) are re-run on Opus 4.8 by Claude Code itself with a transcript notice -- that fallback is Claude Code behavior, not Pilot's (see the [model configuration docs](https://code.claude.com/docs/en/model-config), "Automatic model fallback").

## Quick Mode (Outside /spec) -- Default is Sonnet

`opusplan` resolves to **Sonnet** whenever you are *not* in plan mode. This means regular quick-mode prompts -- everything outside `/spec` and `/fix` planning -- run on Sonnet, not Opus.

This is by design: the model exists specifically to power the planning leg of the spec workflow, not to make Opus the default for all interactions.

**If you want Opus for a quick-mode task**, switch manually:

```text
/model opus[1m]
```

Switch back to `opusplan` before the next `/spec` run:

```text
/model opusplan
```

:::tip Summary
- `opusplan` on = `/spec` and `/fix` plan on Opus, everything else on Sonnet.
- For ad-hoc Opus work outside those workflows, switch to `opus[1m]` for that session.
:::

## Turning It Off -- Opus Everywhere

Turn off **Model Switching** in Console Settings -> Automation to run the entire `/spec` workflow on Opus. Pilot then patches `~/.claude/settings.json` to `opus[1m]` (when Opus context window is 1M) or `opus` (200K) and never enters plan mode for model switching -- plan -> implement -> verify all run on Opus. Choose this if you prefer maximum reasoning quality over cost, or for headless / CI runs.

## Context Window

Each model can run with a **1M** or **200K** context window, independently:

| Model | Default | Notes |
|-------|---------|-------|
| **Opus** | 1M | Safe for all Claude Code subscription tiers. |
| **Sonnet** | 200K | Safe default. Sonnet 1M requires API, Team, or Enterprise; on Max it works for some accounts but not all. |

Pilot manages three env vars in `~/.claude/settings.json` based on your choice:

- `ANTHROPIC_DEFAULT_OPUS_MODEL` -- `claude-opus-4-8[1m]` (1M) or `claude-opus-4-8` (200K)
- `ANTHROPIC_DEFAULT_SONNET_MODEL` -- `claude-sonnet-4-6[1m]` (1M) or `claude-sonnet-4-6` (200K)
- `CLAUDE_CODE_DISABLE_1M_CONTEXT` -- `true` only when **both** models are set to 200K (and never while a Fable-family model is your saved default -- see [Fable 5](#fable-5))

**To change the context window:** Console Settings -> Automation -> Context Window. Click Save -- the change propagates immediately via `pilot sync-env`.

**If a session errors with "model not available":** lower that model's context window to 200K in Console Settings.

**Sub-agents** (`spec-review`) are pinned to the base Sonnet model and do not use the 1M context window regardless of this setting. The changes review runs as the built-in `/code-review` skill on the session model (xhigh effort), so it follows the active model and context window.

## Default-On

Automated model switching is **ON for every install** (a one-time migration enables it for existing users too). The first time you launch after upgrading, Pilot shows a one-time announcement explaining the change and how to disable it. The reviewer sub-agent (`spec-review`) always runs on Sonnet -- sub-agents do not support the 1M context window; the changes review runs as the built-in `/code-review` skill on the session model.
