# FINOS MCP agent plugins

This independent, community-maintained plugin packages the existing **read-only**
AIGF, CDM and FDC3 local MCP servers plus three reference-backed workflows.
This is **not** an official FINOS product or remotely hosted MCP endpoint.

The repository uses one shared plugin at plugins/finos-mcp/ with native Claude Code
metadata and portable Agent Plugins metadata for Codex.

## Requirements

- Install uv and verify that uv is available on the AI client's PATH.
- Allow uv to install or use Python 3.12 (uv python install 3.12).
- Use a supported Claude Code or local Codex/ChatGPT desktop client.
- The first launch downloads pinned PyPI packages; ordinary reference lookups
  then work offline. No FINOS API key, database or hosted service is needed.
- Enabling all three servers uses more memory than using just one server.

## Claude Code

Run these commands **inside Claude Code**:

    /plugin marketplace add vardhjain/finos-mcp
    /plugin install finos-mcp@finos-mcp

Start a new session and check /mcp to verify that finos-aigf, finos-cdm
and finos-fdc3 are connected. The plugin includes corresponding skills.
If uv is not found, add it to the application's PATH and restart.

To validate from a local repo checkout:

    claude plugin validate ./plugins/finos-mcp
    claude plugin validate .

## Codex and ChatGPT desktop

The portable plugin manifest is plugins/finos-mcp/plugin.json; its local
stdio server configuration is plugins/finos-mcp/mcp.json. The repo
marketplace catalog is .agents/plugins/marketplace.json.

In a terminal with a compatible Codex CLI run:

    codex plugin marketplace add vardhjain/finos-mcp
    codex plugin marketplace list

Then open the Plugins Directory in the supported desktop client, select
the finos-mcp marketplace, and install finos-mcp. Start a new session.
CLI marketplace registration does not itself install the plugin.

**Distribution caveat:** this GitHub marketplace enables repo-based discovery;
it is not the OpenAI universal public Plugin Directory. Local MCP plugins
require desktop execution and public-directory submission currently requires
approved partner access. Browser-only ChatGPT cannot launch these stdio servers.

## Test real tools rather than model memory

- AIGF: Ask for a get_control call with id mi-20 and its source URI.
- CDM: Ask for a describe_type call for TradeState and its schema URI.
- FDC3: Ask for suggest_intent with context_type fdc3.instrument and
  goal "show a chart".

A real tool result is required before claiming that client integration works.
See [the MCP tool reference](tools.md) and
[manual client configuration](getting-started.md) for details.

## Releasing updates

Keep the package versions in portable mcp.json and native .mcp.json identical
and pinned to a tested release. Run:

    python scripts/validate_plugin_packaging.py

Then test on a clean installation of each client before publishing updates.
Plugin packaging has no new hosting cost, although using Claude or Codex may
have separate subscription or model usage costs.

Specification references:
- [Claude Code plugins](https://code.claude.com/docs/en/plugins)
- [Claude marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [Portable Agent Plugins](https://agent-plugins.org/specification)

## Directory submission runtime

Plugin 0.1.1 uses an independent plugin-local pyproject.toml and uv.lock.
Launchers run uv --no-config run --project <plugin-root> --frozen against
public-PyPI artifacts pinned with hashes, rather than resolving uvx dependencies
from a checkout. The parent development workspace remains separate.
Regenerate only this lock with:

    uv --no-config lock --project plugins/finos-mcp --no-sources --default-index https://pypi.org/simple --python 3.12

The native manifest uses ${CLAUDE_PLUGIN_ROOT}; the portable manifest uses
${PLUGIN_ROOT}. Keep launcher behavior aligned. The directory may still require
human review of the name similarity to finom. Local MCP support is limited to
Claude Code and Cowork for plugin installs; web chat cannot launch these servers.
The root portable plugin.json is for other clients and is intentionally ignored
by Claude. The listing icon is .claude-plugin/icon.png.
