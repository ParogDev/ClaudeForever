<#
.SYNOPSIS
    Wait for the user's next /reload (or logout) and report what the addon wrote: its selftest table and any
    BugGrabber errors. The read-back half of the verify loop (docs\verify-loop.md).

.DESCRIPTION
    tools\reload-wait.ps1 <AddonName> [-TimeoutMinutes 20] [-Var <SavedVariable>]
    tools\reload-wait.ps1 <AddonName> -File <copy of a SavedVariables .lua>   # read-back only: no wait, no game needed

    SavedVariables are written only on /reload, logout and exit, so this watches the newest
    WTF\Account\*\SavedVariables\<AddonName>.lua (the file is named after the addon; -Var, default
    <AddonName>DB, is the variable parsed inside it) and !BugGrabber.lua for a write newer than
    when it started, then prints JSON: { reloadedAt, selftest, errors[] , file }. Exit 0 = reload seen (even with
    errors: the caller judges), 2 = timeout, 3 = game not running, 4 = reload seen but the read-back broke: the JSON
    then has selftestError and/or bugGrabberError naming the link (does not parse, variable or key absent), and
    selftest is null only in that case. Never sends input to the game.
    Parsing is done by tools\wowf_sv.py (Python 3), never by executing the Lua.
    Run it in the background, then ask the user to /reload. Nothing here sends input to the game.
#>
param([Parameter(Mandatory = $true, Position = 0)][string]$Addon, [int]$TimeoutMinutes = 20, [string]$Var, [string]$File)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'game-lib.ps1')
if (-not $Var) { $Var = "${Addon}DB" }
$py = Join-Path $PSScriptRoot 'wowf_sv.py'

if ($File) {
    # Read-back only: report an existing SavedVariables file (a copy, a test fixture) without waiting or BugGrabber.
    $seen = Get-Item -LiteralPath $File
    $b0 = [datetime]::MaxValue
} else {
    if (-not (Test-GameRunning)) { Write-Output (@{ error = 'game not running' } | ConvertTo-Json -Compress); exit 3 }

    $start = Get-Date
    $svBefore = @(Get-SavedVariablesFiles $Addon | Select-Object -First 1)
    $bgBefore = @(Get-SavedVariablesFiles '!BugGrabber' | Select-Object -First 1)
    $t0 = if ($svBefore.Count) { $svBefore[0].LastWriteTime } else { [datetime]::MinValue }
    $b0 = if ($bgBefore.Count) { $bgBefore[0].LastWriteTime } else { [datetime]::MinValue }

    Write-Host "Waiting up to $TimeoutMinutes min for a /reload that writes $Addon.lua (last write: $t0)..." -ForegroundColor DarkGray
    $deadline = $start.AddMinutes($TimeoutMinutes)
    $seen = $null
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        $sv = @(Get-SavedVariablesFiles $Addon | Select-Object -First 1)
        if ($sv.Count -and $sv[0].LastWriteTime -gt $t0) { $seen = $sv[0]; Start-Sleep -Seconds 2; break }   # let the client finish the write
        if (-not (Test-GameRunning)) { break }
    }
    if (-not $seen) {
        $why = if (Test-GameRunning) { 'timeout' } else { 'game closed before a write was seen' }
        Write-Output (@{ error = $why; waitedMinutes = [math]::Round(((Get-Date) - $start).TotalMinutes, 1) } | ConvertTo-Json -Compress)
        exit 2
    }
}

# Returns @{ value } or @{ error = '<the link that broke>'; code = <wowf_sv exit code, or -1> }. --ascii keeps the
# JSON pure ASCII: PowerShell 5.1 decodes native stdout with [Console]::OutputEncoding, and a code page such as 936
# turned UTF-8 chat text into a missing quote, so ConvertFrom-Json failed and the selftest came back null. Only
# "does not parse" (exit 2) is retried: the client may still be writing the file.
function Parse-Sv([string]$file, [string]$var, [string]$path) {
    # Keep this function-scoped and keep 2>&1: under 'Stop', PS 5.1 turns each native stderr line into a terminating
    # error, and the ErrorRecord/string split below is how stderr (the wowf_sv reason) is told from the JSON.
    $ErrorActionPreference = 'Continue'
    # `python --version`, not Get-Command: the Microsoft Store stub is on PATH and exits non-zero without Python.
    $null = & python --version 2>&1
    if (-not $? -or $LASTEXITCODE -ne 0) { return @{ error = 'python 3 does not run (not on PATH, or the Microsoft Store stub)'; code = -1 } }
    $pyArgs = @($py, $file, '--var', $var, '--ascii')
    if ($path) { $pyArgs += @('--path', $path) }
    for ($try = 1; $try -le 5; $try++) {
        if ($try -gt 1) { Start-Sleep -Seconds 1 }
        $lines = @(& python -I @pyArgs 2>&1)
        $code = $LASTEXITCODE
        $stdout = @($lines | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] }) -join "`n"
        $stderr = (@($lines | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] }) | ForEach-Object { "$_" }) -join ' '
        # 2 does not parse, 3 absent: both can be a file the client is still writing (cut at a top-level boundary,
        # a whole variable is simply not there yet), so both get the retries before they count.
        if ($code -eq 2 -or $code -eq 3) { continue }
        if ($code -ne 0) { return @{ error = $(if ($stderr) { $stderr } else { "wowf_sv.py exited $code" }); code = $code } }
        try { return @{ value = ($stdout | ConvertFrom-Json) } }
        catch { return @{ error = "ConvertFrom-Json (PowerShell 5.1) refused wowf_sv output: $($_.Exception.Message)"; code = -1 } }
    }
    return @{ error = "$stderr (5 tries, 1 s apart)"; code = $code }
}

$st = Parse-Sv $seen.FullName $Var 'selftest'
$selftest = $st.value
$selftestError = if ($st.ContainsKey('error')) { "$(Split-Path -Leaf $seen.FullName): $($st.error)" } else { $null }
# PS 5.1 ConvertFrom-Json yields nothing for [] (an empty Lua table read as a list): never let that pass as a null.
if ($null -eq $selftest -and -not $selftestError) { $selftestError = "$(Split-Path -Leaf $seen.FullName): $Var.selftest parsed to null (empty table?)" }
$errors = @()
$bugGrabberError = $null
$bg = @(Get-SavedVariablesFiles '!BugGrabber' | Select-Object -First 1)
if ($bg.Count -and $bg[0].LastWriteTime -gt $b0) {
    $bgr = Parse-Sv $bg[0].FullName 'BugGrabberDB'
    # BugGrabberDB absent (fresh profile, exit 3) means no errors recorded, not a broken read-back.
    if ($bgr.ContainsKey('error') -and $bgr.code -ne 3) { $bugGrabberError = "!BugGrabber.lua: $($bgr.error)" }
    $bgdb = $bgr.value
    $sessionId = if ($bgdb -and $bgdb.PSObject.Properties['session']) { $bgdb.session } else { $null }
    foreach ($e in @(if ($bgdb) { $bgdb.errors })) {
        if ($e.message -match [regex]::Escape($Addon) -or $e.stack -match [regex]::Escape($Addon)) {
            if (-not $sessionId -or $e.session -eq $sessionId) { $errors += @{ message = $e.message; stack = $e.stack; time = $e.time; counter = $e.counter } }
        }
    }
}
$out = @{ reloadedAt = $seen.LastWriteTime.ToString('s'); file = $seen.FullName; selftest = $selftest; errors = $errors; errorCount = $errors.Count }
if ($selftestError) { $out.selftestError = $selftestError }
if ($bugGrabberError) { $out.bugGrabberError = $bugGrabberError }
Write-Output ($out | ConvertTo-Json -Depth 12)
if ($selftestError -or $bugGrabberError) {
    Write-Host "Reload seen, but the read-back broke: $(@($selftestError, $bugGrabberError) -ne $null -join '; ')" -ForegroundColor Red
    exit 4
}
exit 0
