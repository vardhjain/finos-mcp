# Official MCP Registry — published v0.3.2 metadata

The files in [aigf/server.json](aigf/server.json),
[cdm/server.json](cdm/server.json), and
[fdc3/server.json](fdc3/server.json) describe **three independent**
read-only stdio MCP servers. `finos-mcp-core` is a shared library, not
a fourth server.

The manifests follow the official
[server.json schema](https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json)
and describe **published PyPI v0.3.2** and `uvx`. All three MCP Registry
entries are published and independently verified through the public API.

## Upstream JSON Schema checks in CI

The CI suite runs JSON Schema validation **offline** against a pinned snapshot
of the [Registry's upstream draft `server.schema.json`](https://github.com/modelcontextprotocol/registry/blob/e47b29ec6091a4b05969d9f755a024529ee2b5b3/docs/reference/server-json/draft/server.schema.json)
at upstream commit `e47b29ec6091a4b05969d9f755a024529ee2b5b3`. The exact, unmodified schema is checked into
[`schema/upstream-draft.schema.json`](schema/upstream-draft.schema.json)
so that CI doesn't depend on Registry availability and upstream changes cannot
silently change our passing tests. It is upstream specification data, not a
runtime dependency.

```bash
uv run --no-sync pytest evals/test_registry_schema.py -q
```

**Validation limits:** this pinned draft is **not** the same URL as the
versioned `2025-12-11` schema named in the manifests. It is an additional
upstream-structure check, not proof that the manifests pass the Registry's
current schema, semantic checks, or published-PyPI ownership verification.
Before *any* approved publication, use the current official
`mcp-publisher validate` on all three manifests and resolve every error.
Update the pinned snapshot only in a reviewed PR after checking upstream
changes.

## Official publisher CLI validation in GitHub Actions

All three drafts passed the real **`mcp-publisher validate` v1.8.4**
CLI (schema + semantic checks) in a [read-only verification run](https://github.com/vardhjain/finos-mcp/actions/runs/40257964837).
The executable was the official Linux amd64 [v1.8.4 release](https://github.com/modelcontextprotocol/registry/releases/tag/v1.8.4), verified against its published SHA-256 checksum.

The separate [`registry-validation` workflow](../.github/workflows/registry-validation.yml)
repeats this official CLI check on pull requests and `main` pushes that
change Registry files, package metadata, or the workflow itself. It also
supports a manual **workflow_dispatch** run. It has **read-only**
repository permissions and deliberately uses only `validate`, never
`login` or `publish`. No paid API, registry account, or secrets
are needed.

This pins the **validator release** for reproducible CI; before a future
approved publication, run the latest official CLI too, since Registry
validation rules can change. Successful CLI validation **does not**
prove GitHub namespace authentication or ownership of a published
PyPI package. The three published v0.3.2 Registry entries were authenticated
and verified separately; validation alone was never sufficient.

## Packaging ownership preflight (offline; no publish)

The non-publishing [release-preflight workflow](../.github/workflows/release-preflight.yml)
builds all four Python wheels and source archives, then checks that the
**three server distributions** carry their exact `mcp-name` ownership
comments in both the wheel's `METADATA` description and the sdist's
top-level `README.md`. Core is a shared library and has no Registry entry.
A missing or wrong marker fails the build before any tag or upload.

This checks the files *we would upload*, not what's already on PyPI. It
does **not** unblock the previously published v0.3.1 artifacts. After an
explicitly approved new release, the public PyPI descriptions must still
be checked with the read-only ownership audit, and Registry publication
still needs separate approval.

## Live v0.3.2 Registry publication confirmed

The owner-triggered [official Registry publishing run](https://github.com/vardhjain/finos-mcp/actions/runs/40389712353)
used GitHub Actions OIDC authentication and reported successful publication of
AIGF, CDM and FDC3 on 2026-10-26. An independent, **unauthenticated** public
[Registry visibility check](https://github.com/vardhjain/finos-mcp/actions/runs/40390604767)
subsequently returned three PASS results, verifying active entries, precise
server and package names, PyPI version 0.3.2 and local stdio transports:

- [AIGF public Registry API](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-aigf/versions/0.3.2)
- [CDM public Registry API](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-cdm/versions/0.3.2)
- [FDC3 public Registry API](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-fdc3/versions/0.3.2)

Run the [read-only listing verification](../.github/workflows/verify-mcp-registry-listings.yml)
on demand or with `python scripts/check_registry_discoverability.py`.
No GitHub or Registry authentication is needed to check these entries.

The four v0.3.2 Python packages, the GitHub Release and all three official
Registry entries have been published. The public PyPI descriptions were checked
with the read-only
[`pypi-ownership-audit` workflow](../.github/workflows/pypi-ownership-audit.yml)
before starting any Registry publication workflow. This
workflow can be run manually from GitHub Actions and checks all three live
PyPI v0.3.2 package descriptions without authenticating or publishing.

**Verified 2026-10-26:** the read-only [live PyPI audit run](https://github.com/vardhjain/finos-mcp/actions/runs/40280037055)
reported `PASS` for `finos-mcp-aigf==0.3.2`,
`finos-mcp-cdm==0.3.2`, and `finos-mcp-fdc3==0.3.2`.
PyPI ownership-marker verification is therefore complete for this version.
This does **not** verify GitHub namespace authentication or authorize
Registry publication.

The already-published **0.3.1** PyPI package descriptions do **not**
include the `mcp-name:` proof-of-ownership markers. Those markers were
committed to GitHub **after** the immutable v0.3.1 release.

**Do not publish directly from a PR, merge, or tag.** The guarded workflow was
used for the completed initial submission, and its existence check intentionally
rejects an attempt to republish an already registered v0.3.2 version.
Matching GitHub README text is insufficient: the Registry checks the
*public PyPI package README* when verifying ownership. The Registry
is currently in preview, and its schema can change.

## Guarded initial Registry publication (owner-approved)

The repository owner approved and manually triggered the initial Registry
submission of all three **v0.3.2** servers on 2026-10-26. The workflow
completed successfully; it is not a recurring job.
The [`publish-mcp-registry` workflow](../.github/workflows/publish-mcp-registry.yml)
is not triggered by pushes, tags, or merges. Pull requests run **validation
only**, without OIDC tokens or publication permissions.

The initial publication used the following explicit owner-controlled inputs
for a manual run on reviewed `main`:

- **Expected SHA:** `7d55b725e7e2ce39f159f539e7f6027f436b887a`, the
  reviewed `main` commit used for the original Registry submission.
- **Confirmation:** `PUBLISH MCP REGISTRY v0.3.2`

The workflow checks the published v0.3.2 tag, successful CI on that exact
SHA, public PyPI ownership markers, Registry manifest versions and transport,
and whether a v0.3.2 Registry entry already exists. It uses the official
checksum-pinned `mcp-publisher v1.8.5` and GitHub Actions **OIDC** to
authenticate to the production Registry, without a personal access token or
long-lived secret. Submission proceeds in order: AIGF, CDM, FDC3.

**Future releases:** Partial publishing can occur if one server is accepted
but another fails. Never blindly rerun a publishing batch. Inspect existing
public Registry versions first and verify every accepted entry independently.

## Safe, free preparation

Offline tests verify the three JSON drafts against the real source
package versions, PyPI distribution names, console commands,
ownership markers, the 100-character description limit and
local `stdio` transport. They require no network or model API.

```bash
uv run --no-sync pytest evals/test_registry_manifests.py -q
```

The automated checks do **not** replace the official CLI's schema
and semantic validation. Before publication, run:

```bash
mcp-publisher validate registry/aigf/server.json
mcp-publisher validate registry/cdm/server.json
mcp-publisher validate registry/fdc3/server.json
```

CLI reference: [`mcp-publisher validate`](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/cli/commands.md).

## Checklist for future new-version publication

1. Confirm that each draft names the already-published PyPI v0.3.2
   distribution, and that both `version` and `packages[0].version` are
   `0.3.2`. Run the offline manifest tests.
2. Run the read-only `pypi-ownership-audit` workflow, or
   `python scripts/check_pypi_mcp_ownership.py`, and require **PASS for
   AIGF, CDM, and FDC3** against the *public* PyPI descriptions.
3. Run the latest official `mcp-publisher validate` for all three
   manifests. Confirm GitHub namespace ownership and current policies.
4. **Do not rerun the original v0.3.2 publication batch.** For any new
   Registry release version, review new manifests, adjust the version-specific
   guard and seek explicit owner approval in a separate change. The manual
   workflow must require a reviewed SHA, live public package verification and
   new version availability. Never check tokens into GitHub.

No `remotes` property is included: this project has **local,
installable stdio** MCP servers and optional user-hosted HTTP/Docker,
but operates no public remote endpoint.

This is independent community software **not endorsed by or
affiliated with FINOS**.

Official sources:
[package ownership](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx),
[quickstart](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx),
[server.json reference](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/generic-server-json.md).
