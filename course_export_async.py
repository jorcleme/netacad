import asyncio
import time
import os
import pandas as pd
import logging
import re
import sys

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import List, Tuple, Optional
from pydantic import BaseModel, Field
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
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


class CourseInfo(BaseModel):
    """Pydantic model for course information with validation."""

    course_id: str = Field(..., description="Unique course identifier")
    course_name: str = Field(..., description="Human-readable course name")
    url: str = Field(..., description="Course URL for navigation")
    csv_file_path: str = Field(default="", description="Path to exported CSV file")
    markdown_file_path: str = Field(
        default="", description="Path to exported Markdown file"
    )
    processing_status: str = Field(
        default="pending", description="Current processing status"
    )
    error_message: str = Field(
        default="", description="Error message if processing failed"
    )

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "forbid"  # Prevent extra fields


class AsyncCourseExporter:
    """Optimized async course exporter with concurrent processing capabilities."""

    def __init__(self, max_concurrent_courses: int = 3, max_workers: int = 4):
        self.max_concurrent_courses = max_concurrent_courses
        self.max_workers = max_workers
        self.courses: List[CourseInfo] = []
        self.failed_courses: List[str] = []
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=max_workers)

        # Setup logging
        log_file = LOGS_DIR / "course_export_async.log"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(str(log_file), mode="w", encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
            encoding="utf-8",
        )
        self.logger = logging.getLogger(__name__)

    def create_optimized_driver(self) -> webdriver.Chrome:
        """Creates an optimized Chrome driver instance."""
        options = Options()

        # Performance optimizations
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")  # Don't load images for speed
        options.add_argument("--window-size=1280,720")  # Smaller window

        prefs = {
            "profile.default_content_setting_values.notifications": 2,  # Disable notifications
            "profile.default_content_settings.popups": 0,  # Disable popups
            "download.prompt_for_download": False,
            "download.default_directory": str(DATA_DIR),
            "safebrowsing.enabled": True,
        }
        # Download preferences
        options.add_experimental_option("prefs", prefs)

        # Suppress logging
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)

        return webdriver.Chrome(
            options=options, service=ChromeService(ChromeDriverManager().install())
        )

    async def clear_old_downloads_async(self):
        """Asynchronously clear old CSV and Markdown files."""

        async def clear_directory_files(directory, pattern):
            if not directory.exists():
                return

            try:
                files_to_delete = []
                for file in os.listdir(str(directory)):
                    if re.match(pattern, file):
                        files_to_delete.append(directory / file)

                # Delete files concurrently
                tasks = []
                for file_path in files_to_delete:
                    task = asyncio.create_task(self._delete_file_async(file_path))
                    tasks.append(task)

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            except Exception as e:
                self.logger.error(f"Error clearing directory {directory}: {e}")

        # Patterns for files to delete
        csv_pattern = (
            r"^GRADEBOOK_DATA_\d{4}_\d{2}_\d{2}T\d{2}_\d{2}_\d{2}Z_[\w-]+\.csv$"
        )
        md_pattern = r"^GRADEBOOK_DATA_\d{4}_\d{2}_\d{2}T\d{2}_\d{2}_\d{2}Z_[\w-]+\.md$"

        # Clear all directories concurrently
        await asyncio.gather(
            clear_directory_files(DATA_DIR, csv_pattern),
            clear_directory_files(CSV_DATA_DIR, csv_pattern),
            clear_directory_files(MD_DATA_DIR, md_pattern),
            return_exceptions=True,
        )

        self.logger.info("Completed clearing old download files")

    async def _delete_file_async(self, file_path):
        """Delete a file asynchronously."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(self.thread_executor, os.remove, str(file_path))
            self.logger.info(f"Deleted: {file_path}")
        except Exception as e:
            self.logger.error(f"Error deleting {file_path}: {e}")

    async def login_and_get_courses(self) -> List[CourseInfo]:
        """Login and fetch all course information."""
        loop = asyncio.get_event_loop()

        def _login_and_fetch():
            browser = self.create_optimized_driver()
            wait = WebDriverWait(browser, WEBDRIVER_TIMEOUT)

            try:
                self.logger.info("Navigating to netacad.com...")
                browser.get(BASE_URL)

                # Take a screenshot for debugging
                self.logger.info(f"Page title: {browser.title}")
                self.logger.info(f"Current URL: {browser.current_url}")

                # Login process with better error handling
                try:
                    self.logger.info("Looking for login button...")
                    login_btn = wait.until(
                        EC.element_to_be_clickable((By.CLASS_NAME, "loginBtn--lfDa2"))
                    )
                    login_btn.click()
                    self.logger.info("Login button clicked successfully")
                except Exception as e:
                    self.logger.error(f"Failed to find/click login button: {e}")
                    # Try alternative login selectors
                    try:
                        login_btn = wait.until(
                            EC.element_to_be_clickable(
                                (By.XPATH, "//a[contains(text(), 'Log In')]")
                            )
                        )
                        login_btn.click()
                        self.logger.info("Alternative login button clicked")
                    except Exception as e2:
                        self.logger.error(f"Alternative login button also failed: {e2}")
                        raise

                try:
                    self.logger.info("Looking for username field...")
                    username = wait.until(
                        EC.presence_of_element_located((By.ID, "username"))
                    )
                    username.send_keys(INSTRUCTOR_ID + Keys.ENTER)
                    self.logger.info("Username entered successfully")
                except Exception as e:
                    self.logger.error(f"Failed to enter username: {e}")
                    raise

                try:
                    self.logger.info("Looking for password field...")
                    password = wait.until(
                        EC.presence_of_element_located((By.ID, "password"))
                    )
                    password.send_keys(INSTRUCTOR_PASSWORD + Keys.ENTER)
                    self.logger.info("Password entered successfully")
                except Exception as e:
                    self.logger.error(f"Failed to enter password: {e}")
                    raise

                # Wait for login to complete
                self.logger.info("Waiting for login to complete...")
                time.sleep(3)  # Give time for login redirect

                self.logger.info(f"Post-login URL: {browser.current_url}")

                # Fetch courses from all pages
                courses = []
                course_urls = []
                course_names = []

                page = 0
                while True:
                    page += 1
                    self.logger.info(f"Fetching courses from page {page}")

                    try:
                        course_anchors = wait.until(
                            EC.visibility_of_all_elements_located(
                                (By.CLASS_NAME, "instance_name--dioD1")
                            )
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to find course anchors on page {page}: {e}"
                        )
                        if page == 1:
                            # If we can't find courses on the first page, it's likely a login issue
                            self.logger.error(
                                "No courses found on first page - possible login failure"
                            )
                            return []
                        else:
                            # If we're on a later page, we might have reached the end
                            self.logger.info(
                                "No more courses found, stopping pagination"
                            )
                            break

                    for anchor in course_anchors:
                        url = anchor.get_attribute("href")
                        name = anchor.text.strip()
                        if url and name:
                            # Only add if not already present to avoid duplicates
                            if url not in course_urls:
                                course_urls.append(url)
                                course_names.append(name)

                    # Try to go to next page
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
                        time.sleep(2)  # Give time for page to load
                        self.logger.info(f"Navigated to page {page + 1}")
                    except (NoSuchElementException, TimeoutException):
                        self.logger.info("No more pages. Course collection complete.")
                        break
                    except Exception as e:
                        self.logger.warning(f"Error clicking next page button: {e}")
                        break

                # Create CourseInfo objects
                for i, url in enumerate(course_urls):
                    if url:
                        course_id = url.split("=")[1]
                        course_name = course_names[
                            i
                        ]  # Now safely indexed since lists maintain order
                        courses.append(
                            CourseInfo(
                                course_id=course_id, course_name=course_name, url=url
                            )
                        )

                self.logger.info(f"Successfully fetched {len(courses)} courses")
                return courses

            except Exception as e:
                self.logger.error(f"Error during login/course fetch: {e}")
                return []
            finally:
                browser.quit()

        return await loop.run_in_executor(self.thread_executor, _login_and_fetch)

    async def process_single_course(
        self, course: CourseInfo, semaphore: asyncio.Semaphore
    ) -> CourseInfo:
        """Process a single course with semaphore for concurrency control."""
        async with semaphore:
            loop = asyncio.get_event_loop()

            def _process_course():
                browser = self.create_optimized_driver()
                wait = WebDriverWait(browser, WEBDRIVER_TIMEOUT)

                try:
                    self.logger.info(
                        f"Processing course: {course.course_name} (ID: {course.course_id})"
                    )

                    # Navigate to course
                    browser.get(course.url)

                    # Execute gradebook actions
                    success = self._execute_gradebook_actions_sync(
                        browser, wait, course.course_id, course.course_name
                    )

                    if success:
                        course.processing_status = "success"
                        self.logger.info(
                            f"✅ Successfully processed: {course.course_name}"
                        )
                    else:
                        course.processing_status = "failed"
                        course.error_message = "Gradebook export failed"
                        self.logger.warning(
                            f"❌ Failed to process: {course.course_name}"
                        )

                    return course

                except Exception as e:
                    course.processing_status = "failed"
                    course.error_message = str(e)
                    self.logger.error(f"Error processing {course.course_name}: {e}")
                    return course
                finally:
                    browser.quit()

            return await loop.run_in_executor(self.thread_executor, _process_course)

    def _execute_gradebook_actions_sync(
        self, browser, wait, course_id: str, course_name: str
    ) -> bool:
        """Synchronous gradebook actions for a single course."""
        try:
            # Click gradebook tab
            gradebook_tab = wait.until(
                EC.element_to_be_clickable((By.ID, "Launch-tab-gradebook"))
            )
            gradebook_tab.click()

            # Handle export dropdown
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

            # Handle alert/modal if present
            try:
                wait.until(
                    EC.visibility_of_element_located((By.CLASS_NAME, "modal__content"))
                )
                alert_box_btn_close = wait.until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "modal__close"))
                )
                alert_box_btn_close.click()
            except (NoSuchElementException, TimeoutException):
                pass  # No modal present

            # Refresh and wait for export
            refresh_btn = wait.until(
                EC.element_to_be_clickable((By.ID, "refreshExportList"))
            )
            refresh_btn.click()
            time.sleep(3)  # Reduced wait time

            # Open dropdown and get export link
            dropdown_button = wait.until(
                EC.element_to_be_clickable((By.ID, "dropdown-basic"))
            )
            dropdown_button.click()
            time.sleep(1)  # Reduced wait time

            # Click first export link
            export_links = wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, ".dropdown__menu.show a")
                )
            )

            if export_links:
                export_links[0].click()

                # Wait for download with reduced timeout
                csv_filename = self._wait_for_download_sync(str(DATA_DIR), timeout=15)

                if csv_filename:
                    # Process file asynchronously (will be scheduled)
                    asyncio.create_task(
                        self._process_downloaded_file_async(
                            csv_filename, course_id, course_name
                        )
                    )
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error in gradebook actions for {course_id}: {e}")
            return False

    def _wait_for_download_sync(self, download_path: str, timeout=15) -> Optional[str]:
        """Optimized download waiting with reduced timeout."""
        start_time = time.time()
        initial_files = set(os.listdir(download_path))

        while time.time() - start_time < timeout:
            current_files = set(os.listdir(download_path))
            new_files = current_files - initial_files
            csv_files = [f for f in new_files if f.endswith(".csv")]

            if csv_files:
                latest_csv = max(
                    csv_files,
                    key=lambda f: os.path.getctime(os.path.join(download_path, f)),
                )
                return latest_csv

            time.sleep(0.5)  # Check more frequently

        self.logger.warning(f"Download timeout reached for {download_path}")
        return None

    async def _process_downloaded_file_async(
        self, csv_filename: str, course_id: str, course_name: str
    ):
        """Process downloaded CSV file asynchronously."""
        loop = asyncio.get_event_loop()

        def _process_file():
            original_file_path = DATA_DIR / csv_filename

            if not original_file_path.exists():
                self.logger.error(f"CSV file not found: {csv_filename}")
                return False, "", ""

            try:
                # Read and process CSV
                df = pd.read_csv(str(original_file_path))
                df.insert(0, "COURSE_ID", course_id)

                # Save CSV (no headers)
                csv_output_path = CSV_DATA_DIR / csv_filename
                df.to_csv(str(csv_output_path), index=False, header=False)

                # Generate Markdown content
                markdown_content = self._generate_gradebook_markdown(
                    df, course_id, course_name
                )
                md_filename = csv_filename.replace(".csv", ".md")
                md_file_path = MD_DATA_DIR / md_filename

                # Save Markdown
                with open(md_file_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)

                # Clean up original
                original_file_path.unlink()

                self.logger.info(f"Successfully processed files for {course_name}")
                return True, str(csv_output_path), str(md_file_path)

            except Exception as e:
                self.logger.error(f"Error processing file {csv_filename}: {e}")
                return False, "", ""

        # Run file processing in thread executor
        return await loop.run_in_executor(self.thread_executor, _process_file)

    def _generate_gradebook_markdown(
        self, df: pd.DataFrame, course_id: str, course_name: str
    ) -> str:
        """Generate formatted Markdown content from gradebook data."""
        from datetime import datetime

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

        # Add summary statistics for numeric columns
        numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
        if len(numeric_columns) > 1:  # More than just COURSE_ID
            markdown_lines.extend(
                [
                    "## Grade Summary Statistics",
                    "",
                    "Statistical analysis of student performance across gradeable items.",
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

        # Add complete data table
        markdown_lines.extend(
            [
                "## Complete Student Gradebook Data",
                "",
                "Complete gradebook data for all students in this course.",
                "",
            ]
        )

        # Clean up column names and create table
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

        # Add metadata footer
        markdown_lines.extend(
            [
                "",
                "---",
                "",
                "## Export Metadata",
                "",
                f"- **Generated:** {export_date}",
                f"- **Data Source:** NetAcad Learning Management Platform",
                f"- **Processing System:** Async Optimized Course Export Tool",
                f"- **File Format:** Markdown (.md) - Optimized for AI/LLM Processing",
                "",
            ]
        )

        return "\n".join(markdown_lines)

    async def save_results_async(self):
        """Save processing results to JSON asynchronously."""
        course_data = []

        for course in self.courses:
            course_data.append(
                {
                    "course_id": course.course_id,
                    "course_name": course.course_name,
                    "csv_file_path": course.csv_file_path,
                    "markdown_file_path": course.markdown_file_path,
                    "processing_status": course.processing_status,
                    "error_message": course.error_message,
                }
            )

        df = pd.DataFrame(course_data)
        json_path = DATA_DIR / "courses_export_summary.json"

        # Save asynchronously
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.thread_executor,
            lambda: df.to_json(str(json_path), orient="records", indent=4),
        )

        self.logger.info(f"Export summary saved to: {json_path}")

    async def process_all_courses(self):
        """Main async processing function."""
        start_time = time.time()

        if not validate_setup():
            self.logger.error("Setup validation failed")
            return

        self.logger.info("Starting optimized async course export...")

        # Clear old downloads
        await self.clear_old_downloads_async()

        # Get all courses
        self.courses = await self.login_and_get_courses()

        if not self.courses:
            self.logger.error("No courses found or login failed")
            return

        self.logger.info(f"Found {len(self.courses)} courses to process")
        self.logger.info(
            f"⚡ Processing with max {self.max_concurrent_courses} concurrent courses"
        )

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent_courses)

        # Process courses concurrently
        tasks = []
        for course in self.courses:
            task = asyncio.create_task(self.process_single_course(course, semaphore))
            tasks.append(task)

        # Wait for all courses to complete
        self.logger.info("Processing courses concurrently...")
        processed_courses = await asyncio.gather(*tasks, return_exceptions=True)

        # Update courses list with results
        successful_exports = 0
        failed_exports = 0

        for i, result in enumerate(processed_courses):
            if isinstance(result, CourseInfo):
                self.courses[i] = result
                if result.processing_status == "success":
                    successful_exports += 1
                else:
                    failed_exports += 1
                    self.failed_courses.append(result.course_id)
            else:
                failed_exports += 1
                self.failed_courses.append(self.courses[i].course_id)
                self.logger.error(
                    f"Exception processing course {self.courses[i].course_name}: {result}"
                )

        # Save results
        await self.save_results_async()

        # Print summary
        end_time = time.time()
        elapsed_time = end_time - start_time

        self.logger.info("=" * 60)
        self.logger.info("ASYNC EXPORT SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Total Courses Processed: {len(self.courses)}")
        self.logger.info(f"Successful Exports: {successful_exports}")
        self.logger.info(f"Failed Exports: {failed_exports}")
        self.logger.info(f"Processing Time: {elapsed_time:.2f} seconds")
        self.logger.info(
            f"Average Time per Course: {elapsed_time/len(self.courses):.2f} seconds"
        )
        self.logger.info(f"CSV Files Location: {CSV_DATA_DIR}")
        self.logger.info(f"Markdown Files Location: {MD_DATA_DIR}")

        if self.failed_courses:
            self.logger.warning(f"Failed Course IDs: {', '.join(self.failed_courses)}")

        speed_improvement = (24 * 60) / elapsed_time if elapsed_time > 0 else 0
        self.logger.info(
            f"🚀 Estimated speed improvement: {speed_improvement:.1f}x faster"
        )
        self.logger.info("=" * 60)

        # Cleanup executors
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)


async def main():
    """Main async entry point."""
    # Configurable concurrency - adjust based on your system and NetAcad's rate limits
    # Can be overridden by environment variables
    MAX_CONCURRENT_COURSES = int(os.getenv("ASYNC_CONCURRENT_COURSES", "3"))
    MAX_WORKERS = int(os.getenv("ASYNC_MAX_WORKERS", "4"))

    exporter = AsyncCourseExporter(
        max_concurrent_courses=MAX_CONCURRENT_COURSES, max_workers=MAX_WORKERS
    )

    await exporter.process_all_courses()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
