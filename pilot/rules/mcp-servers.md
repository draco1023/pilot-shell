## Pilot MCP Servers

<!-- CC-ONLY -->
MCP tools are lazy-loaded via `ToolSearch`. Discover by keyword, then call directly. Full param schemas are returned by `ToolSearch` itself — these summaries cover purpose and minimum usage.

```
ToolSearch(query="keyword")               # Discover and load tools by keyword
ToolSearch(query="+server keyword")       # Require a specific server prefix
ToolSearch(query="select:full_tool_name") # Load a specific tool by exact name
```

All servers use the `mcp__plugin_pilot_` prefix. Tools are callable immediately after ToolSearch returns them.
<!-- /CC-ONLY -->
<!-- CODEX-START
MCP tools may be lazy-loaded via `tool_search` or registered at session start — check your available tools. Discover by keyword, then call directly.

```
tool_search(query="keyword")              # Discover and load tools by keyword
tool_search(query="codegraph context")    # Example: find CodeGraph tools
```

All Pilot servers use the `mcp__plugin_pilot_` prefix. Tools are callable immediately after discovery.
CODEX-END -->

---

### CodeGraph — Code Knowledge Graph (PRIMARY)

<!-- CC-ONLY -->
**Structural code search.** First action on any task. Replaces Grep/Glob for symbol/call/impact queries. Complements Semble (intent search — see `cli-tools.md`).
<!-- /CC-ONLY -->
<!-- CODEX-START
**Structural code search.** Use for runtime-code structure: unknown entry points, symbol relationships, callers/callees, and blast radius. In Codex, do not spend a graph call on docs, rules, markdown, config, UI copy, reviews of a known diff, or named-file tasks unless a runtime symbol relationship is genuinely unknown. Complements Semble (intent search — see `cli-tools.md`).
CODEX-END -->

<!-- CODEX-START
For `$spec` and `$prd` planning in Codex, CodeGraph is an orientation tool, not a mandate to exhaust the graph. If the first CodeGraph result is irrelevant, pivot to Semble or direct file reads immediately. Do not chain context, search, explore, callers, and impact unless the next step needs that evidence.
CODEX-END -->

<!-- CC-ONLY -->
| Tool | Purpose |
|------|---------|
| `codegraph_context(task=...)` | **START HERE** — entry points + related symbols |
| `codegraph_explore(query="SymA SymB file.ts")` | Full source from all relevant files in ONE call (replaces dozens of Read/Grep calls). Use specific symbol/file names — NOT natural language. Run `codegraph_search` first to discover names. |
| `codegraph_search` | Find symbols by name |
| `codegraph_callers` / `codegraph_callees` | Trace call flow before modifying. Supplement with Grep as a *completeness check* for indirect/dynamic callers. |
| `codegraph_impact` | Blast radius before committing to a change |
| `codegraph_node` | Details + source for one symbol |
| `codegraph_files` | Project file tree (NOT Glob/ls) |
<!-- /CC-ONLY -->
<!-- CODEX-START
| Tool | Purpose |
|------|---------|
| `codegraph_context(task=...)` | Structural orientation when runtime-code entry points are unknown; skip for named paths, docs/config/rules, and reviews of a known diff. |
| `codegraph_explore(query="SymA SymB file.ts")` | Full source from relevant known symbols/files in one call. Use specific symbol/file names — NOT broad natural-language questions. |
| `codegraph_search` | Find symbols by name. |
| `codegraph_callers` / `codegraph_callees` | Trace call flow before modifying a runtime function with non-local effects. Supplement with exact-text verification for indirect/dynamic callers. |
| `codegraph_impact` | Blast radius for a non-local runtime change. |
| `codegraph_node` | Details + source for one symbol. |
| `codegraph_files` | Project file tree when structure, not code intent, is the question. |
CODEX-END -->

**⛔ NEVER pass `projectPath` for the current project.** The server defaults correctly. Passing it triggers a different code path that fails if `.codegraph/` isn't at that exact path. Only use it for genuinely different codebases.

```
codegraph_context(task="refactor authentication flow")
codegraph_callers(symbol="processOrder")
codegraph_impact(symbol="processOrder", depth=2)
```

---

### Semble — Hybrid Code Search (CO-PRIMARY)

**Intent-based code search — co-primary with CodeGraph.** Excels at concept/feature discovery, cross-language search, finding mutation sites, and debugging queries where CodeGraph's name-based matching falls short. Hybrid BM25 + Model2Vec embeddings, code-aware chunking, ~1.5ms queries, ~263ms cold-index per repo (cached after). Auto-reindex on file change for local paths. Two tools:

| Tool | Purpose |
|------|---------|
| `mcp__semble__search(query, repo?, top_k?, mode?)` | Natural-language or symbol search. `mode` defaults to `hybrid` (best for most queries); also `semantic` / `bm25`. `repo` is a local path or `https://` git URL; omit when a default index was configured at startup. |
| `mcp__semble__find_related(file_path, line, repo?, top_k?)` | Find code semantically similar to a specific location. Use `file_path` + `line` from a prior `search` result. |

```
mcp__semble__search(query="authentication flow", repo="/abs/path")
mcp__semble__search(query="save_pretrained", top_k=10)          # symbol-style
mcp__semble__find_related(file_path="src/auth.ts", line=42, repo="/abs/path")
```

**When NOT to use Semble:** structural questions (callers, callees, impact) — use CodeGraph instead. Semble can find code that *looks* like a caller but cannot enumerate them.

Also available as a CLI (`semble search`, `semble find-related`, `semble savings`) — see `cli-tools.md`.

---

### mem-search — Persistent Memory

Past work, decisions, context across sessions. **3-step workflow — never skip to step 3:**

1. `search(query, limit, type, project, dateStart, dateEnd)` → returns index with IDs
2. `timeline(anchor=ID or query, depth_before, depth_after)` → context around an anchor
3. `get_observations(ids=[...])` → full details for filtered IDs only

`save_memory(text, title?, project?)` to record findings.

**Types:** `bugfix`, `feature`, `refactor`, `discovery`, `decision`, `change`.

---

### context7 — Library Documentation

Up-to-date docs and code examples for any library/framework. Two steps:

1. `resolve-library-id(libraryName, query)` → returns `libraryId` like `/pypi/pytest`
2. `query-docs(libraryId, query)` → answers using indexed docs

Use descriptive queries. Max 3 calls per question per tool.

---

### web-search — Web Search

`search(query, limit?, engines?)` — DuckDuckGo / Bing / Exa, no API keys.

Article fetchers: `fetchGithubReadme(url)`, `fetchLinuxDoArticle(url)`, `fetchCsdnArticle(url)`, `fetchJuejinArticle(url)`.

---

### web-fetch — Web Page Fetching

Playwright-backed; no truncation; handles JS-rendered pages.

- `fetch_url(url, ...)` — single page
- `fetch_urls(urls=[...], ...)` — multiple pages
- `browser_install(withDeps?, force?)` — install Chromium

Useful options: `waitUntil` (`load`/`domcontentloaded`/`networkidle`), `returnHtml`, `waitForNavigation` (anti-bot).

---

### grep-mcp — GitHub Code Search

`searchGitHub(query, language?, repo?, path?, useRegexp?, matchCase?)` — finds real-world code in 1M+ public repos. Query is a literal pattern (or regex with `useRegexp=true`; prefix `(?s)` for multiline). Filter `language=["Python"]`, `repo="vercel/next-auth"`, `path="src/components/"`.

---

### Tool Selection Quick Reference

<!-- CC-ONLY -->
| Need | Tool |
|------|------|
| Task orientation (FIRST on every task) | `codegraph_context` |
| Symbol search by name | `codegraph_search` |
| Call tracing / impact analysis | CodeGraph (`callers` / `callees` / `impact`) |
| Deep code understanding (known symbols) | `codegraph_explore` |
| Concept / feature area search | Semble (`mcp__semble__search` or `semble search`) |
| "Where is X modified / configured" | Semble — finds mutation sites across languages |
| Cross-cutting concern discovery | Semble — surfaces full feature stack (UI, routes, logic) |
| Find similar code / parallel patterns | Semble `find_related` (unique — no CodeGraph equivalent) |
| Past work / decisions | mem-search 3-step |
| Library/framework docs | context7 |
| Web search | web-search |
| GitHub README | web-search `fetchGithubReadme` |
| Production code examples | grep-mcp |
| Full web page content | web-fetch |
<!-- /CC-ONLY -->
<!-- CODEX-START
| Need | Tool |
|------|------|
| Structural runtime-code orientation when entry points are unknown | `codegraph_context` |
| Known file/path, docs/rules/config/UI copy, or known diff | Direct file read, `git diff`, or Semble |
| Symbol search by name | `codegraph_search` |
| Call tracing / impact analysis for non-local runtime changes | CodeGraph (`callers` / `callees` / `impact`) |
| Deep code understanding for known symbols | `codegraph_explore` |
| Concept / feature area search | Semble (`mcp__semble__search` or `semble search`) |
| "Where is X modified / configured" | Semble — finds mutation sites across languages |
| Cross-cutting concern discovery | Semble — surfaces full feature stack (UI, routes, logic) |
| Find similar code / parallel patterns | Semble `find_related` (unique — no CodeGraph equivalent) |
| Past work / decisions | mem-search 3-step |
| Library/framework docs | context7 |
| Web search | web-search |
| GitHub README | web-search `fetchGithubReadme` |
| Production code examples | grep-mcp |
| Full web page content | web-fetch |
CODEX-END -->
