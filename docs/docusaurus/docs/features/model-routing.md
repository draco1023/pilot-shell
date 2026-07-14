---
sidebar_position: 5
title: Model Routing
description: Plan with Opus, implement with Sonnet - automatically, no manual switch.
---

# Model Routing

:::warning Claude Code only
Automated model switching is a Claude Code feature. It is not available in Codex CLI -- on Codex, set the model via `codex --model <name>` or in `~/.codex/config.toml`, and `/spec` runs on whatever model is active.
:::

Opus reasons better; Sonnet is faster and cheaper. The cost-saving move is to plan on Opus, then drop to Sonnet for the mechanical implementation and verification that follow. Pilot does this **automatically** during `/spec` -- no manual `/model` step -- and **both legs run at 1M context**.

## The Configurable Pair

**Console -> Settings -> Model Switching** has two dropdowns:

| Slot | Options | Default |
|------|---------|---------|
| **Plan Model** (plan mode / `/spec` planning) | Opus 4.8 (1M) · Fable 5 (1M) | Opus 4.8 (1M) |
| **Execution Model** (everything else, incl. quick mode) | Sonnet 5 (1M) · Opus 4.8 (1M) | Sonnet 5 (1M) |

Both legs run at the **1M context tier** -- the old 200K planning leg is legacy. An **Opus execution model requires a Fable plan model** (otherwise it is just single-model Opus, which is the toggle-OFF flow); the Console disables the Execution dropdown until you pick Fable planning.

## Fable Planning (fableplan-style)

Claude Code ships an `opusplan` alias (Opus in plan mode, Sonnet otherwise) but **no `fableplan`**. Pilot recreates it -- and adds an Opus execution option -- with **window-scoped slot pins**.

Claude Code's `ANTHROPIC_DEFAULT_OPUS_MODEL` / `ANTHROPIC_DEFAULT_SONNET_MODEL` env vars remap the *opus/sonnet model slots* everywhere, including the `/model` picker rows, and Claude Code hot-reloads them into running sessions. A permanent cross-family pin (the approach the [community `fableplan` plugin](https://github.com/bapttiste73/fableplan) takes) would make real Opus unreachable via `/model` for the whole session. Pilot avoids that by pinning **only inside the window that needs it**:

- **Fable plan model** -> the opus slot serves `claude-fable-5[1m]` **only between EnterPlanMode and ExitPlanMode**. Outside a planning window the opus slot is back to the same-family `claude-opus-4-8[1m]`, so `/model opus`, fast mode, and opus subagents mean real Opus again. Need real Opus in another session *while* a window is open? Switch that session manually: `/model claude-opus-4-8[1m]`.
- **Opus execution model** -> the sonnet slot serves `claude-opus-4-8[1m]` **only from a `/spec` implementation start until the plan is verified**. Outside a running `/spec`, quick mode and the sonnet alias are back to Sonnet 5. Want Sonnet 5 in another session while a spec runs? `/model claude-sonnet-5` (natively 1M).
- **Reverts are explicit rewrites, never deletions.** While Model Switching is ON, both slots always carry an explicit value (`claude-opus-4-8[1m]` / `claude-sonnet-5` at baseline). Claude Code hot-reloads env value *changes* into running sessions, but removing a var does not unset it in a live session -- so closing a window rewrites the slot back to its baseline instead of deleting the pin.

Parallel sessions are safe: each open window holds a refcounted lease, and the pin reverts only when the last live lease closes. A crashed session's lease is reclaimed by the next reconcile via PID liveness. If a future Claude Code release stops hot-reloading these env vars, the choice simply applies at the next session start instead of mid-session -- no breakage.

## How It Works

Pilot rides Claude Code's **Opus Plan** model (`opusplan`): Opus while in plan mode, Sonnet otherwise. When you save the Console settings (or on install), `pilot sync-env` writes into `~/.claude/settings.json`:

- `model: "opusplan"` plus an `ANTHROPIC_MODEL: "opusplan"` pin (env outranks the model field), and
- the same-family baseline pins `ANTHROPIC_DEFAULT_OPUS_MODEL: "claude-opus-4-8[1m]"` (upgrades the planning leg to 1M) and `ANTHROPIC_DEFAULT_SONNET_MODEL: "claude-sonnet-5"` (natively 1M). Both are always explicit while the toggle is ON; window transitions rewrite them.

With **Model Switching** ON (the default), `/spec`:

1. Calls **EnterPlanMode** at the start of planning -> you're on the **Plan Model** (Opus 4.8 by default, or Fable 5) for the reasoning-heavy planning leg.
2. After you approve the plan, calls **ExitPlanMode** -> you drop to the **Execution Model** (Sonnet 5 by default, or Opus 4.8) automatically.
3. Runs implementation and verification on the Execution Model, continuously, in the same session.

There is no pause, no handoff message, and no `/clear` + re-invoke. You approve the plan and implementation begins.

:::info Model Switching wins while ON
While Model Switching is ON, it **overrides a manually saved `/model` choice** (including a saved Fable model) on the next settings sync or restart -- the `ANTHROPIC_MODEL: opusplan` pin outranks the saved model field. Turn the toggle off to control the model entirely via `/model`.
:::

## Set the Opus Plan Model

For automated switching to work, your session must be on the `opusplan` model:

```text
/model opusplan
```

Pilot writes this into `~/.claude/settings.json` during install and whenever Console settings change via `pilot sync-env`, so future sessions start on `opusplan` automatically. (There is no `opusplan[1m]` alias in Claude Code -- the 1M planning tier rides on the same-family opus slot pin instead; see [Context Window](#context-window).)

`/spec` checks your model before planning and behaves differently per model:

- **On a wrong, identifiable model** (e.g. plain **Opus**): `/spec` **hard-blocks** and tells you to run `/model opusplan`. Before plan mode, `opusplan` resolves to Sonnet -- so being on Opus means you never switched. The check trusts your persisted `/model` selection (`~/.claude/settings.json`): if you just ran `/model opusplan`, a statusline that hasn't re-rendered yet won't re-block you.
- **On Sonnet**: allowed. Pilot can't tell `opusplan`'s Sonnet leg from plain Sonnet, so it presumes you're correct rather than false-block every valid user.
- **On Fable 5 / Mythos 5** (`fable`, `mythos`, `claude-fable-5`, `claude-mythos-5`, `best`): allowed in BOTH toggle states -- see [Fable 5](#fable-5) below.

With **Model Switching OFF**, the check flips: `/spec` requires **Opus** (only Opus may enter plan mode; Fable-family models also pass) and hard-blocks any other model. If your selected model is `opusplan`, the block explains the actual conflict -- planning would run on opusplan's execution leg -- and offers both ways out: turn Model Switching ON (Console -> Settings -> Model Switching) to keep `opusplan`, or run `/model opus[1m]` to stay single-model. Resuming an existing plan (`/spec <path/to/plan.md>`) skips the check on any model.

## Troubleshooting: Planning Didn't Switch to Opus

The `opusplan` switch is performed by Claude Code, and Claude Code can decline it silently. If the statusline stays on **Sonnet** during planning -- or flips between Opus and Sonnet part-way through -- the usual causes are:

- **Opus usage-limit fallback** (Max plans). When your Opus pool is exhausted, `opusplan` serves Sonnet even in plan mode and switches back once the rolling limit window frees up. This is Claude Code behavior, not a Pilot bug -- check `/usage`. Because the window is rolling, it looks like "uneven" switching that engages mid-planning.
- **The session isn't on `opusplan`.** Run `/model opusplan` and start `/spec` again.
- **Asking the model doesn't work.** Models don't reliably know which model they are -- a planning leg genuinely running on Opus can still answer "Sonnet". Trust the statusline, not self-reports.

Pilot verifies the switch instead of assuming it: during the planning leg, the `plan_mode_tracker` hook compares the observed session model (from the statusline) against the expected Opus leg at your first plan-file write and injects a visible `PLANNING-LEG MODEL CHECK` warning -- naming the observed model, the likely cause, and the remedy -- when planning is not actually on Opus. No warning means the switch took effect.

## Fable 5

[Claude Fable 5](https://www.anthropic.com/news/claude-fable-5-mythos-5) is Anthropic's frontier model (`/model fable`, or `fable[1m]` for the 1M window). Claude Code has **no native `fableplan`** alias, but Pilot provides the equivalent through the window-scoped **Plan Model = Fable 5** setting (see "Fable Planning" above) -- Fable plans, then the Execution Model implements. You can also run Fable end-to-end:

- **Single-model Fable:** with Model Switching OFF, run `/model fable` and `/spec` runs plan, implement, and verify all on Fable. The planning skills detect a genuine single-model Fable session (a *saved* `/model fable`) and skip `EnterPlanMode`/`ExitPlanMode` entirely -- no model toggling and no `/model opusplan` block.
- **Your saved Fable model is preserved -- while Model Switching is OFF.** `ANTHROPIC_MODEL` (env) outranks the saved `model` field in `~/.claude/settings.json`, so Pilot removes its own overrides instead of writing them when the toggle is off and your saved model is Fable-family. With the toggle ON, Model Switching wins instead (see above).
- **1M context stays available.** `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` removes 1M variants from the model picker, which would break `fable[1m]` -- Pilot forces it to `false`, so `fable[1m]` always works.
- **Statusline and Console Usage** display "Fable 5" / "Mythos 5" with the announced $10/$50 per-MTok pricing.

Note: Fable 5 ships with safety classifiers; flagged requests (mostly cybersecurity/biology) are re-run on Opus 4.8 by Claude Code itself with a transcript notice -- that fallback is Claude Code behavior, not Pilot's (see the [model configuration docs](https://code.claude.com/docs/en/model-config), "Automatic model fallback").

## Quick Mode (Outside /spec) -- Default is Sonnet

`opusplan` resolves to the **Execution Model** (Sonnet 5 by default) whenever you are *not* in plan mode. This means regular quick-mode prompts -- everything outside `/spec` and `/fix` planning -- run on Sonnet 5, not Opus. (If you set the Execution Model to Opus 4.8, that applies only *while a `/spec` is running*; ordinary quick mode outside a spec stays on Sonnet.)

This is by design: the model exists specifically to power the planning leg of the spec workflow, not to make Opus the default for all interactions. **If you want Opus for a quick-mode task**, switch manually:

```text
/model opus[1m]
```

Switch back to `opusplan` before the next `/spec` run (with Model Switching ON, Pilot re-asserts it on the next settings sync or restart anyway):

```text
/model opusplan
```

:::tip Summary
- `opusplan` on = `/spec` and `/fix` plan on Opus 4.8 (1M), everything else on Sonnet 5 (1M).
- For ad-hoc Opus work outside those workflows, switch to `opus[1m]` for that session.
:::

## Turning It Off -- One Model Everywhere

Turn off **Model Switching** in Console -> Settings -> Model Switching to run the entire `/spec` workflow on a single model of your choice. Pilot then defaults `~/.claude/settings.json` to `opus[1m]` (Opus at 1M) and strips its `ANTHROPIC_MODEL` and slot pins, so your `/model` choice rules -- a saved Fable model is preserved. Plan -> implement -> verify all run on the active model. Choose this if you prefer one model end-to-end, or for headless / CI runs.

## Context Window

Everything runs at the **1M tier** -- there is no per-model Context Window setting, and 200K is legacy:

| Toggle | Persisted state | Context window |
|--------|-----------------|----------------|
| **Model Switching ON** | `opusplan` + the opus slot pin | Opus planning leg: **1M** (`claude-opus-4-8[1m]`). Sonnet 5 execution leg: **1M** (native). |
| **Model Switching OFF** | `opus[1m]` (soft default) | Opus 4.8: **1M**. |

The `[1m]` suffix on the pinned ID rides as a context-beta header; Sonnet 5 is natively 1M and needs no pin. There is still no `opusplan[1m]` alias -- the same-family opus pin is how the planning leg reaches 1M.

:::warning 1M context requires usage credits on Max
On Max subscriptions, 1M context is billed via usage credits: a 1M session errors with `Usage credits required for 1M context` until you enable them (`/usage-credits`). Use a tier where 1M is included (API, Team, Enterprise), or enable credits. Where 1M is unavailable, Claude Code falls back to 200K gracefully.
:::

Pilot keeps 1M models available in the `/model` picker by always writing `CLAUDE_CODE_DISABLE_1M_CONTEXT=false`. The `ANTHROPIC_DEFAULT_OPUS_MODEL` / `ANTHROPIC_DEFAULT_SONNET_MODEL` pins are Pilot-managed: always written with explicit values while Model Switching is ON (baselines `claude-opus-4-8[1m]` / `claude-sonnet-5`, swapped only inside plan/execution windows), stripped when it is OFF (including at startup, covering a save that couldn't propagate).

**Sub-agents** (`spec-review`, and `changes-review` when the Changes Review Mode is Single Sub-Agent) are pinned to the base Sonnet model and do not use the 1M context window. When the mode is a Code Review tier, the changes review runs as the built-in `/code-review` skill on the session model at that effort (set per workflow in Console -> Settings -> Spec Workflow -> Changes Review Mode), so it follows the active model and context window.

## Default-On

Automated model switching is **ON for every install** (a one-time migration enables it for existing users too). The first time you launch after upgrading, Pilot shows a one-time announcement explaining the change and how to disable it. The reviewer sub-agent (`spec-review`) always runs on Sonnet -- sub-agents do not support the 1M context window; the changes review runs as the built-in `/code-review` skill on the session model.
