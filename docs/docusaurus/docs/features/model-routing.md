---
sidebar_position: 5
title: Model Routing
description: Plan with Opus, implement with Sonnet — automatically, no manual switch.
---

# Model Routing

:::warning Claude Code only
Automated model switching is a Claude Code feature. It is not available in Codex CLI — on Codex, set the model via `codex --model <name>` or in `~/.codex/config.toml`, and `/spec` runs on whatever model is active.
:::

Opus reasons better; Sonnet is faster and cheaper. The cost-saving move is to plan on Opus, then drop to Sonnet for the mechanical implementation and verification that follow. Pilot does this **automatically** during `/spec` — no manual `/model` step.

## How It Works

Pilot relies on Claude Code's **Opus Plan** model (`opusplan`): Opus while in plan mode, Sonnet otherwise. With **Model Switching** ON (the default), `/spec`:

1. Calls **EnterPlanMode** at the start of planning → you're on **Opus** for the reasoning-heavy planning leg.
2. After you approve the plan, calls **ExitPlanMode** → you drop to **Sonnet** automatically.
3. Runs implementation and verification on **Sonnet**, continuously, in the same session.

There is no pause, no handoff message, and no `/clear` + re-invoke. You approve the plan and implementation begins.

## Set the Opus Plan Model

For automated switching to work, your session must be on the `opusplan` model:

```text
/model opusplan
```

Pilot writes this into `~/.claude/settings.json` during install and whenever Console settings change via `pilot sync-env`, so future sessions start on `opusplan` automatically.

`/spec` checks your model before planning and behaves differently per model:

- **On a wrong, identifiable model** (e.g. plain **Opus**): `/spec` **hard-blocks** and tells you to run `/model opusplan`. Before plan mode, `opusplan` resolves to Sonnet — so being on Opus means you never switched.
- **On Sonnet**: allowed. Pilot can't tell `opusplan`'s Sonnet leg from plain Sonnet, so it presumes you're correct rather than false-block every valid user.

With **Model Switching OFF**, the check flips: `/spec` requires **Opus** (only Opus may enter plan mode) and hard-blocks any other model. Resuming an existing plan (`/spec <path/to/plan.md>`) skips the check on any model.

## Turning It Off — Opus Everywhere

Turn off **Model Switching** in Console Settings → Automation to run the entire `/spec` workflow on Opus. Pilot then patches `~/.claude/settings.json` to `opus[1m]` and never enters plan mode for model switching — plan → implement → verify all run on Opus. Choose this if you prefer maximum reasoning quality over cost, or for headless / CI runs.

## Default-On

Automated model switching is **ON for every install** (a one-time migration enables it for existing users too). The first time you launch after upgrading, Pilot shows a one-time announcement explaining the change and how to disable it. Reviewer sub-agents (`spec-review`, `changes-review`) always run on Sonnet — sub-agents do not support the 1M context window.
