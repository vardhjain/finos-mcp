# Reproducible demo, rendered with VHS (https://github.com/charmbracelet/vhs):
#   vhs examples/demo.tape
# Produces docs/demo.gif. The session script loads the servers once and issues five
# live tool calls; interpreter start-up is hidden from the recording.

Output docs/demo.gif
Set Shell "bash"
Set FontSize 15
Set Width 1400
Set Height 860
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set WaitTimeout 600s

Hide
# The audit log defaults to stderr, which would interleave JSON audit records with the
# demo output and make the recording unreadable. Send it to a file for the recording.
Type "export FINOS_MCP_AUDIT_PATH=/tmp/finos-demo-audit.jsonl && clear"
Enter
Type "uv run python examples/demo_session.py"
Enter
Wait+Screen /READY/
Show

Wait+Screen /DEMO DONE/
Sleep 2s
