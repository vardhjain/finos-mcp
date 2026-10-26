# Official MCP Registry draft metadata — not published

The files in [aigf/server.json](aigf/server.json),
[cdm/server.json](cdm/server.json), and
[fdc3/server.json](fdc3/server.json) describe **three independent**
read-only stdio MCP servers. `finos-mcp-core` is a shared library, not
a fourth server.

The manifests follow the official
[server.json schema](https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json)
and describe **published PyPI v0.3.2** and `uvx`. The Python packages are
released, but these MCP Registry entries are **DRAFTS ONLY**.

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
PyPI package. The v0.3.2 Registry drafts remain unpublished and gated below.

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

## Registry publication remains separately gated

The four v0.3.2 Python packages and the v0.3.2 GitHub Release have been
published. The **three Registry entries have not been published**. Verify the
public PyPI descriptions with the read-only
[`pypi-ownership-audit` workflow](../.github/workflows/pypi-ownership-audit.yml)
before requesting a separate approval to publish Registry entries. This
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

**Do not run `mcp-publisher publish` on these v0.3.2 drafts.**
Matching GitHub README text is insufficient: the Registry checks the
*public PyPI package README* when verifying ownership. The Registry
is currently in preview, and its schema can change.

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

## Checklist before any official publication

1. Confirm that each draft names the already-published PyPI v0.3.2
   distribution, and that both `version` and `packages[0].version` are
   `0.3.2`. Run the offline manifest tests.
2. Run the read-only `pypi-ownership-audit` workflow, or
   `python scripts/check_pypi_mcp_ownership.py`, and require **PASS for
   AIGF, CDM, and FDC3** against the *public* PyPI descriptions.
3. Run the latest official `mcp-publisher validate` for all three
   manifests. Confirm GitHub namespace ownership and current policies.
4. Obtain the owner's **separate, explicit approval** to authenticate and
   publish each Registry entry. Publish one at a time and verify public
   discoverability. Never check tokens into GitHub.

No `remotes` property is included: this project has **local,
installable stdio** MCP servers and optional user-hosted HTTP/Docker,
but operates no public remote endpoint.

This is independent community software **not endorsed by or
affiliated with FINOS**.

Official sources:
[package ownership](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx),
[quickstart](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx),
[server.json reference](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/generic-server-json.md).
