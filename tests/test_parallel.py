#!/usr/bin/env python3
"""
Test script to verify parallel processing functionality.
Run this to test the system without actually scraping gradebooks.
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from course_export import (
    create_optimized_browser,
    login_browser,
    MAX_WORKERS,
    OPTIMIZED_TIMEOUTS,
    validate_setup,
)

# Configure simple logging for test
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def test_browser_creation(worker_id: int) -> dict:
    """Test creating and using a browser instance."""
    browser = None
    try:
        logger.info(f"Worker {worker_id}: Creating browser...")
        start_time = time.time()

        browser = create_optimized_browser(worker_id)
        creation_time = time.time() - start_time

        # Test navigation to a simple page
        browser.get("https://www.google.com")
        navigation_time = time.time() - start_time - creation_time

        total_time = time.time() - start_time

        logger.info(f"Worker {worker_id}: ✅ Success in {total_time:.2f}s")

        return {
            "worker_id": worker_id,
            "success": True,
            "creation_time": creation_time,
            "navigation_time": navigation_time,
            "total_time": total_time,
        }

    except Exception as e:
        logger.error(f"Worker {worker_id}: ❌ Failed - {e}")
        return {"worker_id": worker_id, "success": False, "error": str(e)}
    finally:
        if browser:
            try:
                browser.quit()
            except:
                pass


def test_parallel_processing():
    """Test the parallel processing setup."""
    logger.info("🧪 Testing Parallel Processing Setup")
    logger.info("=" * 50)

    # Check setup
    if not validate_setup():
        logger.error("❌ Setup validation failed!")
        return False

    logger.info(f"⚙️  Configuration:")
    logger.info(f"   - Max Workers: {MAX_WORKERS}")
    logger.info(f"   - Timeouts: {OPTIMIZED_TIMEOUTS}")
    logger.info("")

    # Test parallel browser creation
    start_time = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(test_browser_creation, i): i for i in range(MAX_WORKERS)
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    total_time = time.time() - start_time

    # Analyze results
    successful = [r for r in results if r.get("success", False)]
    failed = [r for r in results if not r.get("success", False)]

    logger.info("📊 Test Results:")
    logger.info(f"   - Total Workers: {len(results)}")
    logger.info(f"   - Successful: {len(successful)}")
    logger.info(f"   - Failed: {len(failed)}")
    logger.info(f"   - Total Time: {total_time:.2f}s")

    if successful:
        avg_time = sum(r["total_time"] for r in successful) / len(successful)
        logger.info(f"   - Average Worker Time: {avg_time:.2f}s")

    if failed:
        logger.warning(f"❌ {len(failed)} workers failed:")
        for f in failed:
            logger.warning(
                f"   - Worker {f['worker_id']}: {f.get('error', 'Unknown error')}"
            )

    logger.info("")

    if len(successful) == MAX_WORKERS:
        logger.info("🎉 All tests passed! Parallel processing is working correctly.")
        logger.info(f"💡 Estimated speedup: {MAX_WORKERS}x for parallel operations")
        return True
    else:
        logger.warning(f"⚠️  Only {len(successful)}/{MAX_WORKERS} workers succeeded.")
        logger.info("💡 Consider reducing MAX_WORKERS if you see failures.")
        return len(successful) > 0


if __name__ == "__main__":
    print("🧪 NetAcad Parallel Processing Test")
    print("=" * 40)
    print("This script tests the parallel processing setup without")
    print("actually scraping gradebooks from NetAcad.")
    print("")

    success = test_parallel_processing()

    print("\n" + "=" * 40)
    if success:
        print("✅ System is ready for parallel gradebook export!")
        print("💡 Run 'python course_export.py' to start the real export.")
    else:
        print("❌ System has issues with parallel processing.")
        print("💡 Check your Chrome installation and system resources.")
        print("💡 Consider reducing MAX_WORKERS in course_export.py")
