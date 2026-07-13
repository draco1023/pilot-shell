---
paths:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.html"
  - "**/*.vue"
  - "**/*.svelte"
  - "**/*.razor"
  - "**/*.css"
  - "**/*.scss"
  - "**/*.sass"
  - "**/*.less"
  - "**/*.module.css"
  - "**/*.razor.css"
---

# Frontend Standards

## Components

**Small, focused components with single responsibility. Compose complex UIs from simple pieces.**

- **Single responsibility:** If you need "and" to describe it, split it
- **Minimal props:** Under 5-7. More = component doing too much. Always typed with defaults.
- **State:** Keep local — only lift when multiple components need it. Prop drilling 3+ levels → use composition or context.
- **Naming:** Components: PascalCase nouns. Props: camelCase, booleans `is*`/`has*`. Events: `on*` for props, `handle*` internal.
- **Split when:** >600-800 lines (deliberately stricter than the global 800/1000 in `development-practices.md` — JSX/component files grow unwieldy faster), multiple responsibilities, reusable elsewhere, testing becomes difficult.

## CSS

**Follow project methodology consistently. Identify first: Utility-first (Tailwind), CSS Modules, BEM, CSS-in-JS, or CSS isolation. Never mix.**

- Use design tokens (`var(--color-primary)`) over hardcoded values
- Work with the framework — if you need `!important`, reconsider your approach
- Custom CSS only for: complex animations, unique effects, third-party integration, browser fixes

## Accessibility

- **Semantic HTML first:** `<button>` for actions, `<a>` for navigation, landmarks (`<nav>`/`<main>`/`<header>`)
- **Keyboard:** Tab navigates, Enter/Space activates, Escape closes. Visible focus indicators always.
- **Labels:** Every input needs a label. `aria-label` for icon-only buttons.
- **Images:** Informative: descriptive alt text. Decorative: `alt=""`
- **Color contrast — verify, never eyeball:** Body/label text ≥ 4.5:1 against its *actual* background, large text (≥18px or bold ≥14px) ≥ 3:1, placeholders ≥ 4.5:1. The single most common failure: muted gray text (or low-opacity ink) that passes on the base background but **fails on elevated surfaces** — cards, modals, dropdowns are lighter/darker than the page, so re-check every surface a token lands on, in *every* theme. Button-label text must clear 4.5:1 against the **button fill**, not the page. Gray text on a colored background reads washed out — use a darker shade of the background's own hue, or a transparency of the text color. Never convey info by color alone. (`impeccable detect` flags many of these; for exact ratios, compute them.)
- **ARIA:** Semantic HTML first, ARIA second. `aria-live="polite"` for dynamic content.
- **Headings:** One `<h1>` per page. Don't skip levels.

## Responsive Design

**Mobile-first with `min-width` media queries.** Use project's standard breakpoints — never arbitrary values.

- **Fluid layouts:** `width: 100%` + `max-width`, grid with `1fr`/`minmax()`/`auto-fit`
- **Units:** `rem` for spacing/layout, `em` for component-relative, `px` only for borders/shadows, `ch` for text widths
- **Touch targets:** Min 44x44px (iOS) / 48x48px (Android)
- **Typography:** Body 16px min, line-height 1.5. Fluid: `clamp(2rem, 5vw, 3rem)`
- **Images:** Use `srcset` and `sizes`

## Design Direction

**Commit to a clear aesthetic. Every visual choice must be intentional.**

**Before coding, answer these four questions:**

1. **Purpose** — What does this interface communicate? Who uses it?
2. **Audience** — Developers? Consumers? Internal tooling?
3. **Tone** — Minimalist, editorial, playful, industrial, luxury, retro-futuristic, etc.
4. **Differentiator** — What's the one thing someone will remember?

Then execute that direction with precision across every detail below.

- **Typography:** Display font for personality, body font for readability. Max 2 fonts. Avoid defaults (Inter, Roboto, Arial, system fonts). Distinctive, characterful choices elevate the entire interface.
- **Color:** Clear hierarchy: Primary (CTAs) → Accent → Neutral → Semantic. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Dark mode: design separately, not just invert.
- **Spacing:** Generous whitespace. Cramped = low quality.
- **Spatial Composition:** Break out of predictable grid layouts. Use asymmetry, overlapping elements, diagonal flow, or grid-breaking accents to create visual interest. Controlled density and unexpected placement make interfaces feel designed rather than templated.
- **Visual Depth:** Create atmosphere beyond solid backgrounds. Use gradient meshes, subtle noise textures, layered transparencies (on background/decorative layers — not blurred translucent card surfaces, which is the glassmorphism ban below), dramatic shadows, decorative borders, or grain overlays — matched to the overall aesthetic. Flat and empty ≠ minimal; depth creates polish.
- **Motion:** Every animation has purpose. Max 500ms. Always respect `prefers-reduced-motion`. Prefer one well-orchestrated page load with staggered reveals (`animation-delay`) over scattered micro-interactions. Use scroll-triggered animations and surprising hover states for high-impact moments. CSS-only for HTML; Motion library for React when available.
- **Avoid AI aesthetic:** Purple gradients on white, symmetric 3-column grids, rounded shadowed cards, overused font families (Inter, Space Grotesk, Geist), cookie-cutter component patterns. The hardest, most recognizable tells are listed under **Absolute Bans** below — treat those as match-and-refuse, not preferences.

## Absolute Bans (match-and-refuse)

**If you're about to write any of these, stop and rewrite the element with different structure.** They are the most recognizable "AI made this" tells; one of them on a page undoes a lot of otherwise-good work. The `impeccable detect` CLI flags most of them at verify time (see `browser-automation.md` → "Design-Quality Detector") — avoid them at write time so the detector stays quiet.

- **Side-stripe borders.** A `border-left`/`border-right` thicker than 1px used as a colored accent on cards, list items, callouts, or alerts. Rewrite with a full border, a background tint, a leading icon/number, or nothing. *(A left border on a `<blockquote>` is the conventional affordance and is fine.)*
- **Gradient text.** `background-clip: text` over a gradient. Decorative, never meaningful — use a single solid color; carry emphasis with weight or size.
- **Glassmorphism as default.** Decorative blur / translucent "glass" cards. Rare and purposeful, or not at all.
- **The hero-metric template.** Big number + small label + supporting stats + gradient accent. The SaaS-landing cliché.
- **Identical card grids.** Same-sized icon-+-heading-+-text cards repeated down the page. Vary structure, or use a different layout (list, table, prose).
- **Uppercase tracked eyebrow on every section.** A small all-caps wide-tracked kicker ("ABOUT", "FEATURES") above every heading. One named kicker as a deliberate system is voice; one on every section is AI grammar. *(Product dashboards may use uppercase section labels — the Linear/Notion convention — that is not this ban; the ban is the per-section marketing eyebrow.)*
- **Numbered section scaffolding (01 / 02 / 03).** Numbers above every section by reflex. They earn their place only when the section genuinely IS an ordered sequence the reader needs.
- **Text that overflows its container.** Long heading words + large `clamp()` scales + narrow grids overflow on tablet/mobile. The viewport is part of the design — test heading copy at every breakpoint and reduce the clamp max or rewrite the copy if it breaks.

## Performance

- **Cache expensive work:** Parsing, transforming, or filtering data in a render/update path must be memoized. If input hasn't changed, output must not be recomputed.
- **Isolate re-renders:** List items should not re-render when unrelated parent state changes. Use framework memoization primitives on list item components.
- **Minimize dependency weight:** Import only what you use. Full library imports where tree-shaken alternatives exist waste bandwidth and parse time.
- **Polling-safe:** If the view refreshes on an interval, child components must not redo expensive work when the underlying data hasn't changed.

## Checklist

- [ ] Components: single responsibility, typed props, local state
- [ ] CSS: project methodology, design tokens, no `!important`
- [ ] Accessible: keyboard, labels, alt text; contrast verified ≥4.5:1 on every surface and theme (incl. button text on its fill)
- [ ] Responsive: mobile-first, fluid, touch targets ≥ 44px
- [ ] Performance: expensive work cached, re-renders isolated, deps tree-shaken, polling-safe
- [ ] Design: intentional direction, visual depth, composition — and zero Absolute Bans
