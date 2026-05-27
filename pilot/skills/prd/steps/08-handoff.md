## Step 8: Hand Off to /spec

After the user confirms the PRD:

**Ask:** "Ready to hand this off to `/spec` for implementation planning?"

Use `AskUserQuestion` with options:
- **"Yes, start /spec now"** — invoke `/spec` immediately
- **"No, I'll run /spec later"** — just confirm the PRD path

### If yes — invoke /spec:

<!-- CC-ONLY -->
```
Skill('spec', args='<one-line-summary> — PRD: docs/prd/YYYY-MM-DD-slug.md — see PRD for full requirements')
```
<!-- /CC-ONLY -->
<!-- CODEX-START
Codex has no callable phase-dispatch tool. Continue immediately with the `$spec` skill instructions using arguments: `<one-line-summary> — PRD: docs/prd/YYYY-MM-DD-slug.md — see PRD for full requirements`.
CODEX-END -->

**The args string must NOT end in `.md`** — the trailing text after the path prevents the `/spec` dispatcher from treating it as an existing plan file. The dispatcher only triggers plan-file mode when args end with `.md` AND the file exists.

### If no:

```
PRD saved to docs/prd/YYYY-MM-DD-slug.md

To implement later, run:
  /spec "Implement <summary> — PRD: docs/prd/YYYY-MM-DD-slug.md — see PRD for full requirements"
```
