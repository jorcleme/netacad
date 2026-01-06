# NetAcad Course Export Tool - PowerShell Runner
# More robust alternative for Windows users who prefer PowerShell

Write-Host "NetAcad Course Export Tool" -ForegroundColor Cyan
Write-Host "=" * 40 -ForegroundColor Cyan
Write-Host ""

# Function to check if command exists
function Test-Command($cmdname) {
    return [bool](Get-Command -Name $cmdname -ErrorAction SilentlyContinue)
}

# Check if Python is installed
if (-not (Test-Command "python")) {
    Write-Host "ERROR: Python is not installed or not in PATH!" -ForegroundColor Red
    Write-Host "Please install Python 3.11+ from https://python.org" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Display Python version
$pythonVersion = python --version
Write-Host "Using $pythonVersion" -ForegroundColor Green
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "env\Scripts\python.exe")) {
    Write-Host "Setting up virtual environment..." -ForegroundColor Yellow
    
    # Create virtual environment
    python -m venv env
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    # Activate and install dependencies
    & "env\Scripts\Activate.ps1"
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install dependencies!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    Write-Host "Setup completed successfully!" -ForegroundColor Green
    Write-Host ""
}

# Check if Playwright browsers are installed
Write-Host "Checking Playwright browser installation..." -ForegroundColor Cyan
$playwrightCheck = & "env\Scripts\python.exe" -c @"
import sys
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            p.chromium.launch(headless=True)
            print('installed')
            sys.exit(0)
        except Exception:
            print('missing')
            sys.exit(1)
except ImportError:
    print('missing')
    sys.exit(1)
"@ 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Playwright browsers (one-time setup)..." -ForegroundColor Yellow
    Write-Host "This may take a few minutes..." -ForegroundColor Yellow
    & "env\Scripts\python.exe" -m playwright install chromium
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Playwright browsers installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Warning: Playwright browser installation may have failed." -ForegroundColor Yellow
        Write-Host "You can manually run: playwright install chromium" -ForegroundColor Yellow
    }
    Write-Host ""
} else {
    Write-Host "✅ Playwright browsers already installed" -ForegroundColor Green
    Write-Host ""
}

# Check environment configuration
Write-Host "Checking environment configuration..." -ForegroundColor Cyan
$envCheck = & "env\Scripts\python.exe" -c @"
import sys
sys.path.append('.')
from constants import create_env_template, validate_setup
import os
from pathlib import Path

# Create .env.development if it doesn't exist
create_env_template('.env.development')

# Load environment variables
from dotenv import load_dotenv, find_dotenv
env_file_path = find_dotenv(filename='.env.development', usecwd=True)
load_dotenv(env_file_path)

# Check if credentials are set and not default values
instructor_id = os.environ.get('INSTRUCTOR_ID', '')
instructor_password = os.environ.get('INSTRUCTOR_PASSWORD', '')

if (not instructor_id or not instructor_password or
    instructor_id == 'your_instructor_email@domain.com' or
    instructor_password == 'your_password'):
    print('\n  NetAcad credentials not configured or using default values.')
    sys.exit(1)
else:
    print('✅ Credentials configured successfully!')
    sys.exit(0)
"@

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Please enter your NetAcad instructor credentials:" -ForegroundColor Yellow
    
    # Prompt for credentials
    $instructorEmail = Read-Host "Instructor Email"
    $instructorPassword = Read-Host "Instructor Password" -AsSecureString
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($instructorPassword))
    
    # Update .env.development file
    $envContent = @"
# Instructor login credentials for NetAcad
INSTRUCTOR_ID="$instructorEmail"
INSTRUCTOR_PASSWORD="$plainPassword"
"@
    
    $envContent | Out-File -FilePath ".env.development" -Encoding UTF8
    Write-Host "Credentials saved to .env.development" -ForegroundColor Green
    Write-Host ""
}

# Starting NetAcad Course Export...
Write-Host "Starting NetAcad Course Export (Playwright version)..." -ForegroundColor Cyan
Write-Host "Using faster Playwright automation (2-3x faster than Selenium)" -ForegroundColor Gray
& "env\Scripts\Activate.ps1"
python courses_playwright.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Application completed successfully!" -ForegroundColor Green
    Write-Host "Check the 'data' directory for your exported files." -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "Application encountered an error!" -ForegroundColor Red
    Write-Host "Please check the logs in the 'logs' directory." -ForegroundColor Yellow
}

Write-Host ""
Read-Host "Press Enter to close"
