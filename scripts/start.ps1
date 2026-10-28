$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (!(Test-Path .env)) {
    Copy-Item .env.example .env
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $bytes = New-Object byte[] 32
    $rng.GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes)
    (Get-Content .env -Raw).Replace('replace-with-generated-secret', $secret) | Set-Content .env -Encoding utf8
    Write-Host 'Utworzono .env. Klucz znajdziesz w pliku.'
}
if (!(Test-Path .venv)) { py -3.12 -m venv .venv; if ($LASTEXITCODE -ne 0) { throw 'Zainstaluj Python 3.12' } }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Instalacja zaleznosci nie powiodla sie' }
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Testy nie przeszly' }
Write-Host 'Control Center: http://127.0.0.1:8000'
& .\.venv\Scripts\python.exe -m uvicorn jarvis.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
