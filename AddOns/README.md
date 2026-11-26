# AddOns

Your own addons live here, one folder per addon: `AddOns/<Name>/`. Each folder is its own git repository (and,
if you want, its own GitHub repository), so this workspace ignores everything in here except this file.

- Make a new one with the `new-addon` skill (it copies `templates/addon/`).
- `tools\link-addons.ps1 -Name <Name>` links the folder into the game (`_forever_\Interface\AddOns\<Name>`), so the
  game loads the files you edit here. Restart the client once after linking a new folder.
- `tools\lua.ps1 all -Path AddOns\<Name>` runs lint, tests and the format check.
- An addon someone else wrote can be cloned here too (`git clone <url> AddOns/<Name>`) and linked the same way.
