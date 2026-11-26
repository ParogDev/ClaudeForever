-- luacheck for a WoW: Forever addon. Run from this folder (tools\lua.ps1 in the workspace does): the generated
-- globals list lives in the workspace's tools\ folder; standalone (this repo's CI) falls back to a short list.
std = "lua51"
max_line_length = 140
codes = true
ignore = {
	"212/self", -- unused self
	"212/_.*", -- unused args named _x
	"211/_.*", -- unused locals named _x
}

local ok, wow = pcall(dofile, "../../tools/luacheck-wow-globals.lua")
if ok and type(wow) == "table" then
	read_globals = {}
	for _, g in ipairs(wow.read_globals) do
		if g ~= "SlashCmdList" then
			read_globals[#read_globals + 1] = g
		end
	end
else
	-- CI in this repo runs standalone: every client global the addon reads must be here.
	read_globals = {
		"CreateFrame", "C_AddOns", "GetBuildInfo", "WOW_PROJECT_ID", "issecretvalue", "date", "strtrim",
	}
end
-- FrameXML globals the generated list doesn't carry.
for _, g in ipairs({ "DEFAULT_CHAT_FRAME" }) do
	read_globals[#read_globals + 1] = g
end

globals = { "__NAME__", "__NAME__DB", "SLASH___UPPER__1", "SlashCmdList" }

files["tests/"] = {
	std = "+busted",
	globals = {
		"__NAME__", "__NAME__DB", "_G", "CreateFrame", "C_AddOns", "GetBuildInfo", "WOW_PROJECT_ID", "issecretvalue",
		"date", "strtrim", "DEFAULT_CHAT_FRAME",
	},
}
exclude_files = { ".luacheckrc", ".release/" }
