---
name: setup-rules
description: Set up and audit project rules — reads codebase, generates modular rules, documents MCP servers
user-invocable: true
---
# /setup-rules - Set Up Project Rules

**Set up and audit project rules.** Reads your codebase, generates modular rules, and documents MCP servers.

**Flow:** Read existing → Migrate → Quality audit → Explore → Compare → Sync rules → Sync MCP → Discover rules → Cross-check → Sync AGENTS.md → Summary

**Skill creation:** Use `/create-skill` to create workflow skills — `/setup-rules` focuses exclusively on rules and MCP documentation.

<!-- CC-ONLY -->
**⛔ ALWAYS use the `AskUserQuestion` tool** for user questions — never list numbered questions in plain text.
<!-- /CC-ONLY -->
<!-- CODEX-START
**⛔ ALWAYS use plain-text numbered options** for user questions — never refer to `AskUserQuestion` as a callable tool in Codex. Present options with trade-offs and wait for the user's response.
CODEX-END -->
