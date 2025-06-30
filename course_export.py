import time
import os
import pandas as pd
import logging
import re

from typing import List, Tuple
from dotenv import find_dotenv, load_dotenv
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from constants import (
    BASE_URL,
    INSTRUCTOR_LOGIN_ID,
    INSTRUCTOR_LOGIN_PASSWORD,
    PAGELOAD_TIMEOUT,
    WEBDRIVER_TIMEOUT,
    DOWNLOADS_DIR,
    LOGS_DIR,
    DATA_DIR,
)

os.makedirs(LOGS_DIR, exist_ok=True)

log_file = os.path.join(LOGS_DIR, "course_export.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file, mode="w"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

load_dotenv(find_dotenv(filename=".env.development", usecwd=True))

_course_names: List[str] = []
_course_ids: List[str] = []
_course_csv_files: List[str | None] = []
_failed_course_ids: List[str] = []


options = Options()
#  # Enable new headless mode for better support
options.add_experimental_option(
    "prefs",
    {
        "download.default_directory": DOWNLOADS_DIR,  # Set download folder
        "download.prompt_for_download": False,  # Disable download pop-ups
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,  # Allow safe browsing downloads
    },
)
logger.info("Initializing Chrome WebDriver...")
browser = webdriver.Chrome(options=options)
wait = WebDriverWait(browser, WEBDRIVER_TIMEOUT)

browser.delete_all_cookies()
browser.get(BASE_URL)
logger.info("Navigating to netacad.com...")


def navigate_to_login():
    try:
        login_btn = wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, "loginBtn--lfDa2"))
        )
        login_btn.click()
        logger.info("Clicked on the login button.")
    except NoSuchElementException:
        logger.error("Element not found")
        browser.close()
        exit()
    except ElementClickInterceptedException:
        logger.warning("Element click intercepted...")
        browser.execute_script("arguments[0].scrollIntoView(true);", login_btn)
        browser.execute_script("arguments[0].click();", login_btn)


def send_username():
    try:
        username = wait.until(EC.presence_of_element_located((By.ID, "username")))
        username.send_keys(INSTRUCTOR_LOGIN_ID + Keys.RETURN)
    except NoSuchElementException:
        logger.error("Username field not found. Exiting...")
        browser.close()
        exit()


def send_password():
    try:
        password = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password.send_keys(INSTRUCTOR_LOGIN_PASSWORD + Keys.RETURN)
    except NoSuchElementException:
        logger.error("Password field not found. Exiting...")
        browser.close()
        exit()


def clear_old_downloads():
    """Deletes all CSV files in the downloads folder before new exports starts."""

    try:
        pattern = r"^GRADEBOOK_DATA_\d{4}_\d{2}_\d{2}T\d{2}_\d{2}_\d{2}Z_[\w-]+\.csv$"
        for file in os.listdir(DOWNLOADS_DIR):
            if file.endswith(".csv") and re.match(pattern, file):
                file_path = os.path.join(DOWNLOADS_DIR, file)
                os.remove(file_path)
                logger.info(f"Deleted old download: {file_path}")
    except Exception as e:
        logger.error(f"Error deleting old downloads: {e}", exc_info=True)


def close_modal_if_present():
    """Closes the modal dialog if it is blocking interactions."""

    try:
        wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "exportCsvModal--XL37A"))
        )
        logger.info("Modal detected. Closing...")
        close_button = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".exportCsvModal--XL37A .modal__close")
            )
        )
        close_button.click()
        time.sleep(1)  # Allow modal to close
        logger.info("Modal closed.")
    except (TimeoutException, NoSuchElementException):
        logger.info("No modal detected.")


def add_course_id_to_csv(csv_filename: str, course_id: str):
    """Adds a COURSE_ID column to the CSV file."""

    file_path = os.path.join(DOWNLOADS_DIR, csv_filename)
    if not os.path.exists(file_path):
        logger.error(f"CSV file not found: {csv_filename}")
        return False

    try:
        df = pd.read_csv(file_path)
        df.insert(0, "COURSE_ID", course_id)
        df.to_csv(file_path, index=False)
        logger.info(f"Added COURSE_ID column to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error updating CSV file: {e}")
        return False


def wait_for_download(download_path: str, timeout=30):
    """Waits for a new file to appear in the download directory."""

    start_time = time.time()
    initial_files = set(os.listdir(download_path))  # Capture existing files

    while True:
        current_files = set(os.listdir(download_path))
        new_files = current_files - initial_files  # Identify new files

        csv_files = [file for file in new_files if file.endswith(".csv")]

        if csv_files:
            latest_csv = max(
                csv_files,
                key=lambda f: os.path.getctime(os.path.join(download_path, f)),
            )
            logger.info(f"Download complete: {latest_csv}")
            return latest_csv

        if time.time() - start_time > timeout:
            logger.warning("Download timeout reached.")
            return None

        time.sleep(1)  # Check every second


def handle_export_dropdown():
    try:
        logger.info("Checking if export dropdown exists...")
        export_dropdown = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".RBDropdown--ATEd3.dropdown > button")
            )
        )
        logger.info("Dropdown found. Attempting to click...")
        export_dropdown.click()
        logger.info("Clicked export dropdown successfully.")
    except TimeoutException:
        logger.error("Export dropdown did not appear in time.")
    except ElementClickInterceptedException:
        logger.warning("Dropdown click intercepted. Using JavaScript click...")
        browser.execute_script("arguments[0].scrollIntoView(true);", export_dropdown)
        browser.execute_script("arguments[0].click();", export_dropdown)
    except Exception as e:
        logger.error(f"Unexpected error clicking dropdown: {e}", exc_info=True)


def handle_export_all():

    try:
        export_all_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".dropdownButton--whS7t:first-of-type")
            )
        )
        export_all_btn.click()
    except (
        ElementClickInterceptedException,
        TimeoutException,
        NoSuchElementException,
    ) as e:
        if isinstance(e, ElementClickInterceptedException):
            browser.execute_script("arguments[0].scrollIntoView(true);", export_all_btn)
            browser.execute_script("arguments[0].click();", export_all_btn)
        elif isinstance(e, TimeoutException):
            logger.error("Element not found in time.")
        elif isinstance(e, NoSuchElementException):
            logger.error("Element not found.")
        else:
            logger.error("Unknown error occurred.")


def handle_alert_box():
    try:
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "modal__content")))
        alert_box_btn_close = wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, "modal__close"))
        )
        alert_box_btn_close.click()
        logger.info("Alert box closed.")
    except (NoSuchElementException, TimeoutException):
        logger.warning(
            "Failed to detect modal alert box. It could be the modal never opened. Continuing..."
        )
        return


def handle_refresh_btn():
    try:
        refresh_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "refreshExportList"))
        )
        refresh_btn.click()
        time.sleep(5)  # Allow page to refresh
        logger.info("Clicked on refresh button.")
    except (NoSuchElementException, TimeoutException):
        logger.error("Failed to click on refresh button.")


def wait_for_latest_export_link():
    """Waits for the latest export <a> link and returns it."""

    try:
        export_links = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".dropdown__menu.show a")
            )
        )
        time.sleep(2)  # Allow animations to finish
        logger.info(f"Dropdown contains {len(export_links)} export links.")

        if export_links:
            return export_links[0]  # Return the first available export link
        else:
            logger.error("No export links found inside dropdown.")
            return None
    except Exception as e:
        logger.error(f"Dropdown did not appear in time. Error: {e}")
        return None


def click_first_export():
    """Clicks the most recent export link and waits for the CSV download."""

    latest_export_link = wait_for_latest_export_link()

    if latest_export_link:
        logger.info("Scrolling to export link and clicking it.")
        browser.execute_script("arguments[0].scrollIntoView(true);", latest_export_link)

        try:
            latest_export_link.click()
            # Wait for file download to complete
            csv_filename = wait_for_download(DOWNLOADS_DIR)
            if csv_filename:
                logger.info(f"Downloaded file: {csv_filename}")
                return csv_filename
            else:
                logger.error("Download failed.")
                return None
        except Exception as e:
            logger.error(f"Error clicking export link: {e}", exc_info=True)
            return None
    else:
        logger.error("No export links available.")
        return None


def open_dropdown(retries: int = 3):
    """Clicks the export dropdown button and ensures it expands properly."""

    for attempt in range(retries):  # Try clicking the dropdown up to 3 times
        handle_refresh_btn()
        try:
            dropdown_button = wait.until(
                EC.element_to_be_clickable((By.ID, "dropdown-basic"))
            )
            browser.execute_script(
                "arguments[0].scrollIntoView(true);", dropdown_button
            )
            dropdown_button.click()
            time.sleep(2)  # Allow dropdown to expand
            logger.info("Exported dropdown list opened successfully...")
            return True
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}/{retries}...\nError: {e}")
            if attempt == retries - 1:  # If last attempt fails, return False
                logger.error("Reached maximum attempts. Failed to open dropdown.")
                return False
            time.sleep(2)  # Wait before retrying


def handle_gradebook_tab():
    try:
        gradebook_tab = wait.until(
            EC.element_to_be_clickable((By.ID, "Launch-tab-gradebook"))
        )
        gradebook_tab.click()
    except NoSuchElementException:
        logger.error("Gradebook tab not found.")


def execute_gradebook_actions(course_id: str):
    try:
        logger.info(f"Starting gradebook actions for Course ID: {course_id}")
        handle_gradebook_tab()
        handle_export_dropdown()
        handle_export_all()
        handle_alert_box()
        handle_refresh_btn()

        logger.info("Waiting for dropdown to open...")
        if not open_dropdown():
            logger.error("Skipping this course...")
            _failed_course_ids.append(course_id)
            return False

        csv_filename = click_first_export()

        _course_csv_files.append(os.path.join(DOWNLOADS_DIR, csv_filename))

        if csv_filename:
            add_course_id_to_csv(csv_filename, course_id)
            return True
        else:
            logger.error(f"Failed to export grades for course {course_id}")
            return False

    except Exception as e:
        logger.error(
            f"Error while executing gradebook actions for {course_id}: {e}",
            exc_info=True,
        )
        return False


def save_courses_data_to_json():
    course_data = [
        {
            "course_id": course_id,
            "course_name": course_name,
            "csv_filename": csv_filename,
        }
        for course_id, course_name, csv_filename in zip(
            _course_ids, _course_names, _course_csv_files
        )
    ]

    df = pd.DataFrame(course_data)
    json_path = os.path.join(DATA_DIR, "courses.json")
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    df.to_json(json_path, orient="records", indent=4)


def paginate_and_fetch_courses() -> Tuple[List[str], List[str]]:
    """Cycles through all pages and collects course URLs and names."""

    course_urls = set()
    course_names = set()

    i = 0
    while True:
        i += 1
        logger.info(f"My Classlist Page {i}")

        # Collect course anchors on the current page.
        course_anchors = wait.until(
            EC.visibility_of_all_elements_located(
                (By.CLASS_NAME, "instance_name--dioD1")
            )
        )
        for anchor in course_anchors:
            course_urls.add(anchor.get_attribute("href"))
            course_names.add(anchor.text.strip())

        # Try to find and click the next button.
        try:
            next_button = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.CSS_SELECTOR,
                        "button.pageItem--BNJmT.sides--EdMyh span.icon-chevron-right",
                    )
                )
            )
            next_button.find_element(By.XPATH, "./..").click()
        except (NoSuchElementException, TimeoutException):
            logger.info("No next button found. Exiting pagination loop.")
            break
        except ElementClickInterceptedException:
            btn = next_button.find_element(By.XPATH, "./..")
            browser.execute_script("arguments[0].scrollIntoView(true);", btn)
            browser.execute_script("arguments[0].click();", btn)

    logger.info(f"Total course names collected: {len(course_names)}")
    logger.info(f"Total course URLs collected: {len(course_urls)}")
    return list(course_urls), list(course_names)


def process_courses(clear_old_downloads: bool = True):
    """Processes each course, navigates to its page, and exports its gradebook."""
    start_time = time.time()
    logger.info("Clearing old downloads...")
    if clear_old_downloads:
        clear_old_downloads()
    navigate_to_login()
    send_username()
    send_password()

    course_urls, course_names = paginate_and_fetch_courses()
    for i, url in enumerate(course_urls):
        print(url)
        if url:
            course_name = course_names[i]
            course_id = url.split("=")[1]
            logger.info(
                f"Processing course {i + 1}/{len(course_urls)}: {course_name}. Course URL: {url}"
            )

            if course_id not in _course_ids:
                _course_ids.append(course_id)
            if course_name not in _course_names:
                _course_names.append(course_name)

            browser.get(url)

            if execute_gradebook_actions(course_id):
                logger.info(f"✅ Successfully exported grades for course {course_name}")
            else:
                logger.error(f"❌ Failed to export grades for course {course_name}")

            logger.info("-" * 50)

    logger.info(f"Length of Course Ids processed: {len(_course_ids)}")
    logger.info(f"Length of Course Names processed: {len(_course_names)}")
    browser.quit()
    save_courses_data_to_json()
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"Program execution completed in {elapsed_time:.2f} seconds.")


# List of courses Anthony and Jeff care about

if __name__ == "__main__":
    process_courses()
