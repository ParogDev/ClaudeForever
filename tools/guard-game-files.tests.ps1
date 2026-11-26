<#
.SYNOPSIS
    Feeds PreToolUse payloads to tools\guard-game-files.ps1 (as the hook runs it: JSON on stdin) and checks each
    decision: deny, note or allow.

.DESCRIPTION
    WOWF_GAME_DIR points at a scratch folder in %TEMP%, so no real game folder is touched and the "game running"
    check is false (no Wow.exe runs from the scratch folder): WTF writes come back as a note, not a deny.
    Prints one line per case and exits 1 when any case fails.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\guard-game-files.tests.ps1 [-ShowReasons]
#>
param([switch]$ShowReasons)
$ErrorActionPreference = 'Stop'
$hook = Join-Path $PSScriptRoot 'guard-game-files.ps1'
$repo = (Split-Path $PSScriptRoot -Parent) -replace '\\', '/'
$scratch = Join-Path $env:TEMP ('wowf-guard-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
$null = New-Item -ItemType Directory -Force "$scratch\_forever_\Interface\AddOns\Foo", "$scratch\_forever_\WTF"
$g = ($scratch -replace '\\', '/') + '/_forever_'
$gw = $scratch + '\_forever_'

function Invoke-Hook($payload) {
    $json = ConvertTo-Json -InputObject $payload -Depth 5 -Compress
    $psi = New-Object Diagnostics.ProcessStartInfo 'powershell', "-NoProfile -ExecutionPolicy Bypass -File `"$hook`""
    $psi.UseShellExecute = $false; $psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true
    $psi.EnvironmentVariables['WOWF_GAME_DIR'] = $scratch
    $p = [Diagnostics.Process]::Start($psi)
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $p.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length); $p.StandardInput.Close()
    $out = $p.StandardOutput.ReadToEnd(); $p.WaitForExit()
    if (-not $out.Trim()) { return @{ decision = 'allow'; reason = '' } }
    $o = ConvertFrom-Json $out
    $h = $o.hookSpecificOutput
    if ($h.permissionDecision -eq 'deny') { return @{ decision = 'deny'; reason = $h.permissionDecisionReason } }
    return @{ decision = 'note'; reason = $h.additionalContext }
}

function Shell($tool, $cmd, $cwd = $repo) { @{ tool_name = $tool; cwd = $cwd; tool_input = @{ command = $cmd } } }
function EditOf($path) { @{ tool_name = 'Edit'; cwd = $repo; tool_input = @{ file_path = $path; old_string = 'a'; new_string = 'b' } } }

$cases = @(
    @('edit through game AddOns', 'deny', (EditOf "$g/Interface/AddOns/Foo/Core.lua")),
    @('edit through game AddOns (backslashes)', 'deny', (EditOf "$gw\Interface\AddOns\Foo\Core.lua")),
    @('write WTF, game closed', 'note', (EditOf "$g/WTF/Config.wtf")),
    @('edit the repo copy', 'allow', (EditOf "$repo/AddOns/Foo/Core.lua")),
    @('bash ls with 2>/dev/null', 'allow', (Shell 'Bash' "ls `"$g/WTF`" 2>/dev/null")),
    @('bash read SavedVariables', 'allow', (Shell 'Bash' "cat `"$g/WTF/Account/X/SavedVariables/Foo.lua`" 2>&1")),
    @('bash copy out of WTF', 'allow', (Shell 'Bash' "cp `"$g/WTF/Config.wtf`" /tmp/Config.wtf")),
    @('bash redirect into game AddOns', 'deny', (Shell 'Bash' "echo x > `"$g/Interface/AddOns/Foo/a.lua`"")),
    @('bash copy into game AddOns', 'deny', (Shell 'Bash' "cp a.lua `"$g/Interface/AddOns/Foo/`"")),
    @('bash relative write after cd', 'deny', (Shell 'Bash' "cd `"$g/Interface/AddOns/Foo`" && echo x > a.lua")),
    @('bash read after cd', 'allow', (Shell 'Bash' "cd `"$g/Interface/AddOns/Foo`" && ls -la 2>/dev/null")),
    @('bash copy out after cd', 'allow', (Shell 'Bash' "cd `"$g/WTF`" && cp Config.wtf /tmp/Config.wtf")),
    @('bash sed -i in WTF, game closed', 'note', (Shell 'Bash' "sed -i s/a/b/ `"$g/WTF/Config.wtf`"")),
    @('powershell read with 2>$null', 'allow', (Shell 'PowerShell' "Get-Content `"$gw\WTF\Config.wtf`" 2>`$null")),
    @('powershell Remove-Item in game AddOns', 'deny', (Shell 'PowerShell' "Remove-Item `"$gw\Interface\AddOns\Foo`" -Recurse")),
    @('powershell Set-Content in game AddOns', 'deny', (Shell 'PowerShell' "Set-Content -Path `"$gw\Interface\AddOns\Foo\a.lua`" -Value x")),
    @('unrelated git command', 'allow', (Shell 'Bash' 'git status -sb'))
)

$failed = 0
try {
    foreach ($c in $cases) {
        $r = Invoke-Hook $c[2]
        $ok = $r.decision -eq $c[1]
        if (-not $ok) { $failed++ }
        $line = "{0} {1,-42} expected {2,-5} got {3}" -f $(if ($ok) { 'PASS' } else { 'FAIL' }), $c[0], $c[1], $r.decision
        if ($ShowReasons -and $r.reason) { $line += "`n     $($r.reason)" }
        Write-Output $line
    }
} finally {
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Output ("{0} case(s), {1} failed" -f $cases.Count, $failed)
exit ([int]($failed -gt 0))
