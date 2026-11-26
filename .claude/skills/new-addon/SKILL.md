---
name: new-addon
description: Scaffold a new WoW Forever addon under AddOns/<Name> from templates/addon, as its own git repo, lint/test/CI ready, with the selftest contract, and junction-linked into the game. Use for "new addon", "create an addon", "scaffold <Name>". Not for porting someone else's addon (read it first, then use this for the shell only).
---

# New addon

Inputs (ask once for what the request does not give):
- `Name`: PascalCase, letters and digits only. It becomes the folder, the `.toc`, the addon table and `<Name>DB`.
- One line saying what the addon does (the `.toc` `## Notes`).
- Author name for `## Author` and the `LICENSE`. Use what the user gives; else `git config user.name`; never invent one.

## Steps

1. **Check the name is free**: `AddOns/<Name>` must not exist, and `<game>\_forever_\Interface\AddOns\<Name>` must not
   be an installed addon (`tools\link-addons.ps1 -Status`).
2. **Copy the template**: copy `templates/addon/` (hidden files included: `.busted`, `.luacheckrc`, `.stylua.toml`,
   `.pkgmeta`, `.gitignore`, `.github/`) to `AddOns/<Name>/`. Rename `__NAME__.toc` to `<Name>.toc`. In every file,
   replace the placeholders, then grep the folder for `__[A-Z]*__` and expect no hits:

   | Placeholder | Becomes | Example |
   |---|---|---|
   | `__NAME__` | Name | `LootNotes` |
   | `__LOWER__` | name in lower case (the slash command) | `lootnotes` |
   | `__UPPER__` | name in upper case (the `SlashCmdList` key) | `LOOTNOTES` |
   | `__NOTES__` | the one-line description | |
   | `__AUTHOR__` | the author | |
   | `__YEAR__` | the current year | |

   Use the Edit/Write tools for the replacements, so each change is visible.
3. **Lint and test offline**: `powershell -NoProfile -ExecutionPolicy Bypass -File tools\lua.ps1 all -Path AddOns\<Name>`
   must be green before anything else. Docker not running: tell the user (start Docker Desktop), don't skip the step.
4. **Git**: the addon is its own repo, and the workspace ignores `AddOns/*/`:
   `git -C "AddOns/<Name>" init -b main`, then `git -C "AddOns/<Name>" add -A` and
   `git -C "AddOns/<Name>" commit -m "Scaffold <Name>"`.
5. **GitHub (optional, ask first)**: ask whether to create a GitHub repo for it, and public or private. Only on a
   yes: `gh auth status` (not logged in: ask the user to run `gh auth login` themselves), then
   `gh repo create <Name> --public --source "AddOns/<Name>" --push` (or `--private`). This creates it under the
   user's own account. Never create a repo, push or pick a visibility without that yes.
6. **Link into the game**: `powershell -NoProfile -ExecutionPolicy Bypass -File tools\link-addons.ps1 -Name <Name>`.
   A new addon folder is only seen after a **full client restart** (exit the game and start it again); `/reload`
   is not enough the first time. Tell the user so in plain words.
7. **First in-game check** (after the user's restart): the `verify` skill. `tools\reload-wait.ps1 <Name>` shows
   `selftest.version` and zero errors once the user has `/reload`ed or logged out.

## Rules the addon keeps

- `local ADDON, ns = ...` at the top of every Lua file; no globals except `<Name>`, `<Name>DB` and the slash
  command's `SLASH_<UPPER>1`.
- Every chat or unit-data path checks `issecretvalue()` before comparing, measuring or matching a value, and skips
  the analysis instead of failing (`docs/forever-api.md`, "Secret values").
- The `selftest` fields stay as `docs/verify-loop.md` lists them; add your own counters to `counters`.
- A new `.lua` file goes in the `.toc` (load order: data before the code that reads it, `Core.lua` last) and in
  `tests/wow_mock.lua`'s `loadAddon` list. A file newly added to the `.toc` needs a client restart, not a `/reload`.
- Nothing private in a public repo: no account, character, realm or guild names, no chat text, no local paths.
