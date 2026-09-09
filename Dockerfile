# finos-mcp: read-only MCP servers over the streamable-http transport.
#
#   docker run --rm -p 8000:8000 ghcr.io/vardhjain/finos-mcp
#   docker run --rm -p 8000:8000 ghcr.io/vardhjain/finos-mcp \
#       finos-mcp-cdm --transport streamable-http --host 0.0.0.0 --port 8000
#
# The image needs no writable filesystem: vendored content is baked in, the servers make no
# network calls, and the audit log goes to stderr unless FINOS_MCP_AUDIT_PATH says otherwise.
# Run it locked down:  --read-only --cap-drop ALL --network none is enough for stdio-style use;
# an HTTP deployment obviously keeps its port.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
WORKDIR /src
COPY . .
# Build wheels rather than copying a uv venv: `uv sync` installs workspace members as editable,
# which would drag the source tree into the runtime image.
RUN set -eux; \
    for pkg in finos-mcp-core finos-mcp-aigf finos-mcp-cdm finos-mcp-fdc3; do \
        uv build --package "$pkg" --wheel --out-dir /wheels; \
    done

FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/vardhjain/finos-mcp" \
      org.opencontainers.image.description="Read-only MCP servers for FINOS standards (AIGF, CDM, FDC3)" \
      org.opencontainers.image.licenses="Apache-2.0"

COPY --from=build /wheels /wheels
# --find-links prefers the local wheels for our four packages; third-party deps still resolve
# from PyPI. finos-mcp-core is not published, so it must come from /wheels.
RUN set -eux; \
    pip install --no-cache-dir --find-links /wheels \
        finos-mcp-aigf finos-mcp-cdm finos-mcp-fdc3; \
    rm -rf /wheels; \
    useradd --create-home --uid 10001 finos

USER 10001
WORKDIR /home/finos
EXPOSE 8000

# Fail fast if the vendored content does not match its recorded hashes.
RUN python -c "\
from pathlib import Path; \
import finos_mcp.aigf, finos_mcp.cdm, finos_mcp.fdc3; \
from finos_mcp.core import verify; \
[verify(Path(m.__file__).parent / '_vendor') for m in (finos_mcp.aigf, finos_mcp.cdm, finos_mcp.fdc3)]; \
print('vendored content verified')"

CMD ["finos-mcp-aigf", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
