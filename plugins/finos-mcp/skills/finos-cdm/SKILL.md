---
name: finos-cdm
description: Explore and validate Common Domain Model schemas, types, events and trade JSON using the read-only CDM MCP server.
---

# CDM schema and validation

Use the finos-cdm MCP server for published Common Domain Model definitions.
Never infer a required CDM JSON field or validation result from memory.

1. Search using search_types or list_types, then call describe_type for the
   specific type, fields, cardinalities and schema resource URI.
2. For examples, call list_samples then get_sample; check which CDM version
   and document format the sample uses before adapting it.
3. Given a trade JSON object, call validate_object, with the intended type
   and format if the user provides them. Include each issue's exact JSON
   path and issue kind. Do not claim validation passed without a tool call.
4. Use explain_event to describe qualifying rules and trade event structure.
5. Include CDM source identifiers and cdm:// resource references. Distinguish
   published schema information from application-specific recommendations.

Example: Describe TradeState and validate an example trade document while
reporting the exact paths of validation errors.
