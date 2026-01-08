#!/usr/bin/env bash

# Get the script directory
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR" || exit

# Set default host and port
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

# In production (Docker), use pre-installed browsers at /ms-playwright
# In dev, let Playwright use default user cache directories
if [ "$ENV" = "prod" ]; then
    export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}"
fi

KEY_FILE=".secret_key"

# Only generate if SECRET_KEY is not set
if [ -z "$SECRET_KEY" ]; then
    echo -e "\033[0;33mSECRET_KEY not provided. Falling back to file.\033[0m"

    if [ ! -f "$KEY_FILE" ]; then
        echo -e "\033[0;32mGenerating SECRET_KEY\033[0m"
        
        # Check if openssl is available
        if command -v openssl &> /dev/null; then
            openssl rand -base64 32 > "$KEY_FILE"
        else
            # Fallback: Generate random key using /dev/urandom
            echo -e "\033[0;33mopenssl not found, using /dev/urandom to generate key\033[0m"
            head -c 32 /dev/urandom | base64 > "$KEY_FILE"
        fi
    fi

    export SECRET_KEY=$(cat "$KEY_FILE" | tr -d '\n')
fi

# Activate virtual environment if it exists
if [ -d "env/bin" ]; then
    echo -e "\033[0;36mActivating virtual environment...\033[0m"
    source env/bin/activate
    echo -e "\033[0;32mVirtual environment activated\033[0m"
else
    echo -e "\033[0;33mVirtual environment not found. Using system Python.\033[0m"
fi

# In production (Docker), browsers are pre-installed during build
# Only check/install in development environments
if [ -z "$ENV" ] || [ "$ENV" = "dev" ]; then
    # Check if Playwright browsers are installed
    echo -e "\033[0;36mChecking Playwright installation...\033[0m"
    if ! python -c "from playwright.sync_api import sync_playwright; sync_playwright().start().chromium.launch()" &> /dev/null; then
        echo -e "\033[0;33mPlaywright chromium not found. Installing...\033[0m"
        playwright install chromium
        playwright install-deps chromium
        echo -e "\033[0;32mPlaywright chromium installed successfully\033[0m"
    else
        echo -e "\033[0;32mPlaywright chromium already installed\033[0m"
    fi
else
    echo -e "\033[0;36mProduction environment detected. Using pre-installed Playwright browsers.\033[0m"
fi

# Start uvicorn server
SECRET_KEY="$SECRET_KEY" exec uvicorn app.main:app --host "$HOST" --port "$PORT" --forwarded-allow-ips='*'
