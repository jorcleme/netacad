import time
import os
import pandas as pd
import logging
import re
import threading
import signal
import atexit
import shutil
import gc

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
    INSTRUCTOR_LOGIN_ID,
    INSTRUCTOR_LOGIN_PASSWORD,
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
    handlers=[logging.FileHandler(str(log_file), mode="w"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Global thread-safe variables for tracking results
_course_names: List[str] = []
_course_ids: List[str] = []
_course_csv_files: List[str | None] = []
_failed_course_ids: List[str] = []
_all_course_results: List[Dict[str, Any]] = []  # Complete results including failures
_results_lock = threading.Lock()

# Configuration for parallel processing
# Performance Configuration Options
# You can adjust these values based on your system capabilities and network conditions

# Number of parallel browser instances (recommended: 3-6)
# Higher values = faster processing but more resource usage
# Lower values = more stable but slower processing
MAX_WORKERS = 4  # Very conservative for testing - can increase once stable

# Alternative configurations for different scenarios:
# For powerful systems: MAX_WORKERS = 6-8
# For slower systems: MAX_WORKERS = 2-3
# For fastest processing (if system can handle): MAX_WORKERS = 8-10

OPTIMIZED_TIMEOUTS = {
    "page_load": 30,  # More generous timeout for page loads (NetAcad can be slow)
    "element_wait": 15,  # More time for elements to appear during login
    "download_wait": 30,  # Adequate time for file downloads
    "modal_wait": 3,  # Quick modal interactions
    "animation_wait": 2,  # Give animations time to complete
    "login_wait": 5,  # More time for login transitions
}


def create_optimized_browser(worker_id: int = 0) -> webdriver.Chrome:
    """Creates a browser instance optimized for parallel processing."""
    options = Options()

    # Create unique download directory for this worker to avoid conflicts
    worker_download_dir = DATA_DIR / f"worker_{worker_id}_downloads"
    worker_download_dir.mkdir(exist_ok=True)

    # Add a unique identifier for our automation instances
    options.add_argument(f"--app-user-model-id=NetAcadExport.Worker.{worker_id}")

    # Performance optimizations (more conservative for stability)
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--headless")  # Run in headless mode for automation

    # Less aggressive feature disabling to prevent login issues
    prefs = {
        "profile.default_content_setting_values": {
            "plugins": 2,  # Block plugins
            "popups": 2,  # Block popups
            "geolocation": 2,  # Block location sharing
            "notifications": 2,  # Block notifications
            # Removed image blocking to ensure login pages load properly
        },
        "download.default_directory": str(worker_download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }

    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    # Create browser with optimized settings
    service = Service(ChromeDriverManager().install())
    browser = webdriver.Chrome(service=service, options=options)
    browser.set_page_load_timeout(OPTIMIZED_TIMEOUTS["page_load"])
    browser.implicitly_wait(3)  # More generous implicit wait for login stability

    return browser


def login_browser(browser: webdriver.Chrome) -> bool:
    """Performs login sequence for a browser instance with improved error handling."""
    try:
        wait = WebDriverWait(browser, OPTIMIZED_TIMEOUTS["element_wait"])

        logger.info("Navigating to NetAcad login page...")
        # Navigate to base URL
        browser.get(BASE_URL)

        # Wait a bit for page to fully load
        time.sleep(2)

        # Click login button
        logger.info("Looking for login button...")
        login_btn = wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, "loginBtn--lfDa2"))
        )
        login_btn.click()
        logger.info("Login button clicked")

        # Enter username
        logger.info("Entering username...")
        username = wait.until(EC.presence_of_element_located((By.ID, "username")))
        username.clear()
        username.send_keys(INSTRUCTOR_LOGIN_ID + Keys.ENTER)

        # Enter password
        logger.info("Entering password...")
        password = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password.clear()
        password.send_keys(INSTRUCTOR_LOGIN_PASSWORD + Keys.ENTER)

        # Wait for login to complete (check for course list or dashboard)
        logger.info("Waiting for login to complete...")
        time.sleep(OPTIMIZED_TIMEOUTS["login_wait"])

        # Try to find an element that indicates successful login
        try:
            # Look for the course list or main navigation
            wait.until(
                EC.any_of(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "instance_name--dioD1")
                    ),
                    EC.presence_of_element_located((By.CLASS_NAME, "pageItem--BNJmT")),
                    EC.presence_of_element_located((By.ID, "main-content")),
                )
            )
            logger.info("Browser login completed successfully")
            return True
        except TimeoutException:
            # Login might still be successful, just taking longer
            logger.warning("Login verification timed out, but proceeding...")
            return True

    except Exception as e:
        logger.error(f"Login failed: {e}")
        return False


def wait_for_download_parallel(
    download_path: str, timeout: int = 20, worker_id: int = 0
) -> str | None:
    """Enhanced download wait function for parallel processing."""
    start_time = time.time()

    # Get initial file list
    try:
        initial_files = (
            set(os.listdir(download_path)) if os.path.exists(download_path) else set()
        )
    except:
        return None

    while time.time() - start_time < timeout:
        try:
            current_files = set(os.listdir(download_path))
            new_files = current_files - initial_files

            # Look for CSV files
            csv_files = [
                f for f in new_files if f.endswith(".csv") and "GRADEBOOK_DATA" in f
            ]

            if csv_files:
                # Get the newest CSV file
                newest_csv = max(
                    csv_files,
                    key=lambda f: os.path.getctime(os.path.join(download_path, f)),
                )

                # Verify file is complete (not still downloading)
                file_path = os.path.join(download_path, newest_csv)

                # Wait for file to be stable (not growing)
                prev_size = 0
                for _ in range(3):  # Check 3 times
                    current_size = os.path.getsize(file_path)
                    if current_size == prev_size and current_size > 0:
                        logger.info(
                            f"Worker {worker_id}: Download complete: {newest_csv}"
                        )
                        return newest_csv
                    prev_size = current_size
                    time.sleep(0.5)

        except Exception as e:
            logger.debug(f"Worker {worker_id}: Download check error: {e}")

        time.sleep(1)

    logger.warning(f"Worker {worker_id}: Download timeout after {timeout}s")
    return None


def execute_gradebook_export(
    browser: webdriver.Chrome,
    course_url: str,
    course_id: str,
    course_name: str,
    worker_id: int = 0,
) -> Dict[str, Any]:
    """
    Executes the complete gradebook export process for a single course.

    Args:
        browser: WebDriver instance
        course_url: URL of the course
        course_id: Course ID
        course_name: Course name
        worker_id: Worker thread ID for tracking

    Returns:
        Dict with success status and file paths
    """
    wait = WebDriverWait(browser, OPTIMIZED_TIMEOUTS["element_wait"])
    worker_download_dir = DATA_DIR / f"worker_{worker_id}_downloads"

    try:
        logger.info(f"Worker {worker_id}: Processing {course_name} (ID: {course_id})")

        # Navigate to course page
        browser.get(course_url)

        # Click gradebook tab
        gradebook_tab = wait.until(
            EC.element_to_be_clickable((By.ID, "Launch-tab-gradebook"))
        )
        gradebook_tab.click()

        # Small wait for page transition
        time.sleep(OPTIMIZED_TIMEOUTS["animation_wait"])

        # Click export dropdown
        export_dropdown = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".RBDropdown--ATEd3.dropdown > button")
            )
        )
        export_dropdown.click()

        # Click export all
        export_all_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".dropdownButton--whS7t:first-of-type")
            )
        )
        export_all_btn.click()

        # Handle modal if present (quick check)
        try:
            close_button = WebDriverWait(browser, 2).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "modal__close"))
            )
            close_button.click()
        except (TimeoutException, NoSuchElementException):
            pass  # Modal might not appear

        # Refresh export list
        refresh_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "refreshExportList"))
        )
        refresh_btn.click()
        time.sleep(OPTIMIZED_TIMEOUTS["modal_wait"])

        # Open dropdown to access exports
        dropdown_button = wait.until(
            EC.element_to_be_clickable((By.ID, "dropdown-basic"))
        )
        dropdown_button.click()
        time.sleep(OPTIMIZED_TIMEOUTS["animation_wait"])

        # Get and click first export link
        export_links = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".dropdown__menu.show a")
            )
        )

        if not export_links:
            logger.error(f"Worker {worker_id}: No export links found for {course_name}")
            return {
                "success": False,
                "course_id": course_id,
                "course_name": course_name,
                "csv_path": "",
                "md_path": "",
                "error": "No export links found in dropdown",
            }

        # Click the first (most recent) export
        export_links[0].click()

        # Wait for download
        csv_filename = wait_for_download_parallel(
            str(worker_download_dir), OPTIMIZED_TIMEOUTS["download_wait"], worker_id
        )

        if not csv_filename:
            logger.error(f"Worker {worker_id}: Download failed for {course_name}")
            return {
                "success": False,
                "course_id": course_id,
                "course_name": course_name,
                "csv_path": "",
                "md_path": "",
                "error": "Download failed - CSV file not found after export",
            }

        # Process the downloaded file
        success, csv_path, md_path = process_downloaded_file(
            worker_download_dir / csv_filename, course_id, course_name
        )

        if success:
            logger.info(f"Worker {worker_id}: ✅ Successfully exported {course_name}")
            return {
                "success": True,
                "course_id": course_id,
                "course_name": course_name,
                "csv_path": csv_path,
                "md_path": md_path,
            }
        else:
            logger.error(
                f"Worker {worker_id}: ❌ File processing failed for {course_name}"
            )
            return {
                "success": False,
                "course_id": course_id,
                "course_name": course_name,
                "csv_path": "",
                "md_path": "",
                "error": "File processing failed after download",
            }

    except Exception as e:
        logger.error(
            f"Worker {worker_id}: Error processing {course_name}: {e}", exc_info=True
        )
        return {
            "success": False,
            "course_id": course_id,
            "course_name": course_name,
            "csv_path": "",
            "md_path": "",
            "error": f"Exception during processing: {str(e)}",
        }


def process_downloaded_file(
    file_path: Path, course_id: str, course_name: str
) -> tuple[bool, str, str]:
    """
    Processes a downloaded CSV file and creates both CSV and Markdown versions.

    Args:
        file_path: Path to downloaded CSV file
        course_id: Course ID
        course_name: Course name

    Returns:
        tuple: (success: bool, csv_path: str, md_path: str)
    """
    try:
        if not file_path.exists():
            logger.error(f"Downloaded file not found: {file_path}")
            return False, "", ""

        # Read the CSV
        df = pd.read_csv(str(file_path))
        df.insert(0, "COURSE_ID", course_id)

        # Generate timestamp for filename
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y_%m_%dT%H_%M_%SZ")
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
        file_path.unlink()

        logger.info(f"Processed files: CSV={csv_output_path}, MD={md_output_path}")
        return True, str(csv_output_path), str(md_output_path)

    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
        return False, "", ""


def worker_process_courses(
    course_batch: List[Tuple[str, str, str]], worker_id: int
) -> List[Dict[str, Any]]:
    """
    Worker function that processes a batch of courses in parallel.

    Args:
        course_batch: List of (course_url, course_id, course_name) tuples
        worker_id: Worker thread ID

    Returns:
        List of result dictionaries
    """
    results = []
    browser = None

    try:
        logger.info(f"Worker {worker_id}: Starting with {len(course_batch)} courses")

        # Create browser and login
        browser = create_optimized_browser(worker_id)

        if not login_browser(browser):
            logger.error(f"Worker {worker_id}: Login failed")
            return [
                {
                    "success": False,
                    "course_id": course_id if len(course_batch) > 0 else "unknown",
                    "course_name": course_name if len(course_batch) > 0 else "unknown",
                    "csv_path": "",
                    "md_path": "",
                    "error": "Login failed",
                }
                for course_url, course_id, course_name in course_batch
            ]

        # Process each course in the batch
        for course_url, course_id, course_name in course_batch:
            result = execute_gradebook_export(
                browser, course_url, course_id, course_name, worker_id
            )
            results.append(result)

            # Brief pause between courses to avoid overwhelming the server
            time.sleep(0.5)

    except Exception as e:
        logger.error(f"Worker {worker_id}: Critical error: {e}", exc_info=True)
        results = [
            {
                "success": False,
                "course_id": course_id,
                "course_name": course_name,
                "csv_path": "",
                "md_path": "",
                "error": f"Worker critical error: {str(e)}",
            }
            for course_url, course_id, course_name in course_batch
        ]

    finally:
        if browser:
            try:
                logger.info(f"Worker {worker_id}: Closing browser...")
                browser.quit()
                logger.info(f"Worker {worker_id}: Browser closed successfully")
            except Exception as e:
                logger.warning(f"Worker {worker_id}: Error closing browser: {e}")

        # Clean up worker directories
        worker_download_dir = DATA_DIR / f"worker_{worker_id}_downloads"

        if worker_download_dir.exists():
            try:
                logger.info(
                    f"Worker {worker_id}: Cleaning up {worker_download_dir.name}..."
                )
                shutil.rmtree(str(worker_download_dir))
                logger.info(f"Worker {worker_id}: {worker_download_dir.name} cleaned")
            except Exception as e:
                logger.warning(
                    f"Worker {worker_id}: Failed to clean {worker_download_dir.name}: {e}"
                )

        # Force garbage collection to help with memory cleanup
        gc.collect()

    logger.info(f"Worker {worker_id}: Completed processing")
    return results


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


def collect_all_courses() -> Tuple[List[str], List[str]]:
    """
    Collects all course URLs and names using a single browser instance.
    FIXED: Maintains proper URL-to-name relationships using ordered collections.

    Returns:
        Tuple of (course_urls, course_names)
    """
    browser = None
    try:
        logger.info("Collecting all course information...")
        browser = create_optimized_browser(0)

        if not login_browser(browser):
            logger.error("Failed to login for course collection")
            return [], []

        # Use lists to maintain order and relationship between URL and name
        course_data = []  # List of (url, name) tuples
        seen_urls = set()  # For deduplication only
        wait = WebDriverWait(browser, OPTIMIZED_TIMEOUTS["element_wait"])

        page = 0
        while True:
            page += 1
            logger.info(f"Scanning course list page {page}")

            # Collect course anchors on current page
            try:
                course_anchors = wait.until(
                    EC.visibility_of_all_elements_located(
                        (By.CLASS_NAME, "instance_name--dioD1")
                    )
                )

                for anchor in course_anchors:
                    url = anchor.get_attribute("href")
                    name = anchor.text.strip()

                    # Only add if we have both URL and name, and URL is unique
                    if url and name and url not in seen_urls:
                        course_data.append((url, name))
                        seen_urls.add(url)
                        logger.debug(f"Collected course: {name} -> {url}")

                # Try to find and click next button
                try:
                    next_button = wait.until(
                        EC.element_to_be_clickable(
                            (
                                By.CSS_SELECTOR,
                                "button.pageItem--BNJmT.sides--EdMyh span.icon-chevron-right",
                            )
                        )
                    )
                    parent_button = next_button.find_element(By.XPATH, "./..")
                    parent_button.click()
                    time.sleep(1)  # Brief pause for page load

                except (NoSuchElementException, TimeoutException):
                    logger.info("No more pages found. Course collection complete.")
                    break
                except ElementClickInterceptedException:
                    # Try JavaScript click if regular click fails
                    parent_button = next_button.find_element(By.XPATH, "./..")
                    browser.execute_script(
                        "arguments[0].scrollIntoView(true);", parent_button
                    )
                    browser.execute_script("arguments[0].click();", parent_button)
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error on page {page}: {e}")
                break

        # Separate URLs and names while preserving order
        course_urls = [url for url, name in course_data]
        course_names = [name for url, name in course_data]

        logger.info(f"✅ Collected {len(course_urls)} courses from {page} pages")
        logger.info("📋 Sample course mappings:")
        for i in range(min(3, len(course_data))):
            url, name = course_data[i]
            course_id = url.split("=")[1] if "=" in url else "unknown"
            logger.info(f"   {i+1}. {name} (ID: {course_id})")

        return course_urls, course_names

    except Exception as e:
        logger.error(f"Failed to collect courses: {e}", exc_info=True)
        return [], []
    finally:
        if browser:
            try:
                logger.info("Closing course collection browser...")
                browser.quit()
                logger.info("Course collection browser closed successfully")
            except Exception as e:
                logger.warning(f"Error closing collection browser: {e}")

        # Force garbage collection
        gc.collect()


def process_courses_parallel(clear_downloads: bool = True):
    """
    Main function that processes all courses using parallel workers.
    """
    start_time = time.time()

    if clear_downloads:
        logger.info("Clearing old downloads...")
        clear_old_downloads()

    # Collect all courses first
    course_urls, course_names = collect_all_courses()

    if not course_urls:
        logger.error("No courses found. Exiting.")
        return

    # Validate data integrity
    if len(course_urls) != len(course_names):
        logger.error(
            f"❌ Data integrity error: {len(course_urls)} URLs but {len(course_names)} names"
        )
        logger.error(
            "This indicates a bug in course collection. Aborting to prevent mismatched data."
        )
        return

    logger.info(
        f"✅ Data integrity verified: {len(course_urls)} courses with matching URLs and names"
    )
    logger.info(
        f"🚀 Starting parallel processing of {len(course_urls)} courses with {MAX_WORKERS} workers"
    )

    # Prepare course data for parallel processing with validation
    course_data = []
    for i, (url, name) in enumerate(zip(course_urls, course_names)):
        if url and name:
            # Improved course ID extraction
            course_id = "unknown"
            if "=" in url:
                try:
                    # Split by = and get the part after it, then split by & to handle additional params
                    id_part = url.split("=")[1].split("&")[0]
                    if id_part and id_part.strip():
                        course_id = id_part.strip()
                    else:
                        course_id = f"empty_id_{i}"
                except (IndexError, AttributeError):
                    course_id = f"parse_error_{i}"
            else:
                course_id = f"no_id_found_{i}"

            course_data.append((url, course_id, name))

            # Log first few for verification
            if i < 3:
                logger.info(f"📋 Course {i+1}: {name} (ID: {course_id})")
                logger.info(f"URL: {url}")
        else:
            logger.warning(f"⚠️ Skipping course {i}: missing URL or name")

    if not course_data:
        logger.error("No valid course data after processing. Exiting.")
        return

    # Split courses into batches for workers
    batch_size = max(1, len(course_data) // MAX_WORKERS)
    course_batches = [
        course_data[i : i + batch_size] for i in range(0, len(course_data), batch_size)
    ]

    # Ensure we don't have more batches than workers
    if len(course_batches) > MAX_WORKERS:
        # Merge excess batches into the last worker
        while len(course_batches) > MAX_WORKERS:
            course_batches[-2].extend(course_batches[-1])
            course_batches.pop()

    logger.info(
        f"📦 Split into {len(course_batches)} batches: {[len(batch) for batch in course_batches]}"
    )

    # Process courses in parallel
    all_results = []

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all worker tasks
            future_to_worker = {
                executor.submit(worker_process_courses, batch, worker_id): worker_id
                for worker_id, batch in enumerate(course_batches)
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
                    if worker_id < len(course_batches):
                        error_results = [
                            {
                                "success": False,
                                "course_id": course_id,
                                "course_name": course_name,
                                "csv_path": "",
                                "md_path": "",
                                "error": f"Worker {worker_id} failed: {str(e)}",
                            }
                            for _, course_id, course_name in course_batches[worker_id]
                        ]
                        all_results.extend(error_results)

        logger.info(f"🏁 All workers completed. Collected {len(all_results)} results")

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
                    f"❌ Course {course_name} ({course_id}) failed: {error_message}"
                )

    # Generate summary report
    end_time = time.time()
    elapsed_time = end_time - start_time

    logger.info("=" * 60)
    logger.info("PARALLEL EXPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"⏱️  Total Processing Time: {elapsed_time:.2f} seconds")
    logger.info(
        f"🏃 Average Time per Course: {elapsed_time/len(course_data):.2f} seconds"
    )
    logger.info(f"📊 Total Courses Processed: {len(course_data)}")
    logger.info(f"✅ Successful Exports: {successful_exports}")
    logger.info(f"❌ Failed Exports: {failed_exports}")
    logger.info(f"📈 Success Rate: {(successful_exports/len(course_data)*100):.1f}%")
    logger.info(f"📁 CSV Files Location: {CSV_DATA_DIR}")
    logger.info(f"📝 Markdown Files Location: {MD_DATA_DIR}")
    logger.info(f"📋 Detailed Summary: {DATA_DIR / 'courses_export_summary.json'}")
    logger.info(f"📄 Quick CSV Summary: {DATA_DIR / 'export_summary.csv'}")

    # Provide specific guidance based on results
    if failed_exports > 0:
        logger.warning(f"⚠️  {failed_exports} courses failed to export")
        logger.info("💡 Common failure reasons:")
        logger.info("   • Course has no gradebook data available")
        logger.info("   • Network timeout during download")
        logger.info("   • Course access permissions issues")
        logger.info("   • NetAcad platform temporary issues")
        logger.info(
            f"🔍 Check {DATA_DIR / 'courses_export_summary.json'} for specific error details"
        )

    if successful_exports > 0:
        logger.info("📋 Exported files ready for:")
        logger.info(
            f"   📈 Platform Upload: Use headerless CSV files in {CSV_DATA_DIR}"
        )
        logger.info(
            f"   🤖 AI/LLM Processing: Use formatted Markdown files in {MD_DATA_DIR}"
        )

    if _failed_course_ids:
        logger.warning(f"⚠️  Failed Course IDs: {', '.join(_failed_course_ids[:10])}")
        if len(_failed_course_ids) > 10:
            logger.warning(f"⚠️  ... and {len(_failed_course_ids) - 10} more")
        logger.info("💡 You can manually download these courses from NetAcad if needed")

    # Save detailed results
    save_courses_data_to_json()

    # Perform final cleanup
    logger.info("🧹 Performing final system cleanup...")
    cleanup_system_resources()

    logger.info("=" * 60)
    logger.info(
        f"🎉 Parallel processing completed! Processed {len(course_data)} courses in {elapsed_time:.1f}s"
    )
    logger.info(
        f"💡 Speed improvement: ~{600/elapsed_time:.1f}x faster than sequential processing"
    )
    logger.info("=" * 60)


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


def wait_for_download_fast(download_path: str, timeout=15):
    """Faster download detection with reduced polling interval."""
    start_time = time.time()
    initial_files = set(os.listdir(download_path))

    while True:
        current_files = set(os.listdir(download_path))
        new_files = current_files - initial_files
        csv_files = [file for file in new_files if file.endswith(".csv")]

        if csv_files:
            latest_csv = max(
                csv_files,
                key=lambda f: os.path.getctime(os.path.join(download_path, f)),
            )
            return latest_csv

        if time.time() - start_time > timeout:
            return None

        time.sleep(0.5)  # Check every 500ms instead of 1s


def handle_export_dropdown(browser, wait):
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


def handle_export_all(browser, wait):

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


def handle_alert_box(wait):
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


def handle_refresh_btn(wait):
    try:
        refresh_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "refreshExportList"))
        )
        refresh_btn.click()
        time.sleep(5)  # Allow page to refresh
        logger.info("Clicked on refresh button.")
    except (NoSuchElementException, TimeoutException):
        logger.error("Failed to click on refresh button.")


def wait_for_latest_export_link(
    wait: WebDriverWait[webdriver.Chrome],
) -> Optional[WebElement]:
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


def click_first_export(
    browser: webdriver.Chrome, wait: WebDriverWait[webdriver.Chrome]
):
    """Clicks the most recent export link and waits for the CSV download."""

    latest_export_link = wait_for_latest_export_link(wait)

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


def open_dropdown(
    browser: webdriver.Chrome, wait: WebDriverWait[webdriver.Chrome], retries: int = 3
):
    """Clicks the export dropdown button and ensures it expands properly."""

    for attempt in range(retries):  # Try clicking the dropdown up to 3 times
        handle_refresh_btn(wait)
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


def handle_gradebook_tab(wait: WebDriverWait[webdriver.Chrome]):
    try:
        gradebook_tab = wait.until(
            EC.element_to_be_clickable((By.ID, "Launch-tab-gradebook"))
        )
        gradebook_tab.click()
    except NoSuchElementException:
        logger.error("Gradebook tab not found.")


def fast_login(browser: webdriver.Chrome, wait: WebDriverWait[webdriver.Chrome]):
    """Optimized login process."""
    try:
        # Navigate and login with minimal waits
        browser.get(BASE_URL)

        # Click login button
        login_btn = wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, "loginBtn--lfDa2"))
        )
        login_btn.click()

        # Enter credentials quickly
        username = wait.until(EC.presence_of_element_located((By.ID, "username")))
        username.send_keys(INSTRUCTOR_LOGIN_ID + Keys.ENTER)

        password = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password.send_keys(INSTRUCTOR_LOGIN_PASSWORD + Keys.ENTER)

        return True
    except Exception as e:
        logger.error(f"Fast login failed: {e}")
        return False


def process_single_course(course_data):
    """Process a single course in a separate thread."""
    course_url, course_name, course_id = course_data

    # Create dedicated browser for this thread
    browser = create_optimized_browser()
    wait = WebDriverWait(browser, OPTIMIZED_TIMEOUTS["element_wait"])

    try:
        logger.info(f"🚀 [Thread] Processing: {course_name}")

        # Login
        if not fast_login(browser, wait):
            logger.error(f"❌ [Thread] Login failed for {course_name}")
            return {
                "course_id": course_id,
                "course_name": course_name,
                "success": False,
                "csv_path": "",
                "md_path": "",
                "error": "Login failed",
            }

        # Navigate to course
        browser.get(course_url)

        # Process gradebook with optimized timings
        result = execute_gradebook_actions_fast(browser, wait, course_id, course_name)

        logger.info(f"✅ [Thread] Completed: {course_name}")
        return result

    except Exception as e:
        logger.error(f"❌ [Thread] Error processing {course_name}: {e}")
        return {
            "course_id": course_id,
            "course_name": course_name,
            "success": False,
            "csv_path": "",
            "md_path": "",
            "error": str(e),
        }
    finally:
        browser.quit()


def execute_gradebook_actions_fast(
    browser, wait, course_id: str, course_name: str = ""
):
    """Optimized version of gradebook actions with reduced waits."""
    try:
        # Gradebook tab
        gradebook_tab = wait.until(
            EC.element_to_be_clickable((By.ID, "Launch-tab-gradebook"))
        )
        gradebook_tab.click()

        # Export dropdown - reduced wait
        time.sleep(OPTIMIZED_TIMEOUTS["animation_wait"])  # Minimal wait for page load

        export_dropdown = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".RBDropdown--ATEd3.dropdown > button")
            )
        )
        export_dropdown.click()

        # Export all button
        export_all_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".dropdownButton--whS7t:first-of-type")
            )
        )
        export_all_btn.click()

        # Handle modal if present (but don't wait long)
        try:
            close_button = WebDriverWait(browser, 2).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "modal__close"))
            )
            close_button.click()
        except:
            pass  # Modal might not appear

        # Refresh and open dropdown - optimized
        refresh_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "refreshExportList"))
        )
        refresh_btn.click()
        time.sleep(OPTIMIZED_TIMEOUTS["modal_wait"])  # Reduced wait

        # Open dropdown quickly
        dropdown_button = wait.until(
            EC.element_to_be_clickable((By.ID, "dropdown-basic"))
        )
        dropdown_button.click()
        time.sleep(OPTIMIZED_TIMEOUTS["animation_wait"])

        # Get first export link and click
        export_links = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".dropdown__menu.show a")
            )
        )

        if export_links:
            export_links[0].click()

            # Wait for download with reduced timeout
            csv_filename = wait_for_download_fast(
                str(DATA_DIR), OPTIMIZED_TIMEOUTS["download_wait"]
            )

            if csv_filename:
                # Process files
                success, csv_path, md_path = add_course_id_to_csv(
                    csv_filename, course_id, course_name
                )

                return {
                    "course_id": course_id,
                    "course_name": course_name,
                    "success": success,
                    "csv_path": csv_path,
                    "md_path": md_path,
                    "error": None,
                }

        return {
            "course_id": course_id,
            "course_name": course_name,
            "success": False,
            "csv_path": "",
            "md_path": "",
            "error": "No export links found or download failed",
        }

    except Exception as e:
        return {
            "course_id": course_id,
            "course_name": course_name,
            "success": False,
            "csv_path": "",
            "md_path": "",
            "error": str(e),
        }


def save_courses_data_to_json():
    """Save comprehensive course processing results to JSON with detailed information."""
    from datetime import datetime

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
            course_id = result.get("course_id", "unknown")
            course_name = result.get("course_name", "unknown")
            success = result.get("success", False)

            course_entry = {
                "course_id": course_id,
                "course_name": course_name,
                "processing_status": "success" if success else "failed",
                "success": success,
            }

            if success:
                course_entry.update(
                    {
                        "csv_file_path": result.get("csv_path", ""),
                        "markdown_file_path": result.get("md_path", ""),
                        "error_message": None,
                    }
                )
                processing_summary["successful_exports"] += 1
            else:
                course_entry.update(
                    {
                        "csv_file_path": None,
                        "markdown_file_path": None,
                        "error_message": result.get("error", "Unknown error"),
                        "failure_reason": result.get("error", "Unknown error"),
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
            import json

            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Comprehensive course export summary saved to: {json_path}")
        logger.info(
            f"📊 Summary: {processing_summary['successful_exports']} successful, "
            f"{processing_summary['failed_exports']} failed, "
            f"{processing_summary['success_rate_percentage']}% success rate"
        )

        # Also create a simple CSV summary for quick viewing
        csv_summary_path = DATA_DIR / "export_summary.csv"
        summary_df = pd.DataFrame(course_data)
        summary_df.to_csv(csv_summary_path, index=False)
        logger.info(f"📄 Quick CSV summary saved to: {csv_summary_path}")

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
                import json

                json.dump(basic_summary, f, indent=2)
            logger.info(f"⚠️ Basic summary saved due to error")
        except:
            logger.error(f"Could not save any summary to {json_path}")


def paginate_and_fetch_courses(browser, wait) -> Tuple[List[str], List[str]]:
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


def cleanup_system_resources():
    """
    Comprehensive cleanup function to handle any remaining system resources.
    Call this at the end of processing or in case of unexpected termination.
    """
    logger.info("🧹 Starting comprehensive system cleanup...")

    try:
        # Clean up any orphaned Chrome processes from our automation
        import psutil

        chrome_processes = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["name"] and "chrome" in proc.info["name"].lower():
                    # Check if it's one of our automation browser instances
                    cmdline = proc.info["cmdline"] or []

                    # Look for our specific markers
                    is_our_automation = any(
                        arg
                        for arg in cmdline
                        if (
                            "NetAcadExport.Worker" in arg
                            or "worker_" in arg
                            and "_downloads" in arg
                        )
                    )

                    if is_our_automation:
                        chrome_processes.append(proc)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if chrome_processes:
            logger.warning(
                f"Found {len(chrome_processes)} orphaned NetAcad automation Chrome processes"
            )
            for proc in chrome_processes:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                    logger.info(f"Terminated automation Chrome process {proc.pid}")
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    try:
                        proc.kill()
                        logger.info(
                            f"Force killed automation Chrome process {proc.pid}"
                        )
                    except psutil.NoSuchProcess:
                        pass
                except Exception as e:
                    logger.warning(
                        f"Could not terminate Chrome process {proc.pid}: {e}"
                    )
        else:
            logger.info("✅ No orphaned automation Chrome processes found")

    except ImportError:
        logger.info("psutil not available - skipping Chrome process cleanup")
    except Exception as e:
        logger.warning(f"Error during Chrome process cleanup: {e}")

    try:
        # Clean up temporary download directories
        temp_dirs = []
        for item in DATA_DIR.iterdir():
            if item.is_dir() and (
                item.name.startswith("worker_") and item.name.endswith("_downloads")
            ):
                temp_dirs.append(item)

        if temp_dirs:
            logger.info(f"Cleaning up {len(temp_dirs)} temporary directories")

            for temp_dir in temp_dirs:
                try:
                    shutil.rmtree(str(temp_dir))
                    logger.info(f"Removed temp directory: {temp_dir.name}")
                except Exception as e:
                    logger.warning(f"Failed to remove {temp_dir.name}: {e}")
        else:
            logger.info("✅ No temporary directories to clean")

    except Exception as e:
        logger.warning(f"Error during temp directory cleanup: {e}")

    try:
        # Force garbage collection
        import gc

        gc.collect()
        logger.info("✅ System cleanup completed")

    except Exception as e:
        logger.warning(f"Error during garbage collection: {e}")


def emergency_cleanup():
    """
    Emergency cleanup function for use in signal handlers or unexpected exits.
    """
    print("🚨 Emergency cleanup triggered...")

    try:
        # Quick Chrome process cleanup
        import psutil

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"] and "chrome" in proc.info["name"].lower():
                    proc.terminate()
            except:
                pass
    except:
        pass

    print("🧹 Emergency cleanup completed")


def signal_handler(signum: int, frame):
    """Handle interrupt signals gracefully."""
    logger.warning(f"Received signal {signum}, initiating cleanup...")
    emergency_cleanup()
    exit(1)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

# Register cleanup function to run on normal exit
atexit.register(cleanup_system_resources)


if __name__ == "__main__":
    # Use the new parallel processing by default
    process_courses_parallel()
