---
sidebar_position: 2
title: Language Servers
description: Real-time diagnostics, go-to-definition, and find-references via auto-installed LSP servers for Python, TypeScript, Go, Rust, and other major languages.
---

# Language Servers

:::warning Claude Code only
Language Server integration requires Claude Code's LSP support. Codex CLI does not have an equivalent LSP integration. On Codex, the `file_checker.py` hook still provides linting and type-checking via the underlying CLI tools (ruff, basedpyright, ESLint, go vet, dotnet format) — but without real-time editor-style diagnostics, hover docs, or go-to-definition.
:::

Real-time diagnostics and go-to-definition for Claude Code, auto-installed and configured.

Language servers give Claude Code real-time diagnostics, type information, and go-to-definition on every file edit. All three are auto-installed and configured via stdio transport — no manual setup. They work alongside the `file_checker.py` hook: hooks catch formatting and linting errors, LSP provides type-level intelligence.

## Python — basedpyright

- Strict type checking with inference
- Real-time diagnostics on every edit
- Go-to-definition and find-references
- Hover documentation for any symbol
- Auto-restart on crash (max 3 attempts)

> Works with uv virtual environments automatically.

## TypeScript — vtsls

- Full TypeScript and JavaScript support
- Type checking across the entire project
- Import auto-completion and refactoring
- Auto-restart on crash (max 3 attempts)

> Handles both `.ts` and `.tsx` files. Respects your `tsconfig.json` settings automatically.

## Go — gopls

- Official Go language server by Google
- Static analysis and vet diagnostics
- Go module-aware resolution
- Rename and code actions support
- Auto-restart on crash (max 3 attempts)

> Requires Go modules. Respects GOPATH and module proxy settings.

## C# — csharp-ls (opt-in)

Unlike the servers above, the C# language server is **not auto-installed** — it needs the .NET SDK, which Pilot does not ship. .NET developers enable it explicitly, so non-.NET users aren't burdened with a .NET toolchain.

[C# LSP](https://claude.com/plugins/csharp-lsp) is the Roslyn-based `csharp-ls` server recommended by Claude. It provides real-time diagnostics, go-to-definition, find-references, hover, and `.editorconfig`-aware formatting for `.cs` files across .NET Core/Framework and multi-project solutions.

**Enable it:**

1. Install the plugin from the [C# LSP plugin page](https://claude.com/plugins/csharp-lsp).
2. Install the server: `dotnet tool install --global csharp-ls` (or `brew install csharp-ls`). Requires .NET SDK 6.0+.

> With the LSP active you get the real-time compile diagnostics that the `file_checker.py` hook does not provide for C# — the hook runs a single-file `dotnet format` check only. Compile errors otherwise surface when you run `dotnet test`.

:::tip Add custom language servers
Add custom language servers via `.lsp.json` in your project root. Each language key maps to its server configuration:

```json
{
  "rust": {
    "command": "rust-analyzer",
    "args": [],
    "transport": "stdio",
    "maxRestarts": 3
  }
}
```
:::
