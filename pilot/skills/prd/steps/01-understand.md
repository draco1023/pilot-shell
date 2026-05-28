## Step 1: Understand the Idea

1. **Restate the idea** in your own words — confirm you understand what the user is thinking
<!-- CC-ONLY -->
2. **Explore the project context** — `codegraph_context(task="<idea description>")` for structure, then `mcp__semble__search` for intent-based discovery (feature areas, configuration patterns, cross-cutting concerns). Use `codegraph_search` + `codegraph_explore` for deeper symbol understanding. Check docs and recent commits for additional context.
<!-- /CC-ONLY -->
<!-- CODEX-START
2. **Explore the project context with a bounded pass** — use `codegraph_context(task="<idea description>")` only when the idea touches existing runtime code and entry points are unknown, then at most one `mcp__semble__search` for intent-based discovery. If the user names paths, docs, rules, config, UI copy, or concrete features, read those files directly instead of spending a graph call.
CODEX-END -->
3. **Identify the core problem** — what problem does this solve? For whom? Why now?
4. **Scope check — is this one PRD, or several?** If the request spans multiple independent subsystems (e.g., "build a platform with chat, file storage, billing, and analytics"), flag it now. Do not spend the rest of the workflow refining details of a project that needs to be split first.

   When the project is too large for a single PRD, help the user decompose:
   - List the independent pieces and how they relate
   - Suggest a build order (what unblocks what)
   - Pick **one** sub-project to PRD now — the rest become follow-up PRDs

   <!-- CC-ONLY -->
   Use `AskUserQuestion` to confirm the chosen sub-project before continuing.
   <!-- /CC-ONLY -->
   <!-- CODEX-START
   Use one bundled plain-text prompt to confirm the chosen sub-project before continuing.
   CODEX-END -->

Do NOT jump to solutions. Understand the problem space first.
