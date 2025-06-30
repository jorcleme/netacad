import os
import platform
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(filename=".env.development", usecwd=True))

BASE_URL = "http://www.netacad.com"
LOGIN_ID = "arenli@cisco.com"
INSTRUCTOR_LOGIN_ID = os.environ.get("INSTRUCTOR_LOGIN")
INSTRUCTOR_LOGIN_PASSWORD = os.environ.get("INSTRUCTOR_PASSWORD")
PAGELOAD_TIMEOUT = 5
WEBDRIVER_TIMEOUT = 20
LOGS_DIR = os.path.join(os.getcwd(), "logs")
DATA_DIR = os.path.join(os.getcwd(), "data")

if platform.system() == "Windows":
    DOWNLOADS_DIR = os.path.join(os.environ["USERPROFILE"], "Downloads")
else:
    DOWNLOADS_DIR = os.path.join(os.environ["HOME"], "downloads")
