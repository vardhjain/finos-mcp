# Upstream outreach

Drafts prepared from the findings in [../upstream-findings.md](../upstream-findings.md).
**Nothing here has been filed.** Each needs a decision before it goes to a FINOS repository.

| Draft | Target | Kind | Why it is worth filing |
|---|---|---|---|
| [aigf-issue-frontmatter.md](aigf-issue-frontmatter.md) | `finos/ai-governance-framework` | Bug | Concrete, reproducible, one-line fix per file; costs the project 19 bogus reference keys and 8 lost link sets today |
| *(unwritten)* | `finos/ai-governance-framework` | PR | Add finos-mcp under community integrations, alongside the existing `finos/aigf-mcp-server` |
| *(unwritten)* | `finos/common-domain-model` | Bug | Eight 7.2.0 schema files emit Rosetta basic-type names as JSON Schema `type`, which makes a strict Draft 4 validator raise `UnknownType` |
| *(unwritten)* | `finos/common-domain-model` | Question | 18 of 28 official 7.2.0 samples fail the published 7.2.0 schema on `required` alone; is the schema or the sample set authoritative? |
| *(unwritten)* | `finos/FDC3` | Enhancement | Ship the intent-to-context mapping as machine-readable JSON; it exists only as markdown bullet lists today |

## Before filing anything

- **FINOS requires EasyCLA** on pull requests. Sign the individual CLA first; it is immediate.
- File the AIGF bug **before** the integration PR. It is a genuine contribution and makes the
  integration link land better than a link on its own would.
- The CDM `required` mismatch is a question, not a bug report: the samples may legitimately be
  partial fixtures. Ask rather than assert.
- Do not frame any of this as criticism of `finos/aigf-mcp-server`. It is a different design
  (live GitHub fetch, filename ids); this project vendors and derives the published `AIR-*` ids.
