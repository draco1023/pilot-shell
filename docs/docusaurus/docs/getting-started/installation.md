---
sidebar_position: 2
title: Installation
description: One-command installation that works with any existing project — no scaffolding, no restructuring. Run the installer once, then use Pilot across all repos.
---

# Installation

Works with any existing project — no scaffolding required.

## One-Command Installation

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh | bash
```

Run from any directory — it installs globally to `~/.pilot/` and `~/.claude/` (and `~/.codex/` if Codex CLI is detected). After installation, just run `claude` or `codex` directly — Pilot Shell loads automatically.

## What the Installer Does

9 steps with progress tracking and rollback on failure. Steps 3 and 4 are agent-conditional — they skip cleanly when the matching agent CLI is not detected on your system. The installer **does not install Claude Code or Codex CLI itself**; you install at least one of them yourself per [Prerequisites](#prerequisites).

| Step | Title | Description |
|------|-------|-------------|
| 1 | Prerequisites | Checks/installs Homebrew, Node.js, Python 3.12+, uv, git, jq. Verifies at least one supported agent (Claude Code or Codex CLI) is on the system; aborts with a clear error otherwise. |
| 2 | Pilot files | Installs agent-neutral Pilot Shell-managed assets: hooks to `~/.pilot/hooks/`, Console scripts/UI to `~/.pilot/`, raw rule sources to `~/.pilot/rules/` (read by Codex's adapter), and the canonical skill source to `~/.claude/skills/` (used by both agents — Claude reads it natively, Codex adapts it). Always runs. |
| 3 | Claude files | Installs Claude-specific assets to `~/.claude/`: rules, sub-agents, and `settings.json` (three-way merged); plus Claude post-install merges (hooks into settings, `~/.claude.json` MCP block, model config). **Skipped when Claude Code CLI is not detected.** |
| 4 | Codex files | Installs Codex-specific assets: adapted skills to `~/.agents/skills/`, review agents to `~/.codex/agents/`, `~/.codex/AGENTS.md`, `~/.codex/config.toml`, `~/.codex/hooks.json`. Per-category counts mirror the Claude section. **Skipped when Codex CLI is not detected.** |
| 5 | Config files | Creates `.nvmrc` and project config |
| 6 | Dependencies | Installs Semble, RTK, CodeGraph, Chrome DevTools MCP, playwright-cli, agent-browser, language servers, plus the `codex@openai-codex` Claude marketplace plugin. Claude-side plugins (Codex companion plugin, Chrome DevTools MCP plugin, LSP plugins) are skipped on Codex-only systems. |
| 7 | Shell integration | Auto-configures bash, fish, and zsh with the `pilot` alias. Add `# pilot-shell:managed-elsewhere` to a config file to opt out (for framework-managed shells) |
| 8 | VS Code extensions | Installs recommended extensions for your language stack |
| 9 | Finalize | Success message with next steps |

## Browser Automation

Pilot installs three browser tools automatically: **Chrome DevTools MCP**, **playwright-cli**, and **agent-browser**.

- **Claude Code:** also install the [Claude Code Chrome extension](https://code.claude.com/docs/en/chrome) for the richest browser context. Tier order: Chrome extension → Chrome DevTools MCP → playwright-cli → agent-browser.
- **Codex CLI:** the Chrome extension is not available. Tier order: Chrome DevTools MCP → playwright-cli → agent-browser.

## Codex Companion Plugin (Included)

The [Codex companion plugin](https://github.com/openai/codex-plugin-cc) is installed automatically by the Pilot installer. It provides adversarial code review powered by OpenAI — an independent second opinion during Claude Code's `/spec` planning and verification.

1. Run `/codex:setup` in any Pilot session to authenticate with your OpenAI account
2. Enable the Codex Companion Reviewers in Console Settings → Reviewers

This is separate from [Codex CLI support](/docs/getting-started/codex-cli) — the companion plugin runs from within Claude Code, while Codex CLI is a standalone agent.

## Dev Container

Pilot Shell works inside Dev Containers. Copy the `.devcontainer` folder from the [Pilot Shell repository](https://github.com/maxritter/pilot-shell/tree/main/.devcontainer) into your project, adapt it to your needs (base image, extensions, dependencies), and run the installer inside the container. The installer auto-detects the container environment and skips system-level dependencies like Homebrew.

For tighter isolation when working with untrusted code, layer Claude Code's [`/sandbox`](https://code.claude.com/docs/en/sandboxing) on top — `bubblewrap`, `socat`, `iptables`, and `ipset` are pre-installed in the Dockerfile so it works out of the box on Linux.

### Further reading

- [Claude Code · Development containers](https://code.claude.com/docs/en/devcontainer) — Anthropic's reference container, persistent volumes, organization policy, network egress, the `--dangerously-skip-permissions` flag.
- [Claude Code · Sandboxing](https://code.claude.com/docs/en/sandboxing) — Seatbelt (macOS) and bubblewrap (Linux/WSL2), `/sandbox` modes, `allowedDomains`, filesystem allow/deny rules, security limitations.

## Install Specific Version

```bash
export VERSION=8.4.0
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh | bash
```

See [releases](https://github.com/maxritter/pilot-shell/releases) for all available versions. Useful when a specific version is known stable.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/uninstall.sh | bash
```

Removes binary, plugin files, managed commands/rules, settings, and shell aliases. Your project's custom `.claude/` and `.codex/` files are preserved.

## Reset & Refresh

Accumulated session logs and Pilot's caches grow over time and can degrade performance. A periodic reset every few weeks restores a clean baseline.

```bash
# 1. If using Claude Code, log out first
/logout

# 2. Back up your current config (just in case)
mv ~/.claude.json ~/.claude.json.bak
mv ~/.claude       ~/.claude.bak
mv ~/.codex        ~/.codex.bak
mv ~/.pilot        ~/.pilot.bak

# 3. Reinstall Pilot Shell from the official installer
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh | bash

# 4. Re-activate your license, then start your agent
pilot activate <your-license-key>
claude   # or: codex
```

Once Pilot Shell is running smoothly again, you can delete the `.bak` copies. Forgot your license key? Recover it in the [Pilot members area](https://polar.sh/max-ritter/portal).
