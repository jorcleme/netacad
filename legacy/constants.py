import os

from dotenv import load_dotenv, find_dotenv
from pathlib import Path


def create_env_template(env_filename: str = ".env.development") -> bool:
    """
    Create a template environment file if it doesn't exist.

    Args:
        env_filename: Name of the environment file to create

    Returns:
        bool: True if template was created or already exists, False if creation failed
    """
    template_env_path = Path(__file__).parent / env_filename

    if template_env_path.exists():
        return True

    template_content = """# Instructor login credentials for NetAcad
# Replace with your actual credentials
INSTRUCTOR_ID="your_instructor_email@domain.com"
INSTRUCTOR_PASSWORD="your_password"
"""
    try:
        template_env_path.write_text(template_content)
        print(f"Created template environment file: {template_env_path}")
        print(f"Please update the {env_filename} file with your actual credentials.")
        return True
    except Exception as e:
        print(f"Warning: Could not create {env_filename} template: {e}")
        return False


# Try to load environment file, create template if it doesn't exist
env_file_path = find_dotenv(filename=".env.development", usecwd=True)

if not env_file_path:
    create_env_template(".env.development")
    # Try to load again after creating template
    env_file_path = find_dotenv(filename=".env.development", usecwd=True)

load_dotenv(env_file_path)

BASE_URL = "https://www.netacad.com"
LOGIN_ID = "arenli@cisco.com"

# Validate required environment variables
INSTRUCTOR_ID = os.environ.get("INSTRUCTOR_ID")
INSTRUCTOR_PASSWORD = os.environ.get("INSTRUCTOR_PASSWORD")

if not INSTRUCTOR_ID or not INSTRUCTOR_PASSWORD:
    print("Warning: INSTRUCTOR_ID and/or INSTRUCTOR_PASSWORD not found in environment.")
    print(
        "Please check your .env.development file and ensure it contains valid credentials."
    )
    if (
        INSTRUCTOR_ID == "your_instructor_email@domain.com"
        or INSTRUCTOR_PASSWORD == "your_password"
    ):
        print(
            "It looks like you're using template values. Please update with your actual credentials."
        )

PAGELOAD_TIMEOUT = 5
WEBDRIVER_TIMEOUT = 10

# You can adjust these values based on your system capabilities and network conditions
MAX_WORKERS = 4  # Very conservative for testing - can increase once stable
# Number of parallel browser instances (recommended: 3-6)
# Higher values = faster processing but more resource usage
# Lower values = more stable but slower processing

OPTIMIZED_TIMEOUTS = {
    "page_load": 30,  # More generous timeout for page loads (NetAcad can be slow)
    "element_wait": 15,  # More time for elements to appear
    "download_wait": 30,  # Adequate time for file downloads
    "modal_wait": 3,  # Quick modal interactions
    "animation_wait": 2,  # Give animations time to complete
    "login_wait": 5,  # More time for login transitions
}


# Create required directories with error handling
def create_directory_safely(directory_path: Path, description: str) -> bool:
    """Create directory safely with error handling and logging."""
    try:
        directory_path.mkdir(parents=True, exist_ok=True)
        if not directory_path.exists():
            print(
                f"Warning: Failed to create {description} directory: {directory_path}"
            )
            return False
        return True
    except PermissionError:
        print(
            f"Error: Permission denied creating {description} directory: {directory_path}"
        )
        print("Please check your permissions or run with appropriate privileges.")
        return False
    except Exception as e:
        print(f"Error: Failed to create {description} directory {directory_path}: {e}")
        return False


# Project directories (relative to script location)
LOGS_DIR = Path(__file__).parent / "logs"
create_directory_safely(LOGS_DIR, "logs")

DATA_DIR = Path(__file__).parent / "data"
create_directory_safely(DATA_DIR, "data")

CSV_DATA_DIR = DATA_DIR / "csv"
create_directory_safely(CSV_DATA_DIR, "CSV data")

MD_DATA_DIR = DATA_DIR / "markdown"
create_directory_safely(MD_DATA_DIR, "Markdown data")


# Validation summary for debugging
def validate_setup():
    """Validate that all required components are set up correctly."""
    issues = []

    if not INSTRUCTOR_ID or not INSTRUCTOR_PASSWORD:
        issues.append("Missing instructor credentials in .env.development")

    if not LOGS_DIR.exists():
        issues.append(f"Logs directory not accessible: {LOGS_DIR}")

    if not DATA_DIR.exists():
        issues.append(f"Data directory not accessible: {DATA_DIR}")

    if issues:
        print("\n⚠️  Setup Issues Detected:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nPlease resolve these issues before running the application.")
        return False
    else:
        print("✅ All directories and configuration validated successfully!")
        return True
