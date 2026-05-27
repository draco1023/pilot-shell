---
sidebar_label: Codex CLI
description: How Pilot Shell works with OpenAI Codex CLI — supported skills, limitations, and differences from Claude Code.
---

# Codex CLI Support

Pilot Shell works with [OpenAI Codex CLI](https://developers.openai.com/codex/cli) alongside Claude Code. **Install Codex CLI separately first** — the Pilot installer auto-detects it and sets up hooks, skills, MCP servers, and rules.

**For the full Pilot Shell experience, use Claude Code.** Codex support covers the core workflows but not every feature.

## What works on Codex

### Skills

All non-bot skills are available on Codex — use `$` instead of `/` to invoke them:

| Skill | Codex | Claude Code | Description |
|-------|-------|-------------|-------------|
| `$spec` | ✅ | ✅ `/spec` | Spec-driven development — plan, implement, verify |
| `$fix` | ✅ | ✅ `/fix` | Bugfix workflow — investigate, RED test, fix |
| `$prd` | ✅ | ✅ `/prd` | Brainstorm requirements with optional research |
| `$benchmark` | ✅ | ✅ `/benchmark` | Benchmark rules and skills with before/after comparisons |
| `$setup-rules` | ✅ | ✅ `/setup-rules` | Set up and audit project rules |
| `$create-skill` | ✅ | ✅ `/create-skill` | Create reusable skills interactively |

The spec sub-skills (`$spec-plan`, `$spec-bugfix-plan`, `$spec-implement`, `$spec-verify`, `$spec-bugfix-verify`) are also available on Codex.

**Codex-specific adaptations:** The skills are automatically adapted for Codex at install time and on every session start. Claude Code-only features (subagent reviewers, model switching handoff, `AskUserQuestion` tool) are stripped and replaced with Codex-compatible alternatives. The core workflow — plan, implement, verify with TDD — is identical. The benchmark runner supports `--agent codex` for benchmarking with Codex's `codex exec` headless mode.

**What's different in Codex skills:**

- **No reviewer sub-agents** — Spec-review and changes-review sub-agents are Claude Code features (they launch separate context windows). In Codex, the agent self-reviews instead.
- **No Codex companion reviews** — The Codex adversarial reviewer is launched from Claude Code via the Codex plugin. It's not available when already running inside Codex.
- **No model switching** — Codex doesn't have a `/model` command. Plan → implement → verify runs continuously on the active model.
- **Plain-text questions** — Where Claude Code uses `AskUserQuestion` (structured form UI), Codex presents numbered options as plain text.

### Console Views

Some Console views work with Codex sessions:

| Console View | Codex | Claude Code | Notes |
|-------------|-------|-------------|-------|
| **Requirements** | ✅ | ✅ | PRDs created by `$prd` appear in the Console |
| **Specifications** | ✅ | ✅ | Plans created by `$spec` appear with task progress and phase tracking |
| **Extensions** | ✅ | ✅ | Skills, rules, and agents — the source files are shared across both agents |
| **Changes** | ✅ | ✅ | Git diff viewer works with any agent — it reads `git status` and `git diff` |
| **Usage** | ✅ | ✅ | Token costs and model breakdown tracked for Codex sessions |
| **Settings** | ✅ | ✅ | Settings that apply to both agents are labeled (see below) |
| **Dashboard** | ⚠️ | ✅ | Stats from Codex sessions are partial (no memory/session data) |
| **Sessions** | ✅ | ✅ | Codex sessions read from `~/.codex/sessions/`; Claude Code from observation hooks |
| **Memories** | ❌ | ✅ | Persistent memory requires the Console observation pipeline |

### Console Settings

Settings are labeled in the Console UI to indicate agent support:

| Setting | Support | Description |
|---------|---------|-------------|
| Plan Approval | **Claude Code + Codex** | Require approval before implementation |
| Branch Isolation | **Claude Code + Codex** | Ask about branch/worktree for `/spec` changes |
| Ask Questions | **Claude Code + Codex** | Ask clarifying questions during planning |
| Model Switching | **Claude Code only** | Pause after planning to switch models |
| Spec Review | **Claude Code only** | Sub-agent plan reviewer |
| Changes Review | **Claude Code only** | Sub-agent code reviewer |
| Codex Spec Review | **Claude Code only** | Codex companion plan reviewer (from CC) |
| Codex Changes Review | **Claude Code only** | Codex companion code reviewer (from CC) |

### MCP Servers

Six of seven Pilot Shell MCP servers are configured for Codex via `~/.codex/config.toml`:

| Server | Description |
|--------|-------------|
| **context7** | Library and framework documentation |
| **CodeGraph** | Code knowledge graph — callers, callees, impact analysis. Auto-initialized per-project via SessionStart hook. |
| **Semble** | Hybrid semantic + lexical code search (BM25 + Model2Vec) |
| **web-search** | Web search via DuckDuckGo, Bing, Exa |
| **grep-mcp** | GitHub code search across 1M+ public repos |
| **web-fetch** | Playwright-backed web page fetching |

**Not available on Codex:** `mem-search` (Pilot Console persistent memory) — requires the Console worker daemon which depends on Claude Code hooks.

### Rules

Pilot Shell's instruction rules (testing, development practices, verification, etc.) are delivered via `~/.codex/AGENTS.md`. Codex loads this file automatically as global instructions. The rules are adapted for Codex — Claude Code-specific tool references are replaced with Codex equivalents.

### Hooks

Hooks registered in `~/.codex/hooks.json`:

- **SessionStart** — license verification, CodeGraph initialization, Codex skill rebuild (syncs skills from Claude Code sources with license gating)
- **UserPromptSubmit / PostToolUse / Stop** — session registration, observation capture, focused quality warnings, and session summarization
- **PreCompact / SessionStart(compact)** — preserves and restores lightweight plan state around compaction

Pilot Console memory context is **not** injected on Codex SessionStart. Codex currently surfaces hook-provided developer context in the UI/event stream, so the Codex integration keeps startup quiet instead of dumping memory context into the visible transcript. The context monitor uses Codex token-count transcript events when available and stays silent rather than estimating from transcript file size.

### Configuration

The installer configures `~/.codex/config.toml` with optimized defaults:

| Key | Value | Purpose |
|-----|-------|---------|
| `approval_policy` | `"never"` | Equivalent to Claude Code's bypass permissions mode |
| `sandbox_mode` | `"danger-full-access"` | Full filesystem and network access |
| `model_reasoning_effort` | `"xhigh"` | Maximum reasoning effort for GPT-5.5 |
| `model_reasoning_summary` | `"concise"` | Concise reasoning summaries (like Claude Code's summarized thinking) |
| `personality` | `"pragmatic"` | Direct, engineering-focused output |
| `check_for_update_on_startup` | `true` | Check for Codex CLI updates on launch |
| `features.apps` | `true` | Enable ChatGPT Apps/connectors support |
| `features.hooks` | `true` | Enable Pilot Shell lifecycle hooks |
| `features.memories` | `true` | Enable Codex's built-in memory system |
| `features.mentions_v2` | `true` | V2 file picker with `@` mentions |
| `features.plugins` | `true` | Enable plugin support |
| `features.tool_call_mcp_elicitation` | `true` | Allow MCP tools to request user input |
| `features.tool_search` | `true` | Enable tool discovery |
| `features.tool_suggest` | `true` | Enable tool suggestions for discoverable connectors |
| `features.undo` | `true` | Enable undo support for reverting changes |

Existing user settings are preserved — only missing keys are added. The model itself (`model = "gpt-5.5"`) is not set by the installer — Codex defaults to GPT-5.5; users can override via `codex --model <name>` or by setting `model` in config.toml.

## What requires Claude Code

These features depend on Claude Code-specific APIs and are not available on Codex:

| Feature | Why Claude Code only |
|---------|---------------------|
| **Automatic memory context injection** | Codex surfaces hook-injected developer context visibly; Pilot keeps SessionStart memory injection disabled |
| **Status line** | Claude Code-specific status line API; Codex has no equivalent |
| **Pilot Bot** | Scheduled tasks, background jobs — requires Claude Code's cron and remote control |
| **Some quality hooks** | Tool redirect and spec mode guard depend on Claude Code-specific command/tool semantics |
| **Bot skills** | `/bot-boot`, `/bot-channel-task`, `/bot-defaults`, `/bot-heartbeat`, `/bot-jobs` — depend on Claude Code cron and remote control |
| **Spec collaboration** | Console annotation sharing requires the full observation pipeline |
| **Review sub-agents** | `spec-review` and `changes-review` launch in separate Claude Code context windows |
| **Codex companion reviews** | Launched from Claude Code via the Codex plugin — not available inside Codex itself |
| **Model switching** | Claude Code's `/model` command and the `spec_handoff_resume` hook |
| **Token optimization hooks** | RTK proxy hook, context monitoring — require Claude Code's `PreToolUse`/`PostToolUse` pipeline |

## Differences from Claude Code

| Aspect | Claude Code | Codex CLI |
|--------|-------------|-----------|
| Model | Claude Opus 4.7 / Sonnet 4.6 | GPT-5.5 (xhigh reasoning) |
| Skill invocation | `/spec`, `/fix`, `/prd` | `$spec`, `$fix`, `$prd` |
| Config format | `~/.claude/settings.json` (JSON) | `~/.codex/config.toml` (TOML) |
| MCP config | `~/.claude.json` | `~/.codex/config.toml` `[mcp_servers.*]` |
| Rules location | `~/.claude/rules/*.md` | `~/.codex/AGENTS.md` |
| Skills location | `~/.claude/skills/` | `~/.agents/skills/` |
| Hooks location | `~/.claude/settings.json` `hooks` key | `~/.codex/hooks.json` |
| Interactive questions | `AskUserQuestion` tool | Plain-text numbered options |
| Permissions | `bypassPermissions` in settings | `approval_policy = "never"` in config.toml |
| Memory | Pilot Console (mem-search MCP) | Codex built-in memories (`features.memories`) |

## Installation

**Prerequisite:** Install [Codex CLI](https://developers.openai.com/codex/cli) first. Then run the Pilot installer — it auto-detects Codex and adds support:

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh | bash
```

After installation, run `codex` directly. Pilot Shell's hooks and skills load automatically.

## Updating

`pilot update` checks for updates to Pilot Shell, Claude Code (if installed), and Codex CLI (if installed):

```bash
pilot update
```
