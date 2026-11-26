# Combat Rogue macros (WoW: Forever 1.60.1)

A worked example of a macro set for a combat rogue, with the reasoning for each line. Each macro has
a status: **untested** until it has been pressed in game, then **works** or **changed** with a
dated line in the log at the bottom (keep that habit in your own copy). Every body is under the
255-character limit; the fenced blocks are the exact text to paste into `/macro`.

Client facts were read from `vendor/BlizzardInterfaceResources` (slash commands, CVars, macro
slot counts). The conditional list is Warcraft Wiki's `Macro_conditionals` page; the rogue kit is
Warcraft Wiki's `Rogue abilities (Forever)` and `Shank` pages. Nothing here has been run in the
game yet.

## What a macro can and cannot do

| Can | Cannot |
|---|---|
| Pick a spell by stealth, combat, weapon type, known spell: `[stealth]` `[combat]` `[equipped:Daggers]` `[known:Cold Blood]` | Tell a player from an NPC, or read creature type (humanoid or not) |
| Aim without changing target: `@mouseover`, `@focus`, `@cursor` (ground spells) | Read health, energy, combo points, buffs, debuffs, cooldowns, range or facing |
| Test the target: `[harm]` `[help]` `[dead]` `[exists]` and their `no` forms | Cast two abilities that share the global cooldown on one press |
| Chain abilities that are off the global cooldown with one that is on it | Wait, loop or press itself again |
| Fall through: a `/cast` that fails (on cooldown, not usable) lets the next `/cast` try, at the price of an error on each failed line | Decide in Lua: `/run` cannot cast, target or use items |
| `/cancelaura`, `/targetenemy`, `/castsequence`, `/equipslot`, `/use 13` | Hold more than 255 characters; 120 account plus 30 character slots |

`/cast Name` with no rank always uses the highest rank known. A spell dragged from the spellbook
keeps the rank it had, so macros also save re-dragging after each trainer visit.

### Pick Pocket and players

No conditional says "the target is a player", so a macro cannot skip the line. What it does
instead:

1. The game refuses Pick Pocket on a player ("Invalid target") and the opener on the next line
   still fires on the same press. Stealth holds.
2. That refusal is an error you will see and hear. It is a kept exception to the house rules
   below: splitting Pick Pocket onto its own key would cost a press on every mob.
3. For an opener with no Pick Pocket at all, keep the plain spell on another key.

All three openers assume Pick Pocket is off the global cooldown, as it was in Classic, so the
opener fires on the same press. First thing to check in game: if the first press only picks the
pocket and the opener needs a second press, Pick Pocket is on the global cooldown here and the
openers become two-press.

A real skip needs an addon that looks at the target out of combat and swaps the button. Not built.

Turn on auto loot (`/console autoLootDefault 1`), or the Pick Pocket loot window stays open
through the opener.

## House rules

General advice that this set follows. Break one when you have a reason; write the reason next to
the macro.

- **Stealth is never in a macro.** Stealth is the plain spell on its own key, and the main bar
  already swaps to a stealth page when it is up. The opener macros go on that page and do
  nothing out of stealth.
- **No macro hides errors.** No error-speech toggles, no cleared error text: an error means
  something is wrong (cooldown, range, no target), and every macro here still raises those like
  the bare spell would.
- **No macro errors by design.** A line that fails on most presses (Riposte or Shank in front of
  Sinister Strike) is a separate button instead. Three exceptions are kept on purpose, each with
  the reason in its note: Pick Pocket on a player in the openers, `ColdEvis` while Cold Blood is
  on cooldown, and `Burst` on a repeat press.
- **No `/startattack`, no `/stopattack`**, unless you want one for a named reason. See
  "Auto-attack" near the end.
- **One macro, one job.** No key-combination or mouse-button branches, ever: a second job is a
  second macro on its own key. A spell that needs nothing added is not a macro at all (Kidney
  Shot, Eviscerate, Slice and Dice, Expose Armor, Vanish, Evasion, Sprint, Blade Flurry, Riposte, Shank): drag it
  from the spellbook.

## Openers

### `Stun` (Pick Pocket, then Cheap Shot): untested

```
#showtooltip Cheap Shot
/cast [stealth,harm,nodead] Pick Pocket
/cast Cheap Shot
```

### `Opener` (Pick Pocket, then Ambush with a dagger, Garrote without): untested

```
#showtooltip
/cast [stealth,harm,nodead] Pick Pocket
/cast [stealth,equipped:Daggers] Ambush; [stealth] Garrote
```

The damage opener. It reads the weapon, so a sword build gets Garrote and a dagger main hand
gets Ambush with no edit. `equipped:Daggers` is true for a dagger in either hand: with a dagger
off hand only, change the last line to plain Garrote.

### `Sap`: untested

```
#showtooltip Sap
/cast [stealth,@mouseover,harm,nodead][stealth,harm,nodead] Pick Pocket
/cast [@mouseover,harm,nodead][harm,nodead] Sap
```

Saps the unit under the mouse, else the target, and picks its pocket first. Mouseover means the
kill target stays selected.

### `Pockets` (farming): untested

```
#showtooltip Pick Pocket
/cast [stealth,@mouseover,harm,nodead][stealth,harm,nodead] Pick Pocket
```

Walk through a camp in stealth and press it on each mob under the mouse.

## Rotation

### `Strike` (Sinister Strike): untested

```
#showtooltip Sinister Strike
/stopmacro [stealth]
/targetenemy [noharm][dead]
/cast Sinister Strike
```

The builder key. With no live enemy targeted it takes the nearest one. In
stealth it does nothing, so a stray press cannot break stealth before the opener.

Riposte and Shank stay on their own buttons, straight from the spellbook. Folding them in ahead
of Sinister Strike works, but every press while they are not ready raises an error, and an error
should mean something is wrong.

To watch in the first test: that `/targetenemy` does not pick a sapped mob. If it does, delete
that line.

### `ColdEvis` (Cold Blood into Eviscerate): untested

```
#showtooltip Eviscerate
/cast [known:Cold Blood] Cold Blood
/cast Eviscerate
```

Cold Blood is off the global cooldown, so both land on one press. Without the talent it is a
plain Eviscerate. Pressed while Cold Blood is on cooldown it still Eviscerates, with a "not
ready" error: use plain Eviscerate then, and this key only when Cold Blood is up.

### `Burst` (trinkets, Blade Flurry, Adrenaline Rush): untested

```
#showtooltip Adrenaline Rush
/use 13
/use 14
/cast [known:Blade Flurry] Blade Flurry
/cast [known:Adrenaline Rush] Adrenaline Rush
```

Press twice if Blade Flurry takes the global cooldown: the first press starts it, the second
starts Adrenaline Rush. That second press errors on the Blade Flurry line and on any trinket
already used; it is the cost of one burst key.

### `FlurryOff` (cancel Blade Flurry): untested

```
#showtooltip Blade Flurry
/cancelaura Blade Flurry
```

Drops the buff before a Sap, Gouge or Blind nearby would be broken by the second hit.

## Control

### `Kick` (mouseover, else target): untested

```
#showtooltip Kick
/cast [@mouseover,harm,nodead][harm,nodead] Kick
```

### `FocusKick`: untested

```
#showtooltip Kick
/cast [@focus,harm,nodead] Kick
```

Set a focus with `/focus` on the caster you want to watch.

### `Gouge`: untested

```
#showtooltip Gouge
/cast [@mouseover,harm,nodead][harm,nodead] Gouge
```

Gouges the unit under the mouse, else the target.

### `Blind`: untested

```
#showtooltip Blind
/cast [@mouseover,harm,nodead][harm,nodead] Blind
```

Blinds the unit under the mouse, else the target. Needs Blinding Powder.

### `Distract` (at the cursor, no targeting circle): untested

```
#showtooltip Distract
/cast [@cursor] Distract
```

## Movement and escapes

### `Run` (Sprint and Gouge on one press): untested

```
#showtooltip Sprint
/cast Sprint
/cast [harm,nodead] Gouge
```

Sprint is off the global cooldown, so the Gouge goes out with it. The target has to be facing
you for Gouge.

## Poisons

### `PoisonMH` (main hand): untested

```
#showtooltip
/use Instant Poison
/use 16
/click StaticPopup1Button1
```

### `PoisonOH` (off hand): untested

```
#showtooltip
/use Deadly Poison
/use 17
/click StaticPopup1Button1
```

Edit the item name in each to the exact rank in the bags (`Instant Poison VI`). The last line
answers the "replace the current poison?" box.

Best effort, the least certain macros here: they assume a poison is applied by using it and then
the weapon slot, and the `/click` runs before the box exists, so replacing a poison takes a
second click (the first opens the box, the second answers it). If the box never closes, click it
by hand and delete the last line.

## Auto-attack: no `/startattack`, no `/stopattack`

**The rule:** no macro uses `/startattack` or `/stopattack` unless you want one for a named
reason. Assume Forever's auto-attack does the right thing by itself. The old Classic habit of
adding these lines can fight the new behaviour, so do not add them "to be safe".

**Seen in play:** auto-attack carries on when switching target, and Gouge stops it without
breaking.

**Known from the client and guides:**

- A Forever rogue PvP guide (Mobalytics) says Blind, Gouge and Sap switch auto-attack off by
  themselves.
- Changing target keeps auto-attack going on the new enemy. That is the CVar
  `stopAutoAttackOnTargetChange`, default `0`. It has no checkbox in the options, only
  `/console`. `assistAttack` (start attacking after `/assist`) defaults to `0`.
- Auto-attacks only ever apply to the current target (`SwingTimerDocumentation.lua`).
- What Forever did change is ranged: a hunter-only "Auto Attack/Auto Shot" option
  (`autoRangedCombat`), and a built-in swing timer (`showSwingTimer`, under Advanced Options).
- Blizzard's beta development notes (builds of 2026-09-24 to 2026-10-16, first part read) have
  no line about melee auto-attack. The written source for the melee change is still missing;
  the rule above rests on what was seen in play, not on a note.

**Still open, to note here when seen:** whether a strike pressed with no energy starts the
swing, and whether the attack comes back by itself after a Gouge or Blind ends.

## Settings these lean on

| CVar | Value | Why |
|---|---|---|
| `autoLootDefault` | `1` | Pick Pocket loot is taken without a window |
| `autoDismount`, `autoStand` | `1` (default) | An ability press gets you off the mount or the floor |

## Log

- First set written. Nothing tested in game yet; add a dated line here as each macro is pressed.
