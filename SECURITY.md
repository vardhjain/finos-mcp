# Security policy

finos-mcp servers are read-only catalogues with no network access at runtime. The safety
model is described in [docs/safety.md](docs/safety.md).

## Reporting a vulnerability

Please open a private security advisory on GitHub for this repository, or email the
maintainer listed in `pyproject.toml`. Include the server, the tool call that triggers the
issue, and the version (`server_info` reports it). You will get an acknowledgement within
five working days.

## Scope

In scope: anything that lets a tool call write, exfiltrate, exhaust resources beyond the
documented limits, bypass the read-only gate, or leak server internals to the calling model.

Out of scope: the content of the FINOS standards themselves (report those upstream), and
deployments that expose the HTTP transport without their own authentication layer.
