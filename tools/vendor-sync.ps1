<#
.SYNOPSIS
    Fetch the read-only references for the Forever client into vendor\ (gitignored) and regenerate the luacheck
    globals list from them. Run once after cloning and after each client patch.

.DESCRIPTION
    vendor\wow-ui-source              Gethe/wow-ui-source, branch forever (Blizzard's UI code + API docs), shallow
    vendor\BlizzardInterfaceResources Ketho/BlizzardInterfaceResources, branch forever (what this client has), shallow
    tools\luacheck-wow-globals.lua    generated from the Ketho lists (tools\gen_luacheck_globals.py; needs Python 3)
    vendor\wow-api                    optional: Logonz/WoW-API LuaLS ---@meta output (needs uv; -WithLuaLs)

    -Status prints each reference's commit and date. Nothing in vendor\ is ever committed or edited.
    Without Python the clone still happens and the committed tools\luacheck-wow-globals.lua stays as it is.
#>
param([switch]$Status, [switch]$WithLuaLs)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Vendor = Join-Path $Root 'vendor'
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null

$refs = @(
    @{ name = 'wow-ui-source';              url = 'https://github.com/Gethe/wow-ui-source.git';              branch = 'forever' },
    @{ name = 'BlizzardInterfaceResources'; url = 'https://github.com/Ketho/BlizzardInterfaceResources.git'; branch = 'forever' }
)
if ($WithLuaLs) { $refs += @{ name = 'wow-api-src'; url = 'https://github.com/Logonz/WoW-API.git'; branch = 'main' } }

foreach ($r in $refs) {
    $dir = Join-Path $Vendor $r.name
    if ($Status) {
        if (Test-Path $dir) { $line = (& git -C $dir log -1 --format='%h %cs %s' 2>$null); Write-Output ("{0,-30} {1}" -f $r.name, $line) }
        else { Write-Output ("{0,-30} (missing)" -f $r.name) }
        continue
    }
    if (Test-Path (Join-Path $dir '.git')) {
        Write-Host "Updating $($r.name) ($($r.branch))..."
        & git -C $dir fetch --depth 1 origin $r.branch 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Error "git fetch failed for $($r.name)" }
        & git -C $dir reset -q --hard FETCH_HEAD
    } else {
        Write-Host "Cloning $($r.name) ($($r.branch), shallow)..."
        & git clone -q --depth 1 --branch $r.branch $r.url $dir
    }
    if ($LASTEXITCODE -ne 0) { Write-Error "git failed for $($r.name)" }
    Write-Output ("{0,-30} {1}" -f $r.name, (& git -C $dir log -1 --format='%h %cs %s'))
}
if ($Status) { exit 0 }

# `python --version`, not Get-Command: the Microsoft Store stub is on PATH and exits non-zero without Python.
$ErrorActionPreference = 'Continue'
$null = & python --version 2>&1
$hasPython = $? -and $LASTEXITCODE -eq 0
$ErrorActionPreference = 'Stop'
if ($hasPython) {
    & python -I (Join-Path $Root 'tools\gen_luacheck_globals.py') (Join-Path $Vendor 'BlizzardInterfaceResources\Resources') (Join-Path $Root 'tools\luacheck-wow-globals.lua')
    if ($LASTEXITCODE -ne 0) { Write-Error 'luacheck globals generation failed (tools\gen_luacheck_globals.py)' }
} else {
    Write-Warning 'Python 3 does not run here (not on PATH, or only the Microsoft Store stub): tools\luacheck-wow-globals.lua was not regenerated.'
}

if ($WithLuaLs) {
    $src = Join-Path $Vendor 'wow-api-src'
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Write-Warning 'uv not installed; skipping LuaLS meta (pip install uv, then rerun with -WithLuaLs).' }
    else {
        Push-Location $src
        try { & uv run generate.py sources; & uv run generate.py } finally { Pop-Location }
        $out = Join-Path $src 'WoW-API'
        if (Test-Path $out) { Write-Output "LuaLS library: $out\library" }
    }
}
Write-Host 'vendor sync done.' -ForegroundColor Green
