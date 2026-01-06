#!/bin/bash
# NetAcad Course Export Tool - Bash Runner

echo -e "\e[1;36mNetAcad Course Export Tool\e[0m"
echo -e "\e[1;36m========================================\e[0m"
echo ""

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Check if Python is installed
if ! command_exists python3; then
  echo -e "\e[1;31mERROR: Python is not installed or not in PATH!\e[0m"
  echo -e "\e[1;33mPlease install Python 3.11+ from https://python.org\e[0m"
  echo -e "\e[1;33mOn most Linux distributions, you can run: sudo apt install python3 python3-venv\e[0m"
  read -p "Press Enter to exit"
  exit 1
fi

# Display Python version
PYTHON_VERSION=$(python3 --version)
echo -e "\e[1;32mUsing $PYTHON_VERSION\e[0m"
echo ""

# Check if virtual environment exists
if [ ! -d "env" ] || [ ! -f "env/bin/python" ]; then
  echo -e "\e[1;33mSetting up virtual environment...\e[0m"
  
  # Create virtual environment
  python3 -m venv env
  if [ $? -ne 0 ]; then
    echo -e "\e[1;31mERROR: Failed to create virtual environment!\e[0m"
    echo -e "\e[1;33mYou may need to install python3-venv package\e[0m"
    read -p "Press Enter to exit"
    exit 1
  fi
  
  # Activate and install dependencies
  source env/bin/activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  
  if [ $? -ne 0 ]; then
    echo -e "\e[1;31mERROR: Failed to install dependencies!\e[0m"
    read -p "Press Enter to exit"
    exit 1
  fi
  
  echo -e "\e[1;32mSetup completed successfully!\e[0m"
  echo ""
else
  # Activate existing environment
  source env/bin/activate
fi

# Check if Playwright browsers are installed
echo -e "\e[1;36mChecking Playwright browser installation...\e[0m"
python -c "
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
" 2>/dev/null

if [ $? -ne 0 ]; then
  echo -e "\e[1;33mInstalling Playwright browsers (one-time setup)...\e[0m"
  echo -e "\e[1;33mThis may take a few minutes...\e[0m"
  python -m playwright install chromium
  
  if [ $? -eq 0 ]; then
    echo -e "\e[1;32m✅ Playwright browsers installed successfully!\e[0m"
  else
    echo -e "\e[1;33m⚠️  Warning: Playwright browser installation may have failed.\e[0m"
    echo -e "\e[1;33mYou can manually run: playwright install chromium\e[0m"
  fi
  echo ""
else
  echo -e "\e[1;32m✅ Playwright browsers already installed\e[0m"
  echo ""
fi

# Check environment configuration
echo -e "\e[1;36mChecking environment configuration...\e[0m"
python -c "
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
    print('\n⚠️  NetAcad credentials not configured or using default values.')
    sys.exit(1)
else:
    print('✅ Credentials configured successfully!')
    sys.exit(0)
"

if [ $? -ne 0 ]; then
  echo ""
  echo -e "\e[1;33mPlease enter your NetAcad instructor credentials:\e[0m"
  
  # Prompt for credentials
  read -p "Instructor Email: " instructor_email
  read -s -p "Instructor Password: " instructor_password
  echo ""
  
  # Update .env.development file
  cat > .env.development << EOF
# Instructor login credentials for NetAcad
INSTRUCTOR_ID="$instructor_email"
INSTRUCTOR_PASSWORD="$instructor_password"
EOF
  
  echo -e "\e[1;32mCredentials saved to .env.development\e[0m"
  echo ""
fi

# Run application
echo -e "\e[1;36mStarting NetAcad Course Export (Playwright version)...\e[0m"
echo -e "\e[1;90mUsing faster Playwright automation (2-3x faster than Selenium)\e[0m"
python courses_playwright.py

if [ $? -eq 0 ]; then
  echo ""
  echo -e "\e[1;32mApplication completed successfully!\e[0m"
  echo -e "\e[1;33mCheck the 'data' directory for your exported files.\e[0m"
else
  echo ""
  echo -e "\e[1;31mApplication encountered an error!\e[0m"
  echo -e "\e[1;33mPlease check the logs in the 'logs' directory.\e[0m"
fi

echo ""
read -p "Press Enter to close"