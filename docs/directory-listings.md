# Directory listings and registry readiness

Maintainer notes for how to help developers **discover** the independent
FINOS MCP project. Last reviewed: **25 October 2026**.

**Ownership and affiliation:** The packages belong to
[`vardhjain/finos-mcp`](https://github.com/vardhjain/finos-mcp).
They are **independent community tools, not official FINOS projects**.
Never claim FINOS endorsement or imply that any third-party MCP directory
listing is a certification of the tools.

## GitHub search profile

GitHub [About settings](https://github.com/vardhjain/finos-mcp) already have
a description, homepage and these relevant topics:

`ai-agents`, `ai-governance`, `cdm`, `fdc3`, `finos`, `fintech`,
`llm-tools`, `mcp`, `model-context-protocol`, `python`.

The current description is reasonable but emphasizes implementation details
instead of what a newcomer can do. If the repository owner wants to refine it,
a clearer **suggested** GitHub About description is:

> Read-only MCP servers for FINOS AI governance, CDM trade schemas and FDC3. Offline Python tools with citable sources.

Keep the existing homepage:
`https://vardhjain.github.io/finos-mcp/`.

Optional targeted topic additions (not yet applied):
`financial-services` and `mcp-server`. Avoid replacing specific
standards tags with vague marketing tags.

The connected GitHub integration used to prepare this page can edit source
files but cannot change repository **About** metadata or topics. The owner
can open the repository homepage, use the **About** panel's gear icon,
edit the description/website/topics and save. No GitHub metadata change
is implied by merging this documentation.

## Directory inventory and priority

| Directory | Current situation | Next step |
|---|---|---|
| [Glama](https://glama.ai/mcp/servers/vardhjain/finos-mcp) | **Already indexed**. Its snapshot still says 23 AIGF risks / 23 controls, CDM 7.7.0-era numbers, and labels the entry *Remote*, though our recommended install is local `uvx` over stdio. | **Claim or request a refresh of the existing listing**, and correct its description and local/remote classification. Do **not** submit a duplicate entry, assume Glama's generated preview is up to date, or pay for hosting. |
| [Official MCP Registry](https://github.com/modelcontextprotocol/registry) | Publication **not verified**. Requires a server manifest, GitHub namespace authentication, and proof of the published PyPI package's ownership. The registry is in preview. | **After the next authorized PyPI release** includes the `mcp-name` markers below, validate three separate `server.json` manifests and publish them through the official `mcp-publisher` CLI with owner approval. No registry action is performed by this PR. |
| [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | Community list accepts open GitHub servers but its PR bot currently expects a valid Glama listing and score badge; the PR queue is long. | Consider a standards/data category entry **after** the Glama details are corrected; no unsolicited PR now. |
| [mcpnav](https://mcpnav.dev/submit/) | Aggregates the official MCP Registry and community awesome lists, with no direct submission route. | Expect it to discover the project *through* the official Registry or awesome list. |
| [PulseMCP](https://www.pulsemcp.com/submit) | New submissions and edits are **paused** (notice dated September 3, 2026). | Don't submit while paused. It recommends official Registry publication first. |
| Smithery | Its remote-server listing route expects a public endpoint. This project ships local `uvx` tools and a self-hostable image, **not** a hosted public endpoint. | Skip remote-only registration instead of deploying a paid public server solely for a directory. |

Sources: [Official Registry publishing guide](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx),
[PyPI package ownership rules](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx),
[Glama submission FAQ](https://glama.ai/mcp/faq),
[awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers),
[mcpnav submission rules](https://mcpnav.dev/submit/), and
[PulseMCP submission status](https://www.pulsemcp.com/submit).

## Official Registry package ownership prerequisites

Each real MCP server is a **separate PyPI distribution**.
`finos-mcp-core` is a library and must not be advertised as a fourth MCP
server. Proposed distinct *GitHub-owned* registry names are:

| Server namespace name | PyPI package | stdio executable |
|---|---|---|
| `io.github.vardhjain/finos-mcp-aigf` | `finos-mcp-aigf` | `finos-mcp-aigf` |
| `io.github.vardhjain/finos-mcp-cdm` | `finos-mcp-cdm` | `finos-mcp-cdm` |
| `io.github.vardhjain/finos-mcp-fdc3` | `finos-mcp-fdc3` | `finos-mcp-fdc3` |

The official Registry accepts PyPI packages from `https://pypi.org`.
For PyPI ownership verification, it reads the **published PyPI README** and
requires an exact `mcp-name: io.github.vardhjain/finos-mcp-<server>`
marker. This repository now contains the matching HTML comments in each
package README, but **the already-published v0.3.1 distributions predate
these changes**. Committing a marker to GitHub does **not** update a
historical PyPI package or satisfy the Registry check immediately.

Before registry submission:

1. Obtain explicit approval for the next versioned PyPI release and include
   these updated READMEs in its built distributions.
2. Independently verify that all three **new public PyPI project pages**
   contain the exact ownership markers. Do not use old v0.3.1 manifests
   as a workaround.
3. Prepare and schema-validate **three separate** `server.json` manifests
   with matching `io.github.vardhjain/...` names, the actual published
   package versions, `registryType: "pypi"`, and `transport.type: "stdio"`.
   Confirm install commands for each package; use the official schema and
   its latest requirements, not guesses.
4. Have the owner authenticate with GitHub to the Registry and approve
   three `mcp-publisher publish` actions; verify published entries via the
   official API. Publishing server metadata is a public external action,
   **not** part of this repo PR.

The ownership marker is not a certification or a FINOS brand claim. The
project's non-affiliation statement remains present on each package page.

## Directory-ready short descriptions (drafts, not submitted)

**Project:** Independently maintained, read-only Python MCP servers for FINOS
AI governance, CDM 7.8.0 trade schemas and FDC3 desktop intents.
Offline vendor-pinned standards, citations, tests and local `uvx` setup.

**AIGF:** Look up FINOS AI Governance Framework risks and controls with
published identifiers, crosswalks, citations and offline search.

**CDM:** Explore CDM 7.8.0 types and validate trade JSON in Rune and legacy
formats; errors include precise document paths.

**FDC3:** Browse FDC3 context schemas and intents, validate contexts and
suggest interoperable desktop actions.

**Usage:** [Install and configure a client](getting-started.md) |
[Try real calls without a model key](use-cases.md) |
[Tool reference](tools.md) |
[Latest published release](https://github.com/vardhjain/finos-mcp/releases/latest).

Do not represent the project's local-stdio packages as a **hosted remote
service** or claim they directly execute trades, enforce compliance or modify
other systems.

## Next owner action

Review the GitHub About suggestion, then decide whether to **claim and
correct the existing Glama entry**. That is the nearest-term improvement
because a listing already exists; the official Registry requires a later
authorized package release and ownership verification. No submissions,
third-party logins, payments, GitHub topic edits or release actions are
performed as part of this document.
