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

Pilot writes this into `~/.claude/settings.json` during install and whenever Console settings change via `pilot sync-env`, so future sessions start on `opusplan` automatically. (There is no `opusplan[1m]` alias in Claude Code — see [Context Window](#context-window) for how 1M applies to each leg.)

`/spec` checks your model before planning and behaves differently per model:

- **On a wrong, identifiable model** (e.g. plain **Opus**): `/spec` **hard-blocks** and tells you to run `/model opusplan`. Before plan mode, `opusplan` resolves to Sonnet -- so being on Opus means you never switched.
- **On Sonnet**: allowed. Pilot can't tell `opusplan`'s Sonnet leg from plain Sonnet, so it presumes you're correct rather than false-block every valid user.
- **On Fable 5 / Mythos 5** (`fable`, `mythos`, `claude-fable-5`, `claude-mythos-5`, `best`): allowed in BOTH toggle states -- see [Fable 5](#fable-5) below.

With **Model Switching OFF**, the check flips: `/spec` requires **Opus** (only Opus may enter plan mode; Fable-family models also pass) and hard-blocks any other model. Resuming an existing plan (`/spec <path/to/plan.md>`) skips the check on any model.

## Troubleshooting: Planning Didn't Switch to Opus

The `opusplan` switch is performed by Claude Code, and Claude Code can decline it silently. If the statusline stays on **Sonnet** during planning -- or flips between Opus and Sonnet part-way through -- the usual causes are:

- **Opus usage-limit fallback** (Max plans). When your Opus pool is exhausted, `opusplan` serves Sonnet even in plan mode and switches back once the rolling limit window frees up. This is Claude Code behavior, not a Pilot bug -- check `/usage`. Because the window is rolling, it looks like "uneven" switching that engages mid-planning.
- **The session isn't on `opusplan`.** Run `/model opusplan` and start `/spec` again.
- **Asking the model doesn't work.** Models don't reliably know which model they are -- a planning leg genuinely running on Opus can still answer "Sonnet". Trust the statusline, not self-reports.

Pilot verifies the switch instead of assuming it: during the planning leg, the `plan_mode_tracker` hook compares the observed session model (from the statusline) against the expected Opus leg at your first plan-file write and injects a visible `PLANNING-LEG MODEL CHECK` warning -- naming the observed model, the likely cause, and the remedy -- when planning is not actually on Opus. No warning means the switch took effect.

## Fable 5

[Claude Fable 5](https://www.anthropic.com/news/claude-fable-5-mythos-5) is Anthropic's frontier model (`/model fable`, or `fable[1m]` for the 1M window). There is **no `fableplan`** -- no Fable equivalent of `opusplan` exists (for now), so automated model switching does not apply. Pilot is fully Fable-aware instead:

- **`/spec` runs single-model on Fable**, in both Model Switching states. The planning skills detect a Fable session and skip `EnterPlanMode`/`ExitPlanMode` entirely -- plan, implement, and verify all run on Fable with no model toggling and no `/model opusplan` block.
- **Your saved Fable model is preserved.** `ANTHROPIC_MODEL` (env) outranks the saved `model` field in `~/.claude/settings.json`, so Pilot removes its own `ANTHROPIC_MODEL` override instead of writing it when your saved model is Fable-family -- on installs, on Console settings changes (`pilot sync-env`), and healed on every `pilot` startup.
- **1M context stays available.** `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` removes 1M variants from the model picker, which would break `fable[1m]` -- Pilot forces it to `false` whenever a Fable-family model is selected, so `fable[1m]` always works.
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

Turn off **Model Switching** in Console Settings -> Automation to run the entire `/spec` workflow on Opus. Pilot then defaults `~/.claude/settings.json` to `opus[1m]` (Opus at 1M, the default everywhere now). It never writes an `ANTHROPIC_MODEL` pin, so a per-session `/model opus` (200K) still works -- but Pilot re-asserts `opus[1m]` as the default on the next settings write (install / upgrade / Console Save). Plan -> implement -> verify all run on Opus. Choose this if you prefer maximum reasoning quality over cost, or for headless / CI runs.

## Context Window

There is no per-model Context Window setting. Pilot persists the model alias by toggle state, and 1M applies **per model alias**, not globally:

| Toggle | Persisted model | Context window |
|--------|-----------------|----------------|
| **Model Switching ON** | `opusplan` | Sonnet 5 execution leg: **1M** (native). Opus planning leg: **200K**. |
| **Model Switching OFF** | `opus[1m]` | Opus 4.8: **1M**. |

The asymmetry comes from Claude Code's aliases: **`sonnet` already resolves to Sonnet 5 with a native 1M window** (no suffix needed), but **bare `opus` resolves to 200K** -- you need the `opus[1m]` alias to get Opus's 1M window. There is **no `opusplan[1m]` alias** (only `opus[1m]` and `sonnet[1m]` exist), so the `opusplan` planning leg cannot be forced to 1M. If you need 1M during planning, turn Model Switching **off** and run `/model opus[1m]` (or `/model default`, which resolves to Opus 4.8 at 1M).

:::warning 1M context requires usage credits on Max
On Max subscriptions, 1M context is billed via usage credits: an `opus[1m]` session errors with `Usage credits required for 1M context` until you enable them (`/usage-credits`). Use a tier where 1M is included (API, Team, Enterprise), or enable credits. Where 1M is unavailable, these aliases fall back to 200K gracefully.
:::

Pilot keeps 1M models available in the `/model` picker by always writing `CLAUDE_CODE_DISABLE_1M_CONTEXT=false`, and removes the obsolete `ANTHROPIC_DEFAULT_OPUS_MODEL` / `ANTHROPIC_DEFAULT_SONNET_MODEL` env vars (the model alias replaces them).

**Sub-agents** (`spec-review`, and `changes-review` when the Changes Review Mode is Single Sub-Agent) are pinned to the base Sonnet model and do not use the 1M context window. When the mode is a Code Review tier, the changes review runs as the built-in `/code-review` skill on the session model at that effort (set per workflow in Console -> Settings -> Spec Workflow -> Changes Review Mode), so it follows the active model and context window.

## Default-On

Automated model switching is **ON for every install** (a one-time migration enables it for existing users too). The first time you launch after upgrading, Pilot shows a one-time announcement explaining the change and how to disable it. The reviewer sub-agent (`spec-review`) always runs on Sonnet -- sub-agents do not support the 1M context window; the changes review runs as the built-in `/code-review` skill on the session model.
