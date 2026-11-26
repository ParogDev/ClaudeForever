# The Forever client and its API

What the WoW: Forever client is, which API it has, and the traps that differ from Classic, with the evidence for each.

## What the client is

| Fact | Value | Evidence |
|---|---|---|
| Version / build | 1.60.1.70790 (launch 2026-11-04) | `.build.info` in the install; wow-ui-source `forever` commit "1.60.1 (70790)" |
| Product code | `wowf`; install subfolder `_forever_` | `.build.info`, `Config.wtf` (`agentUID "wowf"`) |
| TOC interface | `## Interface: 16001` | `Config.wtf` `engineSurveyPatch "16001"`; Warcraft Wiki TOC_format |
| Project constant | `WOW_PROJECT_ID == WOW_PROJECT_CAMELOT` (18) | `vendor/wow-ui-source/Interface/AddOns/Blizzard_ProjectConstants/Camelot/ProjectConstants.lua` |
| Game type names | `camelot` (TOC game type), `forever` alias | Warcraft Wiki Patch 1.60.1/API changes |
| UI codebase | **Mainline** (Midnight 12.1.x), with `Camelot/` override folders per Blizzard addon | `vendor/wow-ui-source/Interface/AddOns/*/Camelot` |
| Lua | 5.1 (Blizzard variant: `bit`, no `io`/`os`/`require`; sandboxed `import`) | Warcraft Wiki |

Blizzard said it plainly (2026-09-15, via Warcraft Wiki): Forever "shares Mainline WoW's UI architecture, including the vast majority of APIs available in 12.1.5". Forever and Midnight are two game types (`camelot`, `standard`) of the Mainline family. Classic Era (1.15, interface 11509) is a different codebase; its docs and addons do not apply.

## Where to look things up (in this order)

1. `vendor/BlizzardInterfaceResources/Resources/GlobalAPI.lua`, `FrameXML.lua`, `Events.lua`, `LuaEnum.lua`: does this client have it at all? (`tools/luacheck-wow-globals.lua` is generated from these.)
2. `vendor/wow-ui-source/Interface/AddOns/Blizzard_APIDocumentationGenerated/*.lua`: signatures and types for every `C_*` function and event.
3. `vendor/wow-ui-source/Interface/AddOns/<Blizzard addon>/{Shared,Mainline,Camelot}/`: how Blizzard's own UI does it. A `Camelot/` file overrides the Mainline one.
4. `https://warcraft.wiki.gg/wiki/API_<name>`: prose, restrictions, history. `/wiki/Patch_1.60.1/API_changes` for what Forever added or removed.
5. ForeverPlusPlus `docs/forever-api.md` on GitHub (xIGBClutchIx): a working addon author's notes.

The `/forever-api` skill does this walk.

## Renamed or removed since the APIs you may remember

| Old | Forever |
|---|---|
| `GetItemInfo` | `C_Item.GetItemInfo` |
| `GetSpellInfo` | `C_Spell.GetSpellInfo` (returns a table) |
| `UnitAura`, `UnitBuff` | `C_UnitAuras.*` |
| `GetContainerItemInfo` | `C_Container.GetContainerItemInfo` |
| `IsAddOnLoaded`, `GetAddOnMetadata` | `C_AddOns.*` |
| `GetMouseFocus` | `GetMouseFoci` |
| `EasyMenu` | `MenuUtil` |
| `ChatFrame_AddMessageEventFilter` | `ChatFrameUtil.AddMessageEventFilter` (`Blizzard_ChatFrameBase/Shared/ChatFrameFilters.lua:202`); check `Blizzard_DeprecatedChatInfo` before relying on the old global |
| `InterfaceOptions_AddCategory` | `Settings.RegisterAddOnCategory` / `Settings.RegisterCanvasLayoutCategory` (`Blizzard_Settings_Shared/Blizzard_Settings.lua`) |
| `COMBAT_LOG_EVENT_UNFILTERED`, `CombatLogGetCurrentEventInfo` | gone (secret values) |

Forever additions worth knowing: `C_GameRules` (`IsGameRuleActive`, `GetForeverExperiencePreset`, `IsHardcoreActive`), `C_SkillInfo`, `C_PetInfo` (happiness, loyalty), `UnitUsesAmmo`, events `PLAYER_SWING`, `UNIT_HAPPINESS`, `GAME_RULES_CHANGED`, `SHARD_TRANSFER`. Absent: `C_Seasons`, `C_Engraving`, `C_ClassicPlus`.

## Secret values (the rule that bites a chat addon)

Midnight's addon restrictions are on. A *secret* is a Lua value you can store, concatenate and hand to a FontString, but not compare, measure (`#`, `strlen`), pattern-match or do arithmetic on: those raise an error. Check with `issecretvalue(v)`; `canaccessvalue(v)` says whether this code path may read it.

| Where | What becomes secret |
|---|---|
| Communication-restricted maps (dungeons, raids, battlegrounds, arenas) and encounters | incoming chat text (`CHAT_MSG_*` arg 1) and addon messages; sender names are not |
| Any combat / encounter | unit health, power, auras, cast info, nameplate data |
| Always | `COMBAT_LOG_EVENT_UNFILTERED` (removed), GUID server/spawn parts obfuscated |

For a chat addon: every `CHAT_MSG_*` handler starts with `if issecretvalue(text) then show raw; mark "instance"; return end`. The selftest table records how many lines were secret (`templates/addon/Core.lua` shows the pattern). Simulate in town: `/console addonChatRestrictionsForced 1` (and `0` to clear). Never `debugstack()` a secret into a SavedVariable.

Other 1.60.1 restrictions: `SendChatMessage` EMOTE needs a hardware event outside instances (SAY and YELL already did); trial and Veteran accounts cannot send addon messages; addon messages are 255 bytes, ~10/s per prefix, and blocked under the same lockdown.

## Chat events and text

Register `CHAT_MSG_GUILD`, `CHAT_MSG_OFFICER`, `CHAT_MSG_PARTY`, `CHAT_MSG_PARTY_LEADER`, `CHAT_MSG_RAID`, `CHAT_MSG_RAID_LEADER`, `CHAT_MSG_WHISPER`, `CHAT_MSG_SAY`, `CHAT_MSG_YELL`, `CHAT_MSG_CHANNEL`. Payload: `text, playerName, languageName, channelName, playerName2, specialFlags, zoneChannelID, channelIndex, channelBaseName, languageID, lineID, guid, bnSenderID, isMobile, isSubtitle, hideSenderInChatFrame, supressRaidIcons`. The full list of chat types: `Blizzard_ChatFrameBase/Shared/ChatTypeInfoConstants.lua`.

Text is UTF-8 bytes. Han (CJK Unified Ideographs U+4E00–U+9FFF) are three-byte sequences `E4 B8 80` … `E9 BF BF`; Extension A (U+3400–U+4DBF) is `E3 90 80` … `E4 B6 BF`. Iterate characters with `"[%z\1-\127\194-\244][\128-\191]*"`. `strlenutf8` exists; there is no `utf8` library.

## Fonts

Blizzard's font families (`Blizzard_Fonts_Shared/Mainline/Fonts.xml`) include a Chinese member, `Fonts\ARKai_T.ttf`, but a client installed without a Chinese locale may not ship the file, and then CJK renders as boxes (WoWTranslator hit this on Forever). Probe: `pcall(fs.SetFont, fs, "Fonts\\ARKai_T.ttf", 12)` returns false with "Invalid font asset" when missing. Mitigation: bundle a subsetted OFL font (Noto Sans CJK SC) under `AddOns\<Name>\Fonts\` and set it on the addon's own FontStrings. Never call `SetFont` on a FontFamily object: it strips the CN/KR/RU alphabets; use `SetFontObject` then `SetFontHeight`.

## SavedVariables and getting data out

Written only on `/reload`, logout, exit or disconnect (a `.lua.bak` of the previous file beside it). Path: `_forever_\WTF\Account\<ACCOUNT>\SavedVariables\<Addon>.lua` for `## SavedVariables`, `...\<ACCOUNT>\<realm id>\<Char-Realm>\SavedVariables\` for `## SavedVariablesPerCharacter`. Nothing in Lua reaches the network or the filesystem. The built-in `/chatlog` streams incoming chat to `_forever_\Logs\WoWChatLog.txt` during play, in blocks rather than per line. Data *into* the game: a `.lua` file already listed in the TOC, rewritten on disk, is picked up on the next `/reload`; a file newly added to the TOC needs a client restart.

## Tooling that is Forever-aware

BigWigsMods/packager ≥ 2.6.1 (`-g forever`, detects `_Camelot.toc` suffix and plain TOCs with 16001); CurseForge flavor "Forever" (1.60.1), Wago flavor `forever`; WowUp 2.24.1, CurseBreaker 4.9.1; BugSack and BugGrabber have Forever builds; ElvUI 16.00+. Logonz/WoW-API generates LuaLS `---@meta` for Forever (`tools\vendor-sync.ps1 -WithLuaLs`, needs `uv`).
