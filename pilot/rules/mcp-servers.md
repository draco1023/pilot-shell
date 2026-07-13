## Pilot MCP Servers

<!-- CC-ONLY -->
MCP tools are lazy-loaded via `ToolSearch`. Discover by keyword, then call directly. Full param schemas are returned by `ToolSearch` itself — these summaries cover purpose and minimum usage.

```
ToolSearch(query="keyword")               # Discover and load tools by keyword
ToolSearch(query="+server keyword")       # Require a specific server prefix
ToolSearch(query="select:full_tool_name") # Load a specific tool by exact name
```

Each tool resolves as `mcp__<server>__<tool>` (e.g. `mcp__semble__search`, `mcp__codegraph__codegraph_explore`, `mcp__web-search__search`) — the exact names ToolSearch returns and the examples below use. Tools are callable immediately after ToolSearch returns them.
<!-- /CC-ONLY -->
<!-- CODEX-START
MCP tools may be lazy-loaded via `tool_search` or registered at session start — check your available tools. Discover by keyword, then call directly.

```
tool_search(query="keyword")              # Discover and load tools by keyword
tool_search(query="codegraph explore")     # Example: find the CodeGraph tool
```

Each tool resolves as `mcp__<server>__<tool>` (e.g. `mcp__semble__search`, `mcp__codegraph__codegraph_explore`) — check your available tools for the exact names. Tools are callable immediately after discovery.
CODEX-END -->

---

### CodeGraph — Code Knowledge Graph (PRIMARY)

<!-- CC-ONLY -->
**Structural code search.** The fastest way to orient on a code task — replaces Grep/Glob for symbol/call/impact queries. Complements Semble (intent search — see `cli-tools.md`).
<!-- /CC-ONLY -->
<!-- CODEX-START
**Structural code search.** Use for runtime-code structure: unknown entry points, symbol relationships, callers/callees, and blast radius. In Codex, do not spend a graph call on docs, rules, markdown, config, UI copy, reviews of a known diff, or named-file tasks unless a runtime symbol relationship is genuinely unknown. Complements Semble (intent search — see `cli-tools.md`).
CODEX-END -->

<!-- CODEX-START
For `$spec` and `$prd` planning in Codex, CodeGraph is an orientation tool, not a mandate to exhaust the graph. If the first CodeGraph result is irrelevant, pivot to Semble or direct file reads immediately. Do not chain context, search, explore, callers, and impact unless the next step needs that evidence.
CODEX-END -->

<!-- CC-ONLY -->
**One tool — `codegraph_explore`.** The shipped CodeGraph exposes a single tool. It takes either a natural-language question (`"how does auth work"`) or a bag of symbol/file names (`"SymA SymB file.ts"`), and returns the verbatim line-numbered source grouped by file **plus** the call path among those symbols **plus** a blast-radius summary — so ONE call replaces a Grep/Read loop *and* gives you callers + impact in the same response.

| Call | Use for |
|------|---------|
| `codegraph_explore(query="<task description>")` | **START HERE** — orient on a task; entry points + related symbols + source in one call |
| `codegraph_explore(query="SymA SymB relevant-file.ts")` | Deep-dive known symbols — full source from every relevant file at once (replaces dozens of Read/Grep calls) |
| `codegraph_explore(query="callers and impact of processOrder")` | Call flow / blast radius — the response includes the dependency edges; no separate callers/impact tool |

Grep/Glob stay for exact-text sweeps and as a completeness check only for dynamic/reflective call sites the AST can't follow — not for re-verifying codegraph's structural results.
<!-- /CC-ONLY -->
<!-- CODEX-START
**One tool — `codegraph_explore`.** The shipped CodeGraph exposes a single tool that takes a natural-language question OR a bag of symbol/file names and returns verbatim source + the call path + a blast-radius summary in one call.

| Call | Use for |
|------|---------|
| `codegraph_explore(query="<runtime task>")` | Structural orientation when runtime-code entry points are unknown |
| `codegraph_explore(query="SymA SymB file.ts")` | Full source from relevant known symbols/files in one call |
| `codegraph_explore(query="callers and impact of processOrder")` | Call flow / blast radius for a non-local runtime change |

Codex proportionality: skip the graph for named paths, docs/config/rules, UI copy, and reviews of a known diff — read the file or use `git diff` directly. If the first result is irrelevant, pivot to Semble or direct reads instead of re-querying.
CODEX-END -->

**⛔ NEVER pass `projectPath` for the current project.** The server defaults correctly. Passing it triggers a different code path that fails if `.codegraph/` isn't at that exact path. Only use it for genuinely different codebases.

```
codegraph_explore(query="refactor authentication flow")
codegraph_explore(query="processOrder callers and blast radius")
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
| Structural code — orientation, symbols, call tracing, impact, deep-dive | `codegraph_explore` (single tool; one call returns source + callers + blast radius) |
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
| Structural runtime-code — orientation, symbols, call tracing, impact, deep-dive | `codegraph_explore` (single tool; one call returns source + callers + blast radius) |
| Known file/path, docs/rules/config/UI copy, or known diff | Direct file read, `git diff`, or Semble |
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
