param([string]$Config = "$PSScriptRoot/config.local.json", [switch]$DryRun)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location -LiteralPath $projectRoot
try {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) { throw 'Install Python 3.13 or newer and its Windows launcher. Restart the terminal.' }
    & py -3 -c 'import sys; assert sys.version_info >= (3, 13)'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.13 or newer is required.' }
    $deployPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $deployPython)) {
        & py -3 -m venv (Join-Path $PSScriptRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Cannot create deployment virtual environment.' }
    }
    & $deployPython -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot install deployment dependencies.' }
    $deployArgs = @('-m', 'scripts.deploy.client', '--config', $Config)
    if ($DryRun) { $deployArgs += '--dry-run' }
    & $deployPython @deployArgs
    if ($LASTEXITCODE -ne 0) { throw 'Deployment did not complete.' }
} finally { Pop-Location }
