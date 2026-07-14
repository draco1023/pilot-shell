---
sidebar_position: 8
title: Pilot Console
description: Local Pilot Console at localhost:41777 - monitor sessions, browse memories, manage extensions, view diffs, track usage, and control Pilot from the browser.
---

# Pilot Console

Local web dashboard at `localhost:41777` - monitor and manage your sessions.

The Console runs locally as a Bun/Express server with a React web UI. It starts when you launch Pilot and stops when all sessions close. All data - memories, sessions, usage - lives in a local SQLite database. Nothing leaves your machine.

```bash
$ open http://localhost:41777
```

:::tip Custom port
The default port `41777` is configurable. Open the **Settings** tab and edit the **Console -> Worker Port** field, then click **Save Port** (or edit `CLAUDE_PILOT_WORKER_PORT` in `~/.pilot/memory/settings.json` directly). Restart your `claude` or `codex` session for the change to take effect.
:::

## Views

Each view that supports project filtering has an inline **Project Filter** dropdown next to the title. The **Dashboard** shows stats across all projects with clickable tiles that navigate to the relevant view.

| View | Description |
|------|-------------|
| **Dashboard** | Global command center - 8 clickable stat cards (Projects, Sessions, Active, Memories, Extensions, Requirements, Specifications, Changes), 4 recent-item cards with "Show all" links, active specs as pills in the top bar, notification bell in the top right. |
| **Sessions** | Browse past sessions with search. Copy a session ID and run `/resume <session-id>` in Claude Code to jump back in (Claude Code only). |
| **Memories** | Observations (decisions, discoveries, bugfixes) with type filters and search. Each memory links back to the session it came from. |
| **Requirements** | PRD documents with view/annotate modes. Selected opens as a tab, others live in a Previous dropdown. |
| **Specifications** | Spec plans with task progress, phase tracking (PENDING/COMPLETE/VERIFIED), and iteration history. Hosts Plan Annotation and Spec Sharing (below). |
| **Extensions** | All extensions - local, plugin, remote - with team sharing via git (push, pull, diff), color-coded categories, and scope filtering. |
| **Changes** | Git diff viewer with staged/unstaged files, branch info, worktree context. Hosts Code Review and Spec Task Correlation (below). |
| **Usage** | Daily token costs, model routing breakdown (Opus vs Sonnet), and usage trends. |
| **Settings** | Spec workflow toggles (branch isolation, ask questions, plan approval, Model Switching), reviewer toggles. See [Settings](#settings) below. |
| **Documentation** | Embedded pilot-shell.com documentation - full technical reference without leaving the Console. |

## Plan Annotation

When a spec plan is in the planning phase (PENDING, not yet approved), the Specifications tab auto-opens in **Annotate mode**. Toggle between View and Annotate using the control next to the "Specifications" heading.

Select any passage and write a free-text note in the popover that appears - no type selection, no submit button. Annotations save immediately and appear in the sidebar panel, where you can edit or delete them.

When the agent reaches the approval checkpoint, it reads your annotations directly from the Console, incorporates every note into the plan, and asks for approval again. Just write your notes and say "ready" when done.

## Code Review

After a spec completes automated verification, the agent prompts you to review the code changes. Switch to the **Changes** tab and enable **Review mode** using the toggle next to the "Changes" heading.

In Review mode, a **+** button appears on hover for every diff line. Click it to open an inline annotation form - write your note and press Save. Annotations appear in a panel at the bottom of the diff viewer.

The agent reads your code-review annotations directly from the Console before marking the spec verified. Say "fix" to have it address them, "approve" to mark the spec as verified. Annotations persist across page reloads, so you can review asynchronously while the agent runs verification in the background.

## Spec Task Correlation

When a `/spec` task is active, the Changes tab correlates each changed file with the spec task that touched it - instant traceability.

- Each file in the file list shows a **T{N}** badge (e.g., `T1`, `T3`) linking it to the matching spec task
- Hover the badge for the full task name
- Click the **Spec** button to switch to **group-by-spec** view - files organized by spec name and task number
- Correlation is parsed from the `**Files:**` section of each task, so any spec following the standard format works automatically

Especially useful for multi-task specs: instead of scrolling a flat file list, review changes task by task.

## Spec Sharing

Share specs with teammates for collaborative review - no cloud service required. Everything works locally with compressed URLs.

**Share:**

1. Open a spec, click **Share with Teammate** in the metadata row
2. A share URL is generated - the spec content and your annotations are compressed into the URL fragment (per the HTTP spec, fragments are never sent to any server)
3. Copy the URL and send it via Slack, email, or any channel
4. The **Receive Feedback** dialog opens automatically so you're ready for their response

**Review a shared spec:**

1. Your colleague opens the URL in their Pilot Console
2. They see your spec and annotations as read-only highlights
3. They add their own feedback via text selection or the **+** button on any block
4. Click **Send Feedback** to generate a feedback URL

**Import feedback:**

1. Click **Receive Feedback** on the original spec
2. Paste the URL - a preview shows the incoming annotations
3. **Accept** or **Reject** each annotation individually, or use **Accept All** / **Reject All**

Importing the same feedback twice is safe - annotations matching existing ones are skipped. For specs larger than ~32KB compressed, an embedded paste service stores the data locally in `~/.pilot/share/` with 3-day auto-expiry.

:::tip Both annotation methods work everywhere
The **+** button and text selection both work on the normal review page and on shared feedback pages. The **+** button is more reliable for quick block-level comments.
:::

## Notifications

The Console sends real-time alerts via Server-Sent Events when your agent needs input or a significant phase completes - no need to watch the terminal.

- Plan requires your approval - review and respond
- Spec phase completed - implementation done, verification starting
- Clarification needed - the agent is waiting for design decisions
- Session ended - completion summary with observation count

## Settings

The Settings tab (`localhost:41777/#/settings`, or your custom port) is a single scrollable page with two stacked sections: **Spec Workflow** and **Console**. Toggle preferences save to `~/.pilot/config.json`. The **Console -> Worker Port** field saves to `~/.pilot/memory/settings.json` and lets you move the Console off `41777` if it conflicts with another service. Both changes take effect after restarting your session.

:::info Model selection lives in the agent
Pilot doesn't manage model preferences. Set the model with Claude Code's `/model` command or Codex's `codex --model <name>` / `~/.codex/config.toml`. See [Model Routing](./model-routing.md).
:::

### Spec Workflow -> Review Agents

Two reviews run during `/spec` on Claude Code and Codex; **Changes Review** also runs at the end of `/fix`. Toggle each on or off. On Claude Code, **Spec Review** runs as a Claude sub-agent and **Changes Review** runs per the mechanism chosen for each workflow (see [Changes Review Mode](#spec-workflow---changes-review-mode) below); Codex runs both as managed custom agents installed under `~/.codex/agents/`.

| Agent | Default | Role |
|-------|---------|------|
| **Spec Review** | On | Validates plans before implementation. Checks alignment with requirements, flags risky assumptions. |
| **Changes Review** | On | Reviews code after `/spec` implementation and `/fix`. Hunts bugs, security issues, and cleanups; plan compliance and goal achievement stay covered on both agents (inline workflow audit on Claude Code, the native agent's own pass on Codex). |

**Codex Companion Reviewers (optional, Claude Code only)** - OpenAI Codex plugin reviewers that provide an independent second opinion while you are working inside Claude Code.

| Agent | Default | Role |
|-------|---------|------|
| **Codex Companion Spec Review** | Off | Plugin plan review - second opinion before implementation. |
| **Codex Companion Changes Review** | Off | Plugin code review - second opinion after `/spec` and `/fix`. |

### Spec Workflow -> Changes Review Mode

Chooses the **Changes Review** mechanism separately for `/spec` verification and `/fix` - two dropdowns, four options each:

| Option | What runs | Token cost |
|--------|-----------|------------|
| **Single Sub-Agent** (default) | One `changes-review` sub-agent reviews the diff and writes a findings file | Lowest |
| **Code Review - Medium / High / XHigh** | The built-in `/code-review` skill at that effort - it spawns many finder/verifier sub-agents | Scales steeply with the tier |

The billed cloud `ultra` mode stays excluded. Pick **Single Sub-Agent** to keep review costs minimal (also a good fit for lighter models); raise to **Code Review - XHigh** for high-risk or security-sensitive work. The choice flows to the workflows via `$PILOT_SPEC_CODE_REVIEW_MODE` / `$PILOT_FIX_CODE_REVIEW_MODE` and is allow-listed at the point of use (an unset or unrecognized value falls back to the single sub-agent). It applies only while the Changes Review toggle is on, and to Claude Code only - on Codex the changes review always runs as the native agent with its own reasoning effort. Upgrading from an older Pilot resets both dropdowns to **Single Sub-Agent** (the previous single effort setting is retired).

### Spec Workflow -> Automation

Four toggles control user interaction points during `/spec`. Disable all four for fully autonomous end-to-end execution.

| Toggle | Default | Enabled | Disabled |
|--------|---------|---------|----------|
| **Branch Isolation** | On | Asks how to isolate `/spec` changes (new branch or worktree) | Always works on the current branch |
| **Ask Questions** | On | Asks clarifying questions during planning | Planning makes autonomous default choices |
| **Plan Approval** | On | Requires your approval before implementation starts | Implementation begins automatically after planning |
| **Model Switching** *(Claude Code only; own Settings block with Plan Model + Execution Model dropdowns)* | On | Automatically runs `/spec` planning on the configurable **Plan Model** (Opus 4.8 default, or Fable 5) and implementation + verification on the **Execution Model** (Sonnet 5 default, or Opus 4.8) - requires the `opusplan` model (see [Model Routing](model-routing)). A Fable plan model applies only during plan-mode windows and an Opus execution model only during a running `/spec`, so the cross-family remap is transient (Opus execution requires Fable planning); window reverts rewrite the slot pins back to their explicit baselines so running sessions switch back too. No manual `/model` step. | The whole `/spec` workflow runs on your active `/model` choice (Pilot defaults it to Opus 4.8 at 1M; a saved Fable model is preserved) |

With all four workflow toggles off, `/spec add user authentication` plans, implements, and verifies the feature end-to-end without checkpoints, entirely on your active model.

:::warning Token usage in autonomous mode
No checkpoints means your agent executes the entire workflow without asking. Make sure your prompt is specific enough to avoid misinterpretation. You can always interrupt with Escape.
:::

### Config file

All settings are stored in `~/.pilot/config.json`:

```json
{
  "reviewerAgents": {
    "specReview": true,
    "changesReview": true
  },
  "codexReviewers": {
    "specReview": false,
    "changesReview": false
  },
  "specWorkflow": {
    "branchIsolation": true,
    "askQuestionsDuringPlanning": true,
    "planApproval": true,
    "modelSwitch": true
  },
  "codeReview": {
    "spec": "agent",
    "fix": "agent"
  }
}
```

`codeReview.spec` / `codeReview.fix` accept `agent`, `medium`, `high`, or `xhigh` (see [Changes Review Mode](#spec-workflow---changes-review-mode) above); unknown values fall back to `agent`.

You can edit `~/.pilot/config.json` directly - the Settings UI is a convenience wrapper. Changes take effect after restarting your session.
