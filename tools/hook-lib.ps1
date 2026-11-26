<#
.SYNOPSIS
    Shared helpers for the PreToolUse guard tools\guard-game-files.ps1 (.claude\settings.json runs it). Dot-source
    it; it defines functions only.

.DESCRIPTION
    A guard function takes the parsed hook input and returns $null (allow, nothing to say), New-Deny <reason> or
    New-Note <text>. Guards never call exit; Format-HookAnswer turns the answer into hook JSON.
#>

function Norm([string]$p) {
    if (-not $p) { return $null }
    $p = $p.Trim('"', "'") -replace '\\', '/'
    if ($p -match '^/([a-zA-Z])/(.*)$') { $p = "$($Matches[1]):/$($Matches[2])" }
    return $p.TrimEnd('/')
}

function Under([string]$path, [string]$root) {
    if (-not $path -or -not $root) { return $false }
    $p = $path.ToLowerInvariant(); $r = $root.ToLowerInvariant()
    return ($p -eq $r -or $p.StartsWith("$r/"))
}

function New-Deny([string]$why) { return [pscustomobject]@{ kind = 'deny'; text = $why } }
function New-Note([string]$text) { return [pscustomobject]@{ kind = 'note'; text = $text } }

# Hook JSON for one answer (or $null when there is nothing to say).
function Format-HookAnswer($answer) {
    if (-not $answer) { return $null }
    $h = if ($answer.kind -eq 'deny') { @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $answer.text } }
         else { @{ hookEventName = 'PreToolUse'; additionalContext = $answer.text } }
    return (ConvertTo-Json -InputObject @{ hookSpecificOutput = $h } -Depth 5 -Compress)
}

# Shell-ish tokenizer: whitespace-separated words with their quotes removed. Adjacent quoted and unquoted parts are one
# word (-m"a b", --message="a b"). Bash ($ps false): '...' literal; $'...' with \x escapes; inside "..." (or $"...")
# a backslash escapes " \ $ and the backtick; outside quotes it escapes shell syntax (quotes, $, `, \, ( ) ; & | < >,
# whitespace) and is kept before anything else, so an unquoted C:\Users\x stays a Windows path. PowerShell ($ps
# true): the backtick escapes outside '...', and a doubled quote ("" in "...", '' in '...') is one quote. A here-string
# (@'...'@, @"..."@) starting a word is one token, kept verbatim.
$script:HereStringRx = New-Object regex '\G(@''[ \t]*\r?\n[\s\S]*?\n''@|@"[ \t]*\r?\n[\s\S]*?\n"@)'
function Tokens([string]$s, [bool]$ps = $false) {
    $esc = if ($ps) { [char]'`' } else { [char]'\' }
    $out = New-Object System.Collections.Generic.List[string]
    $b = New-Object System.Text.StringBuilder
    $inWord = $false
    $i = 0
    while ($i -lt $s.Length) {
        $c = $s[$i]
        if (-not $inWord) {
            if ([char]::IsWhiteSpace($c)) { $i++; continue }
            if ($c -eq '@') {
                $h = $script:HereStringRx.Match($s, $i)
                if ($h.Success) { $out.Add($h.Value); $i += $h.Length; continue }
            }
            $inWord = $true
        }
        if ([char]::IsWhiteSpace($c)) { $out.Add($b.ToString()); [void]$b.Clear(); $inWord = $false; $i++; continue }
        if ($c -eq $esc -and $i + 1 -lt $s.Length) {
            if ($ps -or $s[$i + 1] -match '[''"$`\\();&|<>\s]') { [void]$b.Append($s[$i + 1]); $i += 2 }
            else { [void]$b.Append($c); $i++ }
            continue
        }
        if (-not $ps -and $c -eq '$' -and $i + 1 -lt $s.Length -and $s[$i + 1] -eq "'") {   # bash ANSI-C $'...'
            $i += 2
            while ($i -lt $s.Length -and $s[$i] -ne "'") {
                if ($s[$i] -eq '\' -and $i + 1 -lt $s.Length) { [void]$b.Append($s[$i + 1]); $i += 2; continue }
                [void]$b.Append($s[$i]); $i++
            }
            $i++; continue
        }
        if (-not $ps -and $c -eq '$' -and $i + 1 -lt $s.Length -and $s[$i + 1] -eq '"') { $i++; continue }   # $"..." is "..."
        if ($c -eq "'") {
            $i++
            while ($i -lt $s.Length) {
                if ($s[$i] -eq "'") {
                    if ($ps -and $i + 1 -lt $s.Length -and $s[$i + 1] -eq "'") { [void]$b.Append("'"); $i += 2; continue }
                    break
                }
                [void]$b.Append($s[$i]); $i++
            }
            $i++; continue
        }
        if ($c -eq '"') {
            $i++
            while ($i -lt $s.Length) {
                $d = $s[$i]
                if ($d -eq '"') {
                    if ($ps -and $i + 1 -lt $s.Length -and $s[$i + 1] -eq '"') { [void]$b.Append('"'); $i += 2; continue }
                    break
                }
                if ($d -eq $esc -and $i + 1 -lt $s.Length -and ($ps -or '"\$`'.Contains([string]$s[$i + 1]))) { [void]$b.Append($s[$i + 1]); $i += 2; continue }
                [void]$b.Append($d); $i++
            }
            $i++; continue
        }
        [void]$b.Append($c); $i++
    }
    if ($inWord) { $out.Add($b.ToString()) }
    $out.ToArray()
}

# Same length as $s, with quoted text masked to 'x': all of '...'; inside "..." everything but $, backticks, word
# characters and the '(' of '$(' (bash expands those there). Unquoted backslash escapes of shell syntax are masked too.
# $ps: PowerShell quoting instead (escape is the backtick; "..." is masked whole).
function Mask([string]$s, [bool]$ps = $false) {
    $esc = if ($ps) { [char]'`' } else { [char]'\' }
    $b = New-Object System.Text.StringBuilder $s.Length
    $state = 0   # 0 unquoted, 1 '...', 2 "...", 3/4 PowerShell here-string @'...'@ / @"..."@, 5 bash $'...'
    for ($i = 0; $i -lt $s.Length; $i++) {
        $c = $s[$i]
        if ($state -eq 5) {
            if ($c -eq '\' -and $i + 1 -lt $s.Length) { [void]$b.Append('xx'); $i++ }
            elseif ($c -eq "'") { $state = 0; [void]$b.Append($c) }
            else { [void]$b.Append('x') }
        } elseif (-not $ps -and $state -eq 0 -and $c -eq '$' -and $i + 1 -lt $s.Length -and $s[$i + 1] -eq "'") {
            $state = 5; [void]$b.Append("`$'"); $i++
        } elseif ($state -eq 3 -or $state -eq 4) {   # PowerShell here-string: ends at a line starting '@ / "@
            $q = if ($state -eq 3) { "'" } else { '"' }
            if ($c -eq "`n" -and $i + 2 -lt $s.Length -and $s[$i + 1] -eq $q -and $s[$i + 2] -eq '@') { [void]$b.Append("x$q@"); $i += 2; $state = 0 }
            else { [void]$b.Append('x') }
        } elseif ($ps -and $state -eq 0 -and $c -eq '@' -and $i + 2 -lt $s.Length -and $s[$i + 1] -in @("'", '"') -and $s.Substring($i + 2) -match '^[ \t]*\r?\n') {
            $state = if ($s[$i + 1] -eq "'") { 3 } else { 4 }; [void]$b.Append('@' + $s[$i + 1]); $i++
        } elseif ($state -eq 1) {
            if ($c -eq "'") { $state = 0; [void]$b.Append($c) } else { [void]$b.Append('x') }
        } elseif ($state -eq 2) {
            if ($c -eq $esc -and $i + 1 -lt $s.Length) { [void]$b.Append('xx'); $i++ }
            elseif ($c -eq '"') { $state = 0; [void]$b.Append($c) }
            elseif (-not $ps -and ($c -match '[\w$`{]' -or ($c -eq '(' -and $i -gt 0 -and $s[$i - 1] -eq '$'))) { [void]$b.Append($c) }
            else { [void]$b.Append('x') }
        } else {
            if ($c -eq $esc -and $i + 1 -lt $s.Length -and ($ps -or $s[$i + 1] -match '[''"$`\\();&|<>\s]')) { [void]$b.Append('xx'); $i++ }
            else { if ($c -eq "'") { $state = 1 } elseif ($c -eq '"') { $state = 2 }; [void]$b.Append($c) }
        }
    }
    return $b.ToString()
}

# The command's segments (split on && || ; | and newlines outside quotes), trimmed: @{ m = masked; o = original }.
# $m is Mask's output for the same command.
function Segments([string]$cmd, [string]$m) {
    $seps = @([regex]::Matches($m, '&&|\|\||[;|\n]'))
    $starts = @(0) + @($seps | ForEach-Object { $_.Index + $_.Length })
    $ends = @($seps | ForEach-Object { $_.Index }) + @($m.Length)
    for ($k = 0; $k -lt $starts.Count; $k++) {
        $ms = $m.Substring($starts[$k], $ends[$k] - $starts[$k]); $os = $cmd.Substring($starts[$k], $ends[$k] - $starts[$k])
        $lead = $ms.Length - $ms.TrimStart().Length
        $ms = $ms.Substring($lead).TrimEnd(); $os = $os.Substring($lead, $ms.Length)
        if ($ms) { @{ m = $ms; o = $os } }
    }
}

# Adds .dir to each segment: the directory it runs in, following cd / pushd / popd / cd - (and Set-Location,
# Push-Location, sl, Pop-Location in the PowerShell tool) from $cwd. A cd segment itself gets .cd = $true.
function Add-SegmentDirs($segments, [string]$cwd, [string]$tool) {
    $cdBase = $cwd; $cdPrev = $cwd; $cdStack = @()
    foreach ($seg in $segments) {
        $s = $seg.o
        $seg.cd = $false
        if ($s -match '^(?i)(popd|Pop-Location)$') {
            if ($cdStack.Count) { $cdPrev = $cdBase; $cdBase = $cdStack[-1]; $cdStack = @($cdStack | Select-Object -SkipLast 1) }
            $seg.cd = $true
        } elseif ($s -match '^(?i)(cd|pushd|sl|Set-Location|Push-Location)(?:\s+--\s+|\s+-(?:Literal)?Path(?::\s*|\s+)|\s+)(?:"([^"]+)"|''([^'']+)''|(\S+))$') {
            $seg.cd = $true
            $d = Norm (@($Matches[2], $Matches[3], $Matches[4]) | Where-Object { $_ } | Select-Object -First 1)
            # cd -: bash goes to the previous directory; Windows PowerShell 5.1 fails and stays put.
            if ($d -eq '-') { if ($tool -eq 'Bash') { $t = $cdBase; $cdBase = $cdPrev; $cdPrev = $t } }
            else {
                if ($Matches[1] -in @('pushd', 'Push-Location')) { $cdStack += $cdBase }
                $cdPrev = $cdBase
                $cdBase = if ($d -match '^([a-zA-Z]:)?/') { $d } else { "$cdBase/$d" }
            }
        }
        $seg.dir = $cdBase
    }
}

# A shell call's command, masked, split into segments with their directories: @{ cmd; masked; segments }.
function Get-ShellContext($in) {
    $tool = [string]$in.tool_name
    $cmd = [string]$in.tool_input.command
    $masked = Mask $cmd ($tool -eq 'PowerShell')
    $segments = @(Segments $cmd $masked)
    foreach ($seg in $segments) { $seg.ps = ($tool -eq 'PowerShell') }   # quoting rules for Tokens
    Add-SegmentDirs $segments (Norm ([string]$in.cwd)) $tool
    return @{ cmd = $cmd; masked = $masked; segments = $segments }
}
