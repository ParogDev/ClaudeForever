# ForeverAuras on Forever: what an aura can know, and when

ForeverAuras (FA, 1.4.3) is a WeakAuras fork for the Forever client. Forever runs Mainline 12.1 UI
code, so Midnight's **secret values** apply: in combat the game hands addons many numbers as
secrets, which can be drawn but not compared. Every aura design starts from the question "is the
value I decide on readable at the moment I need it?". This page answers it, with the source for
each line. Authoring by file: `tools/foreverauras/README.md`. First aura set:
`docs/auras/rogue-combat.md`.

## The rule in one paragraph

A secret can be stored, passed to a widget (`StatusBar:SetValue`, a cooldown swipe, a FontString)
and run through Blizzard's curve and duration objects, but Lua cannot compare it, do arithmetic on
it or branch on it. So **in combat an aura can always display a secret value, but it cannot make
a Lua decision from it**. Decisions come from values that are never secret, or from FA features
that hand the secret to a Blizzard object that decides on its own (colour curves, native aura
frames, the Cooldown Manager).

## When values turn secret

From `vendor/wow-ui-source/.../Blizzard_APIDocumentationGenerated/SecretPredicatesDocumentation.lua`:

| Data | Secret when | API it applies to |
|---|---|---|
| Auras (buffs, debuffs, durations, stacks) | combat, encounter, challenge mode, PvP match. Single spells can be flagged never or always secret | `C_UnitAuras.GetPlayerAuraBySpellID`, `GetUnitAuraBySpellID`, `GetAuraDataByIndex` |
| Spell and action cooldowns | same as auras, with the same per-spell flags | `C_Spell.GetSpellCooldown`, `GetSpellCharges`, `GetActionCooldown` |
| Unit power (energy, mana) | always for power types not flagged never-secret | `UnitPower`, `UnitPowerPercent` |
| Max power, max health | when the unit is not player-controlled | `UnitPowerMax`, `UnitHealthMax` |
| Cast info | when the unit is not the player or their pet | `UnitCastingInfo` |
| Combat log | gone entirely | `COMBAT_LOG_EVENT_UNFILTERED` |
| Chat | instances and encounters | `CHAT_MSG_*` (`docs/forever-api.md`) |

Never secret (no secret tag in the API docs): **`C_Spell.IsSpellUsable`** (usable, not enough
power), **`C_Spell.IsSpellInRange`**, `IsUsableAction`, `IsActionInRange`, the player's own cast
events, `GetTime`.

The per-spell and per-power flags are game data, not in the UI source. Ask the client:
`/dump C_Secrets.GetPowerTypeSecrecy(Enum.PowerType.Energy)` (0 never, 1 always, 2 contextual),
`GetPowerTypeSecrecy(Enum.PowerType.ComboPoints)`, `C_Secrets.GetSpellAuraSecrecy(6774)` (Slice and
Dice), `C_Secrets.GetSpellCooldownSecrecy(1329283)` (Shank). FA's own switch is
`C_Secrets.ShouldAurasBeSecret() or ShouldCooldownsBeSecret()` (`ForeverAuras\ClientAPI.lua:6-16`),
re-checked on combat changes (`Secrets.lua:11-39`).

Measured on Forever (1.60.1, a rogue): **energy is 2 (contextually secret)**, so it is hidden in
combat as the rules above assume. **Combo points are 0 (never secret)**: `UnitPower("player",
Enum.PowerType.ComboPoints)` can be compared in custom code even in combat.

## Which FA trigger to use for which decision

| You want to show | Trigger (`type` / `event`) | Works in combat? | Notes |
|---|---|---|---|
| "Ability is usable now" (reactive: Riposte after a parry) | `spell` / `Action Usable` | **Yes**, usability is never secret | `Prototypes.lua:5968`. When cooldowns are secret, readiness uses the cooldown widget data (`:6033`) |
| Cooldown swipe and "ready" state | `spell` / `Cooldown Progress (Spell)` | Yes for display (secret-safe duration object, `:5000`) | `genericShowOn` = `showOnCooldown` / `showOnReady` / `showAlways`. Condition variables `onCooldown`, `spellUsable`, `insufficientResources`, `spellInRange` |
| Buff or debuff with a duration bar | `secretAura` ("Aura (Modern)") | **Yes**, draws through Blizzard's own aura frames | Time conditions allow only `<` and `>=`, no Else If (`enUS.lua:1695-1697`) |
| Same, the WeakAuras way | `aura2` ("Aura (Legacy)") | **Unreliable**: in combat it only asks per exact spell id and drops secret results (`BuffTrigger2.lua:290-320`) | Fine out of combat; don't build combat displays on it |
| Cooldowns and buffs from Blizzard's Cooldown Manager | `cdm` | Yes, the designed path | Needs the spell in the Cooldown Manager (`/fa cdmsetup`). Not confirmed for every Forever rogue spell |
| Energy bar | `unit` / `Power`, `powertype = 3` | Display yes. A trigger filter on energy no (out of combat only) | Colour by energy with **Conditions** (they go through curves, `Prototypes.lua:2459`) |
| Combo points | `unit` / `Power`, `powertype = 4` | **Yes, filterable in combat** (`PowerFilterable`, `:2439`; never secret, measured) | One trigger filter per pip works; custom code may compare them too |
| Health threshold glow | `unit` / `Health` + Condition on `percenthealth` | Display and colour/glow yes | Conditions only, no trigger filter |
| Swing timer | `unit` / `Swing Timer` | Fed by `PLAYER_SWING`, no combat log | Value secrecy unconfirmed |
| Anything custom | `custom` | Yes if the code reads only non-secret APIs | Sandboxed: `AuraEnvironment.lua:232` blocklist. Use `issecretvalue()` before any comparison |

## Rules of thumb for auras that work out of the box

1. **Decide on usability, display the numbers.** "Enough energy for Sinister Strike" is
   `insufficientResources` on a spell trigger (never secret), not `energy >= 45` in Lua.
2. **A window with no aura is a custom clock.** When the game shows a proc only as "becomes usable"
   (Riposte), start the aura's own `GetTime()` clock when usability flips on. That clock is never secret.
3. **Buffs in combat go through `secretAura` or `cdm`**, never `aura2`.
4. **Set `internalVersion` on every display** written by file to the installed addon's value (91 in
   FA 1.4.3; later FA versions raise it, and `fa.py lint` names a mismatch), or the v<7 migration
   replaces the triggers (`Modernize.lua:101-111`). `fa.py encode` fills a missing one.
5. **Always set trigger 1's `type` and `event`.** The data stub fills nil fields with an
   `aura2`/`Health` default (`Types.lua:3735-3796`).
6. **Load by class and known spell**, so a shared aura stays silent on a character without the
   talent.
7. **Spell ids from Forever, not Classic.** FA's own rank table (`SecretAuraRanks.lua:324-361`)
   lists the rogue ranks it knows; Forever-new spells (Shank 1329283/1329549, Poised 1328825) are
   missing from FA's tables, so give them by id.

## Sharing

An export string is `!WA:2!` + LibDeflate print-encoding of a raw-DEFLATE LibSerialize payload
`{m="d", d=group, c={children}, v=1421, s="1.4.3"}` (`Transmission.lua:372-476`). FA reads `!WA:`
and `!FA:` prefixes, so stock WeakAuras strings for Classic import, but most of their triggers
(`aura2`, combat-log) will not work in combat here. The sets in `auras/` are built from source with
`tools/foreverauras/fa.py encode`; the import still goes through FA's import window, which runs the
same validation as a pasted string.

## Open questions to settle in game (once, then update this page)

- Whether the rogue spells the example set uses appear in the Cooldown Manager (`cdm` triggers).
- Swing Timer values in combat.
- Riposte's usable window after a parry (Classic: 5 s). The rogue set measures it, see its page.
