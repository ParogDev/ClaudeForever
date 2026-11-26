-- Minimal WoW client globals so the addon loads under busted. Dumb tables and no-ops, not a client: the real check
-- is the in-game /reload. Add a global here only when a file under test touches it at load.
local M = {}

local function newFrame()
	local f = { _events = {} }
	function f:RegisterEvent(e)
		self._events[e] = true
	end
	function f:SetScript(k, fn)
		self["_" .. k] = fn
	end
	M.frames[#M.frames + 1] = f
	return f
end

function M.install()
	M.frames = {}
	M.secret = {} -- values listed here are secret: issecretvalue(v) is true
	M.chat = {}

	_G.CreateFrame = newFrame
	_G.DEFAULT_CHAT_FRAME = {
		AddMessage = function(_, line)
			M.chat[#M.chat + 1] = line
		end,
	}
	_G.SlashCmdList = {}
	_G.WOW_PROJECT_ID = 18
	_G.GetBuildInfo = function()
		return "1.60.1", "70790", "Nov 4 2026", 16001
	end
	_G.C_AddOns = {
		GetAddOnMetadata = function()
			return "@project-version@"
		end,
	}
	_G.date = function(fmt)
		return os.date(fmt)
	end
	_G.strtrim = function(s)
		return (s:gsub("^%s+", ""):gsub("%s+$", ""))
	end
	_G.issecretvalue = function(v)
		return v ~= nil and M.secret[v] == true
	end
end

-- Loads the addon's files the way the client does (local ADDON, ns = ...), then fires its load events.
function M.loadAddon(dir, saved)
	local ns = {}
	for _, f in ipairs({ "Core.lua" }) do
		local chunk, err = loadfile(dir .. "/" .. f)
		assert(chunk, err)
		chunk("__NAME__", ns)
	end
	_G.__NAME__DB = saved
	M.fire("ADDON_LOADED", "__NAME__")
	M.fire("PLAYER_LOGIN")
	M.ns = ns
	return ns
end

function M.fire(event, ...)
	for _, f in ipairs(M.frames) do
		if f._OnEvent and f._events[event] then
			f._OnEvent(f, event, ...)
		end
	end
end

return M
