# Offline CDM and FDC3 workflow evaluations

Sixteen deterministic scenarios (eight for each MCP server) execute **51 tool calls and resource reads**
through the real in-memory MCP client. No language model or paid provider is involved.

The tasks cover schema and type discovery, fetching and validating official CDM samples,
business-event qualification, FDC3 context detection and validation, intent selection,
source citations, and structured error recovery. Tasks pass the actual output of one
step to the next with a `{"$from": "step_id.field.0.name"}` placeholder.

Run locally with:

```bash
uv run pytest evals/offline/test_workflows.py -v
```

The single evaluation test tries every scenario even if an earlier one fails.
It writes `offline-evals.json` with total and per-server success counts and any
failed scenario names. CI feeds this file into `metrics.json` under `offline_evals`
and adds the two server pass rates to the GitHub job summary.

All outcomes are asserted against returned typed tool results, actual JSON schemas,
and citation resources. These are **offline workflow reliability tests**, not scores
of an LLM's ability to choose tools or compose answers. They complement existing
golden-call and AIGF retrieval benchmarks and do not replace the manual opt-in
agent-in-the-loop evaluation.

Expected shapes are version-neutral where possible. Run the suite again after
upstream CDM or FDC3 changes and investigate any failures instead of lowering gates.
