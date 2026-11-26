-- A small group used by the tests and the parity proof.
return {
  d = {
    id = "FA Example",
    uid = "abcDEF01234",
    regionType = "dynamicgroup",
    internalVersion = 91,
    grow = "RIGHT",
    space = 2,
    xOffset = 0,
    yOffset = -120.5,
    triggers = { { trigger = { type = "aura2", unit = "player", debuffType = "HELPFUL" } } },
  },
  c = {
    {
      id = "FA Example: Slice and Dice",
      regionType = "icon",
      internalVersion = 91,
      width = 40,
      height = 40,
      color = { 1, 1, 1, 1 },
      triggers = {
        activeTriggerMode = -10,
        {
          trigger = {
            type = "aura2",
            unit = "player",
            debuffType = "HELPFUL",
            auranames = { "Slice and Dice" },
            useName = true,
          },
          untrigger = {},
        },
      },
      conditions = {
        {
          check = { trigger = 1, variable = "expirationTime", op = "<", value = "3" },
          changes = { { property = "color", value = { 1, 0.2, 0.2, 1 } } },
        },
      },
    },
    {
      id = "FA Example: Energy",
      regionType = "text",
      internalVersion = 91,
      displayText = "%c",
      customText = [==[
function()
  local t = { [[nested]] }
  return t[1] .. "]]" -- a closing bracket in code
end]==],
      fontSize = 0x10,
      triggers = {
        { trigger = { type = "unit", event = "Power", unit = "player", use_powertype = true, powertype = 3 } },
      },
    },
  },
}
