# Rogue Combat v2: design spec (ForeverAuras 1.4.3, Forever 1.60.1)

Spec for the second version of the combat-rogue HUD. v1 is `auras/rogue-combat/rogue-combat.lua`
and `docs/auras/rogue-combat.md`; what an aura may read in combat is `docs/foreverauras.md`.
The source in `auras/rogue-combat/` now follows this spec; it is kept as the design record, so you can
see why each element sits where it does before you move it for your own screen.

## Direction

**Brackets.** The HUD stops being a stack in front of the character and becomes two slim vertical
gauges standing either side of it, with small icon groups at their four ends. The column the
character, the target and the floating damage numbers live in stays empty.

- **Left is fuel and strikes** (energy, Shank, Riposte). **Right is tempo** (combo points, Slice
  and Dice, burst). Offence sits at the top ends, defence and control at the bottom ends.
- **One slot per ability, and the slot changes state.** Ready, running and cooling down are the
  same place on screen. v1's four text bars for running buffs are gone.
- **Colour only where it means something.** Six colours, one meaning each (below). Everything else
  is a spell icon, a dark track or a bone-white number.
- **One thing moves at a time.** Only Riposte, a missing Slice and Dice and a Slice and Dice under
  3 s animate. Nothing else pulses, slides or bounces.

## What was wrong with v1

Measured on a 1080p combat screenshot:

- v1's group centre is 150 below screen centre. Its 240-wide stack covered the space right under
  the character, the proc row sat on its feet, and the defensive row sat where incoming damage
  numbers scroll.
- Contrast: v1's "cannot afford" energy fill, a grey-blue at (0.35, 0.4, 0.55) on a 55 % black
  track, reads as "mostly dark". v2 uses a lighter slate on a darker track.

**Duplicate energy and combo points.** If another addon (or the game's "Personal Resource
Display") already draws energy and combo points above the character, v2 duplicates them. v2's
energy bar carries the "affordable" colour and its pips the "5 = spend" colour, which a plain
resource bar does not; turn the other display off if you keep this one. `/fstack` over an unknown
number on screen tells you which addon draws it.

## Layout map

Offsets are from screen centre at 1080p, +x right, +y up, the way FA stores `xOffset`/`yOffset`.
The character is taken to stand at about (0, -20). The group `Rogue Combat` moves to
`xOffset = 0, yOffset = 0` (v1: -150); every child offset below is relative to the group, so
dragging the group moves the whole HUD.

```
 y
+120                                (target nameplate, not ours)
        ┌────────┐
 +90    │RIPOSTE │                                              STRIKE NOW (left top)
        └────────┘                                              BURST (right top)
 +55  ┌──────┐ ▮                         ▯ ▮ ┌────┐┌────┐┌────┐
 +37  │Shank │ ▮                         ▯ ▮ │ BF ││ AR ││ CB │
      └──────┘ ▮                         ▯ ▮ └────┘└────┘└────┘
               ▮                         ▯ ▮
 -20           ▮       character         ▯ ▮
               ▮       kept clear        ▯ ▮
               ▮                         ▯ ▮
 -81 ┌──┐┌──┐┌──┐▮                       ▯ ▮┌──┐┌──┐┌──┐
     │Sp││Va││Ev│▮                       ▯ ▮│Ki││Go││KS│      ESCAPE (left bottom)
 -95 └──┘└──┘└──┘                                └──┘└──┘└──┘   CONTROL (right bottom)
-110             62                         14.2
                energy                 pips  Slice and Dice

 x  -228 -196 -164 -134                 +117 +134 +164 +196 +228
```

| Zone | Box (x from..to, y from..to) | Holds |
|---|---|---|
| Left gauge | -141..-127, -95..+55 | Energy bar, number under it |
| Right gauge | +112..+141, -95..+55 | Combo pips (inner), Slice and Dice bar (outer), time under it |
| Strike now | -184..-132, +19..+114 | Shank, Riposte above it |
| Burst | +150..+248, +25..+55 | Blade Flurry, Adrenaline Rush, Cold Blood |
| Escape | -242..-150, -95..-67 | Evasion, Vanish, Sprint |
| Control | +150..+242, -95..-67 | Kick, Gouge, Kidney Shot |
| Kept empty | -126..+111, all y; and everything below y -120 | Character, target, damage numbers |

Total footprint 490 x 240, hollow. Drawn area is about a third of v1's.

## Colour and type

| Name | Hex | RGBA (0-1) | Means |
|---|---|---|---|
| Brass | `#F5C84B` | 0.96, 0.78, 0.29, 1 | Energy, and Sinister Strike is affordable |
| Slate | `#7383AD` | 0.45, 0.51, 0.68, 1 | Energy, Sinister Strike not affordable |
| Ember | `#FF7A1A` | 1, 0.48, 0.10, 1 | Capped, spend now: energy at 90+, five combo points |
| Bone | `#EFE7D2` | 0.94, 0.91, 0.82, 1 | Counters and every number |
| Jade | `#45D6A8` | 0.27, 0.84, 0.66, 1 | A buff of yours is running (Slice and Dice fill, edge of a running-buff icon) |
| Alarm | `#FF4338` | 1, 0.26, 0.22, 1 | Upkeep broken or about to break (no Slice and Dice, under 3 s) |
| Ink (track) | `#000000` 62 % | 0, 0, 0, 0.62 | Bar background |
| Ink (edge) | `#000000` 90 % | 0, 0, 0, 0.9 | 1 px border on bars, pips, icons |
| Socket | `#000000` 55 % | 0, 0, 0, 0.55 | Unlit combo pip |

Icon tints stay v1's, because they multiply the icon art: short on energy `#738CFF`
(0.45, 0.55, 1, 1), out of range `#FF5959` (1, 0.35, 0.35, 1).

Type is one face, the one FA bundles: **Fira Sans Condensed Black** (`text_font = "Fira Sans
Condensed Black"`), flag `OUTLINE`, always Bone unless a condition says otherwise. Sizes: 24
(Riposte seconds), 18 (energy, Slice and Dice time), 13 (seconds on a running-buff icon). No
labels anywhere: v1's "Slice and Dice", "Sprint", "Evasion" words are replaced by position and by
the spell's own icon. This also removes the v1 Sprint bar's unreadable text (0.1 grey on a dark
bar) at the root.

Bar texture is the flat `Clean` statusbar, no spark. Icons use `zoom = 0.3` (crops the painted
frame of the Blizzard icon) with a 1 px Ink edge.

## Elements

"Trigger" names are from the table in `docs/foreverauras.md`. Every display keeps
`internalVersion = 91`, a fixed `uid`, `parent = "Rogue Combat"`, and loads only if its spell is
known. Unless a row says otherwise there is no animation.

### Left gauge

**RC Energy** (changed)
- Region `aurabar`, 14 x 150, at (-134, -20). `orientation = "VERTICAL"` (fills bottom to top),
  `texture = "Clean"`, `spark = false`, `backgroundColor` Ink track, `barColor` Brass.
- Sub-regions: `subforeground`, `subbackground`; `subborder` (edge "Square Full White", size 1,
  offset 1, Ink edge); `subtext` `%p`, 18, anchored `BOTTOM` with `anchorYOffset = -4` so the
  number hangs under the bar at about y -110.
- Triggers: unchanged from v1. 1 = `unit`/`Power` energy, 2 = `spell`/`Cooldown Progress (Spell)`
  on Sinister Strike (`showAlways`) for its never-secret `insufficientResources`.
- States (conditions, later wins): default Brass; trigger 2 `insufficientResources == 1` → Slate;
  trigger 1 `power >= 90` → Ember (a Power condition, so it runs through a colour curve).
- Shows: in combat.

### Strike now (left top)

**RC Shank** (changed)
- Region `icon`, 36 x 36, at (-166, +37). `zoom = 0.3`, `cooldown = true`, `cooldownSwipe = true`,
  `cooldownTextDisabled = true`. `subborder` 1 px Ink edge.
- Trigger: `Cooldown Progress (Spell)` 1329283, **`showAlways`** (v1: `showOnReady`).
- States: ready = full colour. Cooling down = `desaturate` + swipe (`onCooldown == 1`). Short on
  energy = blue tint (`insufficientResources == 1`). Out of range = red tint (`spellInRange == 0`).
- Shows: in combat. Why always: Shank is pressed every 10 s, so in v1 it blinked in and out for
  the whole fight. A swipe you can see coming is calmer than a pop.

**RC Riposte** (moved, restyled)
- Region `icon`, 48 x 48, at (-156, +90). `zoom = 0.3`, swipe on, `cooldownEdge = true`,
  `inverse = false`, `cooldownTextDisabled = true`.
- Sub-regions: `subtext` `%p`, 24, centre; `subglow` on, `glowType = "Pixel"`, `useGlowColor`,
  `glowColor` Brass, `glowLines = 8`, `glowLength = 10`, `glowThickness = 2`, `glowFrequency = 0.25`;
  `subborder` 1 px Ink edge.
- Trigger: v1's custom clock, unchanged (usable window after a parry on `C_Spell.IsSpellUsable`,
  learned length).
- Shows: only during the window, in or out of combat. Animation: start preset `shrink` (FA labels
  it "Grow": it pops up from small, 0.25 s), finish preset `fade`.
- Why here and why Pixel: it is the largest thing in the HUD and the only one with motion, 160
  left of the character at head height. The Pixel glow runs along the icon's own edge, so it
  cannot spill onto a neighbour the way v1's action-button glow did, and nothing is within 11 px
  of it anyway.

### Right gauge

**RC Combo 1 .. RC Combo 5** (replace v1's `RC Combo Points` bar)
- Region `texture`, 10 x 26 each, `texture` = FA's `Media\Textures\Square_FullWhite`, at x +117,
  y -82, -51, -20, +11, +42 (pip 1 at the bottom, 5 px gaps, same 150 span as the bars).
  `subborder` 1 px Ink edge. `color` Socket by default.
- Trigger: `unit`/`Power`, `powertype = 4`, no filter. Combo points are never secret.
- States for pip n: `power >= n` → Bone; `power >= 5` → Ember (all five turn together).
- Shows: in combat (load condition). Empty sockets stay visible so the count has a frame.
- Why next to Slice and Dice and not next to energy: the finisher decision is "how many points,
  and how long has the buff left". Those two are now one glance. Energy and Shank are the builder
  decision and sit together on the other side.

**RC Slice and Dice** (changed)
- Region `aurabar`, 14 x 150, at (+134, -20), `orientation = "VERTICAL"`, `texture = "Clean"`,
  `barColor` Jade, Ink track, `subborder` as RC Energy.
- Sub-regions: `subtext` `%p`, 18, `BOTTOM`, `anchorYOffset = -4` (keep it at index 4 as in v1 if
  the condition path is reused); `subglow` off by default, `glowType = "Pixel"`, `glowColor` Alarm,
  `anchor_area = "bar"`.
- Trigger: `secretAura` on 5171/6774, `showOnActive` (unchanged).
- States: `faAuraRemaining < 3` → time text Alarm and the glow on. That is all a remaining-time
  condition may change, same as v1.
- Shows: whenever the buff is up, in or out of combat.

**RC Slice and Dice Missing** (changed) and **RC Slice and Dice Missing Icon** (new)
- Bar: `aurabar` 14 x 150 at (+134, -20), vertical, `barColor` alpha 0, `backgroundColor` Alarm at
  0.55. Trigger `secretAura` `showOnMissing`. Main animation preset `alphaPulse` (FA: "Flash").
- Icon: `icon` 26 x 26 at (+134, -113), where the time would be. Trigger `secretAura`
  `showOnMissing` (FA draws its static sample of the spell). Same `alphaPulse`. 1 px Ink edge.
- Shows: in combat while the buff is missing. v1's "NO SLICE AND DICE" words are dropped: a
  pulsing red slot with the spell's icon under it says the same in less room.

### Burst (right top)

**RC Blade Flurry Ready**, **RC Adrenaline Rush Ready**, **RC Cold Blood** (moved, resized)
- Region `icon`, 30 x 30, at (+165, +40), (+199, +40), (+233, +40). `zoom = 0.3`, 1 px Ink edge.
- Trigger: `Cooldown Progress (Spell)`, `showOnReady` (unchanged). Blade Flurry keeps its blue
  tint on `insufficientResources`.
- Shows: in combat, only while ready. Start animation preset `fade`.

**RC Blade Flurry**, **RC Adrenaline Rush** (were bars, now icons in the same slots)
- Region `icon`, 30 x 30, at the same positions as their Ready twins. Swipe on, `inverse = true`
  if the swipe should drain rather than fill (check in game), `cooldownTextDisabled = true`.
- Sub-regions: `subtext` `%p`, 13, centre; `subborder` size 2, Jade.
- Trigger: `secretAura` on 13877 / 13750, `showOnActive` (unchanged).
- Shows: while the buff is up, in or out of combat. The Ready twin hides when the cooldown
  starts, so the slot reads: bright = press, jade edge with seconds = running, empty = spent.

### Escape (left bottom)

**RC Evasion**, **RC Vanish**, **RC Sprint** (changed)
- Region `icon`, 28 x 28, at (-164, -81), (-196, -81), (-228, -81). `zoom = 0.3`, 1 px Ink edge.
- Triggers: 1 = `Cooldown Progress (Spell)`, **`showOnReady`** (v1: `showAlways`).
  2 = `unit`/`Health` on the player. `disjunctive = "all"`, so the icon shows exactly when the
  spell is ready.
- States: default alpha 1. Trigger 2 `percenthealth >= 50` → `alpha = 0.35`. So the escapes are
  faint while you are healthy and come to full strength when you drop under half. Health is
  secret in combat, but an alpha change from a Health condition is one of the two things FA runs
  through a curve.
- Shows: in combat while ready. A five-minute cooldown that is ticking is not a choice you have,
  so it is not drawn.
- If the alpha condition does not work on an icon in combat (see risks), fall back to a fixed
  alpha of 0.6.

**RC Evasion Active**, **RC Sprint Active** (were bars, now icons in the same slots)
- As the burst "running" icons: 28 x 28, `subborder` size 2 Jade, `subtext` `%p` 13, swipe.
  `secretAura`, `showOnActive`, same spell ids as v1. In or out of combat.

### Control (right bottom)

**RC Kick**, **RC Gouge**, **RC Kidney Shot** (moved, resized)
- Region `icon`, 28 x 28, at (+164, -81), (+196, -81), (+228, -81). `zoom = 0.3`, swipe on,
  `cooldownTextDisabled = true`, 1 px Ink edge.
- Trigger and conditions unchanged from v1: `showAlways`; `onCooldown` → desaturate;
  `insufficientResources` → blue tint; `spellInRange == 0` → red tint.
- Shows: in combat. These are short cooldowns you plan around, so the swipe stays visible.

## Dropped or merged from v1, and why

| v1 display | v2 | Why |
|---|---|---|
| `RC Combo Points` (one bar with ticks) | Five pip textures | Real gaps, empty sockets, and all five change colour together at 5 |
| `RC Blade Flurry`, `RC Adrenaline Rush` bars | Icons in the burst slots | A 240-wide labelled bar per buff was most of v1's bulk |
| `RC Evasion Active`, `RC Sprint Active` bars | Icons in the escape slots | Same; also ends the unreadable Sprint text |
| "NO SLICE AND DICE" text bar | Pulsing red slot + spell icon | No words in the HUD |
| `RC Feint` | Dropped | A threat tool. The HUD shows no threat, so it cannot say when Feint matters; the action bar has it |
| `RC Blind` | Dropped | Five-minute, deliberate, never a reflex |
| Combo points shown out of combat | In combat only | Sockets need a stable frame; leftover points on a dead target decide nothing |
| Bar labels, cooldown numbers on icons | Dropped | Position and icon identify; the swipe shows time |

Feint and Blind have natural fourth slots at (-260, -81) and (+260, -81) if they are missed.
Still left out for the reasons in `docs/auras/rogue-combat.md`: Kick glow on a cast, energy tick
timer, hit-proc tracking, poisons and Expose Armor.

## States

| State | What draws |
|---|---|
| Out of combat | Nothing. A running Slice and Dice, Sprint, Evasion, Blade Flurry or Adrenaline Rush still shows its own timer |
| In combat | Energy, pips, Slice and Dice, Shank, ready burst, faint escapes, control |
| Riposte window | Adds Riposte above the energy bar with the marching edge and seconds |
| Low Slice and Dice | Time turns Alarm, Alarm edge marches round the bar; at 5 points the pips are Ember beside it |
| No Slice and Dice | Bar slot pulses Alarm, spell icon under it |
| Evasion + Sprint up, hurt | Escape slots at full alpha; the two running ones carry a Jade edge and seconds |
| Short on energy | Energy bar Slate; energy-gated icons tinted blue |

## Build notes

FA options this spec relies on, from the installed addon (`Interface\AddOns\ForeverAuras`):

| Option | Where |
|---|---|
| Icon defaults: `zoom`, `desaturate`, `color`, `inverse`, `cooldownSwipe`, `cooldownEdge`, `cooldownTextDisabled` | `RegionTypes/Icon.lua:20-44`, condition properties `:51-152` |
| Aurabar `orientation`, `texture`, `barColor`, `backgroundColor`, `spark` | `RegionTypes/AuraBar.lua:15-53`; orientation keys `Types.lua:2035-2040` (`VERTICAL` = bottom to top) |
| Vertical bars honoured for `secretAura` bars | `SecretAuraAppearance.lua:584-589` |
| Region `alpha` as a condition property | `RegionTypes/RegionPrototype.lua:19`, `:134-143`; added to icon, aurabar, texture at `Icon.lua:47`, `AuraBar.lua:56`, `Texture.lua:32` |
| Texture region `texture`, `color` | `RegionTypes/Texture.lua:13-30`, `:36-47` |
| `subborder`: `border_edge`, `border_size`, `border_offset`, `border_color` | `SubRegionTypes/Border.lua:14-27`; edge "Square Full White" `Types.lua:3348` |
| `subglow`: `glowType`, `glowLines`, `glowFrequency`, `glowLength`, `glowThickness`, `useGlowColor`, `glowColor`, `anchor_area` | `SubRegionTypes/Glow.lua:16-37`; types `Types.lua:4071-4078` (ACShine, Pixel, buttonOverlay, Proc) |
| `subtext`: `text_font`, `text_fontSize`, `text_fontType`, `anchor_point`, `anchorYOffset`, `text_selfPoint = "AUTO"` | `SubRegionTypes/SubText.lua:20-76`; plain points on a bar resolve at `RegionTypes/AuraBar.lua:1158-1200`, point names `Types.lua:1543-1553`; outside placement via the inverse self point `SubText.lua:655-673` |
| Font "Fira Sans Condensed Black", statusbar "Clean" | `Types.lua:3338`, `:3350` |
| Font flags (`OUTLINE`) | `Types.lua:1627-1636` |
| Animations: `animation.start/main/finish = { type = "preset", preset = ... }` | lookup `Animations.lua:214-215`; presets `Prototypes.lua:518` on; names `Types.lua:3064-3104` (start `fade`, `shrink`; main `alphaPulse`; finish `fade`) |
| Health and Power conditions change Alpha and Color in combat | `Prototypes.lua:2459` (status text), `percenthealth` with `secretCurve` `Prototypes.lua:3393`, power `:3890-3895`; combo points filterable `:2439` |
| `secretAura` conditions: what may change | `SecretAuraConditions.lua:10-23` (root and element properties), Missing sample `:55-61` |
| Sub-elements a `secretAura` display supports (border, text, glow, texture) | `SecretAuraAppearance.lua:132` |

Order of sub-regions matters for `sub.N.*` condition paths: after changing a display's
sub-region list, recount N.

## Open questions and risks for the build

1. **Vertical text under a `secretAura` bar.** The vertical fill is in the code; whether a
   `subtext` anchored `BOTTOM` (outside the bar) is placed the same on the native bar is not
   verified. Fallback: `INNER_BOTTOM`, or a separate `text` region.
2. **Health alpha on the escape icons.** `percenthealth` is marked `hidden` in the trigger
   prototype and the icon has a second trigger. Check in combat that the faint/full switch
   happens and that `disjunctive = "all"` hides the icon while cooling down. Fallback: fixed 0.6.
3. **Ready and Running twins sharing a slot.** For a frame both may show (cooldown event and aura
   event arrive apart). If Cold Blood's cooldown only starts when its buff is used, its Ready icon
   stays up while the buff is active: acceptable, but look.
4. **Swipe direction and edge on `secretAura` icons.** Pick `inverse` in game so a running buff
   drains. The 2 px Jade `subborder` is drawn by FA's native-button border code; confirm it sits
   outside the icon and not under the swipe.
5. **Pixel glow on a 14-wide vertical bar.** `glowLength = 10` may look busy on the short sides;
   try 6 lines.
6. **`alphaPulse` on a `secretAura` Missing sample.** The Missing look has its own alpha handling
   (`SecretAuraConditions.lua:63-71`). If the main animation fights it, drop the pulse and keep
   the red slot.
7. **A second resource display.** Find out what draws any other energy or combo display before
   hiding it (`/fstack`).
8. **Shank `showAlways`** changes how v1 behaved. If the swipe is noisier than the blink was,
   revert to `showOnReady`.
9. **Position is a guess from one screenshot.** Camera distance and UI scale change where the
   character stands. The group is the handle: if the brackets crowd large targets, widen by moving
   the left children -20 and the right children +20, or drop the group by 20 to 30.
10. **Feint and Blind are dropped.** Add them back if you use them; the fourth slots are reserved.
