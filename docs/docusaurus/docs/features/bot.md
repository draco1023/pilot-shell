---
sidebar_position: 2
title: Pilot Bot
description: Persistent Pilot Bot agent — scheduled tasks, background jobs, heartbeat monitoring, and 24/7 automation running on Sonnet for cost-effective Claude operations.
---

# Pilot Bot

Persistent automation agent — scheduled tasks, background jobs, heartbeat monitoring, 24/7 operation. Always runs on Sonnet for cost-effective automation.

```bash
pilot bot
```

Auto-initializes `~/.pilot/bot/` on first run. Only one global instance at a time (PID-enforced). Uses `--continue` to resume previous sessions.

## Optional: Telegram

Install the [Telegram Channels plugin](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/telegram) to enable bidirectional messaging. Pilot Bot auto-detects it at launch — no extra configuration needed. Without Telegram, the bot works as a standalone automation tool.

## Skills

| Skill | Purpose |
|-------|---------|
| **bot-boot** | Boot sequence — health check, job registration via CronCreate, heartbeat setup |
| **bot-heartbeat** | Periodic health check (every 30 min), silent when no issues, dedup via lock file |
| **bot-jobs** | Manage scheduled jobs — `list`, `add`, `remove`, `pause`, `resume`, `edit` |
| **bot-channel-task** | Channel message flow — acknowledge, execute, report (when Telegram available) |
| **bot-defaults** | Standard behaviors — cron deduplication, reporting rules, error handling |

## Config

```
~/.pilot/bot/
├── .bot-pid         # PID file (managed automatically)
└── JOBS.yaml        # Scheduled job definitions (auto-created)
```

Jobs persist in `JOBS.yaml`. CronCreate registrations are session-scoped and re-registered on every boot.
