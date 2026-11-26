---
name: release
description: Tag and package an addon release with the BigWigs packager (Forever flavor) to a GitHub Release, optionally CurseForge and Wago. Use for "release <Name> <version>", "cut a version", "publish the addon". Only from a clean, pushed main.
---

# Release

Inputs: `Name`, `version` (semver `X.Y.Z`; the tag is `vX.Y.Z`). The addon's repo is the user's own GitHub repo
(`git -C AddOns/<Name> remote -v`); without a GitHub remote, stop and say a release needs one (the `new-addon`
skill's GitHub step).

1. In `AddOns/<Name>` on `main`, up to date with `origin/main`, clean tree, `tools\lua.ps1 all -Path AddOns\<Name>`
   green. `CHANGELOG.md` has a section for this version (write it from `git log <last tag>..HEAD`, in words a player
   understands; run the `unslop` skill over it).
2. The `.toc` keeps `## Version: @project-version@`; the packager substitutes the tag. Never hand-edit the version.
   Bump `ns.VERSION` in `Core.lua` to the same number, so a checkout's selftest says which code it is.
3. Dry run when unsure: `docker run --rm -v "${PWD}:/work" -w /work ghcr.io/bigwigsmods/packager:v2 -d -g forever`
   from the addon folder. Check the zip holds the `.toc`, the `.lua` files, any `Libs/` externals from `.pkgmeta`,
   and no `tests/` or `.github/`.
4. Ask the user before publishing: tagging and pushing makes a public release. On a yes:
   `git -C AddOns/<Name> tag -a vX.Y.Z -m "vX.Y.Z"` and `git -C AddOns/<Name> push origin vX.Y.Z`. The repo's
   `.github/workflows/release.yml` runs `BigWigsMods/packager@v2 -g forever` on the tag and attaches the zip to a
   GitHub Release. CurseForge and Wago uploads happen only when the `CF_API_KEY` / `WAGO_API_TOKEN` secrets exist in
   that repo: the user adds them in the repo settings; never ask for the values.
5. Report the release URL (`gh release view vX.Y.Z -R <owner>/<Name>`) and the asset name.
