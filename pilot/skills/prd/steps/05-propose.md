## Step 5: Propose Approaches

**Not the same as Step 3 (Ideate).** Ideate is divergent — pitching distinct *directions* when the problem itself is vague. Propose is convergent — once the problem is clear, pitching 2-3 concrete *implementation approaches* for that known problem. If you already did Ideate and the user picked a direction, Step 5 narrows that direction into approaches. If the input was concrete and you skipped Ideate, Step 5 is the first place options get presented.

After understanding the problem:

1. **Propose 2-3 approaches** with clear trade-offs
2. **Lead with your recommendation** and explain why
3. **Present approaches as context**, then use `AskUserQuestion` for selection
4. **Get the user's choice** before proceeding

<!-- CODEX-START
Codex override: when one approach is clearly best and reversible, select it, state the trade-off, and proceed to scope confirmation. Ask a plain-text selection question only when the wrong approach would materially change scope, user experience, data model, or implementation cost.
CODEX-END -->

Each approach should have:
- A short name
- How it works (2-3 sentences)
- Trade-offs framed as "X at the cost of Y"

**Selection:** After presenting approaches in text, use `AskUserQuestion` with each approach as an option. Mark your recommended approach clearly. The user selects — don't proceed without a choice.

<!-- CODEX-START
Selection questions count toward the two-prompt Codex PRD cap. Do not ask separately for approach and scope when one combined prompt can confirm both.
CODEX-END -->
