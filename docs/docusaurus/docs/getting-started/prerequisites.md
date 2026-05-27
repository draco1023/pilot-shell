---
sidebar_position: 1
title: Prerequisites
description: What you need before installing Pilot Shell — at least one AI agent (Claude Code or Codex CLI), a subscription or API key, and a POSIX shell environment.
---

# Prerequisites

What you need before installing Pilot Shell.

## At Least One AI Agent

Pilot Shell supports **Claude Code** (Anthropic, primary — full feature coverage) and **Codex CLI** (OpenAI — all workflows, fewer platform features). Install at least one. The Pilot installer auto-detects and configures both.

### Claude Code

Install [Claude Code](https://code.claude.com/docs/en/quickstart) using the **native installer**. If you have the `npm` or `brew` version, uninstall it first. Requires a Claude subscription:

| Plan | Audience | Notes |
|------|----------|-------|
| **Max 5x** | Solo — moderate usage | Good for part-time or focused coding sessions |
| **Max 20x** | Solo — heavy usage | Recommended for full-time AI-assisted development |
| **Team Premium** | Teams | 6.25x usage per member + SSO, admin tools, billing management |
| **Enterprise** | Companies | For organizations with compliance, procurement, or security requirements |

### Codex CLI

Install [Codex CLI](https://developers.openai.com/codex/cli) via `npm i -g @openai/codex`. Requires an [OpenAI API key](https://platform.openai.com/api-keys). See the [Codex CLI guide](/docs/getting-started/codex-cli) for the detailed feature matrix.

## Codex Companion Plugin (Included)

The [Codex companion plugin](https://github.com/openai/codex-plugin-cc) is installed automatically with Pilot. It provides adversarial code review powered by OpenAI — an independent second opinion during Claude Code's `/spec` planning and verification.

**Setup:** Run `/codex:setup` once to authenticate, then enable the reviewers in Console Settings → Reviewers. This is separate from Codex CLI — the companion runs from within Claude Code.

## System Requirements

Pilot installs once and works across all your projects. Each project can have its own `.claude/` rules and skills.

| Platform | Notes |
|----------|-------|
| **macOS** | 10.15 Catalina or later, Apple Silicon and Intel |
| **Linux** | Debian, Ubuntu, RHEL-based distros, and most others |
| **Windows** | WSL2 required — native Windows not supported |

:::tip Windows users
Install WSL2 first (`wsl --install -d Ubuntu`), then run the installer inside Ubuntu.
:::
