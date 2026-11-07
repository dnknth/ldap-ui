---
name: Release
description: Build, publish to PyPI, and rebuild Docker images.
---

# Release

Build, publish to PyPI, and rebuild Docker images.

## Workflow

1. **Run tests**
    - Backend (discover all `*_test.py` in `tests/`, excluding the `mock_ldap.py` helper): `uv run python -m unittest discover -s tests -p "*_test.py"`
    - Frontend: `pnpm test`

2. **Check the version**
    - Read `__version__` from `backend/ldap_ui/__init__.py`:
        ```sh
        fgrep __version__ backend/ldap_ui/__init__.py | cut -d'"' -f2
        ```
    - If it's unchanged since the last commit (`git diff --quiet backend/ldap_ui/__init__.py` exits 0), ask the user for a new version to bump to, offering to abort. Amend the last commit with the new version.

3. **Push**
    - Abort if there are any other uncommitted changes.
    - If the last commit was amended, push with `--force-with-lease`; otherwise push normally if required.

4. **Build**
    - Clean stale artifacts:
        ```sh
        rm -rf build dist backend/ldap_ui/statics
        ```
    - Build the SPA: `pnpm build` (writes `backend/ldap_ui/statics/`)
    - Build the Python distribution: `uv build`

5. **Publish to PyPI**
    - Guard: abort if the version is already on PyPI. Read `__version__` from `backend/ldap_ui/__init__.py` and check PyPI's JSON API:
        ```sh
        curl -s https://pypi.org/pypi/ldap-ui/json | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if sys.argv[1] in d['releases'] else 1)" <version>
        ```
        Exit 0 means the version is already published — abort.
    - `uv publish --token \`pass token/pypi.org\` dist/*`

6. **Rebuild Docker images**
    - Read the version for the image tags:
        ```sh
        fgrep __version__ backend/ldap_ui/__init__.py | cut -d'"' -f2
        ```
    - Build and push the multi-platform image (amd64 + arm64) with both the version and `latest` tags:
        ```sh
        docker buildx build --push \
          --platform linux/amd64,linux/arm64 \
          -t dnknth/ldap-ui:<version> -t dnknth/ldap-ui:latest .
        ```

## Notes

- The Docker build needs the SPA present (`backend/ldap_ui/statics/`), so build it before `docker buildx`.
- The image is `dnknth/ldap-ui`; the version tag comes from `__version__` in `backend/ldap_ui/__init__.py`.
- **Bring up Docker if needed (Mac only)** — if `docker buildx` fails with `failed to connect to the docker API at unix:///var/run/docker.sock` (no daemon running), start colima first:
    ```sh
    colima start
    ```
    Colima switches the Docker context to `colima` automatically; verify with `docker context ls` if needed.
