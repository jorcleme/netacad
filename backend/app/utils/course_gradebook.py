import asyncio
import logging
import os
import re
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from app.config import (
    DATA_DIR,
    NETACAD_BASE_URL,
    NETACAD_INSTRUCTOR_ID,
    NETACAD_INSTRUCTOR_PASSWORD,
)
from httpx import delete
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Create gradebook-specific directories
GRADEBOOK_DIR = DATA_DIR / "gradebooks"
GRADEBOOK_CSV_DIR = GRADEBOOK_DIR / "csv"
GRADEBOOK_MD_DIR = GRADEBOOK_DIR / "markdown"

# Ensure directories exist
GRADEBOOK_DIR.mkdir(parents=True, exist_ok=True)
GRADEBOOK_CSV_DIR.mkdir(parents=True, exist_ok=True)
GRADEBOOK_MD_DIR.mkdir(parents=True, exist_ok=True)


class GradebookManager:
    """
    Singleton manager for gradebook downloads from NetAcad courses.
    Handles authentication, navigation, and file processing.

    Maintains a single instance per page to preserve login state across
    multiple course downloads in the same session.
    """

    _instance: Optional["GradebookManager"] = None
    _page: Optional[Page] = None
    _is_logged_in: bool = False

    def __new__(cls, page: Page, headless: bool = True):
        """
        Ensure only one instance exists per page.
        If page changes, create new instance.
        """
        # If no instance exists, or page has changed, create new instance
        if cls._instance is None or cls._page != page:
            logger.info("Creating new GradebookManager singleton instance")
            cls._instance = super(GradebookManager, cls).__new__(cls)
            cls._page = page
            cls._is_logged_in = False
        else:
            logger.info(
                f"Reusing existing GradebookManager instance (logged_in: {cls._is_logged_in})"
            )

        return cls._instance

    def __init__(self, page: Page, headless: bool = True):
        """
        Initialize the GradebookManager.

        Args:
            page: Playwright Page instance
            headless: Whether browser is running in headless mode
        """
        # Only initialize once
        if not hasattr(self, "_initialized"):
            self.page = page
            self.headless = headless
            self._initialized = True
            logger.info("GradebookManager initialized")

    @property
    def is_logged_in(self) -> bool:
        """Get the logged-in status (class-level)."""
        return self.__class__._is_logged_in

    @is_logged_in.setter
    def is_logged_in(self, value: bool):
        """Set the logged-in status (class-level)."""
        if self.__class__._is_logged_in != value:
            logger.info(
                f"Login status changed: {self.__class__._is_logged_in} -> {value}"
            )
        self.__class__._is_logged_in = value

    @staticmethod
    def normalize_course_name(course_name: str) -> str:
        """
        Normalize course name for use in filenames.

        Args:
            course_name: Original course name

        Returns:
            str: Normalized course name (lowercase, alphanumeric with hyphens)
        """
        # Remove special characters and replace spaces with hyphens
        normalized = re.sub(r"[^\w\s-]", "", course_name.lower())
        # Replace multiple spaces/hyphens with single hyphen
        normalized = re.sub(r"[-\s]+", "-", normalized)
        # Remove leading/trailing hyphens
        normalized = normalized.strip("-")
        # Limit length to avoid filesystem issues
        if len(normalized) > 80:
            normalized = normalized[:80].rstrip("-")
        return normalized

    async def check_login_status(self) -> bool:
        """
        Check if we're currently logged in to NetAcad.

        Returns:
            bool: True if logged in, False otherwise
        """
        try:
            current_url = self.page.url
            logger.info(f"Checking login status. Current URL: {current_url}")

            # Check for the login button - if it exists, we're not logged in
            login_btn = self.page.locator(".loginBtn--lfDa2")
            is_visible = await login_btn.is_visible(timeout=3000)
            logger.info(f"Login button visible: {is_visible}")

            if is_visible:
                logger.info("Not logged in - login button is visible")
                self.is_logged_in = False
                return False

            # Check multiple indicators of logged-in state
            # 1. Course list elements (on home page)
            course_elements = await self.page.locator(".instance_name--dioD1").count()
            logger.info(f"Course list elements found: {course_elements}")

            if course_elements > 0:
                logger.info("Already logged in - course list visible")
                self.is_logged_in = True
                return True

            # 2. Gradebook tab (on course page)
            gradebook_tab = await self.page.locator("#Launch-tab-gradebook").count()
            logger.info(f"Gradebook tab found: {gradebook_tab}")

            if gradebook_tab > 0:
                logger.info("Already logged in - on course page with gradebook tab")
                self.is_logged_in = True
                return True

            # 3. Check if URL indicates we're on a course page (logged in)
            if "/course/" in current_url.lower():
                logger.info("Already logged in - URL indicates course page")
                self.is_logged_in = True
                return True

            # As fallback, assume not logged in
            logger.warning("Could not confirm logged-in state via any indicator")
            self.is_logged_in = False
            return False

        except Exception as e:
            logger.warning(f"Error checking login status: {e}")
            self.is_logged_in = False
            return False

    async def perform_login(self) -> bool:
        """
        Perform login to NetAcad.

        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            logger.info("Attempting to log in to NetAcad...")

            # First, check if we're already logged in
            if await self.check_login_status():
                logger.info("Already logged in, skipping login process")
                return True

            # Navigate to base URL if not already there
            current_url = self.page.url
            if not current_url.startswith(NETACAD_BASE_URL):
                logger.info(f"Navigating to {NETACAD_BASE_URL}")
                await self.page.goto(
                    NETACAD_BASE_URL, wait_until="domcontentloaded", timeout=30000
                )

            # Click the login button
            login_btn = self.page.locator(".loginBtn--lfDa2")
            await login_btn.wait_for(state="visible", timeout=10000)

            # Scroll into view and click
            await login_btn.evaluate(
                "element => element.scrollIntoView({block: 'center', behavior: 'smooth'})"
            )
            await self.page.wait_for_timeout(500)
            await login_btn.click()
            logger.info("Clicked login button")

            # Enter username
            username_field = self.page.locator("#username")
            await username_field.wait_for(state="visible", timeout=10000)
            await username_field.fill(NETACAD_INSTRUCTOR_ID)
            await username_field.press("Enter")
            logger.info("Username entered")

            # Enter password
            password_field = self.page.locator("#password")
            await password_field.wait_for(state="visible", timeout=10000)
            await password_field.fill(NETACAD_INSTRUCTOR_PASSWORD)
            await password_field.press("Enter")
            logger.info("Password entered")

            # Wait for successful login
            await self.page.wait_for_selector(".instance_name--dioD1", timeout=30000)
            logger.info("Login successful")

            self.is_logged_in = True
            return True

        except Exception as e:
            logger.error(f"Login failed: {e}", exc_info=True)
            self.is_logged_in = False
            return False

    async def ensure_logged_in(self) -> bool:
        """
        Ensure we're logged in, performing login if necessary.

        Returns:
            bool: True if logged in (or login succeeded), False otherwise
        """
        if self.is_logged_in:
            # Double-check we're still logged in
            if await self.check_login_status():
                return True

        # Need to log in
        return await self.perform_login()

    async def navigate_to_course(self, course_url: str) -> bool:
        """
        Navigate to a specific course URL.

        Args:
            course_url: The full URL of the course

        Returns:
            bool: True if navigation successful, False otherwise
        """
        try:
            logger.info(f"Navigating to course: {course_url}")
            await self.page.goto(
                course_url, wait_until="domcontentloaded", timeout=30000
            )

            # Wait a moment for the page to settle
            await self.page.wait_for_timeout(1000)

            # Check if we got redirected to login
            current_url = self.page.url
            if "login" in current_url.lower() or not current_url.startswith(
                course_url[:50]
            ):
                logger.warning("Got redirected, likely need to log in")
                self.is_logged_in = False
                return False

            logger.info("Successfully navigated to course")
            return True

        except Exception as e:
            logger.error(f"Error navigating to course: {e}")
            return False

    async def wait_for_download_event(self, timeout: int = 30000) -> Optional[str]:
        """
        Wait for a download event and save the file.
        Uses Playwright's download API.

        Args:
            timeout: Maximum milliseconds to wait

        Returns:
            str: Filename of downloaded file, or None if timeout
        """
        try:
            logger.info("Waiting for download event...")

            # Wait for download to start
            async with self.page.expect_download(timeout=timeout) as download_info:
                pass

            download = await download_info.value

            # Get suggested filename
            suggested_filename = download.suggested_filename
            logger.info(f"Download started: {suggested_filename}")

            # Save to our gradebook directory
            save_path = GRADEBOOK_DIR / suggested_filename
            await download.save_as(str(save_path))
            logger.info(f"Download saved to: {save_path}")

            return suggested_filename

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    def create_markdown_export(
        self, df: pd.DataFrame, csv_filename: str, course_id: str, course_name: str
    ) -> Tuple[bool, str]:
        """
        Create a Markdown file from gradebook data.

        Args:
            df: DataFrame with gradebook data
            csv_filename: Name of the CSV file
            course_id: Course ID
            course_name: Course name

        Returns:
            Tuple of (success: bool, markdown_path: str)
        """
        try:
            md_filename = csv_filename.replace(".csv", ".md")
            md_file_path = GRADEBOOK_MD_DIR / md_filename

            markdown_content = self._generate_gradebook_markdown(
                df, course_id, course_name
            )

            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            logger.info(f"Markdown export saved: {md_file_path}")
            return True, str(md_file_path)

        except Exception as e:
            logger.error(f"Error creating Markdown export: {e}")
            return False, ""

    def _generate_gradebook_markdown(
        self, df: pd.DataFrame, course_id: str, course_name: str
    ) -> str:
        """Generate formatted Markdown content from gradebook data."""
        export_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_students = len(df)

        markdown_lines = [
            "# NetAcad Gradebook Export",
            "",
            "## Course Information",
            f"- **Course ID:** {course_id}",
            f"- **Course Name:** {course_name}",
            f"- **Export Date:** {export_date}",
            f"- **Total Students:** {total_students}",
            "",
            "---",
            "",
        ]

        # Add summary statistics
        numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
        if len(numeric_columns) > 1:
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
                    markdown_lines.extend(
                        [
                            f"### {col}",
                            f"- **Mean:** {stats['mean']:.2f}",
                            f"- **Median:** {stats['50%']:.2f}",
                            f"- **Min:** {stats['min']:.2f}",
                            f"- **Max:** {stats['max']:.2f}",
                            f"- **Std Dev:** {stats['std']:.2f}",
                            f"- **Count:** {int(stats['count'])}",
                            "",
                        ]
                    )

            markdown_lines.extend(["---", ""])

        # Add data table
        markdown_lines.extend(
            [
                "## Complete Student Gradebook Data",
                "",
                "Each row represents one student's performance across all gradeable items.",
                "",
            ]
        )

        # Format DataFrame as Markdown table
        display_df = df.copy()
        column_mapping = {
            col: col.replace("_", " ").replace("-", " ").title()
            for col in display_df.columns
        }
        display_df = display_df.rename(columns=column_mapping)
        markdown_table = display_df.to_markdown(index=False, tablefmt="pipe")
        markdown_lines.append(markdown_table)

        # Add footer
        markdown_lines.extend(
            [
                "",
                "---",
                "",
                "## Export Metadata",
                f"- **Generated:** {export_date}",
                f"- **Source:** NetAcad Learning Management Platform",
                f"- **Format:** Markdown (AI/LLM optimized)",
                "",
            ]
        )

        return "\n".join(markdown_lines)

    def process_csv_file(
        self, csv_filename: str, course_id: str, course_name: str
    ) -> Tuple[bool, str, str]:
        """
        Process downloaded CSV file: add course ID and create Markdown version.

        Args:
            csv_filename: Name of the CSV file
            course_id: Course ID to prepend
            course_name: Course name for metadata

        Returns:
            Tuple of (success: bool, csv_path: str, markdown_path: str)
        """
        original_file_path = GRADEBOOK_DIR / csv_filename

        if not original_file_path.exists():
            logger.error(f"CSV file not found: {csv_filename}")
            return False, "", ""

        try:
            # Read CSV with special handling for NetAcad's malformed format
            logger.info(f"Reading CSV file: {original_file_path}")

            # NetAcad CSV format issues:
            # 1. Extra spaces around commas: "NAME        , EMAIL        , ..."
            # 2. "Point Possible" metadata row (row 2) - must skip
            # 3. Empty fields as quoted spaces: " " (confuses pandas Python engine)
            # 4. CRITICAL: Extra unnamed column at the end (trailing comma issue)
            # 5. Empty Assessment values (no grade yet for inactive students)

            # Solution: Pre-process the file to clean up quoted spaces
            # This is more reliable than trying to configure pandas to handle it
            logger.info(
                "Pre-processing CSV to handle quoted spaces and malformed structure"
            )

            cleaned_lines = []
            with open(original_file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # Replace quoted spaces with nothing (will become empty field)
                # Pattern: , " " , becomes ,,
                line = line.replace(', " "', ",")
                line = line.replace('" " ,', ",")
                line = line.replace(', " " ,', ",,")

                # Strip extra whitespace around commas
                # "NAME        , EMAIL" becomes "NAME,EMAIL"
                line = re.sub(r"\s*,\s*", ",", line)

                cleaned_lines.append(line)

            logger.info(f"Pre-processed {len(cleaned_lines)} lines")

            # Write to temporary file
            temp_file_path = (
                original_file_path.parent / f"temp_cleaned_{original_file_path.name}"
            )
            with open(temp_file_path, "w", encoding="utf-8", newline="") as f:
                f.write("\n".join(cleaned_lines))

            logger.info(f"Wrote cleaned CSV to temp file: {temp_file_path}")

            # Now read the cleaned CSV with pandas
            # CRITICAL: NetAcad CSVs often have extra trailing columns (duplicate grade values)
            # that don't have headers. We need to explicitly tell pandas to only use
            # the columns that are actually in the header.

            # First, read just the header to get column count
            with open(temp_file_path, "r", encoding="utf-8") as f:
                header_line = f.readline().strip()
                num_columns = header_line.count(",") + 1
                logger.info(f"Header has {num_columns} columns")

            df = pd.read_csv(
                str(temp_file_path),
                encoding="utf-8",
                # Skip the "Point Possible" row (row 1, 0-indexed)
                skiprows=[1],
                # Remove any remaining leading/trailing whitespace
                skipinitialspace=True,
                # Treat empty strings as NaN
                na_values=["", "NULL"],
                keep_default_na=True,
                # CRITICAL: Only use the first N columns that have headers
                # This prevents extra trailing columns from shifting data
                usecols=range(num_columns),
            )

            # Clean up temp file
            temp_file_path.unlink()
            logger.info("Cleaned up temporary file")

            logger.info(
                f"Successfully read CSV with {len(df)} rows and {len(df.columns)} columns"
            )
            logger.info(f"Raw columns: {list(df.columns)}")

            # Clean column names - strip whitespace and quotes
            df.columns = df.columns.str.strip().str.strip('"')
            logger.info(f"Cleaned columns: {list(df.columns)}")

            # Drop any completely unnamed columns (the extra column at the end)
            unnamed_cols = [
                col for col in df.columns if col.startswith("Unnamed:") or col == ""
            ]
            if unnamed_cols:
                logger.info(f"Dropping unnamed columns: {unnamed_cols}")
                df = df.drop(columns=unnamed_cols)

            # Replace NaN/None with "NULL" for better readability and consistency
            # This handles empty Assessment values and quoted spaces
            df = df.fillna("NULL")

            logger.info(f"Final dataframe: {len(df)} rows x {len(df.columns)} columns")
            logger.info(f"Final columns: {list(df.columns)}")

            # Add COURSE_ID column at the beginning
            df.insert(0, "COURSE_ID", course_id, allow_duplicates=True)

            # Add course name for reference
            df.insert(1, "COURSE_NAME", course_name, allow_duplicates=True)

            # Save cleaned CSV with headers
            csv_output_path = GRADEBOOK_CSV_DIR / csv_filename
            df.to_csv(str(csv_output_path), index=False, header=True)
            logger.info(f"CSV saved: {csv_output_path}")

            # Create Markdown version
            markdown_success, markdown_path = self.create_markdown_export(
                df, csv_filename, course_id, course_name
            )

            if markdown_success:
                # Clean up original download
                original_file_path.unlink()
                logger.info(f"Cleaned up original: {original_file_path}")
                return True, str(csv_output_path), markdown_path
            else:
                logger.warning("Markdown creation failed, but CSV succeeded")
                return True, str(csv_output_path), ""

        except Exception as e:
            logger.error(f"Error processing file {csv_filename}: {e}")

            # Log first few lines of the file for debugging
            try:
                with open(
                    original_file_path, "r", encoding="utf-8", errors="replace"
                ) as f:
                    first_lines = [f.readline() for _ in range(5)]
                    logger.info("First 5 lines of problematic CSV:")
                    for i, line in enumerate(first_lines, 1):
                        logger.info(f"Line {i}: {line.strip()}")
            except:
                pass

            # Keep the original file for debugging
            logger.info(f"Original file preserved at: {original_file_path}")
            return False, "", ""

    async def download_gradebook(
        self, course_id: str, course_name: str, course_url: str
    ) -> Dict[str, any]:
        """
        Download gradebook for a single course.

        Args:
            course_id: Course ID
            course_name: Course name
            course_url: Full URL to the course

        Returns:
            Dict with keys: success (bool), course_id, course_name, csv_path, markdown_path, error
        """
        result = {
            "success": False,
            "course_id": course_id,
            "course_name": course_name,
            "csv_path": "",
            "markdown_path": "",
            "error": "",
        }

        try:
            logger.info(f"Starting gradebook download for: {course_name} ({course_id})")

            # Ensure we're logged in
            if not await self.ensure_logged_in():
                result["error"] = "Login failed"
                return result

            # Navigate to course
            if not await self.navigate_to_course(course_url):
                # Try logging in again if navigation failed
                if not await self.ensure_logged_in():
                    result["error"] = "Failed to navigate to course after login"
                    return result

                # Retry navigation
                if not await self.navigate_to_course(course_url):
                    result["error"] = "Failed to navigate to course"
                    return result

            # Execute gradebook export actions
            success, csv_path, md_path = await self._execute_gradebook_export(
                course_id, course_name
            )

            if success:
                result["success"] = True
                result["csv_path"] = csv_path
                result["markdown_path"] = md_path
                logger.info(f"Successfully downloaded gradebook for {course_name}")
            else:
                result["error"] = "Gradebook export failed"

        except Exception as e:
            logger.error(
                f"Error downloading gradebook for {course_id}: {e}", exc_info=True
            )
            result["error"] = str(e)

        return result

    async def _execute_gradebook_export(
        self, course_id: str, course_name: str
    ) -> Tuple[bool, str, str]:
        """
        Execute the gradebook export workflow on the current course page.

        Args:
            course_id: Course ID
            course_name: Course name

        Returns:
            Tuple of (success: bool, csv_path: str, markdown_path: str)
        """
        try:
            logger.info(f"Executing gradebook export for: {course_id}")

            # Click gradebook tab
            gradebook_tab = self.page.locator("#Launch-tab-gradebook")
            await gradebook_tab.click()
            logger.info("Clicked gradebook tab, checking for export button...")

            # FAST CHECK: Does this course have an export button? (fail fast if not)
            export_dropdown = self.page.locator("button.iconDownload--RKrnV")
            try:
                await export_dropdown.wait_for(state="visible", timeout=5000)
                logger.info("✓ Export button found - course has gradebook")
            except Exception as e:
                logger.warning(
                    f"✗ No export button found - course likely has no gradebook data yet"
                )
                return False, "", ""

            # Click export dropdown
            logger.info("Opening export dropdown...")
            await export_dropdown.click()
            await asyncio.sleep(0.5)

            # Click "Export All"
            export_all_btn = self.page.locator(".dropdownButton--whS7t").first
            await export_all_btn.wait_for(state="visible", timeout=5000)
            await export_all_btn.click()
            logger.info("Clicked 'Export All' button")

            # Handle export confirmation modal
            await self._handle_export_modal()

            # Try to refresh and wait for dropdown with retries
            refresh_btn = self.page.locator("#refreshExportList")
            dropdown_button = self.page.locator("#dropdown-basic")

            max_refresh_attempts = 2
            dropdown_found = False

            for attempt in range(max_refresh_attempts):
                logger.info(f"Refresh attempt {attempt + 1}/{max_refresh_attempts}")
                await refresh_btn.click()
                logger.info("Clicked refresh button, waiting for dropdown...")

                # Wait a bit for the export to be processed
                await asyncio.sleep(1.5)  # Reduced from 2s

                # Check if dropdown button appeared
                try:
                    await dropdown_button.wait_for(
                        state="visible", timeout=5000
                    )  # Reduced from 8s
                    logger.info("Dropdown button found and visible")
                    dropdown_found = True
                    break
                except Exception as e:
                    logger.warning(
                        f"Dropdown not found on attempt {attempt + 1}: {str(e)}"
                    )
                    if attempt < max_refresh_attempts - 1:
                        logger.info("Will retry refresh...")
                        await asyncio.sleep(1)

            if not dropdown_found:
                logger.error(
                    f"Failed to find dropdown after {max_refresh_attempts} refresh attempts"
                )
                return False, "", ""

            # Brief pause for UI to settle
            await asyncio.sleep(1)
            logger.info("Dropdown button ready")

            # Open dropdown with retries
            if not await self._open_export_dropdown():
                logger.error("Failed to open export dropdown")
                return False, "", ""

            # Click first export link to download
            export_links = self.page.locator(".dropdown-item.dropdownItem--gyPVf")
            link_count = await export_links.count()

            if link_count > 0:
                logger.info(f"Found {link_count} export link(s), clicking first one")
                first_link = export_links.first

                # Ensure link is visible and clickable
                await first_link.wait_for(state="visible", timeout=5000)

                # Set up download expectation BEFORE clicking
                try:
                    logger.info("Setting up download handler...")
                    async with self.page.expect_download(
                        timeout=30000
                    ) as download_info:
                        await first_link.click()
                        logger.info(
                            "Clicked download link, waiting for download to start..."
                        )

                    # Get the download
                    download = await download_info.value
                    original_filename = download.suggested_filename
                    logger.info(f"Download started: {original_filename}")

                    # Create new filename with course name and timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    normalized_name = self.normalize_course_name(course_name)
                    new_filename = f"{normalized_name}_{timestamp}.csv"

                    logger.info(f"Renaming to: {new_filename}")

                    # Save to our gradebook directory with new name
                    save_path = GRADEBOOK_DIR / new_filename
                    await download.save_as(str(save_path))
                    logger.info(f"File saved to: {save_path}")

                    # Process the file
                    success, csv_path, markdown_path = self.process_csv_file(
                        new_filename, course_id, course_name
                    )

                    if success:
                        logger.info(
                            f"Successfully processed gradebook for {course_name}"
                        )
                        return True, csv_path, markdown_path
                    else:
                        logger.error(f"Failed to process files for {course_id}")
                        return False, "", ""

                except PlaywrightTimeoutError:
                    logger.error(
                        "Download timeout - no download started within 30 seconds"
                    )
                    return False, "", ""
                except Exception as download_error:
                    logger.error(f"Download error: {download_error}", exc_info=True)
                    return False, "", ""
            else:
                logger.error("No export links found in dropdown")
                # Take screenshot for debugging
                try:
                    screenshot_path = GRADEBOOK_DIR / f"error_{course_id}.png"
                    await self.page.screenshot(path=str(screenshot_path))
                    logger.info(f"Saved error screenshot to {screenshot_path}")
                except:
                    pass
                return False, "", ""

        except Exception as e:
            logger.error(f"Error executing gradebook export: {e}", exc_info=True)
            # Take screenshot for debugging
            try:
                screenshot_path = GRADEBOOK_DIR / f"error_{course_id}_exception.png"
                await self.page.screenshot(path=str(screenshot_path))
                logger.info(f"Saved error screenshot to {screenshot_path}")
            except:
                pass
            return False, "", ""

    async def _handle_export_modal(self):
        """Handle the export confirmation modal that appears."""
        try:
            # Wait for modal with a reasonable timeout
            await self.page.wait_for_selector(
                ".exportCsvModal--XL37A.modal.show", timeout=10000
            )
            logger.info("Export modal appeared")

            # Brief pause to ensure modal is fully rendered
            await asyncio.sleep(0.5)

            # Try multiple strategies to close it
            closed = False

            # Strategy 1: Click OK/Close button (most common)
            if not closed:
                try:
                    # Try common button text patterns
                    modal_button = self.page.locator(
                        ".exportCsvModal--XL37A button:has-text('OK'), "
                        ".exportCsvModal--XL37A button:has-text('Okay'), "
                        ".exportCsvModal--XL37A button:has-text('Close'), "
                        ".exportCsvModal--XL37A button.btn-primary"
                    ).first
                    await modal_button.wait_for(state="visible", timeout=3000)
                    await modal_button.click()
                    logger.info("Clicked modal button")
                    closed = True
                except Exception as e:
                    logger.debug(f"Strategy 1 failed: {e}")

            # Strategy 2: Click X button
            if not closed:
                try:
                    close_btn = self.page.locator(
                        ".exportCsvModal--XL37A button.close, "
                        ".exportCsvModal--XL37A [aria-label='Close'], "
                        ".exportCsvModal--XL37A .modal-header button"
                    ).first
                    await close_btn.wait_for(state="visible", timeout=2000)
                    await close_btn.click()
                    logger.info("Clicked close button")
                    closed = True
                except Exception as e:
                    logger.debug(f"Strategy 2 failed: {e}")

            # Strategy 3: Press Escape key
            if not closed:
                try:
                    await self.page.keyboard.press("Escape")
                    logger.info("Pressed Escape key")
                    closed = True
                except Exception as e:
                    logger.debug(f"Strategy 3 failed: {e}")

            # Wait for modal to disappear (with extended timeout)
            if closed:
                try:
                    await self.page.wait_for_selector(
                        ".exportCsvModal--XL37A.modal.show",
                        state="hidden",
                        timeout=8000,
                    )
                    logger.info("Export modal closed successfully")
                except:
                    # Modal might have closed but selector still present
                    logger.info(
                        "Modal closure verification timed out, continuing anyway"
                    )
            else:
                logger.warning("Could not close modal with any strategy, continuing")

        except PlaywrightTimeoutError:
            logger.info("No export modal appeared (may not be required)")
        except Exception as e:
            logger.warning(f"Modal handling error: {e}, continuing anyway")

    async def _open_export_dropdown(self, max_attempts: int = 3) -> bool:
        """
        Open the export dropdown with retries.

        Args:
            max_attempts: Maximum number of attempts

        Returns:
            bool: True if successful, False otherwise
        """
        for attempt in range(max_attempts):
            try:
                dropdown_button = self.page.locator("#dropdown-basic")

                # Ensure button is visible and clickable
                await dropdown_button.wait_for(state="visible", timeout=5000)
                await dropdown_button.scroll_into_view_if_needed()
                await asyncio.sleep(0.3)  # Brief pause for rendering

                await dropdown_button.click()
                logger.info(f"Clicked dropdown button (attempt {attempt + 1})")

                # Wait for dropdown menu to appear
                await self.page.wait_for_selector(
                    ".dropdown__menu.dropdown-menu.show a", timeout=8000
                )

                # Verify we have export links
                export_links = await self.page.locator(
                    ".dropdown-item.dropdownItem--gyPVf"
                ).count()
                if export_links > 0:
                    logger.info(
                        f"Export dropdown opened successfully with {export_links} link(s)"
                    )
                    return True
                else:
                    logger.warning("Dropdown opened but no export links found")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2)
                        continue

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)

        logger.error("Failed to open export dropdown after all attempts")
        return False

    async def download_multiple_gradebooks(
        self, courses: List[Dict[str, str]], parallel: bool = True, max_workers: int = 5
    ) -> List[Dict[str, any]]:
        """
        Download gradebooks for multiple courses.

        Args:
            courses: List of dicts with keys: course_id, course_name, course_url
            parallel: If True, use parallel downloads (much faster). If False, sequential.
            max_workers: Maximum number of parallel downloads (default 5, max 10 to avoid rate limiting)

        Returns:
            List of result dicts for each course
        """
        if parallel and len(courses) > 1:
            logger.info(
                f"Starting PARALLEL bulk download for {len(courses)} courses with {max_workers} workers"
            )
            return await self._download_parallel(courses, max_workers)
        else:
            logger.info(f"Starting SEQUENTIAL bulk download for {len(courses)} courses")
            return await self._download_sequential(courses)

    async def _download_sequential(
        self, courses: List[Dict[str, str]]
    ) -> List[Dict[str, any]]:
        """Original sequential download method."""
        results = []

        for idx, course in enumerate(courses, 1):
            logger.info(
                f"Processing course {idx}/{len(courses)}: {course['course_name']}"
            )

            result = await self.download_gradebook(
                course["course_id"], course["course_name"], course["course_url"]
            )
            results.append(result)

            # Brief pause between courses
            if idx < len(courses):
                await asyncio.sleep(1)

        # Summary
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful

        logger.info("=" * 60)
        logger.info("BULK DOWNLOAD SUMMARY (Sequential)")
        logger.info("=" * 60)
        logger.info(
            f"Total: {len(courses)} | Successful: {successful} | Failed: {failed}"
        )
        logger.info("=" * 60)

        return results

    async def _download_parallel(
        self, courses: List[Dict[str, str]], max_workers: int
    ) -> List[Dict[str, any]]:
        """
        Download gradebooks in parallel using multiple browser contexts.
        Each worker gets its own browser context with independent session/cookies.

        This is MUCH faster than sequential (4-5x speedup typically).
        """
        from playwright.async_api import async_playwright

        # Limit workers to avoid overwhelming the server
        max_workers = min(max_workers, 10)

        logger.info(f"🚀 Starting parallel downloads with {max_workers} workers")
        logger.info(f"📦 Total courses: {len(courses)}")

        # We need the browser instance from the current page
        # But we'll create new contexts for each worker
        playwright = async_playwright()
        p = await playwright.start()

        try:
            # Launch browser (reuse same browser, but multiple contexts)
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            # Create a semaphore to limit concurrent downloads
            semaphore = asyncio.Semaphore(max_workers)

            async def download_with_semaphore(course_info: Dict[str, str], index: int):
                """Download a single gradebook with semaphore control."""
                async with semaphore:
                    logger.info(
                        f"[Worker {index}/{len(courses)}] Starting: {course_info['course_name']}"
                    )

                    # Create a new browser context (independent session)
                    # CRITICAL: Must have accept_downloads=True for gradebook downloads!
                    context = await browser.new_context(
                        accept_downloads=True,  # Enable downloads
                        viewport={"width": 1920, "height": 1080},
                    )
                    page = await context.new_page()

                    # Create a new GradebookManager instance for this worker
                    # Simply instantiate normally - each page is different so no singleton conflict
                    manager = GradebookManager(page, self.headless)

                    try:
                        result = await manager.download_gradebook(
                            course_info["course_id"],
                            course_info["course_name"],
                            course_info["course_url"],
                        )
                        status = "✓" if result["success"] else "✗"
                        error_msg = (
                            f" - Error: {result.get('error', 'Unknown')}"
                            if not result["success"]
                            else ""
                        )
                        logger.info(
                            f"[Worker {index}/{len(courses)}] {status} Completed: {course_info['course_name']}{error_msg}"
                        )
                        return result
                    except Exception as e:
                        logger.error(
                            f"[Worker {index}/{len(courses)}] ✗ Exception: {course_info['course_name']}: {e}",
                            exc_info=True,
                        )
                        return {
                            "success": False,
                            "course_id": course_info["course_id"],
                            "course_name": course_info["course_name"],
                            "csv_path": "",
                            "markdown_path": "",
                            "error": str(e),
                        }
                    finally:
                        await context.close()

            # Create tasks for all downloads
            tasks = [
                download_with_semaphore(course, idx + 1)
                for idx, course in enumerate(courses)
            ]

            # Run all tasks concurrently and gather results
            import time

            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = time.time() - start_time

            # Convert exceptions to error results
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    final_results.append(
                        {
                            "success": False,
                            "course_id": courses[i]["course_id"],
                            "course_name": courses[i]["course_name"],
                            "csv_path": "",
                            "markdown_path": "",
                            "error": str(result),
                        }
                    )
                else:
                    final_results.append(result)

            # Summary
            successful = sum(1 for r in final_results if r["success"])
            failed = len(final_results) - successful
            avg_time = elapsed / len(courses)

            logger.info("=" * 60)
            logger.info("🎉 BULK DOWNLOAD SUMMARY (Parallel)")
            logger.info("=" * 60)
            logger.info(
                f"Total: {len(courses)} | Successful: {successful} | Failed: {failed}"
            )
            logger.info(
                f"⏱️  Total time: {elapsed:.1f}s | Avg per course: {avg_time:.1f}s"
            )
            logger.info(f"🚀 Speedup: ~{max_workers}x faster than sequential")

            # Log failed courses for debugging
            if failed > 0:
                logger.warning(f"⚠️  {failed} downloads failed:")
                for r in final_results:
                    if not r["success"]:
                        logger.warning(
                            f"  - {r['course_name']}: {r.get('error', 'Unknown error')}"
                        )

            logger.info("=" * 60)

            await browser.close()
            return final_results

        finally:
            await p.stop()

    @staticmethod
    def create_gradebook_zip(
        results: List[Dict[str, any]], include_markdown: bool = True
    ) -> Optional[BytesIO]:
        """
        Create a zip file containing all successfully downloaded gradebooks.

        Args:
            results: List of download results from download_multiple_gradebooks
            include_markdown: Whether to include markdown files in the zip

        Returns:
            BytesIO: In-memory zip file, or None if no successful downloads
        """
        try:
            # Filter successful results
            successful_results = [r for r in results if r["success"]]

            if not successful_results:
                logger.warning("No successful downloads to zip")
                return None

            logger.info(f"Creating zip file for {len(successful_results)} gradebooks")

            # Create in-memory zip file
            zip_buffer = BytesIO()

            with zipfile.ZipFile(
                zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9
            ) as zip_file:
                for result in successful_results:
                    # Add CSV file (use the actual filename which now has course name + timestamp)
                    if result["csv_path"] and Path(result["csv_path"]).exists():
                        csv_path = Path(result["csv_path"])
                        # Use the filename from the path (already has course name + timestamp)
                        zip_filename = csv_path.name
                        with open(csv_path, "rb") as f:
                            zip_file.writestr(zip_filename, f.read())
                        logger.info(f"Added to zip: {zip_filename}")

                    # Add Markdown file if requested
                    if (
                        include_markdown
                        and result["markdown_path"]
                        and Path(result["markdown_path"]).exists()
                    ):
                        md_path = Path(result["markdown_path"])
                        # Use the filename from the path (already has course name + timestamp)
                        zip_filename = md_path.name
                        with open(md_path, "rb") as f:
                            zip_file.writestr(zip_filename, f.read())
                        logger.info(f"Added to zip: {zip_filename}")

                # Add summary file
                summary_content = GradebookManager._create_download_summary(results)
                zip_file.writestr("_DOWNLOAD_SUMMARY.txt", summary_content)

            # Reset buffer position to beginning
            zip_buffer.seek(0)
            logger.info(
                f"Zip file created successfully ({len(zip_buffer.getvalue()) / 1024:.2f} KB)"
            )

            return zip_buffer

        except Exception as e:
            logger.error(f"Error creating zip file: {e}", exc_info=True)
            return None

    @staticmethod
    def _create_download_summary(results: List[Dict[str, any]]) -> str:
        """Create a text summary of the download operation."""
        lines = [
            "=" * 80,
            "GRADEBOOK DOWNLOAD SUMMARY",
            "=" * 80,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Courses: {len(results)}",
            f"Successful: {sum(1 for r in results if r['success'])}",
            f"Failed: {sum(1 for r in results if not r['success'])}",
            "",
            "=" * 80,
            "COURSE DETAILS",
            "=" * 80,
            "",
        ]

        for idx, result in enumerate(results, 1):
            status = "✓ SUCCESS" if result["success"] else "✗ FAILED"
            lines.append(f"{idx}. {result['course_name']}")
            lines.append(f"   Course ID: {result['course_id']}")
            lines.append(f"   Status: {status}")

            if not result["success"] and result["error"]:
                lines.append(f"   Error: {result['error']}")

            lines.append("")

        lines.extend(
            [
                "=" * 80,
                "END OF SUMMARY",
                "=" * 80,
            ]
        )

        return "\n".join(lines)
