## Development Practices

### Codebase Exploration

CodeGraph (structure) and Semble (intent) are primary; Grep/Glob are *verifiers* for completeness checks or known-string lookups.

<!-- CC-ONLY -->
Reach for CodeGraph or Semble first on a code-search task; drop to Grep/Glob to verify their results or to find exact text in a known file.
<!-- /CC-ONLY -->
<!-- CODEX-START
In Codex, spend graph calls only when the graph can answer the next question. For docs, rules, markdown, config, UI copy, reviews of a known diff, or named paths, start with direct file reads, `git diff`, or Semble. Call CodeGraph only after that if a runtime symbol relationship, call path, or blast radius is genuinely unknown.
CODEX-END -->

**⛔ NEVER pass `projectPath` to CodeGraph for the current project** — it causes "not initialized" errors. The MCP server defaults correctly.

#### Tool Selection by Scenario

<!-- CC-ONLY -->
CodeGraph and Semble are **co-primary**. Pick by scenario, not by habit. CodeGraph is a single tool (`codegraph_explore`) — full contract in `mcp-servers.md`.

| Scenario | Tool |
|----------|------|
| Any structural question — orient, find a symbol, callers/callees, blast radius, deep-dive across known symbols | `codegraph_explore(query=...)` — one call returns source + call path + impact |
| Understand a concept / feature area | `semble search "how does X work" ./` |
| Find where something is modified | `semble search "settings.json modify write" ./` |
| Cross-cutting concerns | `semble search "notification push events" ./` |
| Debug: "where does X happen" | `semble search "error handling recovery" ./` |
| Find similar patterns | `semble find-related <file> <line> ./` (unique — no CodeGraph equivalent) |

**Combined workflow:** `codegraph_explore` first (structure), then `semble search` (intent) — especially for cross-language connections and non-structural relationships.
<!-- /CC-ONLY -->

<!-- CODEX-START
CodeGraph and Semble are **co-primary**. Pick by scenario, not by habit. CodeGraph is a single tool (`codegraph_explore`) — full contract in `mcp-servers.md`.

| Scenario | Tool |
|----------|------|
| Any structural runtime-code question — orient, find a symbol, callers/callees, blast radius, deep-dive | `codegraph_explore(query=...)` — one call returns source + call path + impact |
| Understand a concept / feature area | `semble search "how does X work" ./` |
| Find where something is modified | `semble search "settings.json modify write" ./` |
| Cross-cutting concerns | `semble search "notification push events" ./` |
| Debug: "where does X happen" | `semble search "error handling recovery" ./` |
| Find similar patterns | `semble find-related <file> <line> ./` |

Use `codegraph_explore` selectively for structural runtime-code questions, especially when entry points are unknown. For docs, rules, markdown, config, UI copy, reviews of a known diff, or named paths, start with direct file reads or Semble; only call CodeGraph if that reveals an actual runtime symbol/call-graph question.

#### Codex Search Budget

During `$spec` and `$prd` planning, the Codex planning contracts override generic exploration rules. At most one CodeGraph orientation call plus one Semble search is enough for most plans where runtime code structure is unknown. If either result is irrelevant, pivot to direct file reads and draft the plan or PRD. Do not run callers/callees/impact analysis for docs, rules, markdown, config, UI-copy changes, reviews of a known diff, or local bugfixes; for runtime code, run it only for functions you are about to modify or have identified as the likely root cause.
CODEX-END -->

Grep/Glob: (1) verifying CodeGraph/Semble completeness, (2) exact text/regex in a known file.

### Change Discipline

- **Think before coding.** When a request is ambiguous, state assumptions, present alternatives, ask — before writing code.
- **Lineage test.** Every changed line must trace to the user's request. If it doesn't, revert.
- **Orphan cleanup.** Remove imports/vars/functions YOUR changes made unused. Don't touch pre-existing dead code — mention, don't delete.
- **Self-check.** "Would a senior engineer call this overcomplicated?" If 200 lines could be 50, rewrite. Complexity is earned by actual requirements.

<!-- The "build the least" ladder + deliberate-shortcut convention below are adapted from ponytail (MIT, © Dietrich Gebert): https://github.com/DietrichGebert/ponytail -->

#### Build the least that works — the ladder

Before writing code, stop at the **first rung that holds**. It's a reflex, not a research project — two rungs both work, take the higher one and move on.

1. **Does this need to exist at all?** Speculative need → skip it, say so in one line. (YAGNI)
2. **Standard library does it?** Use it.
3. **Native platform feature covers it?** Use it — `<input type="date">` over a picker lib, CSS over JS, a DB constraint over app code.
4. **Already-installed dependency solves it?** Use it. Never add a new dependency for what a few lines can do.
5. **Can it be one line?** Make it one line.
6. **Only then** write the minimum code that works.

No unrequested abstractions (no interface with one implementation, no factory for one product, no config for a value that never changes), no boilerplate "for later," fewest files possible. Lazy means *less code, not the flimsier algorithm*: between two same-size stdlib options, take the one correct on edge cases.

**Never simplify away** (these are not on the chopping block): trust-boundary input validation, error handling that prevents data loss, security, accessibility, and the calibration real hardware needs — a minimal model can't see that a real clock drifts or a sensor reads off. Anything the user explicitly asked for stays; if they want the full version, build it without re-arguing.

- **Mark deliberate shortcuts.** When you intentionally ship a simplification with a known ceiling (global lock, O(n²) scan, naive heuristic), leave a `SHORTCUT:` comment naming the ceiling **and** the upgrade trigger: `# SHORTCUT: global lock, per-account locks if throughput matters`. A shortcut with no named trigger rots into "never" — name the trigger or don't take the shortcut. `grep -rnE '(#|//) ?SHORTCUT:' .` harvests the ledger; `/spec` and `/fix` verification surface unresolved markers (see `verification.md`).

**⛔ Never invent values.** File paths, env var names/values, API keys, IDs (UUIDs, FK ids, third-party object ids), URLs, ports, hostnames, version numbers, third-party service names, function/class names not verified to exist, library API signatures — must be authoritatively confirmed (read the code, run the command, or ask). Pattern-matching a plausible value is the top cause of agent-introduced incidents per the 2026 Agentic Coding Trends Report. If unsure, **STOP and ask** — one round-trip beats a hallucination. See *Evidence Before Claims* in `verification.md`.

### Project Policies

- **File size:** aim < 800 lines. > 1000 is a split signal — only when it's the focus of the current task, not a side-refactor. Test files exempt.
- **Dependency check:** before modifying a shared or non-trivial function, run `codegraph_explore(query="<fn> callers and impact")` — its response includes the call path and blast radius, catching callers you'd otherwise miss. Grep only as a completeness check for dynamic/reflective call sites the AST can't follow, not to re-verify codegraph's structural results. A self-contained local function the plan already isolated doesn't need it.
- **Self-correction:** fix obvious mistakes (syntax, typos, missing imports) in code you're actively writing. Do NOT auto-fix code the user edited — report it.
- **Performance:** hot paths (render loops, request handlers, polling) must cache/memoize. Use lighter alternatives for heavy deps. Don't redo work when input hasn't changed.
- **Diagnostics:** check before starting, after changes. Fix all errors before marking complete.
- **Formatting:** automated formatters handle style. **Backward compatibility:** only when explicitly required.

### Systematic Debugging

**No fixes without root cause investigation.** Phases run sequentially:

1. **Root cause** — read errors completely, reproduce consistently, check `git diff`, instrument at boundaries. For multi-factor repros, **minimise**: shrink to the smallest scenario that still fails, cutting elements (halve first, then one at a time) and re-running after each cut; done when every remaining element is load-bearing. A minimal repro shrinks the hypothesis space and becomes the regression test.
2. **Pattern analysis** — `semble search` to find working examples and related code; `semble find-related` from the bug site to discover parallel implementations. Compare; identify ALL differences.
3. **Hypothesis** — when the trace hasn't conclusively pinned the cause, generate **2–3 ranked, specific, falsifiable hypotheses before testing the first**; single-hypothesis generation anchors on the first plausible idea. Each names a concrete mechanism ("state resets because component remounts on route change") and the prediction that would confirm or refute it — no stated prediction means discard or sharpen. Test the top one with minimal change, one variable at a time.
4. **Implementation** — failing test first (TDD), single fix, verify completely.

**Red flags → STOP:** "quick fix for now," multiple changes at once, proposing fixes before tracing data flow, 2+ failed fixes. **3+ failed fixes = architectural problem** — question the pattern, don't fix again.

**Revert-first.** When something breaks: (1) revert the change, (2) consider deleting the broken thing entirely, (3) one-liner targeted fix, (4) none of the above → stop, reconsider.

**Meta-debugging:** treat your own code as foreign. Your mental model is a guess — the code's behavior is truth.

#### Defense-in-Depth (after fixing)

Make the bug structurally impossible, not just patched. Trace backward from symptom to original trigger (`codegraph_explore(query="<fn> callers")`, or `new Error().stack` instrumentation). Fix at the source. Then add validation at every layer the data passes:

| Layer | Purpose |
|-------|---------|
| Entry point | Reject invalid input at API boundary |
| Business logic | Ensure data makes sense for this operation |
| Environment guards | Prevent dangerous ops in specific contexts (e.g., refuse destructive ops outside temp dirs in tests) |
| Debug instrumentation | Capture context for forensics (cwd, stack, args before risky ops) |

Single validation = "fixed." All four layers = "impossible."

#### Condition-Based Waiting (Flakiness)

Replace arbitrary `sleep`/`setTimeout` with polling for the actual condition:

```python
# ❌ flaky
await sleep(500); result = get_result()

# ✅ reliable
result = await wait_for(lambda: get_result() is not None, timeout=5.0)
```

**Use:** flaky tests, async waits. **Don't use** when testing actual timing (debounce, throttle) — document WHY in that case. Poll every 10 ms, always include a timeout with a clear error, call the getter inside the loop (no stale cache).

### Constraint Classification

- **Hard** — non-negotiable (physics, external contracts, security, deadlines)
- **Soft** — conventions or preferences — negotiable if trade-off is stated
- **Ghost** — past constraints baked in that no longer apply

Ghost constraints are the highest-value to find — they lock out options nobody realises are available. Ask "why can't we do X?" — if nobody can name a current requirement, it may be a ghost.

### Merge Conflict Resolution

For an in-progress merge/rebase conflict:

1. **Survey the state** — conflicting files, both sides' git history.
2. **Find the primary sources** for each hunk whose correct resolution isn't evident from the code itself — commit messages, PRs, original issues — to understand why each side changed. Regenerate generated files (lockfiles, build output) instead of hand-resolving them.
3. **Resolve hunk by hunk, preserving both intents.** When they're incompatible: if the merge's stated goal or the user's request discriminates, pick that side and note the trade-off; when neither the primary sources nor the goal settle it, stop and ask — never invent new behaviour inside a resolution. **Never `--abort` on your own initiative** (an explicit user instruction to abort is the exception): resolving is the default; abandoning the merge is the user's call.
4. **Run the project's checks** (typecheck → tests → format) and fix anything the merge broke.
5. **Completing the merge** (`git add`, `git commit`, `git rebase --continue`) follows the Git Operations rules below.

### Git Operations

**Read git state freely. NEVER execute write commands without EXPLICIT user permission.** This is about git commands, not file edits — file editing is always allowed.

- **⛔ Write commands need permission:** `git add`, `commit`, `push`, `pull`, `merge`, `rebase`, `reset`, `stash`, `checkout`. "Fix this bug" ≠ "commit it."
- **⛔ NEVER `git checkout --` on unstaged changes.** Irreversible — work is permanently lost. Tell the user the consequences and let THEM run it. "Remove this" / "revert this" do NOT mean "discard all unstaged work." Use Edit for targeted changes.
- **⛔ Never `git add -f`** — if gitignored, tell the user.
- **⛔ Never selectively unstage** — commit all staged changes as-is.
- **⛔ Always `git push -u` on new branches** so the local branch tracks the correct remote.
- **⛔ Respect the active branch. Never auto-branch.** Work on whatever branch the user has checked out. Do NOT run `git checkout -b`, do NOT switch branches, do NOT invent branch names (e.g. `<username>/<feature>`, `feat/<slug>`, `fix/<slug>`) unless the user explicitly asks for a new branch in *this* request. Project conventions in `CLAUDE.md` / `AGENTS.md` that mandate a branch-naming pattern do NOT count as a request to create one now — surface the convention and ask. The exception is `/spec` with `Worktree: Yes`, which manages branches in an isolated worktree.
- **Read commands always allowed:** `status`, `diff`, `log`, `show`, `branch`.
- **Exceptions:** explicit override ("checkout branch X", "create a new branch for this"), and worktree during `/spec` (`Worktree: Yes`).
