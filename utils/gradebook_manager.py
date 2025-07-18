from constants import OPTIMIZED_TIMEOUTS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)
from selenium.webdriver.remote.webelement import WebElement
from typing import Optional
import logging


logger = logging.getLogger(__file__)


class GradebookManager:

    def __init__(
        self,
        browser: webdriver.Chrome,
        course_url: str,
        course_id: str,
        course_name: str,
        worker_id: int = 0,
    ):
        self.browser = browser
        self.course_url = course_url
        self.course_id = course_id
        self.course_name = course_name
        self.worker_id = worker_id

    def click_gradebook_tab(self):
        wait = WebDriverWait(self.browser, OPTIMIZED_TIMEOUTS["element_wait"])
        try:
            tab = wait.until(
                EC.element_to_be_clickable((By.ID, "Launch-tab-gradebook"))
            )
            tab.click()
            return True

        except (NoSuchElementException, TimeoutException) as e:
            return False

    def open_export_dropdown(self):
        wait = WebDriverWait(self.browser, OPTIMIZED_TIMEOUTS["element_wait"])
        try:
            button = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".RBDropdown--ATEd3.dropdown > button")
                )
            )
            button.click()
            return True

        except (NoSuchElementException, TimeoutException) as e:
            return False

    def export_all_grades(self):
        wait = WebDriverWait(self.browser, OPTIMIZED_TIMEOUTS["element_wait"])
        try:
            export_all_button = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".dropdownButton--whS7t:first-of-type")
                )
            )
            export_all_button.click()
            return True
        except (NoSuchElementException, TimeoutException) as e:
            return False
        except ElementClickInterceptedException:
            # If the button is not clickable, scroll into view and try again
            export_all_button = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".dropdownButton--whS7t:first-of-type")
                )
            )
            self.browser.execute_script(
                "arguments[0].scrollIntoView(true);", export_all_button
            )
            self.browser.execute_script("arguments[0].click();", export_all_button)
            return True

    def handle_modal(self):
        try:
            # Test for immediate presence of modal without waiting
            modal_close_button = self.browser.find_element(
                By.CLASS_NAME, "modal__close"
            )
            modal_close_button.click()
            logger.info(f"Worker {self.worker_id} - Modal detected and closed")
            return True
        except NoSuchElementException:
            # No modal present, which is perfectly normal
            return True
        except Exception as e:
            logger.warning(f"Worker {self.worker_id} - Error handling modal: {e}")
            return True

    def refresh_export_list(self):
        wait = WebDriverWait(self.browser, OPTIMIZED_TIMEOUTS["element_wait"])
        try:
            refesh_button = wait.until(
                EC.element_to_be_clickable((By.ID, "refreshExportList"))
            )
            refesh_button.click()
            return True
        except (NoSuchElementException, TimeoutException):
            return False
        except ElementClickInterceptedException:
            # If the button is not clickable, scroll into view and try again
            refesh_button = wait.until(
                EC.presence_of_element_located((By.ID, "refreshExportList"))
            )
            self.browser.execute_script(
                "arguments[0].scrollIntoView(true);", refesh_button
            )
            self.browser.execute_script("arguments[0].click();", refesh_button)
            return True

    def open_refresh_list(self):
        wait = WebDriverWait(self.browser, OPTIMIZED_TIMEOUTS["element_wait"])
        try:
            dropdown = wait.until(EC.element_to_be_clickable((By.ID, "dropdown-basic")))
            dropdown.click()
            return True
        except (NoSuchElementException, TimeoutException):
            return False
        except ElementClickInterceptedException:
            # If the dropdown is not clickable, scroll into view and try again
            dropdown = wait.until(
                EC.presence_of_element_located((By.ID, "dropdown-basic"))
            )
            self.browser.execute_script("arguments[0].scrollIntoView(true);", dropdown)
            self.browser.execute_script("arguments[0].click();", dropdown)
            return True

    def export_gradebook_links(self) -> Optional[WebElement]:
        wait = WebDriverWait(self.browser, OPTIMIZED_TIMEOUTS["element_wait"])
        try:
            export_links = wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, ".dropdown__menu.show a")
                )
            )
            return export_links[0]
        except (NoSuchElementException, TimeoutException):
            return None
