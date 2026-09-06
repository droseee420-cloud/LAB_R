$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install and start Docker Desktop with Linux containers.' }
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with Linux containers, then retry.' }
    if (-not (Test-Path -LiteralPath '.env')) {
        $template = Get-Content -LiteralPath '.env.example' -Raw
        foreach ($placeholder in @('REPLACE_WITH_RANDOM_SECRET', 'REPLACE_WITH_AT_LEAST_32_RANDOM_CHARACTERS')) {
            $bytes = New-Object byte[] 32
            $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
            try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
            $value = ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
            $template = $template.Replace($placeholder, $value)
        }
        [IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $template, (New-Object Text.UTF8Encoding($false)))
    }
    & node scripts/workspace.mjs stack up --build --wait --wait-timeout 180
    if ($LASTEXITCODE -ne 0) { throw 'Local services failed to become healthy.' }
    Write-Host 'Local site: http://localhost:8080 (or PUBLIC_URL from .env).'
} finally { Pop-Location }
