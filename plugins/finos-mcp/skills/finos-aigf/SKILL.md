---
name: finos-aigf
description: Research actual AI Governance Framework risks, controls, mitigations and mappings using the read-only AIGF MCP server.
---

# AIGF governance research

Use the finos-aigf MCP server for questions about AI governance risks,
controls, standards mappings and mitigation coverage. Do not substitute
general model knowledge for specific framework records.

1. For a broad question, call search_framework to discover candidate risks and
   controls. For a known identifier, call get_risk or get_control directly.
2. To identify mitigations call map_risks_to_controls. To map published controls
   to external standards use map_control_to_external, or reverse-lookup with
   find_by_external_reference. Use list_reference_frameworks when needed.
3. Prefer results with exact published identifiers and source URIs. Separate
   what the framework states from your suggested next steps.
4. If an identifier is unavailable or ambiguous, report that fact. Never
   invent controls, risk IDs, relationships or legal compliance conclusions.
5. This tool is a read-only information source, not a compliance certification.

Example: Find controls mitigating prompt-injection risks, their IDs and
external standard references.
