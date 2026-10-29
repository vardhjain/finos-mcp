---
name: finos-fdc3
description: Find FDC3 intents and context schemas and validate context objects using the read-only FDC3 MCP server.
---

# FDC3 context and intent matching

Use the finos-fdc3 MCP server to understand standard desktop interoperability
intents and context data. Tool results describe the FDC3 specification;
they do not trigger actions in real desktop applications.

1. For a context and user goal call suggest_intent, or use
   find_intents_by_context for a specific context type.
2. Use get_intent, list_intents or search_intents to verify official intent
   names, accepted contexts, result types and deprecation status.
3. For a context schema, use get_context_schema. For supplied JSON, call
   validate_context and report the exact error paths and kinds returned.
4. Cite fdc3:// resource identifiers from tool output. Do not invent contexts,
   intent support, schema conformance or claims about installed applications.

Example: Suggest appropriate intents for an fdc3.instrument context
when the user wants to view a chart.
