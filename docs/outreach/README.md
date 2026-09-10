# Upstream outreach

Contributions back to the FINOS projects whose standards this repository vendors, arising from
the findings in [../upstream-findings.md](../upstream-findings.md).

## Filed

All three are open at [`finos/ai-governance-framework`](https://github.com/finos/ai-governance-framework),
submitted 2026-09-08/09.

| Item | What it is | Status |
|---|---|---|
| [Issue #378](https://github.com/finos/ai-governance-framework/issues/378) | Bug report: eight risk files silently lose `related_risks` to an unterminated YAML comment | Open |
| [PR #380](https://github.com/finos/ai-governance-framework/pull/380) | The fix. 8 files, one newline each, no content edited. Restores **21** `related_risks` links and removes **19** reference keys that do not exist in `uk-regulations.yml`. DCO check green, mergeable, `Fixes #378` | Open, awaiting review |
| [Issue #381](https://github.com/finos/ai-governance-framework/issues/381) | Introduces this project, asks whether a link would be useful and where, and offers to upstream the offline vendoring and `AIR-*` id derivation to `finos/aigf-mcp-server`. A comment asks whether the `finos-mcp-*` PyPI names are acceptable | Open |

Evidence submitted with PR #380, reproducible from a checkout of that branch: all 46 risk and
mitigation documents parse, every restored link resolves to an existing risk, no `*_references`
list contains a `ri-N` key, and upstream's own `scripts/validate-references.py` still reports
`13 file(s) valid`.

The full bug report as submitted is kept at
[aigf-issue-frontmatter.md](aigf-issue-frontmatter.md).

## Not filed, and why

| Candidate | Target | Why it is on hold |
|---|---|---|
| PR adding this project to a tools / integrations list | `finos/ai-governance-framework` | **There is no such section**, and that repo does not link `finos/aigf-mcp-server` — the official FINOS MCP server for this framework — either. Adding ours would mean inventing a section to place an unaffiliated tool where the official one is absent. Issue #381 asks first instead. |
| Bug: Rosetta basic-type names leak into JSON Schema `type` | `finos/common-domain-model` | Real defect (8 files in 7.2.0 make a strict Draft 4 validator raise `UnknownType`), but it belongs upstream at [REGnosys/rosetta-code-generators](https://github.com/REGnosys/rosetta-code-generators), which needs its own look before filing. |
| Question: 18 of 28 official 7.2.0 samples fail the published 7.2.0 schema on `required` alone | `finos/common-domain-model` | A question, not a bug report: the samples may be deliberately partial fixtures. Worth asking, but only once phrased so it does not read as an accusation. |
| Enhancement: publish the intent-to-context mapping as machine-readable JSON | `finos/FDC3` | Genuinely useful to any consumer, since the mapping exists only as markdown bullet lists today. Not yet written up. |

## Notes for filing anything else here

- **`finos/ai-governance-framework` uses DCO, not EasyCLA.** The only PR check is the probot
  DCO app; `CONTRIBUTING.md` requires a `Signed-off-by` line, so commit with `git commit -s`.
  (An earlier draft of this file claimed EasyCLA was required. It is not.)
- File the bug before the introduction. #378 and #380 went first deliberately, so #381 arrives
  from a contributor rather than a stranger with a link.
- Do not frame any of this as criticism of `finos/aigf-mcp-server`. It is a different design
  (live GitHub fetch, filename-derived ids); this project vendors with provenance and derives
  the published `AIR-*` ids, and those two pieces have been offered upstream to it.
