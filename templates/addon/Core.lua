-- __NAME__: addon entry. Events, the selftest table the verify loop reads back after a /reload, and the slash
-- command. Start your own code from the "Your code" section; keep the selftest contract as it is.
local ADDON, ns = ...

__NAME__ = ns

-- Shown in the selftest when the packager has not replaced @project-version@ (a checkout, not a release zip).
ns.VERSION = "0.1.0"

local DB_VERSION = 1

local counters = { lines = 0, secret = 0 }
local selftest = { counters = counters }
ns.counters = counters
ns.selftest = selftest

local function now()
	return date("%Y-%m-%d %H:%M:%S")
end

local function version()
	local ok, v = pcall(C_AddOns.GetAddOnMetadata, ADDON, "Version")
	if not ok or type(v) ~= "string" or v:find("@", 1, true) then
		return ns.VERSION
	end
	return v
end
ns.version = version

-- Runs fn and records a failure in the selftest instead of raising it, so one bad event never breaks the rest.
-- The error still names where it happened (lastError.where).
local function guard(where, fn, ...)
	local ok, err = pcall(fn, ...)
	if not ok then
		selftest.lastError = { where = where, error = tostring(err), at = now() }
	end
	return ok, err
end
ns.guard = guard

local function say(line)
	DEFAULT_CHAT_FRAME:AddMessage(line)
end

function ns.initDB(saved)
	local db = type(saved) == "table" and saved or {}
	db.dbVersion = db.dbVersion or DB_VERSION
	db.selftest = db.selftest or {}
	ns.db = db
	__NAME__DB = db
	return db
end

-- ---------------------------------------------------------------------------------------------------------------
-- Your code. The example counts the words in /say lines near you, to show the secret-value guard: in instances
-- and encounters the game hands chat text to addons as a secret, which may be shown but not measured, compared or
-- pattern-matched. Check issecretvalue() before any of those, and degrade (skip the analysis) instead of failing.
-- ---------------------------------------------------------------------------------------------------------------

-- Returns the word count of a line, or nil and why it was skipped.
function ns.countWords(text)
	if issecretvalue(text) then
		return nil, "secret"
	end
	if type(text) ~= "string" then
		return nil, "not a string"
	end
	local n = 0
	for _ in text:gmatch("%S+") do
		n = n + 1
	end
	return n
end

function ns.onChat(text)
	counters.lines = counters.lines + 1
	local words, why = ns.countWords(text)
	if not words then
		if why == "secret" then
			counters.secret = counters.secret + 1
		end
		return
	end
	counters.words = (counters.words or 0) + words
end

-- ---------------------------------------------------------------------------------------------------------------
-- selftest: written to __NAME__DB.selftest on login and logout. SavedVariables reach the disk on /reload, logout
-- and exit, so after a /reload tools\reload-wait.ps1 reads this table back and shows which version loaded.
-- ---------------------------------------------------------------------------------------------------------------
function selftest.snapshot(phase)
	local okB, buildVersion, buildNumber, _, interface = pcall(GetBuildInfo)
	ns.db.selftest = {
		phase = phase,
		version = version(),
		build = okB and (tostring(buildVersion) .. "." .. tostring(buildNumber)) or "GetBuildInfo failed",
		interface = okB and interface or nil,
		project = WOW_PROJECT_ID,
		loadedAt = selftest.loadedAt,
		savedAt = now(),
		counters = counters,
		lastError = selftest.lastError,
	}
	return ns.db.selftest
end

-- ---------------------------------------------------------------------------------------------------------------
-- /__LOWER__
-- ---------------------------------------------------------------------------------------------------------------
function ns.slash(msg)
	msg = strtrim(msg or "")
	if msg == "selftest" then
		local st = selftest.snapshot("slash")
		say(string.format("__NAME__ %s: build %s, interface %s", st.version, st.build, tostring(st.interface)))
		say(string.format("  lines %d (secret %d), words %d", counters.lines, counters.secret, counters.words or 0))
		if st.lastError then
			say("  last error in " .. st.lastError.where .. ": " .. st.lastError.error)
		end
	else
		say("__NAME__ " .. version() .. ": /__LOWER__ selftest")
	end
end

SLASH___UPPER__1 = "/__LOWER__"
SlashCmdList.__UPPER__ = function(msg)
	guard("slash", ns.slash, msg)
end

-- ---------------------------------------------------------------------------------------------------------------
-- Events
-- ---------------------------------------------------------------------------------------------------------------
local frame = CreateFrame("Frame")
ns.frame = frame
frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_LOGOUT")
frame:RegisterEvent("CHAT_MSG_SAY")
frame:SetScript("OnEvent", function(_, event, arg1)
	if event == "ADDON_LOADED" then
		if arg1 == ADDON then
			ns.initDB(__NAME__DB)
		end
	elseif event == "PLAYER_LOGIN" then
		selftest.loadedAt = now()
		guard("snapshot", selftest.snapshot, "login")
	elseif event == "PLAYER_LOGOUT" then
		-- The last event before the client writes SavedVariables.
		guard("snapshot", selftest.snapshot, "logout")
	elseif event == "CHAT_MSG_SAY" then
		guard("chat", ns.onChat, arg1)
	end
end)
