<#
.SYNOPSIS
    Where the game is and whether it runs. Dot-sourced by the tools and the hook guard that touch the Forever install.

.DESCRIPTION
    WOWF_GAME_DIR overrides the install folder (the one that holds _forever_). The default is Battle.net's default
    install path. Nothing here writes anything.
#>

function Get-GameRoot {
    $d = if ($env:WOWF_GAME_DIR) { $env:WOWF_GAME_DIR } else { 'C:\Program Files (x86)\World of Warcraft' }
    return $d.TrimEnd('\')
}
function Get-ForeverDir { return (Join-Path (Get-GameRoot) '_forever_') }
function Get-AddOnsDir  { return (Join-Path (Get-ForeverDir) 'Interface\AddOns') }
function Get-WtfDir     { return (Join-Path (Get-ForeverDir) 'WTF') }

# Wow.exe of the Forever client. Battle.net can run several products; match on the process path when readable.
function Test-GameRunning {
    $procs = @(Get-Process -Name 'Wow' -ErrorAction SilentlyContinue)
    if (-not $procs.Count) { return $false }
    $forever = (Get-ForeverDir).ToLowerInvariant()
    foreach ($p in $procs) {
        $path = $null
        try { $path = $p.Path } catch { }
        if (-not $path) { return $true }            # elevated process: path hidden; assume it is the one
        if ($path.ToLowerInvariant().StartsWith($forever)) { return $true }
    }
    return $false
}

# SavedVariables files for an addon (account-wide and per-character), newest first.
function Get-SavedVariablesFiles([string]$addon) {
    $wtf = Get-WtfDir
    if (-not (Test-Path $wtf)) { return @() }
    return @(Get-ChildItem (Join-Path $wtf 'Account') -Recurse -Filter "$addon.lua" -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq 'SavedVariables' } | Sort-Object LastWriteTime -Descending)
}

# Junction state of AddOns\<Name> inside the game: $null (absent), or @{ path; target; isLink }.
function Get-AddOnLink([string]$name) {
    $p = Join-Path (Get-AddOnsDir) $name
    if (-not (Test-Path -LiteralPath $p)) { return $null }
    $item = Get-Item -LiteralPath $p -Force
    $isLink = [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
    $target = $null
    if ($isLink) { try { $target = @($item.Target)[0] } catch { } }
    return @{ path = $p; target = $target; isLink = $isLink }
}
