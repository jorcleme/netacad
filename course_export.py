import time
import os
import pandas as pd
import logging
import re
import sys

from typing import List, Tuple
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
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from constants import (
    BASE_URL,
    INSTRUCTOR_ID,
    INSTRUCTOR_PASSWORD,
    PAGELOAD_TIMEOUT,
    WEBDRIVER_TIMEOUT,
    LOGS_DIR,
    DATA_DIR,
    CSV_DATA_DIR,
    MD_DATA_DIR,
    validate_setup,
)


if not validate_setup():
    print("Setup validation failed. Please check your environment and try again.")
    exit(1)
else:
    print("Setup validation passed. Proceeding with course export...")

log_file = LOGS_DIR / "course_export.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(log_file), mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

_course_names: List[str] = []
_course_ids: List[str] = []
_course_csv_files: List[str | None] = []
_failed_course_ids: List[str] = []


options = Options()
#  # Enable new headless mode for better support
options.add_experimental_option(
    "prefs",
    {
        "download.default_directory": str(
            DATA_DIR
        ),  # Use project data directory instead of system Downloads
        "download.prompt_for_download": False,  # Disable download pop-ups
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,  # Allow safe browsing downloads
    },
)
options.add_argument("--disable-gpu")  # Disable GPU hardware acceleration
options.add_argument("--no-sandbox")  # Bypass OS security model
options.add_argument("--headless")  # Run in headless mode for automation
options.add_argument("--window-size=1920,1080")  # Set window size for headless mode
options.add_argument("--disable-web-security")
options.add_argument("--disable-features=VizDisplayCompositor")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-background-networking")
options.add_argument("--disable-sync")

options.add_argument("--log-level=3")  # Only show fatal errors
options.add_experimental_option("excludeSwitches", ["enable-logging"])
options.add_experimental_option("useAutomationExtension", False)

logger.info("Initializing Chrome WebDriver...")
browser = webdriver.Chrome(
    options=options, service=ChromeService(ChromeDriverManager().install())
)
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
        username.send_keys(INSTRUCTOR_ID + Keys.ENTER)
    except NoSuchElementException:
        logger.error("Username field not found. Exiting...")
        browser.close()
        exit()


def send_password():
    try:
        password = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password.send_keys(INSTRUCTOR_PASSWORD + Keys.ENTER)
    except NoSuchElementException:
        logger.error("Password field not found. Exiting...")
        browser.close()
        exit()


def clear_old_downloads():
    """Deletes old CSV and Markdown files before new exports start."""

    try:
        # Clear CSV files
        pattern = r"^GRADEBOOK_DATA_\d{4}_\d{2}_\d{2}T\d{2}_\d{2}_\d{2}Z_[\w-]+\.csv$"

        # Clear from main DATA_DIR (downloaded files)
        for file in os.listdir(str(DATA_DIR)):
            if file.endswith(".csv") and re.match(pattern, file):
                file_path = DATA_DIR / file
                os.remove(str(file_path))
                logger.info(f"Deleted old download: {file_path}")

        # Clear organized CSV files
        if CSV_DATA_DIR.exists():
            for file in os.listdir(str(CSV_DATA_DIR)):
                if file.endswith(".csv") and re.match(pattern, file):
                    file_path = CSV_DATA_DIR / file
                    os.remove(str(file_path))
                    logger.info(f"Deleted old CSV export: {file_path}")

        # Clear Markdown files
        if MD_DATA_DIR.exists():
            md_pattern = (
                r"^GRADEBOOK_DATA_\d{4}_\d{2}_\d{2}T\d{2}_\d{2}_\d{2}Z_[\w-]+\.md$"
            )
            for file in os.listdir(str(MD_DATA_DIR)):
                if file.endswith(".md") and re.match(md_pattern, file):
                    file_path = MD_DATA_DIR / file
                    os.remove(str(file_path))
                    logger.info(f"Deleted old Markdown export: {file_path}")

    except Exception as e:
        logger.error(f"Error clearing old files: {e}", exc_info=True)


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


def create_markdown_export(
    df: pd.DataFrame, csv_filename: str, course_id: str, course_name: str
) -> tuple[bool, str]:
    """
    Creates a Markdown file from the gradebook data with better formatting.

    Args:
        df: DataFrame containing the gradebook data
        csv_filename: Original CSV filename
        course_id: Course ID
        course_name: Course name

    Returns:
        tuple: (success: bool, file_path: str)
    """
    try:
        # Create markdown filename
        md_filename = csv_filename.replace(".csv", ".md")
        md_file_path = MD_DATA_DIR / md_filename

        # Generate markdown content
        markdown_content = generate_gradebook_markdown(df, course_id, course_name)

        # Write markdown file
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logger.info(f"Markdown export saved to: {md_file_path}")
        return True, str(md_file_path)

    except Exception as e:
        logger.error(f"Error creating Markdown export: {e}")
        return False, ""


def generate_gradebook_markdown(
    df: pd.DataFrame, course_id: str, course_name: str
) -> str:
    """
    Generates formatted Markdown content from gradebook data optimized for LLM consumption.

    Args:
        df: DataFrame containing gradebook data
        course_id: Course ID
        course_name: Course name

    Returns:
        str: Formatted Markdown content
    """
    from datetime import datetime

    # Header information
    export_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_students = len(df)

    markdown_lines = [
        f"# NetAcad Gradebook Export",
        "",
        f"## Course Information",
        f"- **Course ID:** {course_id}",
        f"- **Course Name:** {course_name}",
        f"- **Export Date:** {export_date}",
        f"- **Total Students:** {total_students}",
        "",
        "---",
        "",
    ]

    # Add summary statistics if numeric columns exist
    numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
    if len(numeric_columns) > 1:  # More than just COURSE_ID
        markdown_lines.extend(
            [
                "## Grade Summary Statistics",
                "",
                "This section provides statistical analysis of student performance across gradeable items.",
                "",
            ]
        )

        for col in numeric_columns:
            if col != "COURSE_ID" and not df[col].empty and not df[col].isna().all():
                stats = df[col].describe()
                # Clean column name for display
                display_name = col.replace("_", " ").replace("-", " ").title()

                markdown_lines.extend(
                    [
                        f"### {display_name}",
                        (
                            f"- **Average Score:** {stats['mean']:.2f}"
                            if "mean" in stats
                            else ""
                        ),
                        (
                            f"- **Minimum Score:** {stats['min']:.2f}"
                            if "min" in stats
                            else ""
                        ),
                        (
                            f"- **Maximum Score:** {stats['max']:.2f}"
                            if "max" in stats
                            else ""
                        ),
                        (
                            f"- **Standard Deviation:** {stats['std']:.2f}"
                            if "std" in stats
                            else ""
                        ),
                        (
                            f"- **Students with Grades:** {int(stats['count'])}"
                            if "count" in stats
                            else ""
                        ),
                        "",
                    ]
                )

        markdown_lines.extend(["---", ""])

    # Add the main data table with clear headers
    markdown_lines.extend(
        [
            "## Complete Student Gradebook Data",
            "",
            "Below is the complete gradebook data for all students in this course.",
            "Each row represents one student's performance across all gradeable items.",
            "",
        ]
    )

    # Convert DataFrame to Markdown table with improved formatting
    display_df = df.copy()

    # Clean up column names for better LLM understanding
    column_mapping = {}
    for col in display_df.columns:
        clean_name = col.replace("_", " ").replace("-", " ").title()
        # Special handling for common patterns
        if "id" in col.lower():
            clean_name = clean_name.replace("Id", "ID")
        column_mapping[col] = clean_name

    display_df = display_df.rename(columns=column_mapping)

    # Convert to markdown table
    markdown_table = display_df.to_markdown(index=False, tablefmt="pipe")
    markdown_lines.append(markdown_table)

    # Add metadata footer for LLM context
    markdown_lines.extend(
        [
            "",
            "---",
            "",
            "## Export Metadata",
            "",
            f"- **Generated:** {export_date}",
            f"- **Data Source:** NetAcad Learning Management Platform",
            f"- **Processing System:** Automated Course Export Tool",
            f"- **File Format:** Markdown (.md) - Optimized for AI/LLM Processing",
            f"- **CSV Companion:** Available in separate headerless CSV format",
            "",
            "### Data Notes",
            "- All numeric scores are preserved in original format",
            "- Missing grades are represented as empty cells or NaN values",
            "- Course ID has been prepended to maintain data integrity",
            "- Column headers have been formatted for improved readability",
        ]
    )

    return "\n".join(markdown_lines)


def add_course_id_to_csv(
    csv_filename: str, course_id: str, course_name: str = ""
) -> tuple[bool, str, str]:
    """
    Adds a COURSE_ID column to the CSV file and creates both CSV and Markdown versions.

    Args:
        csv_filename: Name of the CSV file
        course_id: Course ID to add to the data
        course_name: Course name for better organization

    Returns:
        tuple: (success: bool, csv_file_path: str, markdown_file_path: str)
    """
    # Original downloaded file in DATA_DIR
    original_file_path = DATA_DIR / csv_filename

    if not original_file_path.exists():
        logger.error(f"CSV file not found: {csv_filename}")
        return False, "", ""

    try:
        # Read the original CSV
        df = pd.read_csv(str(original_file_path))
        df.insert(0, "COURSE_ID", course_id)

        # Create organized CSV file (without headers for platform compatibility)
        csv_output_path = CSV_DATA_DIR / csv_filename
        df.to_csv(str(csv_output_path), index=False, header=False)
        logger.info(f"CSV file (no headers) saved to: {csv_output_path}")

        # Create Markdown version (with headers for LLM readability)
        markdown_success, markdown_path = create_markdown_export(
            df, csv_filename, course_id, course_name
        )

        if markdown_success:
            logger.info(f"Successfully processed both formats for {course_name}")
            # Clean up the original downloaded file
            original_file_path.unlink()
            logger.info(f"Cleaned up original download: {original_file_path}")

            return True, str(csv_output_path), markdown_path
        else:
            logger.warning(
                f"Markdown creation failed, but CSV was successful for {course_name}"
            )
            return True, str(csv_output_path), ""

    except Exception as e:
        logger.error(f"Error processing file {csv_filename}: {e}")
        return False, "", ""


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
            csv_filename = wait_for_download(str(DATA_DIR))
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


def execute_gradebook_actions(course_id: str, course_name: str = ""):
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

        if csv_filename:
            # Process the file and get both CSV and Markdown paths
            success, csv_path, markdown_path = add_course_id_to_csv(
                csv_filename, course_id, course_name
            )
            if success:
                # Store both file paths for tracking
                _course_csv_files.append(f"CSV: {csv_path} | MD: {markdown_path}")
                logger.info(f"Successfully processed both formats for {course_name}")
                return True
            else:
                logger.error(f"Failed to process files for course {course_id}")
                return False
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
    """Save course processing results to JSON with file path information."""
    course_data = []

    for i, (course_id, course_name) in enumerate(zip(_course_ids, _course_names)):
        # Parse the file paths from the stored string
        file_info = _course_csv_files[i] if i < len(_course_csv_files) else ""

        csv_path = ""
        markdown_path = ""

        if file_info and " | " in file_info:
            parts = file_info.split(" | ")
            csv_path = parts[0].replace("CSV: ", "") if len(parts) > 0 else ""
            markdown_path = parts[1].replace("MD: ", "") if len(parts) > 1 else ""

        course_data.append(
            {
                "course_id": course_id,
                "course_name": course_name,
                "csv_file_path": csv_path,
                "markdown_file_path": markdown_path,
                "processing_status": "success" if file_info else "failed",
            }
        )

    df = pd.DataFrame(course_data)
    json_path = DATA_DIR / "courses_export_summary.json"
    df.to_json(str(json_path), orient="records", indent=4)
    logger.info(f"Course export summary saved to: {json_path}")


def paginate_and_fetch_courses() -> Tuple[List[str], List[str]]:
    """Cycles through all pages and collects course URLs and names."""

    course_urls: List[str] = []
    course_names: List[str] = []

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
            course_urls.append(anchor.get_attribute("href"))
            course_names.append(anchor.text.strip())

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

    logger.info(
        f"Total course names collected: {len(course_names)}\nTotal URLs: {len(course_urls)}"
    )

    if len(course_urls) != len(course_names):
        logger.warning(
            "Mismatch between course URLs and names. Please check the page structure."
        )

    return (course_urls, course_names)


def process_courses(clear_downloads: bool = True):
    """Processes each course, navigates to its page, and exports its gradebook."""
    start_time = time.time()

    if clear_downloads:
        logger.info("Clearing old downloads...")
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

            if execute_gradebook_actions(course_id, course_name):
                logger.info(f"✅ Successfully exported grades for course {course_name}")
            else:
                logger.warning(f"Failed to export grades for course {course_name}")

            logger.info("-" * 50)

    logger.info(f"Length of Course Ids processed: {len(_course_ids)}")
    logger.info(f"Length of Course Names processed: {len(_course_names)}")

    # Summary of file exports
    successful_exports = sum(1 for file_info in _course_csv_files if file_info)
    failed_exports = len(_course_ids) - successful_exports

    logger.info("=" * 60)
    logger.info("EXPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"📊 Total Courses Processed: {len(_course_ids)}")
    logger.info(f"✅ Successful Exports: {successful_exports}")
    logger.info(f"❌ Failed Exports: {failed_exports}")
    logger.info(f"📁 CSV Files Location: {CSV_DATA_DIR}")
    logger.info(f"📝 Markdown Files Location: {MD_DATA_DIR}")

    if _failed_course_ids:
        logger.warning(f"⚠️  Failed Course IDs: {', '.join(_failed_course_ids)}")

    browser.quit()
    save_courses_data_to_json()
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"Program execution completed in {elapsed_time:.2f} seconds.")
    logger.info("=" * 60)


# List of courses Anthony and Jeff care about

if __name__ == "__main__":
    process_courses()
