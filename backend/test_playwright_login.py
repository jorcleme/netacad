#!/usr/bin/env python3
"""
Test script to debug NetAcad login flow with Playwright.
Run this to see what's actually happening during the login process.
"""
import asyncio
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from app.config import NETACAD_INSTRUCTOR_ID, NETACAD_INSTRUCTOR_PASSWORD
from app.utils.course_collector import CourseCollector


async def test_login():
    """Test the login flow with detailed logging."""
    print("=" * 60)
    print("NetAcad Playwright Login Test")
    print("=" * 60)
    print(f"Username: {NETACAD_INSTRUCTOR_ID}")
    print(f"Password: {'*' * len(NETACAD_INSTRUCTOR_PASSWORD)}")
    print("=" * 60)

    # Use headless=False to see what's happening in the browser
    # Set to True for container testing
    collector = CourseCollector(headless=True)

    try:
        async with collector:
            print("\n[1/5] Launching browser...")
            print(f"    Browser launched successfully")

            print("\n[2/5] Navigating to NetAcad...")
            await collector.page.goto(
                "https://www.netacad.com", wait_until="domcontentloaded"
            )
            print(f"    Current URL: {collector.page.url}")

            print("\n[3/5] Looking for login button...")
            await collector._navigate_to_login()
            print(f"    After login click URL: {collector.page.url}")

            print("\n[4/5] Entering credentials...")
            await collector._send_credentials()
            print(f"    After credentials URL: {collector.page.url}")

            print("\n[5/5] Verifying login...")
            # Check if we're on the dashboard
            title = await collector.page.title()
            print(f"    Page title: {title}")

            print("\n" + "=" * 60)
            print("✅ LOGIN SUCCESSFUL!")
            print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print(f"    Final URL: {collector.page.url if collector.page else 'N/A'}")

        # Try to save screenshot
        try:
            if collector.page:
                screenshot_path = "/tmp/netacad_error.png"
                await collector.page.screenshot(path=screenshot_path)
                print(f"    Screenshot saved: {screenshot_path}")
        except:
            pass

        raise


if __name__ == "__main__":
    asyncio.run(test_login())
