#!/usr/bin/env python3
"""
Demo script to show the improved JSON logging and summary features.
"""

import json
from pathlib import Path
from course_export_optimized import (
    save_courses_data_to_json,
    _all_course_results,
    _results_lock,
)


def demo_improved_logging():
    """Demonstrate the improved logging capabilities."""
    print("🧪 Testing Improved Course Export Logging")
    print("=" * 50)

    # Simulate some sample results to show the JSON structure
    sample_results = [
        {
            "success": True,
            "course_id": "test-course-1",
            "course_name": "Sample Success Course",
            "csv_path": "/path/to/success.csv",
            "md_path": "/path/to/success.md",
            "error": None,
        },
        {
            "success": False,
            "course_id": "test-course-2",
            "course_name": "Sample Failed Course",
            "csv_path": "",
            "md_path": "",
            "error": "Download failed - CSV file not found after export",
        },
        {
            "success": False,
            "course_id": "test-course-3",
            "course_name": "Another Failed Course",
            "csv_path": "",
            "md_path": "",
            "error": "No export links found in dropdown",
        },
    ]

    # Add sample results to the global list
    global _all_course_results
    with _results_lock:
        _all_course_results.extend(sample_results)

    print("📝 Generating sample export summary with failures...")
    save_courses_data_to_json()

    # Show what the JSON looks like
    json_path = Path("data/courses_export_summary.json")
    if json_path.exists():
        print(f"\n📄 Sample JSON Summary Structure:")
        print("-" * 30)

        with open(json_path, "r") as f:
            data = json.load(f)

        print("Summary Section:")
        for key, value in data["summary"].items():
            print(f"  {key}: {value}")

        print(f"\nCourse Details ({len(data['courses'])} courses):")
        for course in data["courses"]:
            status = "✅" if course["success"] else "❌"
            print(f"  {status} {course['course_name']} ({course['course_id']})")
            if not course["success"]:
                print(f"      Error: {course.get('error_message', 'Unknown')}")

        print(
            f"\nFailed Courses Summary ({len(data['failed_course_details'])} failures):"
        )
        for failure in data["failed_course_details"]:
            print(f"  ❌ {failure['course_name']}: {failure['error']}")

        print(f"\n📊 Success Rate: {data['summary']['success_rate_percentage']}%")

    else:
        print("❌ JSON file not created")

    print("\n" + "=" * 50)
    print("✅ Improved logging features demonstrated!")
    print("\nKey improvements:")
    print("• ✅ Failed courses now included in JSON summary")
    print("• 🔍 Detailed error messages for each failure")
    print("• 📊 Complete success/failure statistics")
    print("• 📁 Export location information")
    print("• 📅 Timestamp and processing metadata")
    print("• 📄 Additional CSV summary for quick viewing")


if __name__ == "__main__":
    demo_improved_logging()
