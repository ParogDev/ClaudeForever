<#
.SYNOPSIS
    Junction-link this workspace's AddOns\<Name> folders into the game (_forever_\Interface\AddOns\<Name>), so the
    game loads the files you edit here.

.DESCRIPTION
    tools\link-addons.ps1                 link every AddOns\* folder that has a .toc (skips ones already linked here)
    tools\link-addons.ps1 -Name X         link one
    tools\link-addons.ps1 -Status         print each game AddOns entry: ours (junction -> where), foreign, or absent
    tools\link-addons.ps1 -Unlink -Name X remove our junction (never touches a real folder)

    A junction needs no administrator rights. A NEW addon folder is only seen by the client after a full restart
    (exit the game and start it again); edits to files already listed in the .toc only need /reload. Refuses to
    replace a real (non-junction) folder: that is an addon you installed, and it stays yours to remove or rename.
    The game folder comes from WOWF_GAME_DIR (the folder that holds _forever_), default
    C:\Program Files (x86)\World of Warcraft.
#>
param([string]$Name, [switch]$Status, [switch]$Unlink)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'game-lib.ps1')
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$AddOnsDir = Get-AddOnsDir
if (-not (Test-Path $AddOnsDir)) {
    Write-Error "Game AddOns folder not found: $AddOnsDir. Set WOWF_GAME_DIR to the folder that holds _forever_ (for example: `$env:WOWF_GAME_DIR = 'D:\Games\World of Warcraft'), or start the game once so it creates Interface\AddOns."
}

function Get-LocalAddons {
    Get-ChildItem (Join-Path $Root 'AddOns') -Directory -ErrorAction SilentlyContinue |
        Where-Object { Get-ChildItem $_.FullName -Filter '*.toc' -ErrorAction SilentlyContinue } | ForEach-Object { $_.Name }
}

if ($Status) {
    $mine = (Join-Path $Root 'AddOns').TrimEnd('\').ToLower()
    foreach ($e in Get-ChildItem $AddOnsDir -Directory -Force | Sort-Object Name) {
        $l = Get-AddOnLink $e.Name
        $ours = $l.isLink -and $l.target -and $l.target.ToLower().StartsWith($mine)
        $kind = if ($l.isLink -and $ours) { "junction -> $($l.target)" } elseif ($l.isLink) { "junction (elsewhere) -> $($l.target)" } else { 'installed folder' }
        Write-Output ("{0,-28} {1}" -f $e.Name, $kind)
    }
    foreach ($n in Get-LocalAddons) { if (-not (Get-AddOnLink $n)) { Write-Output ("{0,-28} NOT LINKED (local AddOns\{0})" -f $n) } }
    exit 0
}

$names = if ($Name) { @($Name) } else { @(Get-LocalAddons) }
if (-not $names.Count) { Write-Output 'No AddOns\*\*.toc here; nothing to link.'; exit 0 }

foreach ($n in $names) {
    $gamePath = Join-Path $AddOnsDir $n
    $local = Join-Path $Root "AddOns\$n"
    $l = Get-AddOnLink $n
    if ($Unlink) {
        if (-not $l) { Write-Output "${n}: not present in game AddOns."; continue }
        if (-not $l.isLink) { Write-Error "${n}: $gamePath is a real folder, not our junction; not touching it." }
        [IO.Directory]::Delete($gamePath)   # removes the junction only, never the target's contents
        Write-Output "${n}: junction removed."
        continue
    }
    if (-not (Test-Path $local)) { Write-Error "${n}: no AddOns\$n in this workspace." }
    if ($l -and -not $l.isLink) { Write-Error "${n}: $gamePath is an installed addon folder (not a junction). Remove or rename it yourself first." }
    if ($l -and $l.isLink -and $l.target -and ($l.target.TrimEnd('\').ToLower() -eq $local.ToLower())) { Write-Output "${n}: already linked."; continue }
    if ($l -and $l.isLink) { [IO.Directory]::Delete($gamePath) }
    New-Item -ItemType Junction -Path $gamePath -Target $local | Out-Null
    $note = if (-not $l) { ' (new folder: restart the game client to see it; /reload is not enough)' } else { '' }
    Write-Output "${n}: linked -> $local$note"
}
