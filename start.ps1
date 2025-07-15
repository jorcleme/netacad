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
instructor_login = os.environ.get('INSTRUCTOR_LOGIN', '')
instructor_password = os.environ.get('INSTRUCTOR_PASSWORD', '')

if (not instructor_login or not instructor_password or 
    instructor_login == 'your_instructor_email@domain.com' or 
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
INSTRUCTOR_LOGIN="$instructorEmail"
INSTRUCTOR_PASSWORD="$plainPassword"
"@
    
    $envContent | Out-File -FilePath ".env.development" -Encoding UTF8
    Write-Host "Credentials saved to .env.development" -ForegroundColor Green
    Write-Host ""
}

# Starting NetAcad Course Export...
Write-Host "Starting NetAcad Course Export..." -ForegroundColor Cyan
& "env\Scripts\Activate.ps1"
python -m course_export

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
