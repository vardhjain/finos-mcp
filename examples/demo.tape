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
Type "uv run python examples/demo_session.py"
Enter
Wait+Screen /READY/
Show

Wait+Screen /DEMO DONE/
Sleep 2s
