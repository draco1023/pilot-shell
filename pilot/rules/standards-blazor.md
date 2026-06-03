---
paths:
  - "**/*.razor"
  - "**/*.razor.css"
  - "**/*.razor.cs"
---

## Blazor Standards

Framework-specific guidance for Blazor components.

### Components

- **Parameters:** `[Parameter]` properties with sensible defaults; `[EditorRequired]` for mandatory ones.
- **Parent notification:** use `EventCallback<T>` — never call `StateHasChanged()` from a child to refresh a parent (`EventCallback` triggers it automatically).
- **Shared state:** prefer `[CascadingParameter]` or an injected, registered state service over deep parameter drilling.
- **Code organization:** keep markup in `.razor`, logic in a code-behind partial class (`MyComponent.razor.cs`) — avoid large `@code` blocks.

### Styling

- Use CSS isolation (`MyComponent.razor.css`); styles auto-scope via `b-{hash}` — no BEM/naming needed. Use `::deep` to reach child markup.

### Rendering & Lifecycle

- Choose render mode deliberately: `InteractiveServer` / `InteractiveWebAssembly` only when interactivity is needed — don't default to interactive when static SSR suffices.
- Lists: set `@key` so the diff algorithm tracks items; override `ShouldRender()` to skip needless re-renders on hot paths.
- Dispose: `@implements IDisposable` / `IAsyncDisposable` to release timers, event handlers, and subscriptions (a common leak source in `InteractiveServer`).

### Checklist

- [ ] Parameters typed with `[Parameter]`; mandatory ones `[EditorRequired]`
- [ ] Parent updates via `EventCallback<T>`, not child-side `StateHasChanged()`
- [ ] Logic in code-behind; CSS isolation for component styles
- [ ] `@key` on lists; render mode intentional; disposables implemented
