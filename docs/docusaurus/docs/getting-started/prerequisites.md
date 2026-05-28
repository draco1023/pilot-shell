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

Install [Codex CLI](https://developers.openai.com/codex/cli) using the **native installer**. If you have the `npm` or `brew` version, uninstall it first. Authenticate with your ChatGPT account or an API key on first run. Requires a ChatGPT subscription:

| Plan | Audience | Notes |
|------|----------|-------|
| **Plus** | Solo — moderate usage | Good for focused coding sessions each week |
| **Pro $100** | Solo — heavy usage | 5x Plus limits — recommended for full-time AI-assisted development |
| **Pro $200** | Solo — very heavy usage | 20x Plus limits — for the most intensive workflows |
| **Business** | Teams | Flexible credit-based pricing, cloud integrations |
| **Enterprise** | Companies | Compliance, admin tools, organization-wide access |

**API key** is available for automation and CI but is pay-per-token and lacks cloud features (GitHub code review, Slack integration, delayed model access). See [pricing](https://developers.openai.com/codex/pricing) for details.

See the [agent comparison](/docs/getting-started/codex-cli) for the full feature matrix.

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
