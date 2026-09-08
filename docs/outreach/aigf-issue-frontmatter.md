# Draft issue: finos/ai-governance-framework

**Title:** Eight risk files silently lose `related_risks` to an unterminated YAML comment

**Not yet filed.** Prepared from the vendored content at commit `7728f95`.

---

In eight files under `docs/_risks/`, the last entry of `uk-regulations_references` carries an
inline `#` comment that is not terminated by a newline before the next key. YAML therefore
treats `related_risks:` as part of the comment text, and the list items that follow are parsed
as further entries of `uk-regulations_references`.

The affected line looks like this (`ri-1_information-leaked-to-hosted-model.md`, line 47):

```yaml
  - consumer-credit-act-1974 # Consumer-credit protections relevant to AI credit decisionsrelated_risks:
```

Note `decisionsrelated_risks:` — the comment text and the following key have been joined.

## Effect

Loading that file with any standard YAML front-matter parser:

```python
import frontmatter
p = frontmatter.load("docs/_risks/ri-1_information-leaked-to-hosted-model.md")

p.metadata["related_risks"]
# KeyError: the key does not exist

p.metadata["uk-regulations_references"][-2:]
# ['ri-2', 'ri-23']   <- risk ids, parsed as UK-regulation reference keys
```

So each affected risk both **loses its `related_risks` links** and **gains reference keys that
do not exist** in `docs/_data/references/uk-regulations.yml`. Across the eight files this
produces 19 unresolvable reference keys.

The rendered site is unaffected wherever it iterates the reference datasets by known key, which
is presumably why this has gone unnoticed; it shows up immediately in anything that consumes the
front matter directly.

## Affected files

| File | Line |
|---|---|
| `docs/_risks/ri-1_information-leaked-to-hosted-model.md` | 47 |
| `docs/_risks/ri-2_information-leaked-to-vector-store.md` | 49 |
| `docs/_risks/ri-16_bias-and-discrimination.md` | 40 |
| `docs/_risks/ri-17_lack-of-explainability.md` | 48 |
| `docs/_risks/ri-18_model-overreach-expanded-use.md` | 45 |
| `docs/_risks/ri-19_data-quality-and-drift.md` | 45 |
| `docs/_risks/ri-20_reputational-risk.md` | 40 |
| `docs/_risks/ri-22_regulatory-compliance-and-oversight.md` | 78 |

## Fix

A newline before `related_risks:` in each file. Happy to open the pull request if useful.

## Suggested guard

`scripts/validate-references.py` already validates that reference keys resolve against
`docs/_data/references/*.yml`. Extending it to fail on an unresolvable key would have caught
this, since `ri-2` is not a key in `uk-regulations.yml`. A second cheap check is that every
`ri-N`/`mi-N` cross-reference resolves to an existing document.

## How this was found

While parsing the framework into typed records for a read-only MCP server that exposes AIGF
risks and controls to AI agents. The parser reports unresolvable reference keys rather than
dropping them, which surfaced the 19 bogus keys.
