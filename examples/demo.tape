# Reproducible two-minute demo, rendered with VHS (https://github.com/charmbracelet/vhs):
#   vhs examples/demo.tape
# Produces docs/demo.gif. Re-render after any change instead of screen-recording.

Output docs/demo.gif
Set Shell "bash"
Set FontSize 15
Set Width 1400
Set Height 820
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Type "# finos-mcp: typed, read-only MCP servers for FINOS standards"
Enter
Sleep 1s

Type "uv run finos-mcp-aigf --help"
Enter
Sleep 2s

Type "# 1. Ask the AIGF server through the in-memory MCP client"
Enter
Type "uv run python examples/quick_query.py aigf get_control '{\"id\": \"mi-20\", \"include_sections\": false}'"
Enter
Sleep 5s

Type "# 2. Reverse crosswalk: which controls cite NIST SP 800-53 SA-9?"
Enter
Type "uv run python examples/quick_query.py aigf find_by_external_reference '{\"key\": \"sa-9\"}'"
Enter
Sleep 5s

Type "# 3. CDM: validate a Rune-format BusinessEvent and read the structured issues"
Enter
Type "uv run python examples/quick_query.py cdm validate_object @examples/broken_execution.json"
Enter
Sleep 6s

Type "# 4. FDC3: which intents can I raise for an instrument?"
Enter
Type "uv run python examples/quick_query.py fdc3 suggest_intent '{\"context\": {\"type\": \"fdc3.instrument\", \"id\": {\"ticker\": \"AAPL\"}}}'"
Enter
Sleep 5s

Type "# Every call is rate-limited, size-capped, audited, and nothing writes anywhere."
Enter
Sleep 3s
