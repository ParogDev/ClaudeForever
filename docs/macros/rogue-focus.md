# Rogue focus: when to use it and why (WoW: Forever 1.60.1)

This is the reasoning that comes before the macros. It starts from what known PvP rogues actually
bind, works out why, and turns that into rules for the example set. The macros themselves live in
[rogue-combat.md](rogue-combat.md) and follow its house rules. Researched in November 2026, shortly
after launch; nothing here has been pressed in game yet.

## What the known rogues bind

| Who | Where | Focus macros | What they bind instead |
|---|---|---|---|
| Perplexity, long-time Classic PvP rogue and Twitch streamer, author of the [Mobalytics Forever rogue PvP guide](https://mobalytics.gg/wow-forever/classes/rogue-pvp-guide) | Forever: world PvP and battlegrounds | **None** | A "spammable Sap" that targets the nearest enemy player; Vanish + Premeditation + Cheap Shot on one key; Stealth + Sap; a bare `/stopattack`; `/startattack` builders with `/cancelaura Goblin Mortar` |
| Mirlol, Swedish arena rogue ([mirlol.pro/macros](https://mirlol.pro/macros)) | TBC Classic arenas | Twelve: Blind, Gouge, Kick, Sap, Shiv, Cheap Shot, Kidney Shot, Throw, Deadly Throw, Shadowstep, Feint, plus `/focus arena1-3` | The same combo keys as Perplexity (Vanish + Premed + Cheap, nearest-target Sap, Stopattack + Stealth) |
| Pikaboo, multi-time rank one rogue ([his old macro paste](https://pastebin.com/YtCFpmx0)) | Retail arenas, about 2013 | `[target=focus] Sap` and other focus casts (seen in a search summary, paste not read in full) | |
| Skill-Capped's [Forever Subtlety macros](https://www.skill-capped.com/wowarticles/forever/guides/subtlety-rogue-pvp-guide/macros/) | Forever | Blind, Kick, Kidney Shot, Sap, Gouge | A nearest-enemy Sap |

The guide sites (wowcalc, foreverdb, RankedBoost) copy the arena pattern and add fallbacks or
modifier branches. None of them say they tested anything, and two say outright that they did not.

The split matters more than any single macro. **The arena rogues focus everything. The one known
rogue writing for Forever focuses nothing.** Both are right for their game.

## Why the split exists

Focus does one thing: it lets a spell land on a second enemy while the first stays your target.
Whether that is worth a keybind depends on three costs.

1. **Setting the focus costs a press and your attention.** In an arena the enemies are fixed and
   numbered, so `/focus arena2` is one key at the gates and you never think about it again.
   **Forever has no arenas.** PvP is battlegrounds (Warsong Gulch, Arathi Basin, the 15v15
   Darkspear Islands) and the open world, where the second enemy is whoever walked up. Setting a
   focus there is a press you make mid-fight, on someone who may be dead or gone in ten seconds.
2. **The focus has to be worth coming back to.** Mirlol focuses the healer because the healer
   stays for the whole game. In a world fight the second enemy is usually one Blind's worth of
   problem, and the mouse is already on them.
3. **What your target is holding.** Rogues used to need focus because combo points sat on the
   target: retargeting to Blind the healer meant your points were stuck on the old target. One
   search summary claims Forever keeps combo points across a target change. Perplexity's guide
   reads the other way (Slice and Dice to spend points "when we're changing target"). **Not
   settled; check it in game** (see "Open questions").

So Perplexity's set is not a beginner's set missing focus. In the Forever fights it targets, the
target swap is cheap and the focus setup is not. His one "multi-target" tool, the nearest-enemy
Sap, exists to *find* a stealthed rogue or druid, not to hold one.

## What carries over from the arena school

Focus still earns its key in Forever when the second enemy **stays for the fight and you can't
keep them under the mouse**:

- **A battleground healer or flag-carrier peeler** in a fight that will last more than one
  control window: the WSG flag room, a base fight in Arathi Basin or Darkspear Islands.
- **A pre-fight Sap.** Sap no longer breaks Stealth in Forever (lfcarry, RankedBoost), so you can
  Sap the healer and open on the kill target. Focus the healer first, then the focus frame tells you exactly when the Sap
  is about to end.
- **Watching a cast you cannot see.** The focus frame shows the focus's cast bar. Perplexity calls
  PvP "an information based game"; the cast bar is the real reason to keep a focus, more than the
  macros.

## Forever changes that shape the decision

From Perplexity's guide unless noted. Each is one guide's word, not yet checked in game or against
the client's spell data, so the order of rules 1 and 2 below may move once they are:

- **Kick is on the global cooldown and costs 25 energy.** A focus Kick is not a free reflex. It
  costs a global and energy out of your kill window, so plan it before a Backstab or Mutilate,
  not after.
- **Blind has no diminishing returns, not even with itself.** With Dirty Tricks it costs 15
  energy. It is the best spell to put on a focus, because using it on the second enemy never
  shortens anything you will need on the kill target.
- **Sap and Gouge share the incapacitate DR** with each other, with Polymorph and with Freezing
  Trap. A focus Gouge on the healer half-lengthens a teammate's later Polymorph on them. Gouge
  the focus only when you mean it.
- **Cheap Shot and Kidney Shot are separate stun DRs.** DR windows last 15 to 20 seconds, random
  each time, and run 50%, 25%, then immune. A DR tracker addon is on Perplexity's mandatory list.
- **Preparation resets Kick, Blind, Vanish and Stealth**, so a second Blind on the focus is
  possible.
- **Sap flags you for PvP against a flagged target** (since the 24 September build, per
  wowforevertierlist). A focus Sap in a contested zone starts a fight.
- **Damage breaks Blind, Sap and Gouge**, including your own auto-attack and Blade Flurry. Blind,
  Gouge and Sap turn auto-attack off by themselves (play so far matches this), so a CC cast
  straight on a focus will not be broken by your own swing.

## Rules for this set

1. **Focus a unit, not a habit.** Set one only when a second enemy will matter for more than one
   control window and will not stay under the mouse. Otherwise use the mouseover macros already in
   [rogue-combat.md](rogue-combat.md) (Kick, Gouge, Blind, Sap).
2. **Blind is the focus spell.** No DR, 15 energy, and it is the one press you will most often
   want on someone who isn't your target. Kick is second, Sap third (pre-fight only).
3. **No fallback in a focus cast macro, and no `harm,nodead` either.** Use the bare form Mirlol
   (`/cast [target=focus] Blind`) and Skill-Capped (`/cast [@focus] Blind`) bind. The guide-site
   form `[@focus,harm,nodead][]` turns a forgotten focus into a Blind spent on your kill target:
   a lost kill window and a wasted cooldown. Dropping only the `[]` is not enough:
   `[@focus,harm,nodead]` with no focus matches no clause and does nothing, silently. The bare
   `[@focus]` always tries the cast, so with no focus or a dead one the game should raise its own
   error, which keeps the house rule that no macro hides errors (to confirm in game). This is
   also one macro, one job.
4. **Setting the focus is its own key.** One press, mouseover first, else target.
5. **No focus Cheap Shot or Kidney Shot yet.** They need combo points or Stealth on the right
   unit, which is exactly the open question above. Revisit once that is tested.
6. **Kick the heal or the control cast, not the damage cast.** wowforevertierlist puts it as
   "Kick the heal, not the shock" for shamans, and holds Kick on a mage for Polymorph and on a
   warlock for Fear. With Kick on the GCD, a Kick on the wrong spell costs twice.

## PvE

Focus is more useful in dungeons than in the world, because the units stay put and the fight is
planned:

- **Before a pull, Sap from Stealth and focus the mob you Sapped.** You can't re-Sap in combat. The focus frame shows
  when Sap is about to end, so you know when it is coming.
- **Focus the dangerous caster** (healer or fear caster) and Kick it from the focus while you hit
  the tank's target.
- **Blind the runner.** A fleeing mob brings friends; a focus Blind stops it without dropping the
  kill target.
- With a Sapped or Blinded focus nearby, **drop Blade Flurry** (`FlurryOff`) before the second hit
  breaks it.

## Proposed macros (untested)

These follow the house rules. `FocusKick` already exists in
[rogue-combat.md](rogue-combat.md#focuskick-untested) as `[@focus,harm,nodead]`; under rule 3 it
would become `/cast [@focus] Kick`. The rest would be added there once agreed.

### `SetFocus`

```
/focus [@mouseover,harm,nodead][harm,nodead]
```

Focuses the enemy under the mouse, else the target. Both branches do the same job, so this is
still one macro, one job, and unlike a focus cast a fallback here costs nothing: the worst case
is a focus on the wrong enemy, fixed by pressing again. With no enemy under the mouse or
targeted, no clause matches and the focus stays as it was (to confirm; `/clearfocus` is the
plain command if it needs clearing).

### `FocusBlind`

```
#showtooltip Blind
/cast [@focus] Blind
```

Needs Blinding Powder, like the plain spell. With none in the bags the cast fails with the game's
reagent error.

### `FocusSap`

```
#showtooltip Sap
/cast [@focus] Sap
```

Stealth stays the plain key, per the house rules. Whether Forever still needs Stealth for Sap is
an open question (below): if it does, this errors out of Stealth.

### `FocusGouge`

```
#showtooltip Gouge
/cast [@focus] Gouge
```

Melee and facing like a normal Gouge. It shares DR with Sap and Polymorph (rule above), so it is
the least-used of the four.

## Where Perplexity and the house rules disagree

His set breaks three of the house rules. Each one has a reason, so you decide, not this
page:

| His macro | His reason | House rule |
|---|---|---|
| `/stopattack` on its own key | Stop swinging into a teammate's Polymorph or Fear, and stop proccing a mage's Frostbite | No `/stopattack` unless asked for by name |
| Stealth + Sap on one key | Sap lands between DoT ticks that would knock you out of Stealth again | Stealth is never in a macro |
| `/startattack` builders | Builders start the swing from range | No `/startattack` |

His Vanish + Premeditation + Cheap Shot key needs no rule change. Vanish and Premeditation are off
the global cooldown, so one press lands the Cheap Shot with five points ready for Kidney Shot. It
has one job and would fit this set as is.

## Open questions to settle in game

- Do combo points stay on the old target when you switch target? If yes, focus Kidney Shot and
  Cheap Shot become worth binding. If no, Slice and Dice before a swap is the habit.
- Does a focus Sap work at all with Stealth held on the plain key, or does Forever still require
  Stealth even though the tooltip dropped "Must be stealthed" (foreverdb)?
- With no focus set, does `/cast [@focus] Blind` raise an error (as rule 3 expects), and does
  `SetFocus` with nothing under the mouse leave the old focus alone?
- Does the default UI show the focus cast bar without an addon? It should, since this is the
  Mainline UI.

## Sources

- Perplexity, [Rogue PvP guide](https://mobalytics.gg/wow-forever/classes/rogue-pvp-guide) (Mobalytics, Forever, 4 November 2026)
- Mirlol, [Rogue PvP macros](https://mirlol.pro/macros) (TBC Classic)
- [Pikaboo rogue macros](https://pastebin.com/YtCFpmx0) (old retail paste)
- Skill-Capped, [Forever Subtlety macros](https://www.skill-capped.com/wowarticles/forever/guides/subtlety-rogue-pvp-guide/macros/)
- [wowforevertierlist rogue PvP](https://wowforevertierlist.com/classes/rogue/pvp), [lfcarry rogue PvP](https://lfcarry.com/guides/wow-forever-rogue-pvp)
- [wowcalc](https://wowcalc.net/en/forever/wiki/macros/rogue), [foreverdb](https://foreverdb.net/macros/rogue), [RankedBoost](https://rankedboost.com/world-of-warcraft/forever/macros/rogue/) rogue macro pages
- [Icy Veins Forever PvP overview](https://www.icy-veins.com/wow-forever/pvp-overview) (no arenas)
- Client: `/focus` and `FocusUnit` are in `vendor/BlizzardInterfaceResources` (`GlobalStrings/enUS.lua`, `GlobalAPI.lua`)
