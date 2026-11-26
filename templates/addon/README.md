# __NAME__

__NOTES__

An addon for World of Warcraft: Forever (interface 16001).

## Install

Download the zip from the latest release, unpack it into
`World of Warcraft\_forever_\Interface\AddOns\`, and restart the game.

## Use

`/__LOWER__ selftest` prints the loaded version and what the addon has counted so far.

## Develop

Lint, tests and formatting run with luacheck, busted and stylua (Lua 5.1). CI runs all three on every push
(`.github/workflows/ci.yml`). Tests live in `tests/` and load the addon against `tests/wow_mock.lua`.

Release: push a tag `vX.Y.Z`. The BigWigs packager builds the zip for the Forever flavor
(`.github/workflows/release.yml`).

## License

MIT, see `LICENSE`.
