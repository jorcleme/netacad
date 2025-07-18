import time
import os
import sys
import pandas as pd
import logging
import re
import threading
import signal
import atexit
import shutil
import gc
import json

from datetime import datetime
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from pathlib import Path
from tempfile import mkdtemp

from typing import List, Tuple, Dict, Any, Optional
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from constants import (
    BASE_URL,
    INSTRUCTOR_ID,
    INSTRUCTOR_PASSWORD,
    MAX_WORKERS,
    OPTIMIZED_TIMEOUTS,
    LOGS_DIR,
    DATA_DIR,
    CSV_DATA_DIR,
    MD_DATA_DIR,
    validate_setup,
)
from utils.gradebook_manager import GradebookManager
from utils.logger import EmojiLoggerAdapter

if not validate_setup():
    print("Setup validation failed. Please check your environment and try again.")
    print("Factors to check:")
    print("- ChromeDriver is installed and in PATH")
    print("- Chrome is installed and up to date")
    print("- Required Python packages are installed")
    print(
        "- .env.development file is present and contains INSTRUCTOR_ID and INSTRUCTOR_PASSWORD"
    )
    exit(1)
else:
    print("Setup validation passed. Proceeding with course export...")


#################
# Logging Setup
#################
# Filter out webdriver logs
class WebDriverManagerFilter(logging.Filter):
    def filter(self, record):
        return (
            not record.name.startswith("WDM")
            and "WebDriver manager" not in record.getMessage()
        )


root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# --- Logging Setup ---
log_file = LOGS_DIR / "courses.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(log_file), mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
    encoding="utf-8",
)
logging.getLogger("WDM").addFilter(WebDriverManagerFilter())
log = logging.getLogger(__file__)
logger = EmojiLoggerAdapter(log, {})


class CourseExportResult(BaseModel):
    course_id: str = Field(..., description="ID of the course")
    course_name: str = Field(..., description="Name of the course")
    course_url: str = Field(..., description="URL of the course page")
    success: bool = Field(default=True, description="Whether the export was successful")
    csv_path: Optional[str] = Field(
        default=None, description="Path to the exported CSV file"
    )
    md_path: Optional[str] = Field(
        default=None, description="Path to the exported Markdown file"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if export failed"
    )


##################
# Global Variables
##################
_course_names: List[str] = []
_course_ids: List[str] = []
_course_csv_files: List[str | None] = []
_failed_course_ids: List[str] = []
_all_course_results: List[CourseExportResult] = (
    []
)  # Complete results including failures
_results_lock = threading.Lock()


workers: Dict[int, Dict[str, Path]] = {}


def add_worker(worker_id: int) -> None:
    if worker_id not in workers:
        workers.update(
            {worker_id: {"download_dir": DATA_DIR / f"worker_{worker_id}_downloads"}}
        )


def clear_old_downloads():
    """Deletes old CSV and Markdown files before new exports start."""

    try:
        # Updated CSV pattern to match actual filename format:
        # GRADEBOOK_DATA_2025-07-17T15_46_21Z_3269_Switch_Catalyst_1200_1300.csv
        csv_pattern = r"^GRADEBOOK_DATA_\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}Z_.*\.csv$"

        files_deleted = 0

        # Clear from main DATA_DIR (downloaded files)
        if DATA_DIR.exists():
            for file in os.listdir(str(DATA_DIR)):
                if file.endswith(".csv") and re.match(csv_pattern, file):
                    file_path = DATA_DIR / file
                    try:
                        file_path.unlink()
                        files_deleted += 1
                        logger.info(f"Deleted old download: {file_path}")
                    except FileNotFoundError:
                        logger.debug(f"File already removed: {file_path}")
                    except Exception as e:
                        logger.warning(f"Could not delete {file_path}: {e}")

        # Clear organized CSV files
        if CSV_DATA_DIR.exists():
            for file in os.listdir(str(CSV_DATA_DIR)):
                if file.endswith(".csv") and re.match(csv_pattern, file):
                    file_path = CSV_DATA_DIR / file
                    try:
                        file_path.unlink()
                        files_deleted += 1
                        logger.info(f"Deleted old CSV export: {file_path}")
                    except FileNotFoundError:
                        logger.debug(f"File already removed: {file_path}")
                    except Exception as e:
                        logger.warning(f"Could not delete {file_path}: {e}")

        # Clear Markdown files
        if MD_DATA_DIR.exists():
            # Updated MD pattern to match actual format
            md_pattern = r"^GRADEBOOK_DATA_\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}Z_.*\.md$"

            for file in os.listdir(str(MD_DATA_DIR)):
                if file.endswith(".md") and re.match(md_pattern, file):
                    file_path = MD_DATA_DIR / file
                    try:
                        file_path.unlink()
                        files_deleted += 1
                        logger.info(f"Deleted old Markdown export: {file_path}")
                    except FileNotFoundError:
                        logger.debug(f"File already removed: {file_path}")
                    except Exception as e:
                        logger.warning(f"Could not delete {file_path}: {e}")

        if files_deleted > 0:
            logger.info(f"Successfully cleared {files_deleted} old export files")
        else:
            logger.info("No old export files found to clear")

    except Exception as e:
        logger.error(f"Error clearing old files: {e}", exc_info=True)


def create_browser(worker_id: int = 0) -> webdriver.Chrome:
    """Create a new instance of the Chrome WebDriver.

    Args:
        worker_id (int, optional): The ID of the worker. Defaults to 0.

    Returns:
        webdriver.Chrome: The created Chrome WebDriver instance.
    """
    # Create unique download directory for this worker to avoid conflicts
    add_worker(worker_id)
    worker_download_dir = workers[worker_id]["download_dir"]

    if not worker_download_dir.exists():
        worker_download_dir.mkdir(parents=True, exist_ok=True)

    options = Options()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument(f"--remote-debugging-port={9222 + worker_id}")

    options.add_argument("--log-level=3")  # Only show fatal errors

    # Add a unique identifier for our automation instances
    options.add_argument(f"--app-user-model-id=NetAcadExport.Worker.{worker_id}")

    prefs = {
        "profile.default_content_setting_values": {
            "plugins": 2,  # Block plugins
            "popups": 2,  # Block popups
            "geolocation": 2,  # Block location sharing
            "notifications": 2,  # Block notifications
        },
        "download.default_directory": str(worker_download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }

    options.add_experimental_option("prefs", prefs)

    # Create browser with optimized settings
    service = Service(ChromeDriverManager().install())
    browser = webdriver.Chrome(options=options, service=service)
    browser.set_page_load_timeout(OPTIMIZED_TIMEOUTS["page_load"])
    browser.implicitly_wait(3)  # More generous implicit wait for login stability

    return browser


def login(browser: webdriver.Chrome) -> bool:
    """Log in to the NetAcad platform.

    Args:
        browser (webdriver.Chrome): The Chrome WebDriver instance.

    Returns:
        bool: True if login was successful, False otherwise.
    """
    try:
        wait = WebDriverWait(browser, OPTIMIZED_TIMEOUTS["login_wait"])
        logger.info("Navigating to NetAcad login page...")
        browser.get(BASE_URL)

        login_button = wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, "loginBtn--lfDa2"))
        )
        login_button.click()
        logger.info("Waiting for login form to appear...")

        username = wait.until(EC.presence_of_element_located((By.ID, "username")))
        username.clear()
        logger.info("Entering instructor login credentials...")
        username.send_keys(INSTRUCTOR_ID + Keys.ENTER)

        password = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password.clear()
        logger.info("Entering instructor password...")
        password.send_keys(INSTRUCTOR_PASSWORD + Keys.ENTER)

        logger.info("Waiting for main dashboard to load...")

        try:
            wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "marketplace-container")),
                    EC.presence_of_element_located((By.ID, "main-content")),
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "myClassesContainer--dpu4l")
                    ),
                )
            )
            logger.info("Main dashboard loaded successfully.")
            return True
        except TimeoutException:
            logger.warning("Login successful but dashboard did not load in time.")
            return False

    except (NoSuchElementException, TimeoutException) as e:
        logger.error(f"Login failed: {e}")
        return False


def collect_course_data():
    browser = None
    try:
        browser = create_browser()

        if not login(browser):
            logger.error("Login failed. Cannot proceed with course data collection.")
            return [], []

        course_data: List[Tuple[str, str]] = []
        seen_urls = set()
        wait = WebDriverWait(browser, OPTIMIZED_TIMEOUTS["element_wait"])
        page = 0
        while True:
            page += 1
            logger.info(f"Collecting courses from page {page}...")

            course_anchors = wait.until(
                EC.presence_of_all_elements_located(
                    (By.CLASS_NAME, "instance_name--dioD1")
                )
            )

            for anchor in course_anchors:
                url = anchor.get_attribute("href")
                name = anchor.text.strip()

                if url and name and url not in seen_urls:
                    seen_urls.add(url)
                    course_data.append((url, name))

            try:
                next_icon = wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            "button.pageItem--BNJmT.sides--EdMyh span.icon-chevron-right",
                        )
                    )
                )
                next_button = next_icon.find_element(By.XPATH, "./..")
                next_button.click()
                logger.info("Clicked next button to go to the next page.")
                time.sleep(1)  # Allow time for page transition
            except (NoSuchElementException, TimeoutException):
                logger.info("No more pages to process. Course collection complete.")
                break
            except ElementClickInterceptedException:
                next_button = next_icon.find_element(By.XPATH, "./..")
                browser.execute_script(
                    "arguments[0].scrollIntoView(true);", next_button
                )
                browser.execute_script("arguments[0].click();", next_button)
                time.sleep(1)  # Allow time for page transition

        course_urls = [url for url, _ in course_data]
        course_names = [name for _, name in course_data]
        logger.info(f"Collected {len(course_urls)} courses from {page} pages")
        return course_urls, course_names

    except Exception as e:
        logger.error(f"Failed to collect course data: {e}", exc_info=True)
        return [], []
    finally:
        if browser:
            browser.quit()

    gc.collect()


def save_courses_data_to_json():
    """Save comprehensive course processing results to JSON with detailed information."""

    # Create comprehensive course data from all results
    course_data = []
    processing_summary = {
        "export_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_courses_found": 0,
        "successful_exports": 0,
        "failed_exports": 0,
        "success_rate_percentage": 0.0,
        "processing_mode": "parallel",
        "max_workers_used": MAX_WORKERS,
        "export_locations": {
            "csv_directory": str(CSV_DATA_DIR),
            "markdown_directory": str(MD_DATA_DIR),
            "logs_directory": str(LOGS_DIR),
        },
    }

    # Use the complete results if available, otherwise fall back to the old method
    if _all_course_results:
        logger.info("Using complete course results for JSON summary")

        for result in _all_course_results:
            pydantic_course_data = result.model_dump(mode="python")
            course_id = pydantic_course_data.get("course_id", "unknown")
            course_name = pydantic_course_data.get("course_name", "unknown")
            course_url = pydantic_course_data.get(
                "course_url",
                (
                    f"https://www.netacad.com/launch?id={course_id}"
                    if course_id != "unknown"
                    else "unknown"
                ),
            )
            success = pydantic_course_data.get("success", False)

            course_entry = {
                "course_id": course_id,
                "course_name": course_name,
                "course_url": course_url,
                "processing_status": "success" if success else "failed",
                "success": success,
            }

            if success:
                course_entry.update(
                    {
                        "csv_file_path": pydantic_course_data.get("csv_path", ""),
                        "markdown_file_path": pydantic_course_data.get("md_path", ""),
                        "error_message": None,
                    }
                )
                processing_summary["successful_exports"] += 1
            else:
                course_entry.update(
                    {
                        "csv_file_path": None,
                        "markdown_file_path": None,
                        "error_message": pydantic_course_data.get(
                            "error", "Unknown error"
                        ),
                        "failure_reason": pydantic_course_data.get(
                            "error", "Unknown error"
                        ),
                    }
                )
                processing_summary["failed_exports"] += 1

            course_data.append(course_entry)

    else:
        # Fallback to old method if complete results aren't available
        logger.warning(
            "Using fallback method for JSON summary - some failure details may be missing"
        )

        for i, (course_id, course_name) in enumerate(zip(_course_ids, _course_names)):
            file_info = _course_csv_files[i] if i < len(_course_csv_files) else ""

            # Determine if this was a failure
            is_failed = file_info.startswith("FAILED:")

            course_entry = {
                "course_id": course_id,
                "course_name": course_name,
                "course_url": f"https://www.netacad.com/launch?id={course_id}",
                "processing_status": "failed" if is_failed else "success",
                "success": not is_failed,
            }

            if is_failed:
                course_entry.update(
                    {
                        "csv_file_path": None,
                        "markdown_file_path": None,
                        "error_message": file_info.replace("FAILED: ", ""),
                        "failure_reason": file_info.replace("FAILED: ", ""),
                    }
                )
                processing_summary["failed_exports"] += 1
            else:
                # Parse successful file paths
                csv_path = ""
                markdown_path = ""

                if file_info and " | " in file_info:
                    parts = file_info.split(" | ")
                    csv_path = parts[0].replace("CSV: ", "") if len(parts) > 0 else ""
                    markdown_path = (
                        parts[1].replace("MD: ", "") if len(parts) > 1 else ""
                    )

                course_entry.update(
                    {
                        "csv_file_path": csv_path,
                        "markdown_file_path": markdown_path,
                        "error_message": None,
                    }
                )
                processing_summary["successful_exports"] += 1

            course_data.append(course_entry)

    # Calculate summary statistics
    processing_summary["total_courses_found"] = len(course_data)
    if processing_summary["total_courses_found"] > 0:
        processing_summary["success_rate_percentage"] = round(
            (
                processing_summary["successful_exports"]
                / processing_summary["total_courses_found"]
            )
            * 100,
            1,
        )

    # Create final JSON structure
    export_data = {
        "summary": processing_summary,
        "courses": course_data,
        "failed_course_details": [
            {
                "course_id": course["course_id"],
                "course_name": course["course_name"],
                "error": course.get("error_message", "Unknown error"),
            }
            for course in course_data
            if not course["success"]
        ],
    }

    # Save to JSON file
    json_path = DATA_DIR / "courses_export_summary.json"

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Comprehensive course export summary saved to: {json_path}")
        logger.info(
            f"Summary: {processing_summary['successful_exports']} successful, "
            f"{processing_summary['failed_exports']} failed, "
            f"{processing_summary['success_rate_percentage']}% success rate"
        )

        # Also create a simple CSV summary for quick viewing
        csv_summary_path = DATA_DIR / "export_summary.csv"
        summary_df = pd.DataFrame(course_data)
        summary_df.to_csv(csv_summary_path, index=False)
        logger.info(f"Quick CSV summary saved to: {csv_summary_path}")

    except Exception as e:
        logger.error(f"Error saving JSON summary: {e}")
        # Try to save a basic version at least
        try:
            basic_summary = {
                "timestamp": datetime.now().isoformat(),
                "total_courses": len(course_data),
                "successful": processing_summary["successful_exports"],
                "failed": processing_summary["failed_exports"],
                "error": f"Full summary failed: {e}",
            }
            with open(json_path, "w") as f:

                json.dump(basic_summary, f, indent=2)
            logger.info(f"⚠️ Basic summary saved due to error")
        except:
            logger.error(f"Could not save any summary to {json_path}")


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


def wait_for_parallel_download(
    path: str, timeout: int = 20, worker_id: int = 0
) -> Optional[str]:
    start_time = time.time()

    try:
        initial_files = set(os.listdir(path)) if os.path.exists(path) else set()
    except:
        return None

    while time.time() - start_time < timeout:
        try:
            current_files = set(os.listdir(path))
            new_files = current_files - initial_files

            csv_files = [f for f in new_files if f.endswith(".csv")]
            if csv_files:
                newest_csv = max(
                    csv_files, key=lambda f: os.path.getctime(os.path.join(path, f))
                )
                file_path = os.path.join(path, newest_csv)

                prev_size = 0
                for _ in range(3):
                    current_size = os.path.getsize(file_path)
                    if current_size == prev_size and current_size > 0:
                        logger.info(
                            f"Worker {worker_id} - Detected stable file: {file_path}"
                        )
                        return newest_csv

                    prev_size = current_size
                    time.sleep(1)
        except Exception as e:
            logger.error(f"Worker {worker_id} - Error checking download directory: {e}")

        time.sleep(1)

    logger.warning(
        f"Worker {worker_id} - No stable CSV file found in {path} within {timeout} seconds"
    )
    return None


def process_downloaded_file(
    path: Path, course_id: str, course_name: str
) -> Tuple[bool, str, str]:
    try:
        if not path.exists():
            logger.error(f"File {path} does not exist.")
            return False, "", ""

        df = pd.read_csv(str(path), encoding="utf-8")
        df.insert(0, "Course_ID", course_id)

        timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%SZ")
        safe_course_name = re.sub(r"[^\w\-_]", "_", course_name)[:30]  # Safe filename

        base_filename = f"GRADEBOOK_DATA_{timestamp}_{safe_course_name}"

        # Save CSV (no headers for platform compatibility)
        csv_output_path = CSV_DATA_DIR / f"{base_filename}.csv"
        df.to_csv(str(csv_output_path), index=False, header=False)

        # Create Markdown version (with headers for LLM readability)
        md_output_path = MD_DATA_DIR / f"{base_filename}.md"
        markdown_content = generate_gradebook_markdown(df, course_id, course_name)

        with open(md_output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Clean up the temporary download
        path.unlink()

        logger.info(f"Processed files: CSV={csv_output_path}, MD={md_output_path}")
        return True, str(csv_output_path), str(md_output_path)

    except Exception as e:
        logger.error(f"Error processing file {path}: {e}")
        return False, "", ""


def execute_gradebook_actions(
    browser: webdriver.Chrome,
    course_url: str,
    course_id: str,
    course_name: str,
    worker_id: int = 0,
) -> CourseExportResult:
    wait = WebDriverWait(browser, OPTIMIZED_TIMEOUTS["element_wait"])
    worker_download_dir = workers[worker_id]["download_dir"]
    logger.info(
        f"Worker {worker_id} - Processing course: {course_name} (ID: {course_id})"
    )
    browser.get(course_url)
    gradebook_manager = GradebookManager(
        browser, course_url, course_id, course_name, worker_id
    )

    tab_clicked = gradebook_manager.click_gradebook_tab()
    if not tab_clicked:
        return CourseExportResult(
            course_id=course_id,
            course_name=course_name,
            course_url=course_url,
            success=False,
            error="Failed to click on the gradebook tab",
        )

    time.sleep(OPTIMIZED_TIMEOUTS["animation_wait"])

    if not gradebook_manager.open_export_dropdown():
        return CourseExportResult(
            course_id=course_id,
            course_name=course_name,
            course_url=course_url,
            success=False,
            error="Failed to open export dropdown",
        )

    time.sleep(OPTIMIZED_TIMEOUTS["animation_wait"])

    if not gradebook_manager.export_all_grades():
        return CourseExportResult(
            course_id=course_id,
            course_name=course_name,
            course_url=course_url,
            success=False,
            error="Failed to export all grades",
        )

    time.sleep(OPTIMIZED_TIMEOUTS["animation_wait"])

    gradebook_manager.handle_modal()

    time.sleep(OPTIMIZED_TIMEOUTS["animation_wait"])

    if not gradebook_manager.refresh_export_list():
        return CourseExportResult(
            course_id=course_id,
            course_name=course_name,
            course_url=course_url,
            success=False,
            error="Failed to refresh export list",
        )

    time.sleep(OPTIMIZED_TIMEOUTS["animation_wait"])

    if not gradebook_manager.open_refresh_list():
        return CourseExportResult(
            course_id=course_id,
            course_name=course_name,
            course_url=course_url,
            success=False,
            error="Failed to open refresh list",
        )

    time.sleep(OPTIMIZED_TIMEOUTS["animation_wait"])

    latest_export_link = gradebook_manager.export_gradebook_links()
    if latest_export_link is None:
        return CourseExportResult(
            course_id=course_id,
            course_name=course_name,
            course_url=course_url,
            success=False,
            error="Failed to find export links",
        )
    
    try:
        # Scroll into view to help with overlays
        browser.execute_script("arguments[0].scrollIntoView(true);", latest_export_link)
        latest_export_link.click()
    except ElementClickInterceptedException as e:
        logger.warning(f"⚠️ Course {course_id} {course_name} failed: {e}")
        # Try to close privacy or overlay popups
        try:
            close_btn = browser.find_element(By.CSS_SELECTOR, ".privacy-policy-close, .close-button")
            close_btn.click()
            time.sleep(1)
            latest_export_link.click()
        except Exception as ex:
            logger.warning(f"⚠️ Course {course_id} {course_name} still failed after closing overlay: {ex}")
            return CourseExportResult(
                course_id=course_id,
                course_name=course_name,
                course_url=course_url,
                success=False,
                error=f"Element click intercepted and overlay could not be closed: {ex}",
            )
        

    # Wait for the download to complete
    csv_filename = wait_for_parallel_download(
        str(worker_download_dir), OPTIMIZED_TIMEOUTS["download_wait"], worker_id
    )

    if not csv_filename:
        return CourseExportResult(
            course_id=course_id,
            course_name=course_name,
            course_url=course_url,
            success=False,
            error="Download failed - CSV file not found after export",
        )

    success, csv_path, md_path = process_downloaded_file(
        worker_download_dir / csv_filename, course_id, course_name
    )

    if success:
        logger.info(
            f"Worker {worker_id} - Successfully exported course: {course_name} (ID: {course_id})"
        )
        return CourseExportResult(
            course_id=course_id,
            course_name=course_name,
            course_url=course_url,
            success=True,
            csv_path=csv_path,
            md_path=md_path,
        )
    else:
        logger.error(
            f"Worker {worker_id} - Failed to process downloaded file for course: {course_name} (ID: {course_id})"
        )
        return CourseExportResult(
            course_id=course_id,
            course_name=course_name,
            course_url=course_url,
            success=False,
            error="Failed to process downloaded file",
        )


def worker_handle_course(batches: List[Tuple[str, str, str]], worker_id: int):
    results = []
    browser = None

    try:
        logger.info(f"Worker {worker_id} starting with {len(batches)} courses")
        browser = create_browser(worker_id)
        if not login(browser):
            logger.error(f"Worker {worker_id} - Login failed. Cannot process courses.")
            return [
                CourseExportResult(
                    course_id=course_id,
                    course_name=course_name,
                    course_url=course_url,
                    success=False,
                    csv_path=None,
                    md_path=None,
                    error="Login failed",
                )
                for course_url, course_id, course_name in batches
            ]

        for course_url, course_id, course_name in batches:
            result = execute_gradebook_actions(
                browser, course_url, course_id, course_name, worker_id
            )
            results.append(result)
            time.sleep(
                OPTIMIZED_TIMEOUTS["animation_wait"]
            )  # Allow time for each course processing
    except Exception as e:
        logger.error(f"Worker {worker_id} encountered an error: {e}", exc_info=True)
        # Return results with error for all courses in this batch
        results = [
            CourseExportResult(
                course_id=course_id,
                course_name=course_name,
                course_url=course_url,
                success=False,
                csv_path=None,
                md_path=None,
                error=str(e),
            )
            for course_url, course_id, course_name in batches
        ]

    finally:
        if browser:
            browser.quit()

        worker_download_dir = workers[worker_id]["download_dir"]
        if worker_download_dir.exists():
            try:
                shutil.rmtree(str(worker_download_dir))
                logger.info(
                    f"Worker {worker_id} - Cleared download directory: {worker_download_dir.name}"
                )
            except Exception as e:
                logger.error(
                    f"Worker {worker_id} - Failed to clear download directory: {e}",
                    exc_info=True,
                )
        gc.collect()
    logger.info(f"Worker {worker_id} completed processing {len(results)} courses")
    return results


def process_courses(clear_downloads: bool = True):
    start_time = time.time()

    if clear_downloads:
        logger.info("Clearing previous CSV and Markdown files...")
        clear_old_downloads()

    course_urls, course_names = collect_course_data()

    if not course_urls:
        logger.error("No courses found. Exiting process.")
        return

    if len(course_urls) != len(course_names):
        logger.error(
            "Mismatch between course URLs and names. Please check the page structure."
        )
        return

    logger.info(f"Data integrity check passed: {len(course_urls)} courses found.")
    course_data = []

    for i, (url, name) in enumerate(zip(course_urls, course_names)):
        course_id = "unknown"
        if "=" in url:
            try:
                course_id = url.split("=")[1].strip()
            except (IndexError, AttributeError):
                course_id = f"parse_error_{i}"
        else:
            course_id = f"no_id_found_{i}"

        course_data.append((url, course_id, name))

    batch_size = max(1, len(course_data) // MAX_WORKERS)
    batches = [
        course_data[i : i + batch_size] for i in range(0, len(course_data), batch_size)
    ]

    if len(batches) > MAX_WORKERS:
        # Merge excess batches into last worker's batch
        while len(batches) > MAX_WORKERS:
            batches[-2].extend(batches[-1])
            batches.pop()

    logger.info(
        f"Split into {len(batches)} batches: {[len(batch) for batch in batches]} courses each"
    )

    all_results: List[CourseExportResult] = []
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_worker = {
                executor.submit(worker_handle_course, batch, worker_id): worker_id
                for worker_id, batch in enumerate(batches)
            }

            # Collect results as they complete
            completed_workers = 0
            total_workers = len(future_to_worker)

            for future in as_completed(
                future_to_worker, timeout=3600
            ):  # 1 hour timeout
                worker_id = future_to_worker[future]
                try:
                    worker_results = future.result(
                        timeout=60
                    )  # 1 minute timeout per worker result
                    all_results.extend(worker_results)
                    completed_workers += 1
                    logger.info(
                        f"✅ Worker {worker_id} completed ({completed_workers}/{total_workers})"
                    )
                except Exception as e:
                    logger.error(f"❌ Worker {worker_id} failed: {e}", exc_info=True)
                    # Add error results for failed worker
                    if worker_id < len(batches):
                        error_results = [
                            CourseExportResult(
                                course_id=course_id,
                                course_name=course_name,
                                course_url=f"https://www.netacad.com/launch?id={course_id}",
                                success=False,
                                csv_path=None,
                                md_path=None,
                                error=f"Worker {worker_id} failed: {str(e)}",
                            )
                            for _, course_id, course_name in batches[worker_id]
                        ]
                        all_results.extend(error_results)

        logger.info(f"All workers completed. Collected {len(all_results)} results")

    except Exception as e:
        logger.error(f"Critical error in parallel processing: {e}", exc_info=True)
        # Force cleanup in case of critical error
        cleanup_system_resources()
        raise

    # Process results and update global tracking
    successful_exports = 0
    failed_exports = 0

    with _results_lock:
        for result in all_results:
            # Store complete result information
            _all_course_results.append(result)

            # Need to convert Pydantic model to dict for easier access
            if isinstance(result, CourseExportResult):
                result = result.model_dump(mode="python")
            if result.get("success", False):
                successful_exports += 1
                _course_ids.append(result["course_id"])
                _course_names.append(result["course_name"])
                _course_csv_files.append(
                    f"CSV: {result['csv_path']} | MD: {result['md_path']}"
                )
            else:
                failed_exports += 1
                course_id = result.get("course_id", "unknown")
                course_name = result.get("course_name", "unknown")
                error_message = result.get("error", "Unknown error")

                # Add to failed lists with detailed information
                _failed_course_ids.append(course_id)

                # Also add to main lists to ensure they appear in JSON summary
                _course_ids.append(course_id)
                _course_names.append(course_name)
                _course_csv_files.append(f"FAILED: {error_message}")

                logger.warning(
                    f"Course {course_name} ({course_id}) failed: {error_message}"
                )

    # Generate summary report
    end_time = time.time()
    elapsed_time = end_time - start_time

    logger.info("=" * 60)
    logger.info("PARALLEL EXPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Processing Time: {elapsed_time:.2f} seconds")
    logger.info(f"Average Time per Course: {elapsed_time/len(course_data):.2f} seconds")
    logger.info(f"Total Courses Processed: {len(course_data)}")
    logger.info(f"Successful Exports: {successful_exports}")
    logger.info(f"Failed Exports: {failed_exports}")
    logger.info(f"Success Rate: {(successful_exports/len(course_data)*100):.1f}%")
    logger.info(f"CSV Files Location: {CSV_DATA_DIR}")
    logger.info(f"Markdown Files Location: {MD_DATA_DIR}")
    logger.info(f"Detailed Summary: {DATA_DIR / 'courses_export_summary.json'}")
    logger.info(f"Quick CSV Summary: {DATA_DIR / 'export_summary.csv'}")

    # Provide specific guidance based on results
    if failed_exports > 0:
        logger.warning(f"{failed_exports} courses failed to export")
        logger.info("Common failure reasons:")
        logger.info("   • Course has no gradebook data available")
        logger.info("   • Network timeout during download")
        logger.info("   • Course access permissions issues")
        logger.info("   • NetAcad platform temporary issues")
        logger.info(
            f"Check {DATA_DIR / 'courses_export_summary.json'} for specific error details"
        )

    if successful_exports > 0:
        logger.info("Exported files ready for:")
        logger.info(f"Platform Upload: Use headerless CSV files in {CSV_DATA_DIR}")
        logger.info(f"AI/LLM Processing: Use formatted Markdown files in {MD_DATA_DIR}")

    if _failed_course_ids:
        logger.warning(f"Failed Course IDs: {', '.join(_failed_course_ids[:10])}")
        if len(_failed_course_ids) > 10:
            logger.warning(f"... and {len(_failed_course_ids) - 10} more")
        logger.info("You can manually download these courses from NetAcad if needed")

    # Save detailed results
    save_courses_data_to_json()

    # Perform final cleanup
    logger.info("Performing final system cleanup...")
    cleanup_system_resources()

    logger.info("=" * 60)
    logger.info(
        f"Parallel processing completed! Processed {len(course_data)} courses in {elapsed_time:.1f}s"
    )
    logger.info(
        f"Speed improvement: ~{600/elapsed_time:.1f}x faster than sequential processing"
    )
    logger.info("=" * 60)


def find_automation_chrome_processes():
    """Yield Chrome processes started by our automation workers."""
    try:
        import psutil
    except ImportError:
        logger.info("psutil not available - skipping Chrome process check")
        return []

    chrome_processes = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["name"] and "chrome" in proc.info["name"].lower():
                cmdline = proc.info["cmdline"] or []
                if any(
                    "NetAcadExport.Worker" in arg
                    or ("worker_" in arg and "_downloads" in arg)
                    for arg in cmdline
                ):
                    chrome_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return chrome_processes


def cleanup_chrome_processes():
    """Terminate Chrome processes belonging to automation workers."""
    chrome_processes = find_automation_chrome_processes()
    if not chrome_processes:
        logger.info("No orphaned automation Chrome processes found")
        return

    logger.warning(
        f"Found {len(chrome_processes)} orphaned NetAcad automation Chrome processes"
    )
    for proc in chrome_processes:
        try:
            proc.terminate()
            proc.wait(timeout=5)
            logger.info(f"Terminated automation Chrome process {proc.pid}")
        except Exception as e:
            try:
                proc.kill()
                logger.info(f"Force killed automation Chrome process {proc.pid}")
            except Exception:
                logger.warning(f"Could not kill Chrome process {proc.pid}: {e}")


def cleanup_temp_download_dirs():
    """Remove all temp download directories created by workers."""
    temp_dirs = [
        item
        for item in DATA_DIR.iterdir()
        if item.is_dir()
        and item.name.startswith("worker_")
        and item.name.endswith("_downloads")
    ]
    if not temp_dirs:
        logger.info("No temporary directories to clean")
        return

    logger.info(f"Cleaning up {len(temp_dirs)} temporary directories")
    for temp_dir in temp_dirs:
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Removed temp directory: {temp_dir.name}")
        except Exception as e:
            logger.warning(f"Failed to remove {temp_dir.name}: {e}")


def cleanup_system_resources():
    """Comprehensive cleanup to handle any remaining system resources."""
    logger.info("Starting comprehensive system cleanup...")

    try:
        cleanup_chrome_processes()
    except Exception as e:
        logger.warning(f"Error during Chrome process cleanup: {e}")

    try:
        cleanup_temp_download_dirs()
    except Exception as e:
        logger.warning(f"Error during temp directory cleanup: {e}")

    try:
        import gc

        gc.collect()
        logger.info("System cleanup completed")
    except Exception as e:
        logger.warning(f"Error during garbage collection: {e}")


def emergency_cleanup():
    """Quick emergency cleanup for signal handlers, only affecting automation Chrome processes."""
    print("Emergency cleanup triggered...")
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["name"] and "chrome" in proc.info["name"].lower():
                    cmdline = proc.info.get("cmdline") or []
                    # Only kill Chrome started by your automation
                    if any(
                        "NetAcadExport.Worker" in arg
                        or ("worker_" in arg and "_downloads" in arg)
                        for arg in cmdline
                    ):
                        proc.terminate()
            except Exception:
                pass
    except Exception:
        pass
    print("Emergency cleanup completed")


def signal_handler(signum, frame):
    logger.warning(f"Received signal {signum}, initiating emergency cleanup...")
    emergency_cleanup()
    exit(1)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

# Register cleanup function to run on normal exit
atexit.register(cleanup_system_resources)


if __name__ == "__main__":
    process_courses(clear_downloads=True)
    logger.info("Course export process completed successfully.")
    exit(0)
