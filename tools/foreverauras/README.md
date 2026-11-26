# fa: ForeverAuras auras as files

Write an aura group as a Lua file, lint it against the installed ForeverAuras code, turn it into an import string or merge it into SavedVariables. Python 3.12, standard library only.

```
python tools/foreverauras/fa.py encode  group.lua [-o group.txt]       # file -> !WA:2! string
python tools/foreverauras/fa.py decode  <string-or-file> [-o out.lua]  # string -> file
python tools/foreverauras/fa.py pull    --sv <ForeverAuras.lua>                 # list group ids
python tools/foreverauras/fa.py pull    --sv <ForeverAuras.lua> --group <id> -o group.lua
python tools/foreverauras/fa.py install group.lua --sv <ForeverAuras.lua> [--dry-run out.lua]
python tools/foreverauras/fa.py lint    group.lua [--fa-dir <ForeverAuras folder>] [--compile [ssh-host]]
```

The SavedVariables file is `_forever_\WTF\Account\<ACCOUNT>\SavedVariables\ForeverAuras.lua`. `install` refuses while `Wow.exe` runs, because the client rewrites that file on exit. It copies the file to `<sv>.fa-backup-<timestamp>` first. `--fa-dir` defaults to the installed addon (`WOWF_GAME_DIR` overrides the game folder).

## Source file

```lua
return {
  d = { id = "My Group", regionType = "dynamicgroup", internalVersion = 91, ... },
  c = {
    { id = "My Group: Icon", regionType = "icon", internalVersion = 91, triggers = { ... } },
  },
}
```

Only literals: tables, strings (quoted or `[==[ long ]==]`), numbers (hex, negative, float), `true`, `false`, `nil` and `--` comments. No expressions. `decode` and `pull` write this shape with sorted keys and the array part first, so two decodes of a string diff cleanly. Multi-line custom code comes out in long brackets.

`encode` builds what ForeverAuras exports: `{m = "d", d = ..., c = {...}, v = 1421, s = <ForeverAuras.toc version>}`. With `v = 1421` the importer rebuilds `controlledChildren` and every child's `parent` from `c`, so you can leave both out. `v` becomes 2000 only when a child is itself a group, and then parents must be set. A missing `internalVersion` is filled with the addon's value (91), since without it the importer runs every migration on the aura. `install` does the same rebuild, also fills a missing `uid`, and drops displays that belonged to the old group but are gone from the new one.

`lint` reads the installed addon to check each aura. Region types come from `RegisterRegionType`, trigger types from `RegisterTriggerSystem` and event names and their types from `Prototypes.lua` and the files that add prototypes. It also checks that ids and uids are unique, that `internalVersion` matches the addon, that parent and `controlledChildren` agree, and that conditions name a trigger the aura has. By itself it does not compile custom code. It counts those strings and says "not checked".

With `--compile` it compiles every custom code string as ForeverAuras does. Each string goes through `luac5.1 -p` in the `wowf/lua51` container that `tools\lua.ps1` builds, on this PC's Docker. `--compile <ssh-host>` runs the same container on another machine's Docker over ssh instead. A syntax error is reported with the aura id, the field and the line inside that code. When Docker (or ssh) fails, it says so instead of passing.

## Parity with the real libraries

The ports in `luaser.py` (LibSerialize) and `deflate_print.py` (CompressDeflate, EncodeForPrint) were verified against LibSerialize and LibDeflate as shipped in ForeverAuras 1.4.3, in the `wowf/lua51` container (Lua 5.1.5):

- Strings made by this encoder (the test group, a stress table and a table with shared and self references) decode with the real libraries to equal tables, and the references keep their identity.
- Strings made by the real libraries from the same tables decode here to equal tables, identity included.
- LibSerialize's bytes for a list of numbers (every integer width, negatives, floats written as text or as 8 bytes) and a list of strings (embedded lengths, 16- and 24-bit lengths, string references, bytes that are not UTF-8) match this port byte for byte.

Whole tables do not match byte for byte, because Lua's `pairs` order is unspecified. The compressed bytes differ too (zlib against LibDeflate). Both sides read each other's output, which is what an import needs.

## Limits

- Lua tables become Python dicts, and a dict cannot hold both `[1]` and `[true]` (Python treats `True == 1`). Aura data does not do that.
- LibSerialize cannot write `inf`, `nan` or whole numbers of 2^56 and over. Lua corrupts them without a word; this port raises an error.
- Strings with the old `!` (v1) or bare (v0) prefixes use AceSerializer and are refused.

Tests: `python -I -m pytest tools/foreverauras/tests -q` (or `python -m unittest discover -s tools/foreverauras/tests`).
