"""JSON-lines audit log of every request.

Under stdio transport, stdout is the protocol channel, so the log goes to stderr
(default) or to the file named by ``FINOS_MCP_AUDIT_PATH``.  Tool arguments are
hashed by default so the log never becomes a second copy of the agent's inputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

ENV_AUDIT_PATH = "FINOS_MCP_AUDIT_PATH"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(
        self,
        server: str,
        *,
        stream: TextIO | None = None,
        path: Path | None = None,
        hash_inputs: bool = True,
    ) -> None:
        self.server = server
        self.hash_inputs = hash_inputs
        self._path = path
        self._stream: TextIO | None = stream
        self._lock = threading.Lock()
        self.records_written = 0

    @classmethod
    def from_env(cls, server: str, *, hash_inputs: bool = True) -> AuditLog:
        raw = os.environ.get(ENV_AUDIT_PATH)
        if raw:
            p = Path(raw).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            return cls(server, path=p, hash_inputs=hash_inputs)
        return cls(server, stream=sys.stderr, hash_inputs=hash_inputs)

    def describe_args(self, arguments: Mapping[str, Any] | None) -> dict[str, Any]:
        text = canonical_json(arguments or {})
        out: dict[str, Any] = {"args_bytes": len(text.encode("utf-8"))}
        if self.hash_inputs:
            out["args_sha256"] = sha256_text(text)
        else:
            out["args"] = arguments or {}
        return out

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps(
            {
                "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "server": self.server,
                **record,
            },
            ensure_ascii=False,
            default=str,
        )
        with self._lock:
            if self._path is not None:
                with self._path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(line + "\n")
            elif self._stream is not None:
                self._stream.write(line + "\n")
                self._stream.flush()
            self.records_written += 1
