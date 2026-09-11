"""finos-mcp-core: the shared safety layer for finos-mcp servers."""

from .audit import AuditLog
from .catalog import (
    DEFAULT_EMBEDDING_MODEL,
    Catalog,
    Document,
    SearchMode,
    SemanticIndex,
    normalize_id,
    slugify,
    split_sections,
)
from .errors import (
    ErrorEnvelope,
    FinosToolError,
    ambiguous,
    invalid_input,
    not_found,
    unsupported_format,
)
from .metrics import Metrics
from .models import (
    Citation,
    Page,
    SearchHit,
    Section,
    ServerInfo,
    ValidationIssue,
    ValidationReport,
    paginate,
)
from .policy import RateLimit, SafetyPolicy
from .ratelimit import RateLimiter
from .schema import SchemaRegistry
from .server import READ_ONLY, build_server, register_server_info, register_tool, runtime_for
from .vendor import SourceManifest, VendorIntegrityError, build_manifest, verify

__version__ = "0.1.2"

__all__ = [
    "DEFAULT_EMBEDDING_MODEL",
    "READ_ONLY",
    "AuditLog",
    "Catalog",
    "Citation",
    "Document",
    "ErrorEnvelope",
    "FinosToolError",
    "Metrics",
    "Page",
    "RateLimit",
    "RateLimiter",
    "SafetyPolicy",
    "SchemaRegistry",
    "SearchHit",
    "SearchMode",
    "Section",
    "SemanticIndex",
    "ServerInfo",
    "SourceManifest",
    "ValidationIssue",
    "ValidationReport",
    "VendorIntegrityError",
    "__version__",
    "ambiguous",
    "build_manifest",
    "build_server",
    "invalid_input",
    "normalize_id",
    "not_found",
    "paginate",
    "register_server_info",
    "register_tool",
    "runtime_for",
    "slugify",
    "split_sections",
    "unsupported_format",
    "verify",
]
