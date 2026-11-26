---
name: forever-api
description: Answer a WoW Forever API question (does it exist, signature, restrictions, Blizzard usage) from the vendored client lists and UI source, then the wiki. Use before writing any call you are not certain of, or when Classic Era memory and Forever might differ. Delegates to the api-lookup agent for a small-context answer.
---

# Forever API lookup

Forever = Mainline 12.1.x UI with interface 16001 (`docs/forever-api.md`). Classic Era answers are wrong here more
often than right.

1. If `vendor/wow-ui-source` is missing: `powershell -NoProfile -ExecutionPolicy Bypass -File tools\vendor-sync.ps1` first.
2. Spawn the `api-lookup` agent with the question verbatim plus what you intend to do with the answer (so it can
   flag restrictions that matter: secret values, hardware event, combat lockdown).
3. Trust the order: Ketho lists (existence), then `Blizzard_APIDocumentationGenerated` (signature), then a Blizzard
   call site (`Camelot/` over `Mainline/` over `Shared/`), then the wiki (restrictions).
4. Unconfirmed? Give the user a `/dump` line to run in game and code defensively (`if C_Foo and C_Foo.Bar then`).

Record a surprising answer (a rename, a removed global, a secret-value trap) as a row in `docs/forever-api.md`.
