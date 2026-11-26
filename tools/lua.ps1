<#
.SYNOPSIS
    Lua 5.1 checks (luacheck, busted, stylua) in Docker, so nothing Lua is installed on Windows and a local run
    uses the same tools as the addon's CI.

.DESCRIPTION
    tools\lua.ps1 check [-Path AddOns\X]   luacheck (uses the folder's .luacheckrc), twice: with the generated
                                           globals list (tools\luacheck-wow-globals.lua), then standalone, the way
                                           the addon repo's own CI runs it
    tools\lua.ps1 test  [-Path AddOns\X]   busted (needs <folder>\tests)
    tools\lua.ps1 fmt   [-Path AddOns\X]   stylua --check (add -Write to format in place)
    tools\lua.ps1 all   [-Path AddOns\X]   check, then test, then fmt
    tools\lua.ps1 build                    (re)build the image wowf/lua51 from tools\containers\lua51
    tools\lua.ps1 run "<shell command>"    anything else inside the container, workspace mounted at /work

    -Path defaults to every AddOns\* folder that has a .luacheckrc. It may also be any other folder (absolute, or
    relative to the workspace or the current directory): each target is mounted at /work/AddOns/<folder name> with
    tools\ beside it, so its .luacheckrc finds ../../tools/luacheck-wow-globals.lua wherever it lives on disk.
    Exit code is the tool's: non-zero on findings. Docker Desktop must be running; the script says so if not.

    The image carries a label with the SHA-256 of tools\containers\lua51\Dockerfile. When the Dockerfile changes
    (a pin bump), the next run sees a different hash and rebuilds; no manual build needed.
#>
param(
    [Parameter(Position = 0)][ValidateSet('check', 'test', 'fmt', 'all', 'build', 'run')][string]$Command = 'all',
    [Parameter(Position = 1)][string]$Arg,
    [string[]]$Path,
    [switch]$Write
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Image = 'wowf/lua51'

# Native command whose stderr must not become a terminating error (PowerShell 5.1 + $ErrorActionPreference Stop).
function Invoke-Quiet { $ErrorActionPreference = 'Continue'; $null = & $args[0] @($args | Select-Object -Skip 1) 2>$null; return $LASTEXITCODE }

function Test-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error 'Docker is not installed (no docker on PATH). Install Docker Desktop, start it, then rerun. tools\lua.ps1 runs luacheck, busted and stylua in a container.'
    }
    if ((Invoke-Quiet docker version --format '{{.Server.Version}}') -ne 0) {
        Write-Error 'Docker is installed but its engine is not running. Start Docker Desktop, wait until it says "Engine running", then rerun.'
    }
}

# The image is labelled with the SHA-256 of the Dockerfile it was built from. A pin bump (luacheck, busted, stylua)
# changes the hash, and Ensure-Image rebuilds instead of running the stale tools. Line endings are normalised to LF
# first, so a CRLF and an LF checkout of the same Dockerfile agree.
$LabelKey = 'wowf.dockerfile.sha256'
$DockerfileHash = & {
    $text = [IO.File]::ReadAllText((Join-Path $Root 'tools\containers\lua51\Dockerfile')) -replace "`r`n", "`n"
    $sha = [Security.Cryptography.SHA256]::Create()
    (($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($text)) | ForEach-Object { $_.ToString('x2') }) -join '')
}

function Build-Image {
    & docker build -t $Image --label "$LabelKey=$DockerfileHash" (Join-Path $Root 'tools\containers\lua51') | Out-Host
    if ($LASTEXITCODE -ne 0) { Write-Error "docker build failed for $Image" }
}

# The image's labels as docker prints them (map[key:value ...]), or $null when the image does not exist.
# The format has no double quotes: PowerShell 5.1 does not pass them to native commands intact.
function Get-ImageLabels {
    $ErrorActionPreference = 'Continue'
    $out = & docker image inspect --format '{{.Config.Labels}}' $Image 2>&1
    $text = (@($out) | ForEach-Object { "$_" }) -join "`n"
    if ($LASTEXITCODE -eq 0) { return $text }
    if ($text -match 'No such (image|object)') { return $null }
    $ErrorActionPreference = 'Stop'
    Write-Error "docker image inspect $Image failed (exit $LASTEXITCODE), not a missing image: $text"
}

function Ensure-Image {
    $labels = Get-ImageLabels
    if ($null -eq $labels) { Write-Host "Image $Image missing; building it once (a few minutes)."; Build-Image; return }
    if ($labels -notmatch [regex]::Escape("${LabelKey}:$DockerfileHash")) {
        Write-Host "Image $Image was built from another tools\containers\lua51\Dockerfile (pins changed); rebuilding."
        Build-Image
    }
}

# Runs one shell command in the container. $mounts: docker -v arguments; $wd: working directory inside.
# Returns the exit code; output goes to the host.
function Invoke-InContainer([string[]]$mounts, [string]$wd, [string]$sh) {
    # The command travels base64-encoded and is decoded by the container's sh: PowerShell 5.1 mangles double quotes
    # in native arguments. Base64 has no character it interprets. stderr lines must not become terminating errors.
    $ErrorActionPreference = 'Continue'
    $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sh))
    # Decoded to a file, not piped into sh: sh reading its script from stdin would hand the rest of a multi-line
    # command to the first child that reads stdin.
    $run = "echo $b64 | base64 -d > /tmp/wowf-cmd.sh && sh /tmp/wowf-cmd.sh"
    $dockerArgs = @('run', '--rm')
    foreach ($m in $mounts) { $dockerArgs += @('-v', $m) }
    $dockerArgs += @('-w', $wd, $Image, $run)
    & docker @dockerArgs 2>&1 | ForEach-Object { "$_" } | Out-Host
    return $LASTEXITCODE
}

# Full paths of the folders to check.
function Get-Targets {
    if ($Path) {
        return @($Path | ForEach-Object {
            $p = $_
            $candidates = if ([IO.Path]::IsPathRooted($p)) { @($p) } else { @((Join-Path $Root $p), (Join-Path (Get-Location).Path $p)) }
            $hit = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Container } | Select-Object -First 1
            if (-not $hit) { Write-Error "-Path ${p}: no such folder (looked in $($candidates -join ', '))." }
            (Resolve-Path -LiteralPath $hit).Path
        })
    }
    $t = @(Get-ChildItem (Join-Path $Root 'AddOns') -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName '.luacheckrc') } | ForEach-Object { $_.FullName })
    if (-not $t.Count) { Write-Host 'No AddOns\*\.luacheckrc found; nothing to check. (Make one with the new-addon skill.)' }
    return $t
}

function Invoke-Checks([string[]]$targets) {
    if ($Command -eq 'build') { Build-Image; return 0 }
    Ensure-Image
    if ($Command -eq 'run') { return (Invoke-InContainer @("${Root}:/work") '/work' $Arg) }

    $steps = switch ($Command) { 'check' { @('check') } 'test' { @('test') } 'fmt' { @('fmt') } 'all' { @('check', 'test', 'fmt') } }
    $tools = Join-Path $Root 'tools'
    $failed = 0
    foreach ($full in $targets) {
        $leaf = Split-Path $full -Leaf
        $mounts = @("${tools}:/work/tools:ro", "${full}:/work/AddOns/$leaf")
        foreach ($s in $steps) {
            $sh = switch ($s) {
                # Twice: first with the generated globals list beside it (../../tools), then from a copy outside
                # /work, as the addon repo's own CI runs it, where that file is missing and the .luacheckrc falls back
                # to its short list. A global missing from the short list would otherwise pass here and fail CI.
                'check' { 'luacheck . --no-color && echo standalone, as the addon repo CI runs it: && rm -rf /tmp/standalone && cp -r . /tmp/standalone && cd /tmp/standalone && test ! -e ../../tools/luacheck-wow-globals.lua && luacheck . --no-color' }
                'test'  { if (Test-Path (Join-Path $full 'tests')) { 'busted --verbose' } else { $null } }
                'fmt'   { if ($Write) { 'stylua .' } else { 'stylua --check .' } }
            }
            if (-not $sh) { continue }
            Write-Host "== $leaf : $s" -ForegroundColor Cyan
            $code = Invoke-InContainer $mounts "/work/AddOns/$leaf" $sh
            if ($code -ne 0) { $failed++; Write-Host "FAILED ($s) in $full (exit $code)" -ForegroundColor Red }
        }
    }
    if ($failed) { Write-Host "$failed step(s) failed." -ForegroundColor Red; return 1 }
    Write-Host 'All green.' -ForegroundColor Green
    return 0
}

Test-Docker
$targets = @(Get-Targets)
exit (Invoke-Checks $targets)
