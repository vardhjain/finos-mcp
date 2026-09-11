# Releasing

Tagging `v*` runs [`release.yml`](.github/workflows/release.yml), which builds a wheel and
sdist for each of the four packages and cuts a GitHub release with them attached, and
[`docker.yml`](.github/workflows/docker.yml), which builds the container, smoke-tests it, and
pushes a multi-arch image with SBOM and provenance to `ghcr.io`.

```bash
git tag -a v0.1.1 -m "..." && git push origin v0.1.1
```

Publishing to PyPI is **off by default** and does not happen on a tag until it is switched on
below, so a tag is always safe to cut.

## PyPI trusted publishing

Trusted publishing uses a short-lived OIDC token instead of a long-lived API token, so there
is no secret to store or rotate. Two halves have to agree: what PyPI expects, and what this
repository sends. The repository half is already in place.

### Repository half (done)

| Piece | Value | Where |
|---|---|---|
| Workflow | `release.yml` | `.github/workflows/release.yml` |
| Job | `publish-pypi`, a matrix with one job per package | gated on `vars.PUBLISH_TO_PYPI == 'true'` |
| Environments | `pypi`, `pypi-aigf`, `pypi-cdm`, `pypi-fdc3` | one per package, each restricted to tags matching `v*` so no branch can deploy to them |
| OIDC permission | `id-token: write` | workflow-level `permissions` |
| Action | `pypa/gh-action-pypi-publish@release/v1` | no username, no password, no token |

### PyPI half (needs a human)

Only a logged-in PyPI account owner can register a publisher, so this part cannot be
automated from here. At <https://pypi.org/manage/account/publishing/>, with 2FA enabled, add a
**pending publisher** for each project name. Pending, rather than a project publisher, because
none of these projects exist on PyPI yet.

Owner `vardhjain`, repository name `finos-mcp` and workflow name `release.yml` are the same
for all four. The environment differs per project:

| PyPI project name | Environment name |
|---|---|
| `finos-mcp-core` | `pypi` |
| `finos-mcp-aigf` | `pypi-aigf` |
| `finos-mcp-cdm` | `pypi-cdm` |
| `finos-mcp-fdc3` | `pypi-fdc3` |

**Why four environments.** PyPI keys a pending publisher on owner + repository + workflow +
environment and refuses to register the same configuration for a second project, with the
error "A pending trusted publisher matching this configuration has already been registered for
a different project". Its documentation does not mention this. A shared environment can
therefore bootstrap only one package, so `release.yml` publishes each package from its own
matrix job and environment. That is also the tighter design: each environment can publish
exactly one project.

> **The names are not settled.** On PyPI, `finos-cdm` is the official FINOS Common Domain
> Model package, so the `finos-` prefix there reads as "published by FINOS" and these could be
> taken for official output. That question is open with FINOS at
> [ai-governance-framework#381](https://github.com/finos/ai-governance-framework/issues/381);
> the alternative is `mcp-finos-*`, where "finos" describes the subject rather than the
> publisher. Settle it before registering, because a PyPI name cannot practically be released
> once claimed. All four names were unclaimed as of 2026-09-10.

### Switching it on

Once the publishers exist:

```bash
gh variable set PUBLISH_TO_PYPI --body true --repo vardhjain/finos-mcp
```

Then the next `v*` tag publishes all four. Leave the variable unset until then: without a
registered publisher the upload step fails, and a red release run is a worse signal than a
release that simply did not publish.

`finos-mcp-core` is a dependency of the other three, so if PyPI ever rejects part of a batch,
publish `core` first and re-run.
