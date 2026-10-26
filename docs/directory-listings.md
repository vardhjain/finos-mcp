# Directory listings and official Registry publication

Maintainer notes for how to help developers **discover** the independent
FINOS MCP project. Last reviewed: **26 October 2026**.

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
| [Glama](https://glama.ai/mcp/servers/vardhjain/finos-mcp) | **Already indexed**. Its snapshot still says 23 AIGF risks / 23 controls, CDM 7.7.0-era numbers, and labels the entry *Remote*, though our recommended install is local `uvx` over stdio. | **Already claimed; refresh the existing listing**, and correct its description and local/remote classification. Do **not** submit a duplicate entry, assume Glama's generated preview is up to date, or pay for hosting. |
| [Official MCP Registry](https://registry.modelcontextprotocol.io/) | **All three v0.3.2 servers published and independently verified active** with local `stdio` packages. | No resubmission needed. Keep metadata accurate and perform read-only discoverability checks after future changes. |
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

## Refresh the already-claimed Glama listing (owner/support action)

The listing already exists at
[glama.ai/mcp/servers/vardhjain/finos-mcp](https://glama.ai/mcp/servers/vardhjain/finos-mcp).
**Do not submit a duplicate listing or provision a paid hosted endpoint.**

This repository now contains a root
[`glama.json`](https://github.com/vardhjain/finos-mcp/blob/main/glama.json),
with the officially documented ownership shape:

```json
{
  "$schema": "https://glama.ai/mcp/schemas/server.json",
  "maintainers": ["vardhjain"]
}
```

The owner reports that this **existing listing is already claimed** under
GitHub account `vardhjain`. The [Glama maintainer file instructions](https://glama.ai/blog/2025-07-08-what-is-glamajson)
explain this repository's ownership hint. The claim does **not**
automatically change old indexed descriptions or Glama's Remote label.

1. In the existing listing's owner/admin view, update its description
   to describe all three local `uvx`/stdio servers and request a
   repository reindex/sync.
2. The owner has contacted Glama support about the misleading
   **Remote** classification. Follow up on [issue #40](https://github.com/vardhjain/finos-mcp/issues/40)
   if the public label stays incorrect; no hosted endpoint should be claimed.
3. Verify the actual **public** listing, including source version,
   capabilities, classification and non-affiliation. Close issue #40
   only after confirmation. Do not create a duplicate Glama entry.

### Correction text for the existing Glama page

**Suggested name:** FINOS MCP — AIGF, CDM and FDC3 (community project)

**Suggested description:**

> Three independent, read-only Python MCP servers for exploring FINOS
> AI governance controls, Common Domain Model (CDM) trade JSON schemas,
> and FDC3 desktop intents. The standards data are bundled for offline
> tool calls, with citable identifiers. Install locally over stdio with
> `uvx`; self-hosted Streamable HTTP and Docker are optional.
> Not affiliated with or endorsed by FINOS.

**Facts to correct (verified from the current repository):**

| Glama snapshot | Correct information |
|---|---|
| 23 AIGF risks / 23 controls | **24 risks / 25 controls** in the current vendored framework |
| CDM 7.7.0-era information, 1,142 types | Primary CDM **7.8.0**, **767 types and 1,143 JSON schemas**, with CDM 6.30.0 legacy schemas also supported. Don't confuse schema and type counts. |
| "Remote" as the only use mode | **Local stdio via `uvx` is the default**; self-hosted Streamable HTTP is optional. There is no publicly operated remote endpoint from this project. |
| Published project version 0.2.6 | Latest public version is **0.3.2**. Later `main` changes are not necessarily on PyPI. |
| AIGF-only first impression | Repo contains **three separate MCP servers**: `finos-mcp-aigf`, `finos-mcp-cdm`, and `finos-mcp-fdc3`. The core package is a library, not a fourth server. |
| Claim that paid evaluations run nightly | Paid LLM evaluation is **manual opt-in**, not scheduled. Offline checks run in CI. |

**Recommended verified setup:**

```bash
uvx --python 3.12 'finos-mcp-aigf==0.3.2'
uvx --python 3.12 'finos-mcp-cdm==0.3.2'
uvx --python 3.12 'finos-mcp-fdc3==0.3.2'
```

Users normally configure **one** relevant server rather than starting
all three simultaneously. Prefer the
[client-setup documentation](getting-started.md) and
[real first-use examples](use-cases.md) when updating the listing.

**Evidence:**
[README / standards counts](https://github.com/vardhjain/finos-mcp/blob/main/README.md),
[generated tool reference](tools.md),
[public v0.3.2 release](https://github.com/vardhjain/finos-mcp/releases/tag/v0.3.2),
[CI](https://github.com/vardhjain/finos-mcp/actions/workflows/ci.yml),
[release guide](https://github.com/vardhjain/finos-mcp/blob/main/RELEASING.md).

**No external account authorization is stored in the repository.**
Never commit an account password, login token, or Glama session
credential. This file is only a public GitHub username-based maintainer
declaration.

## Official MCP Registry — published and independently verified

These are **three independent, active public Registry entries** at version
`0.3.2`. The fourth package, `finos-mcp-core`, is a shared dependency
and **not** another MCP server.

| Official Registry server | PyPI distribution | Transport | Public record |
|---|---|---|---|
| `io.github.vardhjain/finos-mcp-aigf` | `finos-mcp-aigf==0.3.2` | Local stdio | [AIGF](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-aigf/versions/0.3.2) |
| `io.github.vardhjain/finos-mcp-cdm` | `finos-mcp-cdm==0.3.2` | Local stdio | [CDM](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-cdm/versions/0.3.2) |
| `io.github.vardhjain/finos-mcp-fdc3` | `finos-mcp-fdc3==0.3.2` | Local stdio | [FDC3](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-fdc3/versions/0.3.2) |

The [owner-triggered Registry publishing run](https://github.com/vardhjain/finos-mcp/actions/runs/40389712353)
successfully authenticated using GitHub Actions OIDC and published AIGF,
CDM and FDC3 on **2026-10-26**. An independent
[read-only public Registry API audit](https://github.com/vardhjain/finos-mcp/actions/runs/40390604767)
returned PASS for the three active listings and exact PyPI package versions,
transport type and repository. The
[public PyPI marker audit](https://github.com/vardhjain/finos-mcp/actions/runs/40280037055)
also passed all three.

The Registry records point to installable local stdio packages; this
project **does not operate a public remote MCP endpoint**. An official
Registry listing is a discovery mechanism, not FINOS endorsement or
certification.

The manifests and read-only verifier live in
[`registry/`](https://github.com/vardhjain/finos-mcp/tree/main/registry), and
[`scripts/check_registry_discoverability.py`](https://github.com/vardhjain/finos-mcp/blob/main/scripts/check_registry_discoverability.py).
To check public listings without logging in, run:

```bash
python scripts/check_registry_discoverability.py
```

**Do not rerun the v0.3.2 publication batch.** The guarded workflow
rejects existing Registry versions. Future versions require separate
review, updated publishing guards and explicit owner approval.

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

The **official MCP Registry is complete** for AIGF, CDM and FDC3 v0.3.2.
The remaining directory task is correcting the already-claimed
[Glama listing](https://glama.ai/mcp/servers/vardhjain/finos-mcp):
its outdated profile/sync and misleading Remote label are tracked in
[issue #40](https://github.com/vardhjain/finos-mcp/issues/40).
This documentation update does not submit new directory entries,
require hosting or make paid API calls.
