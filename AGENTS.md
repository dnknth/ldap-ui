# AGENTS.md

Vue 3 + TypeScript frontend (`src/`) and FastAPI + LDAP3 backend (`backend/ldap_ui/`, imported as `ldap_ui`) — a stateless web UI for LDAP directories.

## Commands

Frontend:

```sh
pnpm dev              # Vite dev server
pnpm type-check       # vue-tsc --build; checks src + vite config. The root tsconfig
                      # is solution-style (files: [] + references), so plain
                      # `npx vue-tsc --noEmit` compiles nothing — always use --build.
pnpm test             # vitest (unit tests in src/*.test.ts)
```

Backend:

```sh
uv run python -m unittest tests.backend_test.RangeTest      # one class
uv run python -m unittest tests.backend_test tests.openapi_test tests.schema_test  # full suite
ruff check .                    # `ruff check --fix .` auto-fixes most findings, then re-run
uvx pyright backend/ tests/                                 # type-check (via `uvx`, not in the venv)
```

Run the server: `make debug` (builds `statics` first) or `uv run ldap-ui --reload --port 5000`.

## Testing quirks

- `ReadOnlyTest`/`LoginModeTest`/`ModificationTest` run against `tests/mock_ldap.py`, an in-process ldap3 `MockAsyncStrategy` directory (the `o=Flintstones` fixture from `demo-ldap/flintstones.ldif` plus a `cn=Subschema` entry from the bundled OpenLDAP 2.4 schema). `LdapMixin` (`tests/backend_test.py`): `setUpClass` rebuilds the directory (`mock_ldap.reset()`) so modifications never leak between classes, resets `settings.BASE_DN`/`SCHEMA_DN` to `None` (a dev `.env` `BASE_DN` would 404 every search — keep that), neutralizes `settings.config` (a dev `BIND_PATTERN` changes login mode), and patches `ldap_connection.open` **and** its `ldap_api` re-export to `mock_ldap.mock_open`; `tearDownClass` restores them (ProbeTest needs the real `open`). `mock_ldap.py` substitutes `MockLdapStrategy` for the stock `MockAsyncStrategy` when building each connection; the stock mock can't satisfy the app: single-response ops store an empty entry list, `'+'` searches return the full attribute list plus `hasSubordinates`, `singleLevel` excludes the base, and filter aliases like `gn` resolve to `givenName`.
- Tests mutate module state (`settings.LDAP_URL`, `settings.config`, the `SCHEMA` cache, auth refs) and restore it — follow that pattern or you'll leak state into later classes.

## OpenAPI fixture workflow (critical gotcha)

- `tests/openapi_test.py` writes `tests/resources/openapi-actual.json` (gitignored) and asserts the app's `/openapi.json` matches the committed `tests/resources/openapi.json`. Update with `cp openapi-actual.json openapi.json` (formatting churn is acceptable).
- The spec is **derived**: FastAPI builds it from the `ldap_api.py` routes **and** the Pydantic models in `entities.py` (names, `Literal`s, `Field` constraints, model titles/$refs) — model changes change the spec like route changes. Regenerate fixture + SDK after either.
- **Version bump**: `__version__` (`backend/ldap_ui/__init__.py`) is embedded in `info.version`, so bumping needs the fixture updated too.
- After API changes regenerate the TS SDK: `pnpm generate` (`openapi-ts -i tests/resources/openapi.json -o ./src/generated`). `src/generated/` is gitignored, rebuilt by `pnpm build` — never commit it.
- The `@/generated` barrel re-exports only the call functions (`sdk.gen`) and model types (`types.gen`), not the `client` instance — the direct imports of `./generated/client.gen`/`sdk.gen` are intentional.

## Backend architecture notes

- Package is `backend/ldap_ui/` (pyproject `package-dir = {"" = "backend"}`); run from repo root, not from `backend/`.
- Stateless by design: a fresh LDAP connection per request (`ldap_connect` in `ldap_connection.py`), `bound()` unbinds in a `finally`.
- `/api/whoami` is a **soft** endpoint: `200 ""` when unauthenticated, never 401 (prevents the browser's native Basic-auth dialog on the startup probe); the login dialog validates against it.
- The app's 401s deliberately omit `WWW-Authenticate` (`app.py`/`ldap_api.py`) — it would pop the native dialog on invalid login. The header belongs to an auth-enforcing reverse proxy; the app's `whoami` probe then returns the DN and the login dialog is skipped.
- `SCHEMA` global cache is guarded by an `anyio.Lock` via `ensure_schema()` — use that, not direct lazy init.
- `/api/probe` surfaces `LDAP_URL` (mis)configuration as a `ProbeResult` (`ok` + `diagnostics[]`, never non-200). `ok` is **usability**, not reachability: false whenever any `severity="error"` diagnostic exists. `/api/health` maps that to 503 for Docker.
- TLS is **verified by default**: `open()` builds `Server(url, tls=Tls(validate=ssl.CERT_REQUIRED))`; only `INSECURE_TLS=1` downgrades to `CERT_NONE`. ldap3 otherwise silently defaults to `CERT_NONE` — never drop the `tls=` argument or TLS is MITM-able. Self-signed certs therefore require `INSECURE_TLS=1`.
- `pyright backend/ tests/` is clean. `settings.BASE_DN`/`SCHEMA_DN` and the `SCHEMA` global are typed `str | None`/`SchemaInfo | None`; read them only via `require_base_dn()`/`require_schema_dn()`/`require_schema()`, or pyright rejects the optional access.
- Auth plumbing lives in `ldap_connection.py`: `get_basic_credentials`, `anonymous_user_search`/`find_bind_dn`, the `SCHEMA` cache + `ensure_schema()`/`get_schema()`, and the `require_*` accessors. `ldap_api.py` keeps only the FastAPI dependency generators.
- `check_password`'s `_auth: AuthenticatedConnection` parameter is deliberately unused: it enforces authentication before probing. The check binds a separate anonymous `NO_INFO` connection to `dn`/`check`, since `ldap_connect` would mutate settings during base/schema resolution. Keep the underscore dependency — removing it drops the auth gate.
- `settings.log_warnings()` (`settings.py:141`) runs only from the `ldap-ui` console script, never request paths — not dead code.
- Concurrency is **anyio only** — no `asyncio` imports (backend or tests). Use `anyio.sleep`/`Lock`/`create_task_group` (no `gather`). Timeouts: `with anyio.fail_after(SECONDS):` — cancel scopes are **synchronous** context managers even in async code. `OPERATION_TIMEOUT` (`ldap_helpers.py`) bounds a single LDAP op and turns expiry into a 504.

## Frontend architecture notes

- Auth is in-memory only (`src/auth.ts`): `setCredentials`/`clearCredentials`, `registerAuthInterceptor` (attaches `Authorization: Basic`), external-auth tracking, and a response interceptor that flags the "external-auth trap" (data endpoint 401s while external auth is active).
- `App.vue` gates the login dialog on `!checking && !ldapDown && !authTrap && !authenticated && loginDialog`, probes `/api/probe` at startup, and renders banners for `ldapDown`, `authTrap`, and `deploymentsIssues`.
- Browser password-manager autofill fights `v-model` (it writes input.value without an `input` event, and Safari ignores `autocomplete="off"` on email-like fields). LoginDialog reads values from DOM refs at submit time as a fallback; there is no fully reliable Safari fix for `mail` fields — don't burn time "fixing" it.

## Repo conventions

- Commits get amended freely (see `git log`); the working tree usually carries incremental changes over `HEAD`.
- Security audit (Aug 2026) complete; remaining findings **accepted**: (1) `DEBUG` enables verbose errors — guard in production; (2) cleartext Basic creds over plain HTTP only on loopback or behind a TLS proxy; (3) `/api/probe`/`/api/health` expose config to unauthenticated callers (needed for the frontend banner and Docker healthcheck). CSRF / missing security headers: not applicable or mitigated (header-based auth; CSP + `Referrer-Policy` on the SPA, `nosniff` + `no-store` on `/api`).
- `.env` is gitignored; settings load a `.env` only if present (avoids a startup warning).
- CI (`.github/workflows/ci.yml`) runs `pnpm build`+`test` and the Python suite via `xmlrunner`; it does **not** run `ruff` or the OpenAPI comparison, so those are local-only checks.