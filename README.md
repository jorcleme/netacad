# NetAcad

Welcome to the NetAcad project!

## Overview

This repository contains resources, code, and documentation related to the NetAcad project. The goal is to support the Cisco Small Business Training Team to extract gradebook data as needed.
This repository contains resources, code, and documentation related to the NetAcad project. The goal is to support the Cisco Small Business Training Team to extract gradebook data as needed.

## Features

- Automatic .env file creation
- Automatic directory creation for logs, data, and downloads
- Automatic ChromeDriver management via Selenium
- Automatic Gradebook data extraction
- Automatic .env file creation
- Automatic directory creation for logs, data, and downloads
- Automatic ChromeDriver management via Selenium
- Automatic Gradebook data extraction

## Getting Started

### Prerequisites

- Python 3.11+
- Google Chrome browser
- ChromeDriver (will be automatically managed by Selenium)

### Setup Instructions

1. **Clone the repository:**

### Prerequisites

- Python 3.11+
- Google Chrome browser
- ChromeDriver (will be automatically managed by Selenium)

### Setup Instructions

1. **Clone the repository:**

   ```bash
   git clone https://github.com/jorcleme/netacad.git
   cd netacad
   ```

   ```bash
   git clone https://github.com/jorcleme/netacad.git
   cd netacad
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv env

   # On Linux/Mac:
   source env/bin/activate

   # On Windows:
   env\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure credentials:**

   **Automatic Setup (Recommended):**
   The startup scripts (`start.sh` for Linux/Mac or `start.ps1` for Windows) will automatically:

   - Create a `.env.development` template file if it doesn't exist
   - Check if valid credentials are configured
   - Prompt you to enter your NetAcad credentials if they're missing or using default values
   - Save your credentials securely to the `.env.development` file

   **Manual Setup (Optional):**
   You can also create and edit the credentials file manually:

   ```bash
   # Create .env.development file manually
   touch .env.development
   echo 'INSTRUCTOR_LOGIN="your_instructor_email@domain.com"' >> .env.development
   echo 'INSTRUCTOR_PASSWORD="your_password"' >> .env.development
   ```

5. **Run the application:**

   **For Linux/Mac users:**

   ```bash
   bash start.sh
   ```

   **For Windows users:**

   ```powershell
   # Right-click start.ps1 and select "Run with PowerShell"
   # Or from PowerShell:
   .\start.ps1
   ```

   **First-time setup behavior:**

   - The script will automatically check for Python installation
   - Create a virtual environment if needed
   - Install dependencies automatically
   - Check for NetAcad credentials and prompt you to enter them if missing
   - Run the course export application

   **Subsequent runs:**

   - The script will validate your existing setup
   - Skip setup steps that are already complete
   - Run the application directly if everything is configured

### Automatic Directory Creation

The application automatically creates the following directories if they don't exist:

- `logs/` - Application logs
- `data/` - Main data directory
  - `data/csv/` - CSV exports (without headers for platform upload)
  - `data/markdown/` - Markdown exports (with headers for LLM processing)

### Windows Users - Quick Start Guide

🎯 **For non-tech users: See [WINDOWS_QUICK_START.md](WINDOWS_QUICK_START.md) for super simple instructions!**

For team members who aren't tech-savvy:

1. **First time setup:**

   - Download/clone the project
   - Double-click `run-app.bat`
   - Follow the prompts (it will set up everything automatically)

2. **Regular use:**

   - Just double-click `run-app.bat` each time you want to export data
   - The application will guide you through the process

3. **Finding your files:**

   - All exported data will be in the `data` folder
   - CSV files: `data/csv/` (for uploading to platforms)
   - Markdown files: `data/markdown/` (for AI/LLM processing)

4. **Create desktop shortcut (optional):**
   - Double-click `create-shortcut.bat` to add a shortcut to your desktop

### Troubleshooting

- **Environment file missing**: The app will create a template `.env.development` file automatically
- **Permission errors**: Ensure you have write permissions in the project directory
- **Chrome driver issues**: Make sure Google Chrome is installed and up to date

**Windows-specific troubleshooting:**

- **"Python not found"**: Install Python from <https://python.org> (check "Add Python to PATH")
- **Script won't run**: Right-click the `.bat` file and select "Run as administrator"
- **PowerShell execution policy**: If `.ps1` scripts won't run, open PowerShell as admin and run: `Set-ExecutionPolicy RemoteSigned`

### File Formats Explained

The application creates two types of files for maximum compatibility:

📊 **CSV Files** (`data/csv/` folder):

- No column headers (for platform compatibility)
- Pure data format for uploading to systems that don't support headers
- Filename format: `GRADEBOOK_DATA_YYYY_MM_DDTHH_MM_SSZ_[course-info].csv`

📝 **Markdown Files** (`data/markdown/` folder):

- Rich formatting with headers and metadata
- Optimized for AI/LLM processing and human readability
- Includes statistical summaries and course information
- Filename format: `GRADEBOOK_DATA_YYYY_MM_DDTHH_MM_SSZ_[course-info].md`

### Validation

You can validate your setup by running:

```bash
python -c "from constants import validate_setup; validate_setup()"
```

## Contributing

Contributions are welcome! Please open issues or submit pull requests for improvements.

## License

This project is licensed under the MIT License.

---

_Created by the SMBDev team._

_Created by the SMBDev team._
