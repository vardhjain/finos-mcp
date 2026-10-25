"""finos-mcp-fdc3: read-only MCP server exposing the FINOS FDC3 standard as typed tools."""

from importlib.metadata import version as _distribution_version

from .models import ContextType, Intent
from .registry import Fdc3Registry, get_registry

__version__ = _distribution_version("finos-mcp-fdc3")

__all__ = [
    "ContextType",
    "Fdc3Registry",
    "Intent",
    "__version__",
    "get_registry",
]
