# Safety model

`finos-mcp` servers are catalogues. They answer questions about published FINOS standards and
validate documents an agent hands them. Nothing they do has a side effect outside the process.

## What is enforced, and where

| Guarantee | Mechanism | Code |
|---|---|---|
| No tool can write anywhere | Tools are registered only through `register_tool`, which stamps `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false`. A gate in the middleware refuses every `tools/*` request if any registered tool lacks those annotations. There is no configuration flag that relaxes this. | `core/src/finos_mcp/core/server.py` |
| No network at runtime | All framework content and schemas are vendored at build time. Each `_vendor/` directory carries `SOURCE.json` with the upstream repository, ref, commit hash, fetch time and per-file sha256. `verify()` runs when the server loads its data and in CI; any mismatch aborts. | `core/src/finos_mcp/core/vendor.py` |
| Bounded input | Serialised tool arguments above the policy cap (64 KiB by default, 1 MiB for CDM validation) are rejected before the tool runs, as a structured `input_too_large` result. | middleware, `policy.py` |
| Bounded output | Results above the output cap (512 KiB) are replaced by a structured `output_too_large` result with a hint to narrow the request. | middleware |
| Rate limits | Token bucket per client and per tool. Exhaustion is a JSON-RPC error (`-32029`, `rate_limited`, with `retry_after_s`) so the host sees it, rather than a tool result that could mislead the model. Buckets are LRU-bounded (10k keys) so session churn cannot exhaust memory. | `ratelimit.py` |
| Structured errors | Anticipated failures are `ToolError`s whose text is a JSON `ErrorEnvelope` (`code`, `message`, `hint`, `candidates`). Unexpected exceptions are left to the MCP SDK, which logs the traceback server-side and shows the model only `Error executing tool <name>`. | `errors.py` |
| Audit log | One JSON line per request: timestamp, server, method, tool, argument size and sha256 (raw arguments only with `FINOS_MCP_AUDIT_RAW_ARGS=1`), outcome, duration, result size. Goes to stderr or `FINOS_MCP_AUDIT_PATH`. Never stdout, which is the stdio protocol channel. | `audit.py` |
| Policy only tightens | `FINOS_MCP_MAX_INPUT_BYTES`, `FINOS_MCP_MAX_OUTPUT_BYTES`, `FINOS_MCP_RATE_CALLS`, `FINOS_MCP_RATE_WINDOW_S`, `FINOS_MCP_RATE_BURST` are applied only when stricter than the server's own defaults. | `policy.py` |

## Threats considered

- **Prompt injection through served content.** The servers return verbatim FINOS text and schemas. A document that contained instructions would be served as data; the servers never act on content. Hosts should treat resource text as untrusted input, as with any retrieval tool.
- **Malicious or oversized inputs.** Size caps and Pydantic validation of every argument run before any tool logic. JSON Schema validation of user-supplied documents is bounded by the input cap and by an issue limit.
- **Denial of service.** Per-tool rate limits and bounded bucket storage. The heaviest tool, CDM object validation, has a lower limit and its own input cap.
- **Supply chain of vendored content.** Hash-pinned manifests; a weekly workflow re-syncs upstream into a scratch directory and opens a reviewable pull request, so content never changes silently.
- **Information leakage in errors.** Tracebacks never reach clients; audit logs hash arguments by default.

## What is not covered

- Authentication and transport security for HTTP deployments are the host's responsibility; the MCP SDK's auth hooks can be layered in front of the server.
- The servers do not sandbox the process; they assume a normal Python runtime.
