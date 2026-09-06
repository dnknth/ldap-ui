# AGENTS.md

Vue 3 + TypeScript frontend (`src/`) and FastAPI + LDAP3 backend (`backend/ldap_ui/`, imported as `ldap_ui`) — a stateless web UI for LDAP directories. Python ≥3.10 via `uv` (see `pyproject.toml`), Node via `pnpm` (see `package.json`).

## Commands

Frontend (prefer fast checks over the CI script):

```sh
pnpm dev              # Vite dev server
pnpm type-check       # vue-tsc --build; checks src + vite config. The root tsconfig
                      # is solution-style (files: [] + references), so plain
                      # `npx vue-tsc --noEmit` compiles nothing — always use --build.
pnpm test             # vitest (unit tests in src/*.test.ts)
```

Backend:

```sh
uv run python -m unittest tests.backend_test.RangeTest      # one class (no Docker needed)
uv run python -m unittest tests.backend_test tests.openapi_test tests.schema_test  # full suite
ruff check .                    # `ruff check --fix .` auto-fixes most findings, then re-run
uvx pyright backend/ tests/                                 # type-check (via `uvx`, not in the venv)
```

Run the server: `make debug` (builds `statics` first) or `uv run ldap-ui --reload --port 5000`.

## Testing quirks

- **Docker required** for `ReadOnlyTest` and `ModificationTest`: they spin up the `dnknth/ldap-demo` container via testcontainers (`LdapMixin` in `tests/backend_test.py`) and point `settings.LDAP_URL` at it. Run these only with Docker Desktop running. `LdapMixin.setUpClass` also resets `settings.BASE_DN`/`settings.SCHEMA_DN` to `None` before connecting — a developer's `.env` (e.g. `BASE_DN=dc=foo`) would otherwise make every directory search 404 with "No Such Object". Keep that reset.
- Docker-independent classes: `RangeTest`, `NormalizeDnTest`, `StripSensitiveTest`, `ProbeTest`, `SchemaCacheTest`.
- Several tests mutate module state (`settings.LDAP_URL`, `settings.config`, the `SCHEMA` cache, auth refs) — they are written to restore it; when adding tests, follow that pattern or you'll leak state into later classes.
- Testcontainers/ryuk is deliberately disabled (`ryuk_disabled = True`) — do not "fix" that.

## OpenAPI fixture workflow (critical gotcha)

- `tests/openapi_test.py` writes `tests/resources/openapi-actual.json` (gitignored via `*-actual.*`) and asserts the running app's `/openapi.json` matches the committed `tests/resources/openapi.json`. Update the fixture with `cp openapi-actual.json openapi.json` (formatting churn is acceptable).
- The OpenAPI spec is **derived**: FastAPI builds `/openapi.json` from the routes in `ldap_api.py` **and** the Pydantic models in `backend/ldap_ui/entities.py` (field names, `Literal`s, `Field` constraints, `BaseModel` class names become schema titles/$refs). So model changes (renames, added/removed fields, adjusted constraints) change the spec exactly like route changes do — regenerate the fixture and SDK after any of them.
- **Version bump**: `__version__` lives in `backend/ldap_ui/__init__.py`; it is embedded in the OpenAPI `info.version`, so bumping requires updating the fixture too.
- After changing the API, regenerate the TS SDK: `pnpm generate` (`openapi-ts -i tests/resources/openapi.json -o ./src/generated`). `src/generated/` is gitignored and rebuilt by `pnpm build` — never commit it.

## Backend architecture notes

- Package is `backend/ldap_ui/` (pyproject `package-dir = {"" = "backend"}`); run from repo root, not from `backend/`.
- Stateless by design: a fresh LDAP connection per request (`ldap_connect` in `ldap_connection.py`), `bound()` unbinds in a `finally`.
- `/api/whoami` is a **soft** endpoint: returns `200 ""` when unauthenticated and never 401s (that is what prevents the browser's native Basic-auth dialog on the startup probe). The login dialog validates credentials against it.
- The app's own 401s deliberately omit `WWW-Authenticate` (`app.py`/`ldap_api.py`), because the frontend only consumes the status code and the `/api/whoami` empty DN — never the header. Do not re-add it: it would make the browser open its native Basic-auth dialog whenever the login form submits invalid credentials. This is safe with upstream Basic auth: a reverse proxy that performs Basic auth issues its *own* `WWW-Authenticate` and forwards the browser's credentials to the app; the app's `whoami` probe then returns the DN and the login dialog is skipped. The header belongs to the auth-enforcing proxy, not this app.
- `SCHEMA` global cache is guarded by an `anyio.Lock` via `ensure_schema()` — use that, not direct lazy init.
- `LDAP_URL` (mis)configuration is surfaced by `/api/probe`, which returns a `ProbeResult` with `ok` + `diagnostics[]` (never a non-200, so the frontend can read the details). `ok` is **usability**, not reachability: it is false whenever any `severity="error"` diagnostic exists (unreachable directory, missing/unusable base or schema, unconfigurable login — anything that leaves nothing working), not only when the directory is down. `/api/health` maps that 503 for Docker.
- TLS is **verified by default**: `open()` in `ldap_connection.py` builds `Server(url, tls=Tls(validate=ssl.CERT_REQUIRED))`; only `INSECURE_TLS=1` downgrades to `CERT_NONE` (the flag's documented purpose). ldap3 otherwise silently defaults to `CERT_NONE` — never drop the `tls=` argument "for simplicity" or TLS connections become MITM-able. A deployment with a self-signed cert must set `INSECURE_TLS=1` (the `/api/probe` `insecure-tls` warning flags it).
- `pyright backend/ tests/` is clean. Module-level `settings.BASE_DN`/`SCHEMA_DN` and the `SCHEMA` global (in `ldap_connection.py`) are typed `str | None`/`SchemaInfo | None`; requests go through the `require_base_dn()`/`require_schema_dn()`/`require_schema()` accessors (which raise if unresolvable) rather than reading the raw attributes, or pyright rejects the `str | None` assumptions. Don't reintroduce silent optional-attribute reads.
- Auth plumbing lives in `ldap_connection.py`: `get_basic_credentials`, `anonymous_user_search`/`find_bind_dn`, the `SCHEMA` cache + `ensure_schema()`/`get_schema()`, and the `require_*` accessors. `ldap_api.py` keeps only the FastAPI dependency generators (`authenticated`, `optional_authenticated`, `AuthenticatedConnection`).
- Concurrency primitives are **anyio only** — no `asyncio` imports anywhere (backend or tests). Use `anyio.sleep`, `anyio.Lock`, `anyio.create_task_group` (there is no `gather`; spawn via task group). Timeouts use `with anyio.fail_after(SECONDS):` — anyio cancel scopes are **synchronous** context managers even in async code, so `async with` will not work. `OPERATION_TIMEOUT` in `ldap_helpers.py` bounds a single LDAP operation and turns expiry into a 504. Polling idiom: `get_response(msgid, timeout=0)` + `await anyio.sleep(0.01)` inside the `fail_after`.

## Frontend architecture notes

- Auth is in-memory only (`src/auth.ts`): `setCredentials`/`clearCredentials`, `registerAuthInterceptor` (attaches `Authorization: Basic`), external-auth tracking, and a response interceptor that flags the "external-auth trap" (data endpoint 401s while external auth is active).
- `App.vue` gates the login dialog on `!checking && !ldapDown && !authTrap && !authenticated && loginDialog`, probes `/api/probe` at startup, and renders banners for `ldapDown`, `authTrap`, and `deploymentsIssues`.
- Browser password-manager autofill fights `v-model` (it writes input.value without an `input` event, and Safari ignores `autocomplete="off"` on email-like fields). LoginDialog reads values from DOM refs at submit time as a fallback; there is no fully reliable Safari fix for `mail` fields — don't burn time "fixing" it.

## Repo conventions

- Commits get amended freely (see `git log`); the working tree usually carries incremental changes over `HEAD`.
- Security audit (Aug 2026) is complete; reviewed issues are resolved and the remaining ones are **accepted** (decision: not worth fixing now). Remaining findings: (1) `DEBUG` flag enables verbose error detail if enabled — guard it in production (`DEBUG` only via env); (2) cleartext Basic credentials over plain HTTP, acceptable only because the documented deployment binds to `127.0.0.1` loopback or sits behind a TLS-terminating proxy — never publish the port beyond loopback without TLS; (3) `/api/probe` and `/api/health` deliberately expose configuration state to unauthenticated callers (base/schema resolution, anonymous-bind denial, `INSECURE_TLS`, `BIND_PATTERN` presence) — by design, required for the frontend banner and the Docker healthcheck, and only relevant if the port is ever published beyond loopback without a proxy. CSRF and missing security headers were investigated and are not applicable / already mitigated (auth is header-based, no ambient credentials; CSP + `Referrer-Policy` are on the SPA, `nosniff` + `no-store` on `/api`).
- `.env` is gitignored; settings load a `.env` only if present (avoids a startup warning).
- CI (`.github/workflows/ci.yml`) runs `pnpm build`+`test` and the Python suite via `xmlrunner`; it does **not** run `ruff` or the OpenAPI comparison, so those are local-only checks.