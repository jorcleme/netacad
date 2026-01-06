import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import pandas as pd
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from constants import (
    BASE_URL,
    CSV_DATA_DIR,
    DATA_DIR,
    INSTRUCTOR_ID,
    INSTRUCTOR_PASSWORD,
    LOGS_DIR,
    MD_DATA_DIR,
    WEBDRIVER_TIMEOUT,
    validate_setup,
)

if not validate_setup():
    print("Setup validation failed. Please check your environment and try again.")
    exit(1)
else:
    print("Setup validation passed. Proceeding with course export...")

log_file = LOGS_DIR / "course_export_playwright.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(log_file), mode="w", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Pre-compile regex patterns for performance
CSV_PATTERN = re.compile(
    r"^GRADEBOOK_DATA_\d{4}_\d{2}_\d{2}T\d{2}_\d{2}_\d{2}Z_[\w-]+\.csv$"
)
MD_PATTERN = re.compile(
    r"^GRADEBOOK_DATA_\d{4}_\d{2}_\d{2}T\d{2}_\d{2}_\d{2}Z_[\w-]+\.md$"
)


async def clear_old_downloads():
    """Deletes old CSV and Markdown files before new exports start."""
    try:
        # Clear from main DATA_DIR (downloaded files)
        for file in os.listdir(str(DATA_DIR)):
            if file.endswith(".csv") and CSV_PATTERN.match(file):
                file_path = DATA_DIR / file
                os.remove(str(file_path))
                logger.info(f"Deleted old download: {file_path}")

        # Clear organized CSV files
        if CSV_DATA_DIR.exists():
            for file in os.listdir(str(CSV_DATA_DIR)):
                if file.endswith(".csv") and CSV_PATTERN.match(file):
                    file_path = CSV_DATA_DIR / file
                    os.remove(str(file_path))
                    logger.info(f"Deleted old CSV export: {file_path}")

        # Clear Markdown files
        if MD_DATA_DIR.exists():
            for file in os.listdir(str(MD_DATA_DIR)):
                if file.endswith(".md") and MD_PATTERN.match(file):
                    file_path = MD_DATA_DIR / file
                    os.remove(str(file_path))
                    logger.info(f"Deleted old Markdown export: {file_path}")

    except Exception as e:
        logger.error(f"Error clearing old files: {e}", exc_info=True)


def create_markdown_export(
    df: pd.DataFrame, csv_filename: str, course_id: str, course_name: str
) -> tuple[bool, str]:
    """Creates a Markdown file from the gradebook data with better formatting."""
    try:
        md_filename = csv_filename.replace(".csv", ".md")
        md_file_path = MD_DATA_DIR / md_filename

        markdown_content = generate_gradebook_markdown(df, course_id, course_name)

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
    """Generates formatted Markdown content from gradebook data optimized for LLM consumption."""
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

    # Add the main data table
    markdown_lines.extend(
        [
            "## Complete Student Gradebook Data",
            "",
            "Below is the complete gradebook data for all students in this course.",
            "Each row represents one student's performance across all gradeable items.",
            "",
        ]
    )

    # Convert DataFrame to Markdown table
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
            f"- **Processing System:** Automated Course Export Tool (Playwright)",
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
    """Adds a COURSE_ID column to the CSV file and creates both CSV and Markdown versions."""
    original_file_path = DATA_DIR / csv_filename

    if not original_file_path.exists():
        logger.error(f"CSV file not found: {csv_filename}")
        return False, "", ""

    try:
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


async def wait_for_download(download_path: Path, timeout: int = 30) -> str | None:
    """Waits for a new CSV file to appear in the download directory."""
    initial_files = set(os.listdir(str(download_path)))
    start_time = asyncio.get_event_loop().time()

    while True:
        current_files = set(os.listdir(str(download_path)))
        new_files = current_files - initial_files
        csv_files = [file for file in new_files if file.endswith(".csv")]

        if csv_files:
            latest_csv = max(
                csv_files,
                key=lambda f: os.path.getctime(os.path.join(download_path, f)),
            )
            logger.info(f"Download complete: {latest_csv}")
            return latest_csv

        if asyncio.get_event_loop().time() - start_time > timeout:
            logger.warning("Download timeout reached.")
            return None

        await asyncio.sleep(0.5)  # Check every 500ms


async def navigate_to_login(page: Page):
    """Navigate to the login page and click the login button."""
    try:
        login_btn = page.locator(".loginBtn--lfDa2")
        await login_btn.click(force=True)
        logger.info("Clicked on the login button.")
    except Exception as e:
        logger.error(f"Error navigating to login: {e}")
        raise


async def send_credentials(page: Page):
    """Send username and password."""
    try:
        # Enter username
        username_field = page.locator("#username")
        await username_field.fill(INSTRUCTOR_ID)
        await username_field.press("Enter")
        logger.info("Username entered.")

        # Wait for password field and enter password
        password_field = page.locator("#password")
        await password_field.wait_for(state="visible", timeout=10000)
        await password_field.fill(INSTRUCTOR_PASSWORD)
        await password_field.press("Enter")
        logger.info("Password entered.")

        # Wait for successful login by checking for course list element
        # This is more reliable than networkidle which may never happen
        await page.wait_for_selector(".instance_name--dioD1", timeout=30000)
        logger.info("Login successful.")

    except Exception as e:
        logger.error(f"Error sending credentials: {e}")
        raise


async def paginate_and_fetch_courses(page: Page) -> Tuple[List[str], List[str]]:
    """Cycles through all pages and collects course URLs and names."""
    course_urls = []
    course_names = []
    page_num = 0

    while True:
        page_num += 1
        logger.info(f"My Classlist Page {page_num}")

        # Wait for course anchors to load
        await page.wait_for_selector(".instance_name--dioD1", timeout=15000)

        # Collect course anchors on the current page
        course_anchors = await page.locator(".instance_name--dioD1").all()

        for anchor in course_anchors:
            href = await anchor.get_attribute("href")
            text = await anchor.text_content()
            if href and text:
                course_urls.append(f"{BASE_URL}{href}")
                course_names.append(text.strip())

        # Try to find and click the next button
        try:
            next_button = page.locator(
                "button.pageItem--BNJmT.sides--EdMyh span.icon-chevron-right"
            )

            # Check if next button exists and is enabled
            if await next_button.count() > 0:
                parent_button = next_button.locator("..")
                is_disabled = await parent_button.get_attribute("disabled")

                if is_disabled:
                    logger.info("Next button is disabled. Exiting pagination loop.")
                    break

                await parent_button.click()
                await page.wait_for_load_state("networkidle", timeout=10000)
            else:
                logger.info("No next button found. Exiting pagination loop.")
                break

        except Exception as e:
            logger.info(f"Pagination complete or error: {e}")
            break

    logger.info(f"Total course names collected: {len(course_names)}")
    logger.info(f"Total course URLs collected: {len(course_urls)}")
    return course_urls, course_names


async def execute_gradebook_actions(
    page: Page, course_id: str, course_name: str = ""
) -> tuple[bool, str, str]:
    """Execute gradebook export actions for a single course."""
    try:
        logger.info(f"Starting gradebook actions for Course ID: {course_id}")

        # Click gradebook tab
        gradebook_tab = page.locator("#Launch-tab-gradebook")
        await gradebook_tab.click()
        await page.wait_for_load_state("networkidle", timeout=15000)

        # Click export dropdown - target the Download button specifically
        logger.info("Clicking export dropdown...")
        export_dropdown = page.locator("button.iconDownload--RKrnV")
        await export_dropdown.click()
        await asyncio.sleep(0.5)  # Brief pause for dropdown animation

        # Click "Export All"
        export_all_btn = page.locator(".dropdownButton--whS7t").first
        await export_all_btn.click()

        # Wait for and handle the export confirmation modal
        try:
            # Wait for modal to appear (it has class exportCsvModal--XL37A)
            await page.wait_for_selector(
                ".exportCsvModal--XL37A.modal.show", timeout=5000
            )
            logger.info("Export modal appeared, looking for close/OK button...")

            # Try multiple strategies to close the modal
            closed = False

            # Strategy 1: Look for OK/Close button within the modal
            try:
                # Common button patterns in modals
                modal_button = page.locator(
                    ".exportCsvModal--XL37A button.btn--primary, "
                    ".exportCsvModal--XL37A button[type='button']:has-text('Okay'), "
                    ".exportCsvModal--XL37A button:has-text('Close'), "
                    ".exportCsvModal--XL37A .modal__footer button"
                ).first

                await modal_button.click(timeout=3000)
                logger.info("Clicked modal button.")
                closed = True
            except Exception as e:
                logger.warning(f"Modal button click failed: {e}")

            # Strategy 2: Click X button or aria-label close
            if not closed:
                try:
                    close_btn = page.locator(
                        ".exportCsvModal--XL37A button.close, "
                        ".exportCsvModal--XL37A [aria-label='Close'], "
                        ".exportCsvModal--XL37A .modal-header button"
                    ).first

                    await close_btn.click(timeout=3000)
                    logger.info("Clicked close button.")
                    closed = True
                except Exception as e:
                    logger.warning(f"Close button click failed: {e}")

            # Strategy 3: Press Escape key
            if not closed:
                try:
                    await page.keyboard.press("Escape")
                    logger.info("Pressed Escape to close modal.")
                    closed = True
                except Exception as e:
                    logger.warning(f"Escape key failed: {e}")

            # Wait for modal to disappear
            if closed:
                await page.wait_for_selector(
                    ".exportCsvModal--XL37A.modal.show", state="hidden", timeout=5000
                )
                logger.info("Export modal closed successfully.")
            else:
                logger.warning("Could not close modal with any strategy.")

        except Exception as e:
            logger.warning(f"Modal handling error: {e}")

        # Click refresh button
        refresh_btn = page.locator("#refreshExportList")
        await refresh_btn.click()
        await page.wait_for_load_state("networkidle", timeout=10000)

        # Open dropdown with retries
        success = False
        for attempt in range(3):
            try:
                dropdown_button = page.locator("#dropdown-basic")
                await dropdown_button.click()

                # Wait for dropdown menu to appear
                await page.wait_for_selector(
                    ".dropdown__menu.dropdown-menu.show a", timeout=5000
                )
                logger.info("Exported dropdown list opened successfully...")
                success = True
                break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/3 failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)

        if not success:
            logger.error("Failed to open dropdown after 3 attempts.")
            return False, "", ""

        # Click the first export link
        export_links = page.locator(".dropdown-item.dropdownItem--gyPVf")
        if await export_links.count() > 0:
            first_link = export_links.first
            await first_link.click()

            # Wait for download
            csv_filename = await wait_for_download(DATA_DIR, timeout=30)

            if csv_filename:
                logger.info(f"Downloaded file: {csv_filename}")

                # Process the file
                success, csv_path, markdown_path = add_course_id_to_csv(
                    csv_filename, course_id, course_name
                )

                if success:
                    logger.info(
                        f"Successfully processed both formats for {course_name}"
                    )
                    return True, csv_path, markdown_path
                else:
                    logger.error(f"Failed to process files for course {course_id}")
                    return False, "", ""
            else:
                logger.error("Download timeout or failed.")
                return False, "", ""
        else:
            logger.error("No export links found.")
            return False, "", ""

    except Exception as e:
        logger.error(
            f"Error executing gradebook actions for {course_id}: {e}", exc_info=True
        )
        return False, "", ""


async def collect_course_data(page: Page) -> Tuple[List[str], List[str], List[str]]:
    """Cycles through all pages and collects course URLs and names."""
    course_ids = []
    course_urls = []
    course_names = []
    page_num = 0

    while True:
        page_num += 1
        logger.info(f"My Classlist Page {page_num}")

        # Wait for course anchors to load
        await page.wait_for_selector(".instance_name--dioD1", timeout=15000)

        # Collect course anchors on the current page
        course_anchors = await page.locator(".instance_name--dioD1").all()

        for anchor in course_anchors:
            href = await anchor.get_attribute("href")
            text = await anchor.text_content()
            if href and text:
                course_ids.append(href.split("=")[1].strip())
                course_urls.append(f"{BASE_URL}{href}")
                course_names.append(text.strip())

        # Try to find and click the next button
        try:
            next_button = page.locator(
                "button.pageItem--BNJmT.sides--EdMyh span.icon-chevron-right"
            )

            # Check if next button exists and is enabled
            if await next_button.count() > 0:
                parent_button = next_button.locator("..")
                is_disabled = await parent_button.get_attribute("disabled")

                if is_disabled:
                    logger.info("Next button is disabled. Exiting pagination loop.")
                    break

                await parent_button.click()
                # Wait for new courses to load instead of networkidle
                await asyncio.sleep(1)  # Brief pause for page transition
                await page.wait_for_selector(".instance_name--dioD1", timeout=10000)
            else:
                logger.info("No next button found. Exiting pagination loop.")
                break

        except Exception as e:
            logger.info(f"Pagination complete or error: {e}")
            break

    logger.info(f"Total course names collected: {len(course_names)}")
    logger.info(f"Total course URLs collected: {len(course_urls)}")
    return course_ids, course_urls, course_names


async def get_course_data():
    course_ids = []
    course_urls = []
    course_names = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )  # debug headless=false
        # Create context with download path
        context = await browser.new_context(accept_downloads=True)

        # Create page
        page = await context.new_page()

        try:
            logger.info("Navigating to netacad.com...")
            # Use domcontentloaded instead of networkidle for faster, more reliable loading
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            await navigate_to_login(page)
            await send_credentials(page)

            course_ids, course_urls, course_names = await collect_course_data(page)

        except Exception as e:
            logger.error(f"Error in main processing loop: {e}", exc_info=True)

        finally:
            await context.close()
            await browser.close()

    return course_ids, course_urls, course_names


async def process_courses(clear_downloads: bool = True):
    """Main function to process all courses using Playwright."""
    start_time = asyncio.get_event_loop().time()

    if clear_downloads:
        logger.info("Clearing old downloads...")
        await clear_old_downloads()

    # Initialize results tracking
    course_ids = []
    course_names_list = []
    course_csv_files = []
    failed_course_ids = []

    async with async_playwright() as p:
        # Launch browser
        logger.info("Launching Chromium browser...")
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        # Create context with download path
        context = await browser.new_context(
            accept_downloads=True,
            viewport={"width": 1920, "height": 1080},
        )

        # Set default timeout
        context.set_default_timeout(WEBDRIVER_TIMEOUT * 1000)

        # Create page
        page = await context.new_page()

        try:
            # Navigate and login
            logger.info("Navigating to netacad.com...")
            await page.goto(BASE_URL, wait_until="networkidle")

            await navigate_to_login(page)
            await send_credentials(page)

            # Fetch all courses
            course_urls, course_names = await paginate_and_fetch_courses(page)

            # Process each course
            for i, url in enumerate(course_urls):
                if url:
                    course_name = course_names[i]
                    course_id = url.split("=")[1] if "=" in url else f"unknown_{i}"

                    logger.info(
                        f"Processing course {i + 1}/{len(course_urls)}: {course_name}"
                    )

                    course_ids.append(course_id)
                    course_names_list.append(course_name)
                    logger.info(f"Course URL: {url}")

                    try:
                        # Navigate to course page
                        await page.goto(
                            url, wait_until="domcontentloaded", timeout=30000
                        )

                        # Execute gradebook export
                        success, csv_path, md_path = await execute_gradebook_actions(
                            page, course_id, course_name
                        )

                        if success:
                            course_csv_files.append(f"CSV: {csv_path} | MD: {md_path}")
                            logger.info(
                                f"[SUCCESS] Successfully exported grades for {course_name}"
                            )
                        else:
                            course_csv_files.append("")
                            failed_course_ids.append(course_id)
                            logger.warning(
                                f"[FAILED] Failed to export grades for {course_name}"
                            )

                    except Exception as e:
                        logger.error(
                            f"[ERROR] Unexpected error processing {course_name}: {e}"
                        )
                        course_csv_files.append("")
                        failed_course_ids.append(course_id)

                    logger.info("-" * 50)

        finally:
            await context.close()
            await browser.close()

    # Save summary
    save_courses_data_to_json(course_ids, course_names_list, course_csv_files)

    # Print summary
    successful_exports = sum(1 for file_info in course_csv_files if file_info)
    failed_exports = len(course_ids) - successful_exports
    elapsed_time = asyncio.get_event_loop().time() - start_time

    logger.info("=" * 60)
    logger.info("EXPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Courses Processed: {len(course_ids)}")
    logger.info(f"Successful Exports: {successful_exports}")
    logger.info(f"Failed Exports: {failed_exports}")
    logger.info(f"CSV Files Location: {CSV_DATA_DIR}")
    logger.info(f"Markdown Files Location: {MD_DATA_DIR}")
    logger.info(f"Total Time: {elapsed_time:.2f} seconds")

    if failed_course_ids:
        logger.warning(f"Failed Course IDs: {', '.join(failed_course_ids)}")

    logger.info("=" * 60)


def save_courses_data_to_json(
    course_ids: List[str], course_names: List[str], course_csv_files: List[str]
):
    """Save course processing results to JSON with file path information."""
    course_data = []

    for i, (course_id, course_name) in enumerate(zip(course_ids, course_names)):
        file_info = course_csv_files[i] if i < len(course_csv_files) else ""

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


async def main():
    """Entry point for async execution."""
    course_ids, course_urls, course_names = await get_course_data()

    for id, url, name in zip(course_ids, course_urls, course_names):
        print(f"Course ID: {id}, URL: {url}, Name: {name}")


if __name__ == "__main__":
    asyncio.run(main())
