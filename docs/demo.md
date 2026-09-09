# Demo

The exact output of `examples/demo_session.py`, which loads all three servers in one
process and makes five real tool calls through the in-memory MCP client. Reproduce it with:

```bash
uv run python examples/demo_session.py
```

Latencies are measured per call on the machine that produced this transcript, with the
safety middleware (rate limiting, size caps, audit) in the path. `examples/demo.tape` records
the same session as a GIF, with the caveats in [examples/README.md](https://github.com/vardhjain/finos-mcp/blob/main/examples/README.md).

```console
$ finos-mcp: read-only MCP servers for FINOS standards (AIGF, CDM, FDC3)

# AIGF: resolve a control by its short id and see what it mitigates
$ aigf > get_control {"id": "mi-20", "include_sections": false}
AIR-PREV-020  MCP Server Security Governance  [Preventative, Approved-Specification]
mitigates        AIR-SEC-026, AIR-SEC-008, AIR-RC-001
related controls AIR-PREV-007, AIR-DET-004
crosswalks to    9 references across 3 frameworks
cite             aigf://control/AIR-PREV-020
[54 ms, read-only, rate-limited, audited]

# AIGF: reverse crosswalk, which records cite NIST SP 800-53 SA-9?
$ aigf > find_by_external_reference {"key": "sa-9"}
4 AIGF records cite this reference:
  control AIR-DET-001  AI Data Leakage Prevention and Detection
  control AIR-PREV-007  Legal and Contractual Frameworks for AI Systems
  control AIR-PREV-014  Encryption of AI Data at Rest
  control AIR-PREV-020  MCP Server Security Governance
[29 ms, read-only, rate-limited, audited]

# AIGF: search in plain language, every hit is citable
$ aigf > search_framework {"query": "an employee pastes client data into a public chatbot", "k": 3}
  AIR-RC-023  Intellectual Property (IP) and Copyright
      aigf://risk/AIR-RC-023
  AIR-SEC-010  Prompt Injection
      aigf://risk/AIR-SEC-010
  AIR-PREV-017  AI Firewall Implementation and Management
      aigf://control/AIR-PREV-017
[35 ms, read-only, rate-limited, audited]

# CDM: validate a Rune BusinessEvent an agent got wrong (3 planted defects)
$ cdm > validate_object {"object": "<broken_execution.json>"}
valid=False   format=rune   type=cdm.event.common.BusinessEvent
validator: json-schema draft4 (cdm-json-schema 7.2.0) via Rune normalisation
3 issue(s):
  [enum       ] $.instruction[0].primitiveInstruction.execution.product.economicTerms.payout[0].@type
      'InterestRatePayoutt' is not an alternative of Payout; expected one of ['AssetPayout', 'Commodit
  [required   ] $.after[0]
      'trade' is a required property
  [required   ] $.instruction[0].primitiveInstruction.execution
      'executionDetails' is a required property
[59 ms, read-only, rate-limited, audited]

# FDC3: which intents can I raise for an instrument, and which shows a chart?
$ fdc3 > suggest_intent {"context": {"type": "fdc3.instrument", "id": {"ticker": "AAPL"}}, "goal": "show a price chart"}
context fdc3.instrument (detected by type_field); ranked intents:
  1.44  ViewChart          ViewChart accepts fdc3.instrument; matches goal 'show a pr
  1.31  ViewQuote          ViewQuote accepts fdc3.instrument; matches goal 'show a pr
  1.22  ViewResearch       ViewResearch accepts fdc3.instrument; matches goal 'show a
  1.00  ViewInstrument     ViewInstrument accepts fdc3.instrument; matches goal 'show
  0.80  ViewAnalysis       ViewAnalysis accepts fdc3.instrument; matches goal 'show a
[43 ms, read-only, rate-limited, audited]

$ every tool is read-only; nothing here writes to any external system.
DEMO DONE
```

The CDM step validates [`examples/broken_execution.json`](https://github.com/vardhjain/finos-mcp/blob/main/examples/broken_execution.json):
a real CDM 7 Rune-format `BusinessEvent` with three deliberate defects (a misspelled payout
alternative, a removed required `trade`, and a missing `executionDetails`). Each is reported
with the JSON path *in the submitted document*, which is what lets an agent fix its own output.
