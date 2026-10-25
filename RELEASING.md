# Releasing FINOS MCP

Releasing is a **separate, explicit step** from merging a release-preparation PR.
An annotated `v*` tag activates [`release.yml`](.github/workflows/release.yml),
which builds four Python wheels and source archives, creates a GitHub Release and
may publish to PyPI, and [`docker.yml`](.github/workflows/docker.yml),
which smoke-tests and pushes the multi-architecture container to GHCR.

**Do not push a release tag merely to test packaging:** a tag creates a public
GitHub Release and publishes a GHCR image, even when PyPI uploads are disabled.
Use the safe [`release-preflight.yml`](.github/workflows/release-preflight.yml)
workflow instead.

## Release 0.3.0 checklist

1. Review and merge the version/changelog PR after green cross-platform CI and
   green **release-preflight**. The latter builds and inspects all four wheels
   and source archives, verifies pinned core requirements and vendored manifests,
   and uploads artifacts for inspection without publishing.
2. Verify all six workspace project versions, `uv.lock`, and the release tag
   agree. Locally:

   ```bash
   uv lock --check
   python scripts/release_check.py --tag v0.3.0
   ```

3. Decide **before tagging** whether PyPI publishing should happen.
   `release.yml` publishes only when repository variable
   `PUBLISH_TO_PYPI=true`. Check its current value using GitHub's repository
   Actions variables UI or `gh variable list -R vardhjain/finos-mcp`.
   Also review `PYPI_SKIP_PACKAGES` (comma-separated `core,aigf,cdm,fdc3`
   exclusions) and each package's trusted-publisher configuration and tag
   restrictions. This file does **not** assume their current values.
   If PyPI publishing is wanted, confirm OIDC publisher configuration first.
4. Confirm the successful `main` CI checks after merging. Only then create
   the annotated tag **at that reviewed commit**:

   ```bash
   git fetch origin
   git checkout main
   git pull --ff-only
   python scripts/release_check.py --tag v0.3.0
   git tag -a v0.3.0 -m "FINOS MCP v0.3.0"
   git push origin v0.3.0
   ```

5. Verify both tag workflows and each intended artifact:
   ```bash
   gh run list -R vardhjain/finos-mcp --workflow release.yml --limit 5
   gh run list -R vardhjain/finos-mcp --workflow docker.yml --limit 5
   gh release view v0.3.0 -R vardhjain/finos-mcp
   ```

   GitHub Release should attach **four wheels and four source archives**.
   Review the curated [v0.3.0 release notes](docs/releases/v0.3.0.md)
   against the generated release body. Confirm the GHCR `v0.3.0` image
   and multi-arch manifest. If `PUBLISH_TO_PYPI` was enabled, verify
   all four PyPI package pages show the new version; otherwise describe
   it as a GitHub/container release only, not a PyPI release.

## Trusted PyPI publishing

The four project names have already been claimed and released on PyPI:
`finos-mcp-core`, `finos-mcp-aigf`, `finos-mcp-cdm` and
`finos-mcp-fdc3`. **Do not use the old new-project/pending publisher
bootstrap procedure for an existing package.**

PyPI releases use short-lived OIDC credentials and one tag-restricted
GitHub environment per package (not stored API tokens):

| Project | GitHub environment |
| --- | --- |
| `finos-mcp-core` | `pypi` |
| `finos-mcp-aigf` | `pypi-aigf` |
| `finos-mcp-cdm` | `pypi-cdm` |
| `finos-mcp-fdc3` | `pypi-fdc3` |

The publishing job is gated on `vars.PUBLISH_TO_PYPI == 'true'`, and
the optional `PYPI_SKIP_PACKAGES` variable can exclude selected jobs.
Do not enable publishing until the matching PyPI trusted publishers,
their owners and deployment environment restrictions are confirmed.
`finos-mcp-core` is the dependency of all three servers; resolve any
partial-upload failure without attempting to reuse a PyPI version
that has already been accepted (PyPI package versions are immutable).

When publishing, verify the independent project's non-affiliation
notice remains visible on PyPI. These packages are not official
FINOS packages.
