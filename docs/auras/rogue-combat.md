# Rogue Combat auras (ForeverAuras, Forever 1.60.1)

One group, **Rogue Combat**, built from `auras/rogue-combat/rogue-combat.lua`. Offensive bar on top,
defensive bar below, every icon in a fixed slot so the eye learns where to look. Nothing is
shown out of combat except an active buff and your combo points. What the API allows and why each
trigger was chosen: `docs/foreverauras.md`.

This is a worked example: one player's set, shared so you can read how each trigger was chosen and
change it to fit your own screen and spec.

**v2 "Brackets" replaced the layout below.** The source now follows
`docs/auras/rogue-combat-v2-design.md`: energy gauge left of the character, combo points and
Slice and Dice right, procs at the top ends, escapes and control at the bottom ends, running buffs
as icons in their ability's slot, Feint and Blind dropped. The layout and offensive/defensive
sections further down describe v1 and are kept for the reasoning behind each trigger. v2 imports
over v1 and works in game. Not yet checked one by one: the health-driven alpha on the escapes, the
numbers under the vertical bars, the swipe direction on running-buff icons, and the Slice and Dice
Missing flash (spec risks 1, 2, 4, 6).

**v1 in game.** Hidden out of combat: yes. Slice and Dice bar: good. Riposte overlapped its
neighbours (its proc glow and a second, built-in countdown number), fixed by moving it to its own
slot above the proc row and hiding the cooldown frame's numbers. Still to check: energy colours,
Shank, the Riposte window length.

## Layout

```
                                  [ RIPOSTE 3.2 ]                                     own slot above, so its glow covers nothing
            [Cold Blood] [Shank]                   [Blade Flurry] [Adrenaline Rush]     procs: shown only when ready
            [================ ENERGY  62 ================]                           yellow / grey-blue / orange
            [====|====|====|====|====]                                                combo points, gold at 5
            [Slice and Dice ======================== 11.4]                            red text + red outline under 3 s
            [Blade Flurry ============ 9.0]                                           only while up
            [Adrenaline Rush ========= 7.1]

  [Evasion][Sprint][Vanish][Feint]  [Kick][Gouge][Kidney][Blind]                     in combat only
                 [Evasion ======= 8.2]                                                only while up
                 [Sprint ======== 12.0]
```

The group sits 150 px below screen centre (`yOffset = -150`): offense is just under your
character, defense below that. Move it with the group in `/fa`; the children keep their slots.

## Offensive bar

| Display | Shows | Reads | Why this source |
|---|---|---|---|
| **Riposte** (big, centre, glowing) | Only while Riposte is usable after a parry, with a countdown swipe and the seconds left | Custom trigger on `C_Spell.IsSpellUsable(14251)` + own `GetTime()` clock | Riposte leaves no buff, and usability is never secret, so the clock works in combat. The window length is **learned**: when a window ends without your Riposte cast, its real length is saved (`aura_env.saved.window`, persisted by FA). Starts at 5 s (Classic value; Forever's is undocumented) |
| **Shank** | When off cooldown. Blue tint: not enough energy. Red tint: out of range | `Cooldown Progress (Spell)` on 1329283, `showOnReady` | Shank is a 10 s cooldown on Forever (8 s with Flash of Steel), not a proc. Using it on cooldown is the rotation, so it blinks in and out by design |
| **Cold Blood**, **Blade Flurry**, **Adrenaline Rush** | When ready | Same, `showOnReady`, load only if the talent is known | A burst cooldown that is ready is a decision; one that is cooling down is not, so it stays hidden |
| **Energy** | Bar + number. **Yellow**: Sinister Strike is affordable. **Grey-blue**: not yet. **Orange** at 90+: you are about to waste regen | Power trigger (energy) + Sinister Strike's `insufficientResources` | The "affordable" flag comes from the game's own usability check, so it is right for every rank and for Efficient Strikes, and it is never secret. The 90+ step is a Condition, which FA runs through a colour curve so it works on secret energy |
| **Combo points** | 5-segment bar, red, **gold at 5** | Power trigger (combo points), filtered `>= 1` | Combo-point filters work in combat (`PowerFilterable`). Hidden at 0 |
| **Slice and Dice** | Duration bar. Under 3 s: red time text and a red outline | Aura (Modern) on 5171/6774 | Buff durations are secret in combat; Aura (Modern) draws them through Blizzard's own frames. Remaining time may only drive a text colour or a glow, so the warning is those two, not the bar colour |
| **NO SLICE AND DICE** | Dark red slot, in combat, when the buff is missing | Aura (Modern), `showOnMissing` | Same slot as the bar, so it is either one or the other |
| **Blade Flurry**, **Adrenaline Rush** bars | While up | Aura (Modern) | |

## Defensive bar

Eight icons in combat: Evasion, Sprint, Vanish, Feint, then Kick, Gouge, Kidney Shot and Blind.

- **Bright** means ready. **Grey with a swipe** means cooling down.
- **Blue** means not enough energy. **Red** means the target is out of range (targeted abilities only).
- Below the row, bars for Evasion and Sprint while they are up.

Cooldown swipes use the secret-safe duration object, so they draw in combat.

## Left out on purpose, and why

- **Kick glow on an interruptible cast.** Target cast info is secret for any unit that is not you.
  The Blizzard target frame's castbar already shows it.
- **Low-health glow on Evasion.** A glow cannot follow secret health. Only colour and alpha can,
  and colour already means "energy" and "range" on that icon.
- **Energy tick timer.** Forever's regen is documented as "10/s", not its tick size. Add one once
  ticks are seen in game.
- **Hack and Slash extra attacks, Relentless Strikes and Seal Fate.** They leave no aura, and the
  combat log is gone.
- **Expose Armor, poisons.** Long timers that change no moment-to-moment decision. Easy to add
  later as Aura (Modern) bars.

## Install

1. `python tools/foreverauras/fa.py encode auras/rogue-combat/rogue-combat.lua -o auras/rogue-combat/rogue-combat.txt`
2. In game: `/fa`, then Import, and paste the string from `rogue-combat.txt`. Or, with the game
   closed, run `fa.py install` (see `tools/foreverauras/README.md`).
3. Re-importing updates the installed group in place: the uids are fixed.

After changing it in the `/fa` editor, `fa.py pull --group "Rogue Combat"` brings the edit back to
the source file, so the repo and the game stay one thing.

## First in-game check

Go through these in order, and note each result here with the date.

1. Import: no error, and 21 children under Rogue Combat.
2. Out of combat: only combo points (if any) and active buffs show.
3. Hit a mob. You should see energy, combo segments, the defensive row, and NO SLICE AND DICE.
4. Energy should turn grey-blue right after a Sinister Strike, and yellow once you can afford the
   next one.
5. Cast Slice and Dice: the bar should replace the red slot, and its text should turn red under 3 s.
6. Get parried (fight a humanoid face-on). Riposte should pop with a countdown. Let one window
   run out. Chat should print "Rogue Combat: Riposte window measured at X s" when the measured
   window differs from the one in use. Put X here and in `docs/foreverauras.md`.
7. Shank should blink in after each use, about every 10 s.
8. `/dump C_Secrets.GetPowerTypeSecrecy(Enum.PowerType.Energy)` and `(...ComboPoints)`: put both
   numbers into `docs/foreverauras.md`.
9. `/fa`: does any display show a warning triangle? Copy its text here.
