import os
import sys
import shutil
import logging
import json
import logging
from pathlib import Path
from dotenv import load_dotenv


logging.basicConfig(stream=sys.stdout, level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
BASE_DIR = BACKEND_DIR.parent


# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env.development")

STATIC_DIR = Path(APP_DIR / "static").resolve()
FRONTEND_STATIC_DIR = BASE_DIR / "static"
FRONTEND_BUILD_DIR = Path(BASE_DIR / "build").resolve()


for file in (FRONTEND_STATIC_DIR).glob("**/*"):
    if file.is_file():
        dest = STATIC_DIR / file.relative_to((FRONTEND_STATIC_DIR))
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(file, dest)
        except Exception as e:
            logging.error(f"Error copying {file} to {dest}: {e}")


ENV = os.getenv("ENV", "development")

# Data directories for article scraping
DATA_DIR = BACKEND_DIR / "data"
LOGS_DIR = BACKEND_DIR / "logs"

# Create directories if they don't exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


try:
    PACKAGE = json.loads((BASE_DIR / "package.json").read_text())
except Exception as e:
    logging.error(f"Error reading package.json: {e}")
    PACKAGE = {"version": "0.0.1"}

VERSION = PACKAGE.get("version", "0.0.1")


DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/netacad.db")


NETACAD_BASE_URL = "https://www.netacad.com"
NETACAD_INSTRUCTOR_ID = os.environ.get("INSTRUCTOR_ID")
NETACAD_INSTRUCTOR_PASSWORD = os.environ.get("INSTRUCTOR_PASSWORD")

OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
OAUTH_DISCOVERY_URL = os.getenv("OAUTH_DISCOVERY_URL")
OAUTH_SCOPES = os.environ.get("OAUTH_SCOPES", "openid email profile")
OAUTH_PROVIDER_NAME = os.environ.get("OAUTH_PROVIDER_NAME", "Cisco SSO")

SECRET_KEY = os.environ.get("SECRET_KEY", "super-t0p-secret-key")


def run_migrations():
    logger.info("Running database migrations...")
    try:
        from alembic import command
        from alembic.config import Config

        alembic_config = Config(APP_DIR / "alembic.ini")
        migrations_path = APP_DIR / "alembic"
        alembic_config.set_main_option("script_location", str(migrations_path))
        alembic_config.set_main_option("sqlalchemy.url", DATABASE_URL)
        command.upgrade(alembic_config, "head")
        logger.info("Database migrations completed successfully.")
    except Exception as e:
        logger.error(f"Error running migrations: {e}")


run_migrations()
