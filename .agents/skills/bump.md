---
name: Bump & Release
description: Bump backend and frontend dependencies, bump the project patch version, then run the release steps (build, publish to PyPI, rebuild Docker images).
---

# Bump & Release

Bump backend and frontend dependencies, bump the project patch version, then run the release steps (build, publish to PyPI, rebuild Docker images).

This skill re-uses the `release` skill for the build/publish/Docker steps — do not duplicate them here.

## Workflow

1. **Bump dependencies**
    - Backend (uv): `uv sync --upgrade`
    - Frontend (pnpm): `pnpm update`
    - Abort if nothing has changed.
    - Audit production deps: `pnpm audit --prod`

2. **Bump the patch version**
    - The version lives in `backend/ldap_ui/__init__.py` (`__version__`, e.g. `"0.15.5"`).
    - Read it, bump the patch version (`X.Y.Z` → `X.Y.Z+1`).

3. **Update OpenAPI**
    - The version bump changes `info.version` in the spec, so regenerate the fixture (AGENTS.md: the spec is derived from the routes + Pydantic models, and `__version__` is embedded in `info.version`).
    - Run the OpenAPI test to write the actual spec, then copy it over the committed fixture:
        ```sh
        uv run python -m unittest tests.openapi_test
        mv tests/resources/openapi-actual.json tests/resources/openapi.json
        ```

4. **Commit**
    - `git add` the changed files (dependency lockfiles, `backend/ldap_ui/__init__.py`, `package.json`, `pnpm-lock.yaml`, `uv.lock`, `tests/resources/openapi.json`).
    - If the last commit message is `Bump dependencies` or similar, **amend** it, otherwise create a **new** commit with the message `Bump dependencies`.

5. **Run the release steps**
    - Load the `release` skill and follow its workflow for the build, PyPI publish, and Docker rebuild.
