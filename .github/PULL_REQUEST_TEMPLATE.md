## What this changes

<!-- One or two sentences on what and why. Link the issue if there is one. -->

## Checklist

- [ ] `uv run pytest` passes
- [ ] `uv run ruff check .` and `uv run ruff format --check .` are clean
- [ ] `uv run mypy core/src servers/*/src evals/src` is clean
- [ ] Every tool stays read-only (no writes to any file, network endpoint or external system)
- [ ] New or changed tools have a golden case under `evals/golden/<server>/`
- [ ] Vendored content was changed only by running the sync script, never by hand
- [ ] `CHANGELOG.md` has an entry under "Unreleased" if users would notice the change
