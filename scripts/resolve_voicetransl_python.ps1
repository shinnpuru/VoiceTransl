param(
    [string]$Install = 'F:\VoiceTransl',
    [string]$Python = $env:VOICETRANSL_PYTHON
)

$ErrorActionPreference = 'Stop'
$RuntimeDir = Join-Path $Install 'agent-runtime'
$CacheFile = Join-Path $RuntimeDir 'python.json'

function Find-PythonExecutable([string]$Candidate, [string[]]$PrefixArgs = @()) {
    if (!$Candidate) { return $null }
    try {
        $Result = & $Candidate @PrefixArgs -I -c 'import sys; assert sys.version_info >= (3, 10); print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $Result) {
            $Resolved = ([string]($Result | Select-Object -Last 1)).Trim()
            if (Test-Path -LiteralPath $Resolved -PathType Leaf) { return $Resolved }
        }
    } catch { }
    return $null
}

$SelectedPython = $null
if ($Python) {
    $SelectedPython = Find-PythonExecutable $Python
    if (!$SelectedPython) { throw 'The explicitly configured Python is unavailable or older than 3.10.' }
}

if (!$SelectedPython -and (Test-Path -LiteralPath $CacheFile)) {
    try {
        $Cached = Get-Content -LiteralPath $CacheFile -Raw | ConvertFrom-Json
        $SelectedPython = Find-PythonExecutable $Cached.python
    } catch { }
}

if (!$SelectedPython) {
    # Fixed optional environment, legacy environment, then the source checkout.
    $Candidates = @(
        (Join-Path $RuntimeDir 'venv\Scripts\python.exe'),
        (Join-Path (Split-Path $Install -Parent) 'VoiceTransl-agent-venv\Scripts\python.exe'),
        (Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe')
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            $SelectedPython = Find-PythonExecutable $Candidate
            if ($SelectedPython) { break }
        }
    }
}

if (!$SelectedPython) {
    $PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($PythonCommand -and $PythonCommand.Source -notmatch '\\WindowsApps\\') {
        $SelectedPython = Find-PythonExecutable $PythonCommand.Source
    }
}
if (!$SelectedPython) {
    $Launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($Launcher) { $SelectedPython = Find-PythonExecutable $Launcher.Source @('-3') }
}
if (!$SelectedPython) {
    throw 'No Python 3.10+ found. Configure VOICETRANSL_PYTHON or provision one persistent runtime once; this resolver never creates a venv or installs packages.'
}

$CacheText = @{ python = $SelectedPython } | ConvertTo-Json -Compress
try {
    $ExistingText = if (Test-Path -LiteralPath $CacheFile) {
        [IO.File]::ReadAllText($CacheFile)
    } else { '' }
    if ($ExistingText -ne $CacheText) {
        New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
        [IO.File]::WriteAllText($CacheFile, $CacheText, [Text.UTF8Encoding]::new($false))
    }
} catch {
    Write-Warning 'Could not cache the interpreter path. Reuse the returned absolute path or set VOICETRANSL_PYTHON.'
}
Write-Output $SelectedPython
