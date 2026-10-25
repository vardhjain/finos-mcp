# Reproducible demo, rendered with VHS (https://github.com/charmbracelet/vhs):
#   vhs examples/demo.tape
# Produces docs/demo.gif. The session runs five live MCP calls in three
# sequential, isolated workers so CDM does not share memory with AIGF or FDC3.
# Install the workspace first with: uv sync --all-packages --all-extras

Output docs/demo.gif
Set Shell "bash"
Set FontSize 15
Set Width 1400
Set Height 860
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set WaitTimeout 180s

Hide
# The audit log defaults to stderr, which would interleave JSON audit records with the
# demo output and make the recording unreadable. Send it to a file for the recording.
Type "export FINOS_MCP_AUDIT_PATH=/tmp/finos-demo-audit.jsonl && clear"
Enter
Type "uv run --no-sync python examples/demo_session.py"
Enter
Wait+Screen /READY/
Show

Wait+Screen /DEMO DONE/
Sleep 2s
