# Official MCP Registry draft metadata — not published

The files in [aigf/server.json](aigf/server.json),
[cdm/server.json](cdm/server.json), and
[fdc3/server.json](fdc3/server.json) describe **three independent**
read-only stdio MCP servers. `finos-mcp-core` is a shared library, not
a fourth server.

The manifests follow the official
[server.json schema](https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json)
and describe **PyPI v0.3.1** and `uvx`. They are **DRAFTS ONLY**.

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

## Publication is blocked until a new authorized release

The already-published **0.3.1** PyPI package descriptions do **not**
include the `mcp-name:` proof-of-ownership markers. Those markers were
committed to GitHub **after** the immutable v0.3.1 release.

**Do not run `mcp-publisher publish` on these v0.3.1 drafts.**
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

1. Obtain the owner's **separate approval** for a new PyPI release;
   never overwrite v0.3.1. Include the updated `mcp-name:` markers in
   each *new* distribution's README.
2. Update **both** `version` and `packages[0].version` in each
   draft to match the newly published versions. Run the offline tests.
3. Verify the **new public PyPI pages** contain the exact ownership
   markers; source-controlled READMEs alone do not establish ownership.
4. Run the latest official `mcp-publisher validate` on each updated
   manifest. Confirm GitHub namespace and Registry policies.
5. Obtain separate approval to authenticate and publish **each**
   entry. Publish one at a time and verify public discoverability.
   Never check tokens into GitHub.

No `remotes` property is included: this project has **local,
installable stdio** MCP servers and optional user-hosted HTTP/Docker,
but operates no public remote endpoint.

This is independent community software **not endorsed by or
affiliated with FINOS**.

Official sources:
[package ownership](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx),
[quickstart](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx),
[server.json reference](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/generic-server-json.md).
