local mock = require("tests.wow_mock")

describe("Core", function()
	local ns

	before_each(function()
		mock.install()
		ns = mock.loadAddon(".")
	end)

	it("creates the SavedVariable on first load", function()
		assert.is_table(_G.__NAME__DB)
		assert.equal(1, _G.__NAME__DB.dbVersion)
	end)

	it("keeps an existing SavedVariable", function()
		mock.install()
		mock.loadAddon(".", { dbVersion = 1, keep = "me" })
		assert.equal("me", _G.__NAME__DB.keep)
	end)

	it("writes the selftest at login with the code's version", function()
		local st = _G.__NAME__DB.selftest
		assert.equal("login", st.phase)
		assert.equal(ns.VERSION, st.version)
		assert.equal(16001, st.interface)
		assert.equal(18, st.project)
	end)

	it("refreshes the selftest at logout", function()
		mock.fire("PLAYER_LOGOUT")
		assert.equal("logout", _G.__NAME__DB.selftest.phase)
	end)

	it("counts words in a /say line", function()
		mock.fire("CHAT_MSG_SAY", "hello there friend")
		assert.equal(1, ns.counters.lines)
		assert.equal(3, ns.counters.words)
	end)

	it("skips a secret line and counts it as secret", function()
		local text = "a secret line"
		mock.secret[text] = true
		mock.fire("CHAT_MSG_SAY", text)
		assert.equal(1, ns.counters.lines)
		assert.equal(1, ns.counters.secret)
		assert.is_nil(ns.counters.words)
	end)

	it("records an error in the selftest instead of raising it", function()
		ns.guard("test", function()
			error("boom")
		end)
		assert.equal("test", ns.selftest.lastError.where)
		assert.matches("boom", ns.selftest.lastError.error, 1, true)
	end)

	it("answers its slash command", function()
		SlashCmdList.__UPPER__("selftest")
		assert.matches("__NAME__ " .. ns.VERSION, mock.chat[1], 1, true)
	end)
end)
