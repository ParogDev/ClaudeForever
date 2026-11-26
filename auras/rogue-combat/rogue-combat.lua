-- Rogue Combat v2 "Brackets": ForeverAuras source (WoW Forever 1.60.1, ForeverAuras 1.4.3).
-- Build the import string: python tools/foreverauras/fa.py encode auras/rogue-combat/rogue-combat.lua
-- Design: docs/auras/rogue-combat-v2-design.md (spec), docs/auras/rogue-combat.md (page).
-- Two slim gauges either side of the character, icon groups at their four ends, the centre kept clear.
-- Offsets are from the group's centre; move the group, not the children.
-- uids are fixed so a re-import updates the installed copy instead of duplicating it.
--
-- Colours, one meaning each:
--   Brass  0.96 0.78 0.29  energy, Sinister Strike affordable
--   Slate  0.45 0.51 0.68  energy, not affordable
--   Ember  1.00 0.48 0.10  capped: energy 90+, five combo points
--   Bone   0.94 0.91 0.82  numbers, lit combo points
--   Jade   0.27 0.84 0.66  a buff of yours is running
--   Alarm  1.00 0.26 0.22  Slice and Dice missing or under 3 s
-- Icon tints (multiply the art): short on energy 0.45 0.55 1, out of range 1 0.35 0.35.
return {
  d = {
    id = "Rogue Combat",
    uid = "rcGroup0001",
    internalVersion = 91,
    regionType = "group",
    anchorPoint = "CENTER", selfPoint = "CENTER", anchorFrameType = "SCREEN",
    xOffset = 0, yOffset = 0,
    controlledChildren = {
      "RC Energy", "RC Shank", "RC Riposte",
      "RC Combo 1", "RC Combo 2", "RC Combo 3", "RC Combo 4", "RC Combo 5",
      "RC Slice and Dice", "RC Slice and Dice Missing", "RC Slice and Dice Missing Icon",
      "RC Blade Flurry Ready", "RC Adrenaline Rush Ready", "RC Cold Blood", "RC Blade Flurry", "RC Adrenaline Rush",
      "RC Evasion", "RC Vanish", "RC Sprint", "RC Evasion Active", "RC Sprint Active",
      "RC Kick", "RC Gouge", "RC Kidney Shot",
    },
    triggers = { { trigger = { type = "custom", custom_type = "status", check = "event", events = "", custom = "function() return false end" }, untrigger = {} } },
    load = {},
    conditions = {},
    information = { url = "", desc = "Combat rogue, v2 Brackets: energy gauge left of the character, combo points and Slice and Dice right, procs at the top ends, escapes and control at the bottom ends. Forever 1.60.1." },
  },
  c = {
    -- ============================================================ left gauge: energy (x -134)
    {
      id = "RC Energy", uid = "rcEnergy001", parent = "Rogue Combat", internalVersion = 91,
      regionType = "aurabar", width = 14, height = 150, xOffset = -134, yOffset = -20,
      orientation = "VERTICAL", texture = "Clean", spark = false, icon = false,
      barColor = { 0.96, 0.78, 0.29, 1 }, backgroundColor = { 0, 0, 0, 0.62 },
      triggers = {
        activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "unit", event = "Power", unit = "player", use_unit = true, use_powertype = true, powertype = 3 }, untrigger = {} },
        -- Sinister Strike's "not enough energy" flag: exact for its rank and Efficient Strikes, never secret.
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 1752, use_exact_spellName = false, genericShowOn = "showAlways", track = "auto" }, untrigger = {} },
      },
      load = { use_combat = true, use_spellknown = true, spellknown = 1752 },
      subRegions = {
        { type = "subforeground" }, { type = "subbackground" },
        { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } },
        { type = "subtext", text_text = "%p", text_font = "Fira Sans Condensed Black", text_fontSize = 18, text_fontType = "OUTLINE", text_color = { 0.94, 0.91, 0.82, 1 }, text_visible = true, anchor_point = "BOTTOM", text_selfPoint = "AUTO", anchorYOffset = -4, text_justify = "CENTER" },
      },
      conditions = {
        -- Order matters: a later match overrides an earlier one.
        { check = { trigger = 2, variable = "insufficientResources", op = "==", value = 1 }, changes = { { property = "barColor", value = { 0.45, 0.51, 0.68, 1 } } } },
        { check = { trigger = 1, variable = "power", op = ">=", value = "90" }, changes = { { property = "barColor", value = { 1, 0.48, 0.10, 1 } } } },
      },
    },
    -- ============================================================ strike now: left top
    {
      id = "RC Shank", uid = "rcShank0001", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 36, height = 36, xOffset = -166, yOffset = 37,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownSwipe = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        -- showAlways: pressed every 10 s, so a visible swipe is calmer than blinking in and out.
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 1329283, use_exact_spellName = false, genericShowOn = "showAlways", track = "auto" }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 1329283 },
      subRegions = {
        { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } },
      },
      conditions = {
        { check = { trigger = 1, variable = "onCooldown", op = "==", value = 1 }, changes = { { property = "desaturate", value = true } } },
        { check = { trigger = 1, variable = "insufficientResources", op = "==", value = 1 }, changes = { { property = "color", value = { 0.45, 0.55, 1, 1 } } } },
        { check = { trigger = 1, variable = "spellInRange", op = "==", value = 0 }, changes = { { property = "color", value = { 1, 0.35, 0.35, 1 } } } },
      },
    },
    {
      id = "RC Riposte", uid = "rcRiposte01", parent = "Rogue Combat", internalVersion = 91,
      -- The largest thing in the HUD and the only one that moves. Pixel glow runs on the icon's own
      -- edge, so it cannot spill onto a neighbour the way v1's action-button glow did.
      regionType = "icon", width = 48, height = 48, xOffset = -156, yOffset = 90,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownSwipe = true, cooldownEdge = true, inverse = false,
      -- Our big %p text is the countdown; the cooldown frame's own numbers would print a second one on top.
      cooldownTextDisabled = true,
      triggers = {
        activeTriggerMode = 1, disjunctive = "any",
        {
          trigger = {
            type = "custom", custom_type = "status", check = "event",
            events = "SPELL_UPDATE_USABLE, SPELL_UPDATE_COOLDOWN, ACTIONBAR_UPDATE_USABLE, UNIT_COMBAT:player, UNIT_SPELLCAST_SUCCEEDED:player, PLAYER_REGEN_ENABLED, FA_RIPOSTE_CHECK",
            -- Riposte has no buff: the game only makes it usable for a short window after a parry.
            -- IsSpellUsable is never secret, so we run our own clock from the moment it lights up,
            -- and learn the real window: a window that ends without our Riposte cast is a full one.
            custom = [[
function(event, unit, castGUID, spellID)
  local env = aura_env
  local RIPOSTE = 14251
  if event == "UNIT_SPELLCAST_SUCCEEDED" and not issecretvalue(spellID) and spellID == RIPOSTE then
    env.used = true
  end
  local usable, noEnergy = C_Spell.IsSpellUsable(RIPOSTE)
  if issecretvalue(usable) then usable = false end
  if issecretvalue(noEnergy) then noEnergy = false end
  -- Short on energy still counts as an open window: only expiry or our cast closes it.
  usable = usable or noEnergy
  local now = GetTime()
  if usable and not env.used then
    if not env.start then
      env.start = now
      local w = (env.saved and env.saved.window) or 5
      if C_Timer and WeakAuras and WeakAuras.ScanEvents then
        C_Timer.After(w + 0.1, function() WeakAuras.ScanEvents("FA_RIPOSTE_CHECK") end)
      end
    end
    return true
  end
  if env.start and not env.used then
    local held = now - env.start
    -- A cast seen late (events out of order) makes a sample too short, never too long:
    -- keep the longest one, and ignore anything under 2 s.
    if held >= 2 and held < 15 then
      env.saved = env.saved or {}
      local w = math.floor(held * 10 + 0.5) / 10
      local old = env.saved.window
      if not old or w > old then
        if math.abs(w - (old or 5)) >= 0.2 then
          print(("Rogue Combat: Riposte window measured at %.1f s (was %.1f s)"):format(w, old or 5))
        end
        env.saved.window = w
      end
      env.saved.samples = (env.saved.samples or 0) + 1
    end
  end
  if not usable then env.used = nil end
  env.start = nil
  return false
end]],
            customDuration = [[
function()
  local w = (aura_env.saved and aura_env.saved.window) or 5
  return w, (aura_env.start or GetTime()) + w
end]],
            customIcon = [[function() return C_Spell.GetSpellTexture(14251) end]],
            customName = [[function() return "Riposte" end]],
          },
          untrigger = { custom = [[function() return aura_env.start == nil end]] },
        },
      },
      load = { use_spellknown = true, spellknown = 14251 },
      animation = {
        start = { type = "preset", preset = "shrink", duration_type = "seconds" },
        main = { type = "none", duration_type = "seconds" },
        finish = { type = "preset", preset = "fade", duration_type = "seconds" },
      },
      subRegions = {
        { type = "subtext", text_text = "%p", text_font = "Fira Sans Condensed Black", text_fontSize = 24, text_fontType = "OUTLINE", text_color = { 0.94, 0.91, 0.82, 1 }, text_visible = true, anchor_point = "CENTER", text_justify = "CENTER" },
        { type = "subglow", glow = true, glowType = "Pixel", useGlowColor = true, glowColor = { 0.96, 0.78, 0.29, 1 }, glowLines = 8, glowLength = 10, glowThickness = 2, glowFrequency = 0.25 },
        { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } },
      },
      conditions = {},
    },
    -- ============================================================ right gauge: combo points (x +117)
    -- One texture per point, bottom to top. Combo points are never secret (measured 2026-11-23),
    -- so these conditions are plain comparisons. All five turn Ember together at 5.
    {
      id = "RC Combo 1", uid = "rcCombo0001", parent = "Rogue Combat", internalVersion = 91,
      regionType = "texture", width = 10, height = 26, xOffset = 117, yOffset = -82,
      texture = "Interface\\AddOns\\ForeverAuras\\Media\\Textures\\Square_FullWhite", color = { 0, 0, 0, 0.55 },
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "unit", event = "Power", unit = "player", use_unit = true, use_powertype = true, powertype = 4 }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 1752 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {
        { check = { trigger = 1, variable = "power", op = ">=", value = "1" }, changes = { { property = "color", value = { 0.94, 0.91, 0.82, 1 } } } },
        { check = { trigger = 1, variable = "power", op = ">=", value = "5" }, changes = { { property = "color", value = { 1, 0.48, 0.10, 1 } } } },
      },
    },
    {
      id = "RC Combo 2", uid = "rcCombo0002", parent = "Rogue Combat", internalVersion = 91,
      regionType = "texture", width = 10, height = 26, xOffset = 117, yOffset = -51,
      texture = "Interface\\AddOns\\ForeverAuras\\Media\\Textures\\Square_FullWhite", color = { 0, 0, 0, 0.55 },
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "unit", event = "Power", unit = "player", use_unit = true, use_powertype = true, powertype = 4 }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 1752 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {
        { check = { trigger = 1, variable = "power", op = ">=", value = "2" }, changes = { { property = "color", value = { 0.94, 0.91, 0.82, 1 } } } },
        { check = { trigger = 1, variable = "power", op = ">=", value = "5" }, changes = { { property = "color", value = { 1, 0.48, 0.10, 1 } } } },
      },
    },
    {
      id = "RC Combo 3", uid = "rcCombo0003", parent = "Rogue Combat", internalVersion = 91,
      regionType = "texture", width = 10, height = 26, xOffset = 117, yOffset = -20,
      texture = "Interface\\AddOns\\ForeverAuras\\Media\\Textures\\Square_FullWhite", color = { 0, 0, 0, 0.55 },
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "unit", event = "Power", unit = "player", use_unit = true, use_powertype = true, powertype = 4 }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 1752 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {
        { check = { trigger = 1, variable = "power", op = ">=", value = "3" }, changes = { { property = "color", value = { 0.94, 0.91, 0.82, 1 } } } },
        { check = { trigger = 1, variable = "power", op = ">=", value = "5" }, changes = { { property = "color", value = { 1, 0.48, 0.10, 1 } } } },
      },
    },
    {
      id = "RC Combo 4", uid = "rcCombo0004", parent = "Rogue Combat", internalVersion = 91,
      regionType = "texture", width = 10, height = 26, xOffset = 117, yOffset = 11,
      texture = "Interface\\AddOns\\ForeverAuras\\Media\\Textures\\Square_FullWhite", color = { 0, 0, 0, 0.55 },
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "unit", event = "Power", unit = "player", use_unit = true, use_powertype = true, powertype = 4 }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 1752 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {
        { check = { trigger = 1, variable = "power", op = ">=", value = "4" }, changes = { { property = "color", value = { 0.94, 0.91, 0.82, 1 } } } },
        { check = { trigger = 1, variable = "power", op = ">=", value = "5" }, changes = { { property = "color", value = { 1, 0.48, 0.10, 1 } } } },
      },
    },
    {
      id = "RC Combo 5", uid = "rcCombo0005", parent = "Rogue Combat", internalVersion = 91,
      regionType = "texture", width = 10, height = 26, xOffset = 117, yOffset = 42,
      texture = "Interface\\AddOns\\ForeverAuras\\Media\\Textures\\Square_FullWhite", color = { 0, 0, 0, 0.55 },
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "unit", event = "Power", unit = "player", use_unit = true, use_powertype = true, powertype = 4 }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 1752 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {
        { check = { trigger = 1, variable = "power", op = ">=", value = "5" }, changes = { { property = "color", value = { 1, 0.48, 0.10, 1 } } } },
      },
    },
    -- ============================================================ right gauge: Slice and Dice (x +134)
    {
      id = "RC Slice and Dice", uid = "rcSnD000001", parent = "Rogue Combat", internalVersion = 91,
      regionType = "aurabar", width = 14, height = 150, xOffset = 134, yOffset = -20,
      orientation = "VERTICAL", texture = "Clean", spark = false, icon = false,
      barColor = { 0.27, 0.84, 0.66, 1 }, backgroundColor = { 0, 0, 0, 0.62 },
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "secretAura", unit = "player", debuffType = "HELPFUL", secretUseRankSpellIDs = true, auraRankSpellIDs = { "5171", "6774" }, secretUseSpellIDs = false, secretShowOn = "showOnActive" }, untrigger = {} } },
      load = { use_spellknown = true, spellknown = 5171 },
      subRegions = {
        { type = "subforeground" }, { type = "subbackground" },
        { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } },
        -- sub.4 and sub.5 are named by the condition below: recount if this list changes.
        { type = "subtext", text_text = "%p", text_font = "Fira Sans Condensed Black", text_fontSize = 18, text_fontType = "OUTLINE", text_color = { 0.94, 0.91, 0.82, 1 }, text_visible = true, anchor_point = "BOTTOM", text_selfPoint = "AUTO", anchorYOffset = -4, text_justify = "CENTER" },
        { type = "subglow", glow = false, glowType = "Pixel", useGlowColor = true, glowColor = { 1, 0.26, 0.22, 1 }, glowLines = 6, glowLength = 8, glowThickness = 2, glowFrequency = 0.25, anchor_area = "bar" },
      },
      conditions = {
        -- Remaining time is secret in combat; FA lets it drive only a duration text colour or a glow.
        { check = { trigger = 1, variable = "faAuraRemaining", op = "<", value = 3 }, changes = { { property = "sub.4.text_color", value = { 1, 0.26, 0.22, 1 } }, { property = "sub.5.glow", value = true } } },
      },
    },
    {
      id = "RC Slice and Dice Missing", uid = "rcSnDMiss01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "aurabar", width = 14, height = 150, xOffset = 134, yOffset = -20,
      orientation = "VERTICAL", texture = "Clean", spark = false, icon = false,
      barColor = { 1, 0.26, 0.22, 0 }, backgroundColor = { 1, 0.26, 0.22, 0.55 },
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "secretAura", unit = "player", debuffType = "HELPFUL", secretUseRankSpellIDs = true, auraRankSpellIDs = { "5171", "6774" }, secretUseSpellIDs = false, secretShowOn = "showOnMissing" }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 5171 },
      animation = {
        start = { type = "none", duration_type = "seconds" },
        main = { type = "preset", preset = "alphaPulse", duration_type = "seconds" },
        finish = { type = "none", duration_type = "seconds" },
      },
      subRegions = {
        { type = "subforeground" }, { type = "subbackground" },
        { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } },
      },
      conditions = {},
    },
    {
      id = "RC Slice and Dice Missing Icon", uid = "rcSnDMisIc1", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 26, height = 26, xOffset = 134, yOffset = -113,
      iconSource = -1, zoom = 0.3, cooldown = false,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "secretAura", unit = "player", debuffType = "HELPFUL", secretUseRankSpellIDs = true, auraRankSpellIDs = { "5171", "6774" }, secretUseSpellIDs = false, secretShowOn = "showOnMissing" }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 5171 },
      animation = {
        start = { type = "none", duration_type = "seconds" },
        main = { type = "preset", preset = "alphaPulse", duration_type = "seconds" },
        finish = { type = "none", duration_type = "seconds" },
      },
      subRegions = {
        { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } },
      },
      conditions = {},
    },
    -- ============================================================ burst: right top (y +40)
    -- One slot per ability: bright = ready (cooldown trigger), jade edge + seconds = buff running
    -- (secretAura twin in the same slot), empty = spent.
    {
      id = "RC Blade Flurry Ready", uid = "rcBFReady01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 30, height = 30, xOffset = 165, yOffset = 40,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 13877, use_exact_spellName = false, genericShowOn = "showOnReady", track = "auto" }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 13877 },
      animation = {
        start = { type = "preset", preset = "fade", duration_type = "seconds" },
        main = { type = "none", duration_type = "seconds" },
        finish = { type = "none", duration_type = "seconds" },
      },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {
        { check = { trigger = 1, variable = "insufficientResources", op = "==", value = 1 }, changes = { { property = "color", value = { 0.45, 0.55, 1, 1 } } } },
      },
    },
    {
      id = "RC Adrenaline Rush Ready", uid = "rcARReady01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 30, height = 30, xOffset = 199, yOffset = 40,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 13750, use_exact_spellName = false, genericShowOn = "showOnReady", track = "auto" }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 13750 },
      animation = {
        start = { type = "preset", preset = "fade", duration_type = "seconds" },
        main = { type = "none", duration_type = "seconds" },
        finish = { type = "none", duration_type = "seconds" },
      },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {},
    },
    {
      id = "RC Cold Blood", uid = "rcColdBld01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 30, height = 30, xOffset = 233, yOffset = 40,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 14177, use_exact_spellName = false, genericShowOn = "showOnReady", track = "auto" }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 14177 },
      animation = {
        start = { type = "preset", preset = "fade", duration_type = "seconds" },
        main = { type = "none", duration_type = "seconds" },
        finish = { type = "none", duration_type = "seconds" },
      },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {},
    },
    {
      id = "RC Blade Flurry", uid = "rcBFActive1", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 30, height = 30, xOffset = 165, yOffset = 40,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownSwipe = true, inverse = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "secretAura", unit = "player", debuffType = "HELPFUL", secretUseSpellIDs = true, auraspellids = { "13877" }, secretShowOn = "showOnActive" }, untrigger = {} } },
      load = { use_spellknown = true, spellknown = 13877 },
      subRegions = {
        { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 2, border_offset = 1, border_color = { 0.27, 0.84, 0.66, 1 } },
        { type = "subtext", text_text = "%p", text_font = "Fira Sans Condensed Black", text_fontSize = 13, text_fontType = "OUTLINE", text_color = { 0.94, 0.91, 0.82, 1 }, text_visible = true, anchor_point = "CENTER", text_justify = "CENTER" },
      },
      conditions = {},
    },
    {
      id = "RC Adrenaline Rush", uid = "rcARActive1", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 30, height = 30, xOffset = 199, yOffset = 40,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownSwipe = true, inverse = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "secretAura", unit = "player", debuffType = "HELPFUL", secretUseSpellIDs = true, auraspellids = { "13750" }, secretShowOn = "showOnActive" }, untrigger = {} } },
      load = { use_spellknown = true, spellknown = 13750 },
      subRegions = {
        { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 2, border_offset = 1, border_color = { 0.27, 0.84, 0.66, 1 } },
        { type = "subtext", text_text = "%p", text_font = "Fira Sans Condensed Black", text_fontSize = 13, text_fontType = "OUTLINE", text_color = { 0.94, 0.91, 0.82, 1 }, text_visible = true, anchor_point = "CENTER", text_justify = "CENTER" },
      },
      conditions = {},
    },
    -- ============================================================ escape: left bottom (y -81)
    -- Shown in combat while ready. Faint while you are above half health, full under it: health is
    -- secret in combat, but a Health condition may change alpha (it runs through a curve).
    {
      id = "RC Evasion", uid = "rcDefEvas01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 28, height = 28, xOffset = -164, yOffset = -81,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "all",
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 5277, use_exact_spellName = false, genericShowOn = "showOnReady", track = "auto" }, untrigger = {} },
        { trigger = { type = "unit", event = "Health", unit = "player", use_unit = true }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 5277 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = { { check = { trigger = 2, variable = "percenthealth", op = ">=", value = "50" }, changes = { { property = "alpha", value = 0.35 } } } },
    },
    {
      id = "RC Vanish", uid = "rcDefVani01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 28, height = 28, xOffset = -196, yOffset = -81,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "all",
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 1856, use_exact_spellName = false, genericShowOn = "showOnReady", track = "auto" }, untrigger = {} },
        { trigger = { type = "unit", event = "Health", unit = "player", use_unit = true }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 1856 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = { { check = { trigger = 2, variable = "percenthealth", op = ">=", value = "50" }, changes = { { property = "alpha", value = 0.35 } } } },
    },
    {
      id = "RC Sprint", uid = "rcDefSprt01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 28, height = 28, xOffset = -228, yOffset = -81,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "all",
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 2983, use_exact_spellName = false, genericShowOn = "showOnReady", track = "auto" }, untrigger = {} },
        { trigger = { type = "unit", event = "Health", unit = "player", use_unit = true }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 2983 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = { { check = { trigger = 2, variable = "percenthealth", op = ">=", value = "50" }, changes = { { property = "alpha", value = 0.35 } } } },
    },
    {
      id = "RC Evasion Active", uid = "rcEvasAct01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 28, height = 28, xOffset = -164, yOffset = -81,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownSwipe = true, inverse = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "secretAura", unit = "player", debuffType = "HELPFUL", secretUseSpellIDs = true, auraspellids = { "5277", "26669" }, secretShowOn = "showOnActive" }, untrigger = {} } },
      load = { use_spellknown = true, spellknown = 5277 },
      subRegions = {
        { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 2, border_offset = 1, border_color = { 0.27, 0.84, 0.66, 1 } },
        { type = "subtext", text_text = "%p", text_font = "Fira Sans Condensed Black", text_fontSize = 13, text_fontType = "OUTLINE", text_color = { 0.94, 0.91, 0.82, 1 }, text_visible = true, anchor_point = "CENTER", text_justify = "CENTER" },
      },
      conditions = {},
    },
    {
      id = "RC Sprint Active", uid = "rcSprtAct01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 28, height = 28, xOffset = -228, yOffset = -81,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownSwipe = true, inverse = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "secretAura", unit = "player", debuffType = "HELPFUL", secretUseRankSpellIDs = true, auraRankSpellIDs = { "2983", "8696", "11305" }, secretUseSpellIDs = false, secretShowOn = "showOnActive" }, untrigger = {} } },
      load = { use_spellknown = true, spellknown = 2983 },
      subRegions = {
        { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 2, border_offset = 1, border_color = { 0.27, 0.84, 0.66, 1 } },
        { type = "subtext", text_text = "%p", text_font = "Fira Sans Condensed Black", text_fontSize = 13, text_fontType = "OUTLINE", text_color = { 0.94, 0.91, 0.82, 1 }, text_visible = true, anchor_point = "CENTER", text_justify = "CENTER" },
      },
      conditions = {},
    },
    -- ============================================================ control: right bottom (y -81)
    -- Always shown in combat: short cooldowns you plan around. Grey + swipe = cooling down;
    -- blue = not enough energy; red = target out of range.
    {
      id = "RC Kick", uid = "rcDefKick01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 28, height = 28, xOffset = 164, yOffset = -81,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownSwipe = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 1766, use_exact_spellName = false, genericShowOn = "showAlways", track = "auto" }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 1766 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {
        { check = { trigger = 1, variable = "onCooldown", op = "==", value = 1 }, changes = { { property = "desaturate", value = true } } },
        { check = { trigger = 1, variable = "insufficientResources", op = "==", value = 1 }, changes = { { property = "color", value = { 0.45, 0.55, 1, 1 } } } },
        { check = { trigger = 1, variable = "spellInRange", op = "==", value = 0 }, changes = { { property = "color", value = { 1, 0.35, 0.35, 1 } } } },
      },
    },
    {
      id = "RC Gouge", uid = "rcDefGoug01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 28, height = 28, xOffset = 196, yOffset = -81,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownSwipe = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 1776, use_exact_spellName = false, genericShowOn = "showAlways", track = "auto" }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 1776 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {
        { check = { trigger = 1, variable = "onCooldown", op = "==", value = 1 }, changes = { { property = "desaturate", value = true } } },
        { check = { trigger = 1, variable = "insufficientResources", op = "==", value = 1 }, changes = { { property = "color", value = { 0.45, 0.55, 1, 1 } } } },
        { check = { trigger = 1, variable = "spellInRange", op = "==", value = 0 }, changes = { { property = "color", value = { 1, 0.35, 0.35, 1 } } } },
      },
    },
    {
      id = "RC Kidney Shot", uid = "rcDefKidn01", parent = "Rogue Combat", internalVersion = 91,
      regionType = "icon", width = 28, height = 28, xOffset = 228, yOffset = -81,
      iconSource = -1, zoom = 0.3, cooldown = true, cooldownSwipe = true, cooldownTextDisabled = true,
      triggers = { activeTriggerMode = 1, disjunctive = "any",
        { trigger = { type = "spell", event = "Cooldown Progress (Spell)", spellName = 408, use_exact_spellName = false, genericShowOn = "showAlways", track = "auto" }, untrigger = {} } },
      load = { use_combat = true, use_spellknown = true, spellknown = 408 },
      subRegions = { { type = "subborder", border_visible = true, border_edge = "Square Full White", border_size = 1, border_offset = 1, border_color = { 0, 0, 0, 0.9 } } },
      conditions = {
        { check = { trigger = 1, variable = "onCooldown", op = "==", value = 1 }, changes = { { property = "desaturate", value = true } } },
        { check = { trigger = 1, variable = "insufficientResources", op = "==", value = 1 }, changes = { { property = "color", value = { 0.45, 0.55, 1, 1 } } } },
        { check = { trigger = 1, variable = "spellInRange", op = "==", value = 0 }, changes = { { property = "color", value = { 1, 0.35, 0.35, 1 } } } },
      },
    },
  },
}
