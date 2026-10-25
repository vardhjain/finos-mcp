"""Ensure Glama listing ownership is declared without credentials.

Glama verifies ownership externally after the maintainer signs in.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_glama_ownership_metadata_matches_actual_repo_owner() -> None:
    raw = (ROOT / "glama.json").read_text(encoding="utf-8")
    metadata = json.loads(raw)
    assert metadata == {
        "$schema": "https://glama.ai/mcp/schemas/server.json",
        "maintainers": ["vardhjain"],
    }
    assert "password" not in raw.lower()
    assert "token" not in raw.lower()


def test_glama_claim_instructions_disclose_required_external_verification() -> None:
    guide = (ROOT / "docs" / "directory-listings.md").read_text(encoding="utf-8")
    assert "A `glama.json` file alone" in guide
    assert "**does not claim the listing**" in guide
    assert "Claim" in guide
    assert "Do not submit a duplicate listing" in guide
    assert "Not affiliated with or endorsed by FINOS" in guide
