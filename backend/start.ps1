#!/usr/bin/env pwsh

# Get the script directory
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

# Set default host and port (avoid $HOST as it's a reserved variable in PowerShell)
$SERVER_HOST = if ($env:HOST) { $env:HOST } else { "0.0.0.0" }
$SERVER_PORT = if ($env:PORT) { $env:PORT } else { "8000" }

$KEY_FILE = ".secret_key"

# Only generate if SECRET_KEY is not set
if (-not $env:SECRET_KEY) {
    Write-Host "SECRET_KEY not provided. Falling back to file." -ForegroundColor Yellow

    if (-not (Test-Path $KEY_FILE)) {
        Write-Host "Generating SECRET_KEY" -ForegroundColor Green
        
        # Check if openssl is available
        if (Get-Command openssl -ErrorAction SilentlyContinue) {
            $secret = openssl rand -base64 32
            $secret | Out-File -FilePath $KEY_FILE -NoNewline -Encoding utf8
        } else {
            # Fallback: Generate random key using .NET
            Write-Host "openssl not found, using .NET crypto to generate key" -ForegroundColor Yellow
            $bytes = New-Object byte[] 32
            $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
            $rng.GetBytes($bytes)
            $secret = [Convert]::ToBase64String($bytes)
            $secret | Out-File -FilePath $KEY_FILE -NoNewline -Encoding utf8
        }
    }

    $env:SECRET_KEY = Get-Content $KEY_FILE -Raw
    $env:SECRET_KEY = $env:SECRET_KEY.Trim()
}

# Start uvicorn server
Write-Host "Starting server on ${SERVER_HOST}:${SERVER_PORT}..." -ForegroundColor Green
& uvicorn app.main:app --host $SERVER_HOST --port $SERVER_PORT --forwarded-allow-ips='*'