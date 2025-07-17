import time
import os
import sys
import asyncio
import pandas as pd
import logging
import re
import threading
from typing import List, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)
from webdriver_manager.chrome import ChromeDriverManager

from pydantic import BaseModel, Field, ConfigDict
import aiofiles

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

import signal

shutdown_requested = False
executor = None  # Global for signal handler access
results: List["CourseExportResult"] = []  # Global for signal handler access


def handle_sigterm(signum, frame):
    global shutdown_requested, executor, results
    logger.warning(f"Received signal {signum}. Initiating graceful shutdown ...")
    shutdown_requested = True
    if executor:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            logger.error(f"Exception during executor shutdown: {e}")
    try:
        if results:
            asyncio.run(save_courses_data_to_json(results))
            logger.info("Partial results saved successfully during shutdown.")
    except Exception as e:
        logger.error(f"Failed to save results during shutdown: {e}")
    sys.exit(0)


signal.signal(signal.SIGINT, handle_sigterm)  # Ctrl+C
signal.signal(signal.SIGTERM, handle_sigterm)  # SIGTERM (docker, kill)


# --- Pydantic models for result typing and serialization ---


class CourseExportResult(BaseModel):
    course_id: str = Field(..., description="ID of the course")
    course_name: str = Field(..., description="Name of the course")
    course_url: str = Field(..., description="URL of the course page")
    success: bool = Field(
        ..., default=True, description="Whether the export was successful"
    )
    csv_path: Optional[str] = Field(
        ..., default=None, description="Path to the exported CSV file"
    )
    md_path: Optional[str] = Field(
        ..., default=None, description="Path to the exported Markdown file"
    )
    error: Optional[str] = Field(
        ..., default=None, description="Error message if export failed"
    )


class ExportSummary(BaseModel):
    export_timestamp: str
    total_courses_found: int
    successful_exports: int
    failed_exports: int
    success_rate_percentage: float
    processing_mode: str
    max_workers_used: int
    export_locations: dict


class ExportReport(BaseModel):
    summary: ExportSummary
    courses: List[CourseExportResult]
    failed_course_details: List[dict]


if not validate_setup():
    print("Setup validation failed. Please check your environment and try again.")
    exit(1)
else:
    print("Setup validation passed. Proceeding with course export...")


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
log_file = LOGS_DIR / "course_export_parallel.log"
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
logger = logging.getLogger(__name__)


# Global thread-safe variables for tracking results
_course_names: List[str] = []
_course_ids: List[str] = []
_course_csv_files: List[str | None] = []
_failed_course_ids: List[str] = []
_all_course_results: List[CourseExportResult] = []
_results_lock = threading.Lock()

MAX_WORKERS = 4

OPTIMIZED_TIMEOUTS = {
    "page_load": 30,
    "element_wait": 15,
    "download_wait": 30,
    "modal_wait": 3,
    "animation_wait": 2,
    "login_wait": 5,
}

# ---------------- Helper Functions ------------------
import traceback


def log_and_set_error(result, stage, exc):
    result.error = f"{stage} failed: {exc}"
    tb = traceback.format_exc()
    result.error_traceback = tb
    logger.error(f"[{result.course_name}] {stage} failed: {exc}\n{tb}")


def new_chrome_driver(worker_id: int = 0) -> webdriver.Chrome:
    options = Options()
    worker_download_dir = DATA_DIR / f"worker_{worker_id}_downloads"
    worker_download_dir.mkdir(exist_ok=True)
    prefs = {
        "profile.default_content_setting_values": {
            "plugins": 2,
            "popups": 2,
            "geolocation": 2,
            "notifications": 2,
        },
        "download.default_directory": str(worker_download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-background-networking")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    browser = webdriver.Chrome(
        options=options, service=ChromeService(ChromeDriverManager().install())
    )
    browser.set_page_load_timeout(OPTIMIZED_TIMEOUTS["page_load"])
    browser.implicitly_wait(OPTIMIZED_TIMEOUTS["element_wait"])
    return browser


def clear_old_downloads() -> None:
    try:
        pattern = r"^GRADEBOOK_DATA_\d{4}_\d{2}_\d{2}T\d{2}_\d{2}_\d{2}Z_[\w-]+\.csv$"
        for file in os.listdir(str(DATA_DIR)):
            if file.endswith(".csv") and re.match(pattern, file):
                file_path = DATA_DIR / file
                file_path.unlink(missing_ok=True)
                logger.info(f"Deleted old download: {file_path}")

        if CSV_DATA_DIR.exists():
            for file in os.listdir(str(CSV_DATA_DIR)):
                if file.endswith(".csv") and re.match(pattern, file):
                    file_path = CSV_DATA_DIR / file
                    file_path.unlink(missing_ok=True)
                    logger.info(f"Deleted old CSV export: {file_path}")

        if MD_DATA_DIR.exists():
            md_pattern = (
                r"^GRADEBOOK_DATA_\d{4}_\d{2}_\d{2}T\d{2}_\d{2}_\d{2}Z_[\w-]+\.md$"
            )
            for file in os.listdir(str(MD_DATA_DIR)):
                if file.endswith(".md") and re.match(md_pattern, file):
                    file_path = MD_DATA_DIR / file
                    file_path.unlink(missing_ok=True)
                    logger.info(f"Deleted old Markdown export: {file_path}")
    except Exception as e:
        logger.error(f"Error clearing old files: {e}", exc_info=True)


from selenium.webdriver.remote.webdriver import WebDriver


def login(
    browser: webdriver.Chrome,
    wait: WebDriverWait[WebDriver],
    result: CourseExportResult,
):
    try:
        browser.get(BASE_URL)
        login_btn = wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, "loginBtn--lfDa2"))
        )
        login_btn.click()
        username = wait.until(EC.presence_of_element_located((By.ID, "username")))
        username.send_keys(INSTRUCTOR_ID + Keys.ENTER)
        password = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password.send_keys(INSTRUCTOR_PASSWORD + Keys.ENTER)
        logger.info(f"[{result.course_name}] Login successful")
    except Exception as e:
        log_and_set_error(result, "Login", e)
        raise


def handle_gradebook_tab(
    browser: webdriver.Chrome, wait: WebDriverWait, result: CourseExportResult
):
    try:
        gradebook_tab = wait.until(
            EC.element_to_be_clickable((By.ID, "Launch-tab-gradebook"))
        )
        gradebook_tab.click()
        logger.info(f"[{result.course_name}] Clicked gradebook tab")
    except Exception as e:
        log_and_set_error(result, "Gradebook tab", e)
        raise


def handle_export_dropdown(
    browser: webdriver.Chrome, wait: WebDriverWait, result: CourseExportResult
):
    try:
        export_dropdown = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".RBDropdown--ATEd3.dropdown > button")
            )
        )
        export_dropdown.click()
        logger.info(f"[{result.course_name}] Clicked export dropdown")
    except Exception as e:
        log_and_set_error(result, "Export dropdown", e)
        raise


def handle_export_all(
    browser: webdriver.Chrome, wait: WebDriverWait, result: CourseExportResult
):
    try:
        export_all_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".dropdownButton--whS7t:first-of-type")
            )
        )
        export_all_btn.click()
        logger.info(f"[{result.course_name}] Clicked export all")
    except Exception as e:
        log_and_set_error(result, "Export all", e)
        raise


def handle_alert_box(
    browser: webdriver.Chrome, wait: WebDriverWait, result: CourseExportResult
):
    try:
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "modal__content")))
        alert_box_btn_close = wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, "modal__close"))
        )
        alert_box_btn_close.click()
        logger.info(f"[{result.course_name}] Closed alert box")
    except (NoSuchElementException, TimeoutException):
        logger.info(f"[{result.course_name}] No alert/modal to close")


def handle_refresh_btn(
    browser: webdriver.Chrome, wait: WebDriverWait, result: CourseExportResult
):
    try:
        refresh_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "refreshExportList"))
        )
        refresh_btn.click()
        time.sleep(3)
        logger.info(f"[{result.course_name}] Clicked refresh button")
    except (NoSuchElementException, TimeoutException):
        logger.info(f"[{result.course_name}] No refresh button found")


def open_dropdown(
    browser: webdriver.Chrome,
    wait: WebDriverWait,
    result: CourseExportResult,
    retries: int = 3,
) -> bool:
    for attempt in range(retries):
        handle_refresh_btn(browser, wait, result)
        try:
            dropdown_button = wait.until(
                EC.element_to_be_clickable((By.ID, "dropdown-basic"))
            )
            browser.execute_script(
                "arguments[0].scrollIntoView(true);", dropdown_button
            )
            dropdown_button.click()
            time.sleep(2)
            logger.info(f"[{result.course_name}] Dropdown opened")
            return True
        except Exception as e:
            logger.warning(
                f"[{result.course_name}] Failed to open dropdown (attempt {attempt+1}/{retries}): {e}"
            )
            if attempt == retries - 1:
                log_and_set_error(result, "Open dropdown", e)
                return False
            time.sleep(2)
    return False


def wait_for_latest_export_link(
    browser: webdriver.Chrome, wait: WebDriverWait, result: CourseExportResult
) -> Optional[Any]:
    try:
        export_links = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".dropdown__menu.show a")
            )
        )
        time.sleep(2)
        if export_links:
            logger.info(f"[{result.course_name}] Found export links")
            return export_links[0]
        else:
            logger.error(f"[{result.course_name}] No export links found")
            return None
    except Exception as e:
        log_and_set_error(result, "Wait for export link", e)
        return None


def wait_for_download(download_path: str, timeout=30) -> Optional[str]:
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
        time.sleep(1)


def click_first_export(
    browser: webdriver.Chrome, wait: WebDriverWait, result: CourseExportResult
) -> Optional[str]:
    latest_export_link = wait_for_latest_export_link(browser, wait, result)
    if latest_export_link:
        browser.execute_script("arguments[0].scrollIntoView(true);", latest_export_link)
        try:
            latest_export_link.click()
            logger.info(
                f"[{result.course_name}] Clicked export link, waiting for download..."
            )
            csv_filename = wait_for_download(str(DATA_DIR))
            if not csv_filename:
                log_and_set_error(
                    result, "Download CSV", Exception("CSV download did not complete")
                )
            return csv_filename
        except Exception as e:
            log_and_set_error(result, "Click export link", e)
            return None
    else:
        return None


def paginate_and_fetch_courses(
    browser: webdriver.Chrome, wait: WebDriverWait
) -> Tuple[List[str], List[str]]:
    course_urls = []
    course_names = []
    i = 0
    while True:
        i += 1
        course_anchors = wait.until(
            EC.visibility_of_all_elements_located(
                (By.CLASS_NAME, "instance_name--dioD1")
            )
        )
        for anchor in course_anchors:
            url = anchor.get_attribute("href")
            name = anchor.text.strip()
            if url and url not in course_urls:
                course_urls.append(url)
                course_names.append(name)
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
            break
        except ElementClickInterceptedException:
            btn = next_button.find_element(By.XPATH, "./..")
            browser.execute_script("arguments[0].scrollIntoView(true);", btn)
            browser.execute_script("arguments[0].click();", btn)
    return course_urls, course_names


# --- Async file writing helpers ---


async def async_write_file(filepath: str, content: str) -> None:
    async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
        await f.write(content)


async def async_write_json(filepath: str, data: Any) -> None:
    import json

    async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, indent=4))


# --- Data processing ---


async def create_markdown_export(
    df: pd.DataFrame, csv_filename: str, course_id: str, course_name: str
) -> Tuple[bool, str, Optional[str]]:
    from datetime import datetime

    md_filename = csv_filename.replace(".csv", ".md")
    md_file_path = MD_DATA_DIR / md_filename
    try:
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
        numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
        if len(numeric_columns) > 1:
            markdown_lines.extend(
                [
                    "## Grade Summary Statistics",
                    "",
                    "This section provides statistical analysis of student performance across gradeable items.",
                    "",
                ]
            )
            for col in numeric_columns:
                if (
                    col != "COURSE_ID"
                    and not df[col].empty
                    and not df[col].isna().all()
                ):
                    stats = df[col].describe()
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
        markdown_lines.extend(
            [
                "## Complete Student Gradebook Data",
                "",
                "Below is the complete gradebook data for all students in this course.",
                "Each row represents one student's performance across all gradeable items.",
                "",
            ]
        )
        display_df = df.copy()
        column_mapping = {}
        for col in display_df.columns:
            clean_name = col.replace("_", " ").replace("-", " ").title()
            if "id" in col.lower():
                clean_name = clean_name.replace("Id", "ID")
            column_mapping[col] = clean_name
        display_df = display_df.rename(columns=column_mapping)
        markdown_table = display_df.to_markdown(index=False, tablefmt="pipe")
        markdown_lines.append(markdown_table)
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
        await async_write_file(str(md_file_path), "\n".join(markdown_lines))
        return True, str(md_file_path), None
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Markdown export failed: {e}\n{tb}")
        return False, "", tb


async def add_course_id_to_csv(
    csv_filename: str, course_id: str, course_name: str = ""
) -> Tuple[bool, str, str, Optional[str]]:
    original_file_path = DATA_DIR / csv_filename
    if not original_file_path.exists():
        return False, "", "", "Original CSV file not found"
    try:
        df = pd.read_csv(str(original_file_path))
        df.insert(0, "COURSE_ID", course_id)
        csv_output_path = CSV_DATA_DIR / csv_filename
        await async_write_file(
            str(csv_output_path), df.to_csv(index=False, header=False)
        )
        markdown_success, markdown_path, markdown_tb = await create_markdown_export(
            df, csv_filename, course_id, course_name
        )
        if markdown_success:
            original_file_path.unlink(missing_ok=True)
            return True, str(csv_output_path), markdown_path, None
        else:
            return (
                True,
                str(csv_output_path),
                "",
                f"Markdown export failed:\n{markdown_tb}",
            )
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"CSV processing failed: {e}\n{tb}")
        return False, "", "", tb


# ---------------- Worker and Main Parallel Logic ----------------


def export_course_worker(
    course_info: Tuple[str, str, str], results: List[CourseExportResult]
) -> None:
    course_id, course_name, url = course_info
    result = CourseExportResult(
        course_id=course_id,
        course_name=course_name,
        course_url=url,
        csv_file_path=None,
        markdown_file_path=None,
        processing_status="failed",
    )
    try:
        browser = new_chrome_driver()
        wait = WebDriverWait(browser, WEBDRIVER_TIMEOUT)
        try:
            login(browser, wait, result)
        except Exception:
            browser.quit()
            with _results_lock:
                results.append(result)
            return

        try:
            browser.get(url)
        except Exception as e:
            log_and_set_error(result, "Navigate to course URL", e)
            browser.quit()
            with _results_lock:
                results.append(result)
            return

        try:
            handle_gradebook_tab(browser, wait, result)
            handle_export_dropdown(browser, wait, result)
            handle_export_all(browser, wait, result)
            handle_alert_box(browser, wait, result)
            handle_refresh_btn(browser, wait, result)
            if not open_dropdown(browser, wait, result):
                browser.quit()
                with _results_lock:
                    results.append(result)
                return

            csv_filename = click_first_export(browser, wait, result)
            if csv_filename:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success, csv_path, markdown_path, csv_tb = loop.run_until_complete(
                    add_course_id_to_csv(csv_filename, course_id, course_name)
                )
                if success:
                    result.csv_file_path = csv_path
                    result.markdown_file_path = markdown_path
                    result.processing_status = "success"
                    if csv_tb:
                        result.error = "CSV/Markdown post-processing warning"
                        result.error_traceback = csv_tb
                        logger.warning(
                            f"[{course_name}] CSV/Markdown warning: {csv_tb}"
                        )
                else:
                    log_and_set_error(
                        result,
                        "File processing",
                        csv_tb or Exception("File processing failed"),
                    )
            else:
                log_and_set_error(
                    result, "Export grades", Exception("CSV file not downloaded")
                )
        except Exception as e:
            log_and_set_error(result, "Export pipeline", e)
        browser.quit()
    except Exception as ex:
        log_and_set_error(result, "Unexpected error", ex)
    with _results_lock:
        results.append(result)


async def save_courses_data_to_json(results: List[CourseExportResult]) -> None:
    json_path = DATA_DIR / "courses_export_summary_parallel.json"
    await async_write_json(str(json_path), [r.model_dump() for r in results])
    logger.info(f"Course export summary saved to: {json_path}")


def process_courses_parallel() -> None:
    global executor, results  # <-- Make sure these are the same objects
    if not validate_setup():
        print("Setup validation failed. Please check your environment and try again.")
        exit(1)
    else:
        print("Setup validation passed. Proceeding with parallel course export...")

    clear_old_downloads()
    browser = new_chrome_driver()
    wait = WebDriverWait(browser, WEBDRIVER_TIMEOUT)
    login(
        browser,
        wait,
        CourseExportResult(
            course_id="initial",
            course_name="INITIAL_LOGIN",
            course_url=BASE_URL,
            csv_file_path=None,
            markdown_file_path=None,
            processing_status="info",
        ),
    )
    course_urls, course_names = paginate_and_fetch_courses(browser, wait)
    browser.quit()
    course_tuples = []
    for i, url in enumerate(course_urls):
        course_id = url.split("=")[1]
        course_name = course_names[i]
        course_tuples.append((course_id, course_name, url))

    results.clear()  # Make sure results is empty before run
    max_workers = min(5, len(course_tuples))
    logger.info(
        f"Starting export of {len(course_tuples)} courses using {max_workers} threads."
    )

    # ------ Graceful shutdown aware thread pool ------
    try:
        executor = ThreadPoolExecutor(max_workers=max_workers)
        with executor:
            futures = [
                executor.submit(export_course_worker, info, results)
                for info in course_tuples
            ]
            for future in as_completed(futures):
                if shutdown_requested:
                    logger.warning(
                        "Shutdown requested. Skipping further work and waiting for workers to exit."
                    )
                    break
                try:
                    future.result()
                except Exception as exc:
                    logger.error(f"Worker failed: {exc}")
    finally:
        # This always runs (even on crash or shutdown)
        asyncio.run(save_courses_data_to_json(results))
        success = sum(r.processing_status == "success" for r in results)
        logger.info(f"✅ Successful Exports: {success}")
        logger.info(f"❌ Failed Exports: {len(results) - success}")
        logger.info("All results (partial or complete) saved.")


# ------------------ Main Entry ------------------
if __name__ == "__main__":
    process_courses_parallel()
