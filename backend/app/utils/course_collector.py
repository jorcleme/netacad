import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from app.config import (
    NETACAD_BASE_URL,
    NETACAD_INSTRUCTOR_ID,
    NETACAD_INSTRUCTOR_PASSWORD,
)
from app.utils.playwright_config import (
    get_browser_launch_config,
    get_context_config,
    get_playwright_config,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def parse_course_dates(
    date_string: str,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse course date string and return datetime objects for start and end dates.

    Args:
        date_string: Date string in format "Jul 07, 2025  - Jul 08, 2026"

    Returns:
        Tuple of (start_date, end_date) as datetime objects or (None, None) if parsing fails
    """
    try:
        # Remove extra whitespace and split by hyphen
        date_string = date_string.strip()
        if not date_string or "-" not in date_string:
            return None, None

        parts = date_string.split("-")
        if len(parts) != 2:
            return None, None

        start_str = parts[0].strip()
        end_str = parts[1].strip()

        # Parse dates using datetime - format: "Jul 07, 2025"
        start_date = datetime.strptime(start_str, "%b %d, %Y")
        end_date = datetime.strptime(end_str, "%b %d, %Y")

        logger.debug(
            f"Parsed dates: {start_str} -> {start_date}, {end_str} -> {end_date}"
        )
        return start_date, end_date

    except Exception as e:
        logger.warning(f"Failed to parse date string '{date_string}': {e}")
        return None, None


class CourseCollector:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._launch_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_browser()

    async def _launch_browser(self):
        """Launch the browser and create context."""
        from playwright.async_api import async_playwright

        self.playwright = async_playwright()
        self.p = await self.playwright.start()

        self.browser = await self.p.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        # Create context with proper viewport size
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        self.page = await self.context.new_page()

    async def _close_browser(self):
        """Close browser and cleanup resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, "p"):
            await self.p.stop()

    async def _navigate_to_login(self):
        """Navigate to the login page and click the login button."""
        try:
            logger.info("Looking for login button...")
            login_btn = self.page.locator(".loginBtn--lfDa2")

            # Wait for the button to be visible with increased timeout
            await login_btn.wait_for(state="visible", timeout=30000)
            logger.info("Login button found.")

            # Scroll element into view using JavaScript
            await login_btn.evaluate(
                "element => element.scrollIntoView({block: 'center', behavior: 'smooth'})"
            )

            # Wait a moment for scroll to complete
            await self.page.wait_for_timeout(1000)

            # Click the button
            await login_btn.click()
            logger.info("Clicked on the login button.")

            # Wait for the auth page to load
            await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
            logger.info(f"Navigated to: {self.page.url}")

        except Exception as e:
            logger.error(f"Error navigating to login: {e}")
            logger.error(f"Current URL: {self.page.url}")

            # Try to get page title for debugging
            try:
                title = await self.page.title()
                logger.debug(f"Page title: {title}")
            except:
                pass

            raise

    async def _send_credentials(self):
        """
        Send username and password in a two-step process:
        1. Enter username and submit (navigates to password page)
        2. Enter password and submit (logs in)
        """
        USERNAME = (NETACAD_INSTRUCTOR_ID or "").strip()
        PASSWORD = (NETACAD_INSTRUCTOR_PASSWORD or "").strip()

        logger.info(f"[Step 1/3] Entering username: {USERNAME}")

        try:
            # Wait for username field
            username_field = self.page.locator("#username")
            await username_field.wait_for(state="visible", timeout=30000)
            await username_field.fill(USERNAME)
            logger.info("Username entered.")

            # Find the submit button (not an input, it's a button or input[type=submit])
            # Try common selectors for Keycloak login buttons
            submit_btn = self.page.locator("#kc-login")
            await submit_btn.wait_for(state="visible", timeout=10000)

            logger.info("Submitting username form...")
            current_url = self.page.url
            logger.debug(f"URL before submit: {current_url}")

            # Click the button normally (not middle-click!)
            await submit_btn.click()
            logger.info("Submit button clicked.")

            # Wait for navigation to password page
            # The URL might change or stay the same (SPA behavior)
            await self.page.wait_for_timeout(2000)  # Give it time to process

            new_url = self.page.url
            logger.debug(f"URL after submit: {new_url}")
            logger.debug(f"URL changed: {current_url != new_url}")

            # [Step 2/3] Wait for password field to appear
            logger.info("[Step 2/3] Waiting for password field...")
            password_field = self.page.locator("#password")

            try:
                await password_field.wait_for(state="visible", timeout=30000)
                logger.info("Password field found!")
            except Exception as e:
                logger.error(f"Password field did not appear after {30} seconds")
                logger.error(f"Current URL: {self.page.url}")

                # Debug: Take screenshot and check page state
                try:
                    screenshot_path = "/app/backend/data/no_password_field.png"
                    await self.page.screenshot(path=screenshot_path, full_page=True)
                    logger.error(f"Screenshot saved to {screenshot_path}")

                    # Check what inputs are visible
                    inputs = await self.page.locator("input").all()
                    logger.error(f"Found {len(inputs)} input fields:")
                    for i, inp in enumerate(inputs):
                        try:
                            input_type = await inp.get_attribute("type")
                            input_name = await inp.get_attribute("name")
                            input_id = await inp.get_attribute("id")
                            visible = await inp.is_visible()
                            logger.error(
                                f"  Input {i}: type={input_type}, name={input_name}, id={input_id}, visible={visible}"
                            )
                        except:
                            pass

                    # Check for error messages
                    error_selectors = [
                        ".kc-feedback-text",
                        "#input-error",
                        ".alert-error",
                        "[role='alert']",
                    ]
                    for sel in error_selectors:
                        elem = self.page.locator(sel).first
                        if await elem.is_visible():
                            error_text = await elem.text_content()
                            logger.error(f"⚠️  Error message found: {error_text}")
                except:
                    pass

                raise

            # [Step 3/3] Enter password and submit
            logger.info("[Step 3/3] Entering password...")
            await password_field.fill(PASSWORD)
            logger.info("Password entered, submitting...")

            # Submit by pressing Enter or clicking submit button
            await password_field.press("Enter")

            # Wait for successful login by checking for course list element
            logger.info("Waiting for dashboard to load...")
            await self.page.wait_for_selector("a.instance_name--dioD1", timeout=60000)
            logger.info("✓ Login successful! Dashboard loaded.")
            logger.info(f"Final URL: {self.page.url}")

        except Exception as e:
            logger.error(f"❌ Error during authentication: {e}")
            logger.error(f"Current URL: {self.page.url}")
            raise

    async def _collect_page_courses(
        self,
    ) -> Tuple[
        List[str],
        List[str],
        List[str],
        List[Optional[datetime]],
        List[Optional[datetime]],
    ]:
        """Cycles through all pages and collects course URLs, names, and dates."""
        course_ids = []
        course_urls = []
        course_names = []
        start_dates = []
        end_dates = []
        page_num = 0

        while True:
            page_num += 1
            logger.info(f"My Classlist Page {page_num}")

            # Wait for course name anchors to load (only <a> tags, not divs)
            await self.page.wait_for_selector("a.instance_name--dioD1", timeout=15000)

            # Get all course cards on the current page
            # Note: Each card should have the instance_name anchor inside it
            course_cards = await self.page.locator(".instance_card---8hdF").all()

            # If no cards found, try to get courses directly from anchors
            if len(course_cards) == 0:
                logger.warning("No course cards found, trying direct anchor approach")
                # Only select <a> tags with the instance_name class to avoid divs
                course_anchors = await self.page.locator("a.instance_name--dioD1").all()

                for anchor in course_anchors:
                    href = await anchor.get_attribute("href")
                    text = await anchor.text_content()

                    if href and text:
                        course_ids.append(href.split("=")[1].strip())
                        course_urls.append(f"{NETACAD_BASE_URL}{href}")
                        course_names.append(text.strip())

                        # Try to find date in parent elements using specific selector
                        try:
                            parent = anchor.locator(
                                "xpath=ancestor::div[contains(@class, 'instance_card')]"
                            )
                            # Use the more specific selector that includes the column block class
                            date_element = parent.locator(
                                ".ins_col_block--EK\\+mW .text-weight-300"
                            )
                            if await date_element.count() > 0:
                                date_string = await date_element.first.text_content()
                                date_string = date_string.strip() if date_string else ""
                                start_date, end_date = parse_course_dates(date_string)
                            else:
                                start_date, end_date = None, None
                        except Exception as e:
                            logger.warning(
                                f"Could not extract date for course {text}: {e}"
                            )
                            start_date, end_date = None, None

                        start_dates.append(start_date)
                        end_dates.append(end_date)
                        logger.debug(f"Course: {text.strip()}")
            else:
                # Process cards normally
                for card in course_cards:
                    # Get course name and URL from the anchor (only select <a> tags to avoid divs)
                    anchor = card.locator("a.instance_name--dioD1")

                    # Check if anchor exists (skip cards without links)
                    if await anchor.count() == 0:
                        continue

                    href = await anchor.get_attribute("href")
                    text = (
                        await anchor.text_content()
                        or await anchor.get_attribute("title")
                        or ""
                    )

                    # Get the date string from the date element (more specific selector)
                    date_element = card.locator(
                        ".ins_col_block--EK\\+mW .text-weight-300"
                    )
                    date_string = ""

                    try:
                        if await date_element.count() > 0:
                            # Get the first matching element (the date element)
                            date_string = await date_element.first.text_content()
                            date_string = date_string.strip() if date_string else ""
                    except Exception as e:
                        logger.warning(f"Could not extract date for course {text}: {e}")
                        date_string = ""

                    if href and text:
                        course_ids.append(href.split("=")[1].strip())
                        course_urls.append(f"{NETACAD_BASE_URL}{href}")
                        course_names.append(text.strip())

                        # Parse the dates
                        start_date, end_date = parse_course_dates(date_string)
                        start_dates.append(start_date)
                        end_dates.append(end_date)

                        logger.debug(f"Course: {text.strip()}, Dates: {date_string}")

            # Try to find and click the next button
            try:
                next_button = self.page.locator(
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
                    await self.page.wait_for_selector(
                        "a.instance_name--dioD1", timeout=10000
                    )
                else:
                    logger.info("No next button found. Exiting pagination loop.")
                    break

            except Exception as e:
                logger.info(f"Pagination complete or error: {e}")
                break

        logger.info(f"Total course names collected: {len(course_names)}")
        logger.info(f"Total course URLs collected: {len(course_urls)}")
        logger.info(
            f"Total courses with dates: {sum(1 for d in start_dates if d is not None)}"
        )
        return course_ids, course_urls, course_names, start_dates, end_dates

    async def collect_courses(
        self,
    ) -> Tuple[
        List[str],
        List[str],
        List[str],
        List[Optional[datetime]],
        List[Optional[datetime]],
    ]:
        """Main method to collect all course data."""
        try:
            logger.info("Navigating to netacad.com...")
            # Use domcontentloaded instead of networkidle for faster, more reliable loading
            await self.page.goto(
                NETACAD_BASE_URL, wait_until="domcontentloaded", timeout=30000
            )
            await self._navigate_to_login()
            await self._send_credentials()

            return await self._collect_page_courses()

        except Exception as e:
            logger.error(f"Error in course collection: {e}", exc_info=True)
            return [], [], [], [], []


# Convenience function for backward compatibility
async def get_course_data(
    headless: bool = False,
) -> Tuple[
    List[str], List[str], List[str], List[Optional[datetime]], List[Optional[datetime]]
]:
    """
    Convenience function to collect course data.

    Args:
        headless: Whether to run browser in headless mode

    Returns:
        Tuple of (course_ids, course_urls, course_names, start_dates, end_dates)
        where start_dates and end_dates are datetime objects
    """
    async with CourseCollector(headless=headless) as collector:
        return await collector.collect_courses()
