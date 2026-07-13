---
paths:
  - "**/*.cs"
  - "**/*.csproj"
  - "**/*.sln"
---

## .NET / C# Development Standards

**Standards:** `dotnet` CLI for everything | quiet output | analyzers + nullable enforced | self-documenting code.

### Tooling

```bash
dotnet build                                         # build
dotnet run --project src/MyApp                       # run
dotnet test -v q                                     # quiet (preferred); AVOID -v d/diag unless debugging
dotnet test --filter "Category=Unit"                 # run a single category
dotnet format                                        # format
dotnet format --verify-no-changes                    # format check (CI)
dotnet add package <Name>                            # add a dependency (never hand-edit version pins blindly)
```

### Project Configuration (enforce in `.csproj` / `Directory.Build.props`)

- `<Nullable>enable</Nullable>` — fix nullable warnings, don't suppress with `null!`
- `<ImplicitUsings>enable</ImplicitUsings>`
- `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>` — warnings fail the build
- `<EnableNETAnalyzers>true</EnableNETAnalyzers>` with `<AnalysisLevel>latest-recommended</AnalysisLevel>`
- Categorize tests (unit vs integration) using your test framework's category attribute

### Reminders

- **Async:** `async Task` over `async void`; never block on async (`.Result` / `.Wait()` / `GetAwaiter().GetResult()`).
- **HTTP:** `IHttpClientFactory` / typed clients — never `new HttpClient()` (socket exhaustion).
- **Exceptions:** catch specific types; re-throw with `throw;` (preserves the stack), never `throw ex;`.
- **Logging:** inject `ILogger<T>`; structured templates (`Log.Information("Order {OrderId}", id)`), not interpolation.

### ASP.NET

- Minimal APIs for simple endpoints; controllers when you need shared filters/conventions.
- Bind config to `IOptions<T>` instead of reading `IConfiguration` in services.
- Return `ProblemDetails` for errors; configure `app.UseExceptionHandler()` (no stack traces in prod).
- Policy-based authorization (`[Authorize(Policy = "...")]`); keep auth logic out of controllers.

### Testing & Mocking

Use constructor injection + interfaces so dependencies can be substituted in tests:

| Dependency | Substitute with |
|------------|-----------------|
| HTTP | `IHttpClientFactory` (or a fake `HttpMessageHandler`) |
| File I/O | `IFileSystem` (System.IO.Abstractions) |
| Database | `DbContext` in-memory provider, or a mocked repository interface |
| Time | `TimeProvider` (.NET 8+) or `IClock` — never `DateTime.Now` directly |
| Config | `IOptions<T>` — `Options.Create(new MyOptions { ... })` |

- ASP.NET integration tests: `WebApplicationFactory<Program>`.
- Don't share mutable state across tests; use your framework's setup/teardown lifecycle for async init/cleanup and dispose fixtures (connections, temp files).
- Prefer `TaskCompletionSource` over polling/`Task.Delay` when waiting on async results.

### Verification Checklist

- [ ] `dotnet build` — clean (zero warnings; `TreatWarningsAsErrors`)
- [ ] `dotnet test` — pass
- [ ] `dotnet format --verify-no-changes` — formatted
- [ ] No analyzer / nullable warnings
- [ ] File size within the limit (see `development-practices.md` → File size)
