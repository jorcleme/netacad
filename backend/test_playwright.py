"""Test Playwright installation."""

from playwright.sync_api import sync_playwright


def test_playwright():
    """Test that Playwright can launch a browser."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            print(f"✓ Playwright OK - Browser version: {browser.version}")
            browser.close()
            return True
    except Exception as e:
        print(f"✗ Playwright Error: {e}")
        return False


if __name__ == "__main__":
    success = test_playwright()
    exit(0 if success else 1)
