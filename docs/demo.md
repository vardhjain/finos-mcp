# Live demo

This is the **actual output** of the low-memory demonstration recorded in
[GitHub Actions CI](https://github.com/vardhjain/finos-mcp/actions/runs/40158262833),
not mocked tool results. Five real MCP calls are made across AIGF, CDM and FDC3.

Unlike the earlier version, `examples/demo_session.py` launches each server in a
**separate, short-lived subprocess**, sequentially. The parent does not load any
standard's registry. This prevents the CDM schema-validation step from having to
share one Python process with the AIGF embeddings and FDC3 registry.

Reproduce this output with no API key or paid AI model:

```bash
uv sync --all-packages --all-extras
uv run --no-sync python examples/demo_session.py --fast
```

Omit `--fast` for a paced terminal presentation. To generate
`docs/demo.gif` on a machine with the free [VHS](https://github.com/charmbracelet/vhs)
terminal recorder installed, run `vhs examples/demo.tape`.

**Historical snapshot:** The transcript below was captured with CDM 7.7.0
before the v0.3.1 release. Current `main` and published v0.3.1 instead bundle
**CDM 7.8.0**, so current validator messages may differ from the example below.
The live demo script is still run on every CI pull request and uploads
`demo-transcript.txt` in the metrics artifact; follow the commands above to
produce a fresh transcript. For simpler, currently tested examples, see
[three use cases](use-cases.md).

```console
starting FINOS MCP demo (isolated servers, one at a time) ...
READY

$ finos-mcp: read-only MCP servers for FINOS standards (AIGF, CDM, FDC3)

# AIGF: resolve a control by its short id and see what it mitigates
$ aigf > get_control {"id": "mi-20", "include_sections": false}
AIR-PREV-020  MCP Server Security Governance  [Preventative, Approved-Specification]
mitigates        AIR-SEC-026, AIR-SEC-008, AIR-RC-001
related controls AIR-PREV-007, AIR-DET-004
crosswalks to    8 references across 3 frameworks
cite             aigf://control/AIR-PREV-020
[read-only, rate-limited, audited]

# AIGF: reverse crosswalk, which records cite NIST SP 800-53 SA-9?
$ aigf > find_by_external_reference {"key": "sa-9"}
4 AIGF records cite this reference:
  control AIR-DET-001  AI Data Leakage Prevention and Detection
  control AIR-PREV-007  Legal and Contractual Frameworks for AI Systems
  control AIR-PREV-014  Encryption of AI Data at Rest
  control AIR-PREV-020  MCP Server Security Governance
[read-only, rate-limited, audited]

# AIGF: search in plain language, every hit is citable
$ aigf > search_framework {"query": "an employee pastes client data into a public chatbot", "k": 3}
  AIR-RC-001  Information Leaked To Hosted Model
      aigf://risk/AIR-RC-001
  AIR-RC-023  Intellectual Property (IP) and Copyright
      aigf://risk/AIR-RC-023
  AIR-SEC-010  Prompt Injection
      aigf://risk/AIR-SEC-010
[read-only, rate-limited, audited]

# CDM: validate a Rune BusinessEvent an agent got wrong (3 planted defects)
$ cdm > validate_object {"object": "<broken_execution.json>"}
valid=False   format=rune   type=cdm.event.common.BusinessEvent
validator: json-schema draft4 (cdm-json-schema 7.7.0) via Rune normalisation
3 issue(s):
  [enum       ] $.instruction[0].primitiveInstruction.execution.product.economicTerms.payout[0].@type
      'InterestRatePayoutt' is not an alternative of Payout; expected one of ['AssetPayout', 'Commodit
  [required   ] $.after[0]
      'trade' is a required property
  [required   ] $.instruction[0].primitiveInstruction.execution
      'executionDetails' is a required property
[read-only, rate-limited, audited]

# FDC3: which intents can I raise for an instrument, and which shows a chart?
$ fdc3 > suggest_intent {"context": {"type": "fdc3.instrument", "id": {"ticker": "AAPL"}}, "goal": "show a price chart"}
context fdc3.instrument (detected by type_field); ranked intents:
  1.44  ViewChart          ViewChart accepts fdc3.instrument; matches goal 'show a pr
  1.31  ViewQuote          ViewQuote accepts fdc3.instrument; matches goal 'show a pr
  1.22  ViewResearch       ViewResearch accepts fdc3.instrument; matches goal 'show a
  1.18  ViewInstrument     ViewInstrument accepts fdc3.instrument; matches goal 'show
  0.96  ViewHoldings       ViewHoldings accepts fdc3.instrument; matches goal 'show a
[read-only, rate-limited, audited]

$ every tool is read-only; nothing here writes to any external system.
DEMO DONE
```

The CDM step uses [`examples/broken_execution.json`](https://github.com/vardhjain/finos-mcp/blob/main/examples/broken_execution.json),
a real CDM 7 Rune-format `BusinessEvent` with three deliberate defects:
a misspelled payout alternative, a missing required `trade`, and a missing
`executionDetails`. The validator pinpoints the corresponding JSON paths in
the submitted document. Every other result also comes from the real MCP
tools and is read-only, with citeable identifiers where applicable.
