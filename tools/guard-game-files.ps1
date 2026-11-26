<#
.SYNOPSIS
    Claude Code PreToolUse hook (.claude\settings.json) that keeps Claude out of the game's own folders.

.DESCRIPTION
    - _forever_\WTF\** (Config.wtf, SavedVariables, bindings, chat settings): any Edit/Write and any obvious shell
      write (> >>, Set-Content, Out-File, Add-Content, tee, sed -i, rm/Remove-Item, cp/mv/Copy-Item/Move-Item onto
      it) is DENIED while Wow.exe runs: the client rewrites these on /reload and logout and would silently drop the
      edit. With the game closed the write is allowed with a note.
    - _forever_\Interface\AddOns\** : edits through the game path are ALWAYS denied. Your own addons are junctions
      into this workspace (tools\link-addons.ps1): edit AddOns\<Name>\... here, so the change is in git. Every other
      folder there is an installed addon that belongs to you, not to Claude.
    Reads are never touched. Any error fails open with a note. Game folder from WOWF_GAME_DIR (tools\game-lib.ps1).

    As a hook: hook JSON on stdin, hook JSON (or nothing) on stdout, exit 0. Dot-sourced (tests): defines
    Invoke-GuardGameFiles $in $ctx -> $null | New-Deny | New-Note.
#>
. (Join-Path $PSScriptRoot 'game-lib.ps1')
. (Join-Path $PSScriptRoot 'hook-lib.ps1')

function Get-GameGuardPaths {
    $f = (Get-ForeverDir) -replace '\\', '/'
    return @{ wtf = "$f/WTF"; addons = "$f/Interface/AddOns" }
}

# Paths a shell segment writes to, judged from the command text. Stream merges and null sinks (2>&1, 2>/dev/null,
# >$null, 2>NUL) are not writes; for cp / Copy-Item only the last path is written to (the sources are read).
function Get-ShellWriteTargets($seg) {
    $t = @(Tokens $seg.o ([bool]$seg.ps))
    $out = New-Object System.Collections.Generic.List[string]
    $m = $seg.m -replace '[0-9*]?>{1,2}\s*(&[0-9]|/dev/null(?![\w/.-])|\$null\b|NUL\b)', ''
    $isWrite = $m -match '(^|[^<>=-])>{1,2}\s*\S' -or
        $m -match '(?i)(^|[\s(])(Set-Content|Out-File|Add-Content|tee|Tee-Object|sed\s+-i\S*|rm|Remove-Item|del|erase|mv|Move-Item|ni|New-Item|mkdir|md|rmdir|rd|touch|truncate)\b'
    $isCopy = $m -match '(?i)(^|[\s(])(cp|Copy-Item|copy|xcopy|robocopy)\b'
    # Run from inside the game folder (after a cd): relative words may be paths there too.
    $inGame = [string]$seg.dir -match '(?i)_forever_'
    if ($isWrite) {
        foreach ($x in $t) {
            if ($x -match '(?i)_forever_|[\\/]WTF([\\/]|$)|Interface[\\/]+AddOns') { $out.Add((Norm $x)) }
            elseif ($inGame -and $x -and $x -notmatch '^(-|[<>&|]|([a-zA-Z]:)?[\\/])' -and $x -ne $t[0]) { $out.Add((Norm $x)) }
        }
    } elseif ($isCopy) {
        $paths = @($t | Select-Object -Skip 1 | Where-Object { $_ -notmatch '^-' })
        if ($paths.Count -ge 2) {
            $dest = $paths[-1]
            if ($dest -match '(?i)_forever_|[\\/]WTF([\\/]|$)|Interface[\\/]+AddOns' -or ($inGame -and $dest -notmatch '^([a-zA-Z]:)?[\\/]')) { $out.Add((Norm $dest)) }
        }
    }
    return $out
}

function Invoke-GuardGameFiles($in, $ctx) {
    $tool = [string]$in.tool_name
    $paths = Get-GameGuardPaths
    $targets = @()
    if ($tool -in @('Edit', 'Write', 'MultiEdit', 'NotebookEdit')) {
        $p = Norm ([string]$in.tool_input.file_path)
        if (-not $p -and $in.tool_input.notebook_path) { $p = Norm ([string]$in.tool_input.notebook_path) }
        if ($p) { $targets += $p }
    } elseif ($tool -in @('Bash', 'PowerShell')) {
        if (-not $ctx) { $ctx = Get-ShellContext $in }
        foreach ($seg in $ctx.segments) {
            foreach ($w in (Get-ShellWriteTargets $seg)) {
                $abs = if ($w -match '^([a-zA-Z]:)?/') { $w } else { "$($seg.dir)/$w" }
                $targets += $abs
            }
        }
    } else { return $null }
    if (-not $targets.Count) { return $null }

    foreach ($p in $targets) {
        if (Under $p $paths.addons) {
            return New-Deny "Not through the game folder: $p is inside _forever_\Interface\AddOns. Your own addons are junctions into this workspace: edit AddOns\<Name>\... here (same file, tracked by git). Any other folder there is an installed addon; leave it alone."
        }
        if (Under $p $paths.wtf) {
            if (Test-GameRunning) {
                return New-Deny "Wow.exe is running: $p is under _forever_\WTF, which the client rewrites on /reload and logout, so the edit would be lost. Close the game (or log out to the character screen and exit) first."
            }
            return New-Note "Writing under _forever_\WTF with the game closed: fine, but the client overwrites it on its next save, and keeps a .lua.bak of the old file beside it."
        }
    }
    return $null
}

# As a hook: stdin in, hook JSON out. Not when dot-sourced (tests).
if ($MyInvocation.InvocationName -ne '.' -and [Console]::IsInputRedirected) {
    [Console]::InputEncoding = [Text.Encoding]::UTF8
    [Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
    $r = $null
    try {
        $raw = [Console]::In.ReadToEnd()
        # Fast path: nothing in the call names the game folder (the cwd is in the JSON too), so nothing to judge.
        if ($raw -notmatch '(?i)_forever_|\bWTF\b|Interface(\\\\|/)+AddOns') { exit 0 }
        $in = ConvertFrom-Json $raw
        $r = Invoke-GuardGameFiles $in $null
    } catch { $r = New-Note "guard-game-files failed open: $($_.Exception.Message) (tools\guard-game-files.ps1)." }
    if ($r) { Write-Output (Format-HookAnswer $r) }
    exit 0
}
