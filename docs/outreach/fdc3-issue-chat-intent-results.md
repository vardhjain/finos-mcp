# Draft: StartChat and SendChatMessage do not declare their result

**Status: drafted 2026-10-05, not filed.** Target: [`finos/FDC3`](https://github.com/finos/FDC3/issues).
This is finding 15 in [../upstream-findings.md](../upstream-findings.md). A search of the
FDC3 issue tracker for "StartChat result" and "SendChatMessage output" found nothing covering
it, and the pages on `main` read the same as at `v2.2.3`.

---

**Title:** Docs: `StartChat` and `SendChatMessage` return a ChatRoom in their examples but declare no result

### What the docs say

The intent reference pages for `StartChat` and `SendChatMessage`
(`website/docs/intents/ref/`) each show an app reading a chat room from the intent result:

```js
// StartChat.md
const resolution = fdc3.raiseIntent('StartChat', initSettings);

// Return a reference to the room
const chatRoom = await resolution.getResult();
```

```js
// SendChatMessage.md
// Start a chat and retrieve a reference to the chat room created
const intentResolution = await fdc3.raiseIntent("StartChat", context);
const chatRoom = intentResolution.getResult();
```

Neither page says, outside the example, that the intent returns anything. Other intents in
the same directory do:

- `ViewChat.md` has an `## Output` section: "if the chat gets created, return its ChatRoom
  context".
- `CreateInteraction.md` and `CreateOrUpdateProfile.md` list the result under
  "SHOULD return context as a result".

### Why it matters

An implementer of a chat app reading `StartChat.md` cannot tell whether returning a
`fdc3.chat.room` context is expected, optional or incidental to the example. An app that
raises `StartChat` and then calls `getResult()`, as the `SendChatMessage` example does, relies
on behaviour the specification text never states.

It also affects anything that reads these pages mechanically. I maintain a small read-only
MCP server over the FDC3 context schemas and intent docs
([vardhjain/finos-mcp](https://github.com/vardhjain/finos-mcp), not affiliated with FINOS). It
builds an intent-to-context table from these pages and reports no result type for `StartChat`
or `SendChatMessage`, because none is declared. `ViewChat` correctly reports `fdc3.chat.room`.

### Suggested change

If these intents are meant to return a chat room, add the same kind of statement `ViewChat`
has, for example on `StartChat.md`:

```md
## Output

This intent SHOULD return a [ChatRoom](../../context/ref/ChatRoom) context identifying the
chat that was started.
```

and, if `SendChatMessage` returns nothing, say so, since its example only shows the result of
the earlier `StartChat`.

If the result is deliberately optional, a sentence saying so would settle it.

I am happy to open a pull request with whichever wording the maintainers prefer.

---

## Before filing

- Check the FDC3 contribution guide for whether documentation issues need a template or a
  Standard Working Group discussion first.
- The two example snippets differ in a second way: `StartChat.md` awaits `getResult()` but
  not `raiseIntent()`, and `SendChatMessage.md` does the reverse. Both lines need both
  awaits to run. That is a separate, smaller fix and could go in the same pull request.
