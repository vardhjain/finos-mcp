"""Offline tests for PyPI ownership boundary matching."""

from scripts.check_pypi_mcp_ownership import ownership_marker_present


def test_exact_hidden_comment() -> None:
    assert ownership_marker_present(
        "<!-- mcp-name: io.github.vardhjain/finos-mcp-aigf -->",
        "io.github.vardhjain/finos-mcp-aigf",
    )


def test_trailing_punctuation_is_not_boundary() -> None:
    assert not ownership_marker_present(
        "mcp-name: io.github.vardhjain/finos-mcp-aigf.",
        "io.github.vardhjain/finos-mcp-aigf",
    )


def test_wrong_server_or_prefix_is_not_accepted() -> None:
    assert not ownership_marker_present(
        "mcp-name: io.github.vardhjain/finos-mcp-cdm",
        "io.github.vardhjain/finos-mcp-aigf",
    )
    assert not ownership_marker_present(
        "mcp-name: io.github.vardhjain/finos-mcp-aigf-extra",
        "io.github.vardhjain/finos-mcp-aigf",
    )
