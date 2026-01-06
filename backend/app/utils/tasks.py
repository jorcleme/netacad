import logging

from app.models.courses import Courses
from app.models.sync_status import SyncStatusEnum, SyncStatuses
from app.utils.course_collector import CourseCollector

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def sync_courses_background(sync_id: str):
    """
    Background task to scrape NetAcad courses and sync with database.
    This runs independently and doesn't block the API response.

    Args:
        sync_id: The ID of the sync status record to update
    """
    failed_course_count = 0

    try:
        logger.info(f"Starting background course sync (ID: {sync_id})")

        # Scrape courses from NetAcad
        async with CourseCollector(headless=True) as collector:
            course_ids, course_urls, course_names, start_dates, end_dates = (
                await collector.collect_courses()
            )

        logger.info(f"Scraped {len(course_ids)} courses from NetAcad")

        # Track sync statistics
        new_courses = []
        existing_courses = []
        updated_courses = []

        # Process each scraped course
        for course_id, url, name, start_date, end_date in zip(
            course_ids, course_urls, course_names, start_dates, end_dates
        ):
            try:
                # Check if course already exists in DB
                existing_course = Courses.get_course_by_course_id(course_id)

                if existing_course:
                    # Course exists - check if we need to update it
                    # Note: We're not comparing dates here as they may change frequently
                    # Always update to ensure we have the latest date information
                    updated_course = Courses.update_course(
                        course_id=course_id,
                        name=name,
                        url=url,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    if updated_course:
                        updated_courses.append(course_id)
                        logger.info(f"Updated course: {course_id} - {name}")
                    else:
                        existing_courses.append(course_id)
                else:
                    # New course - insert into database
                    new_course = Courses.insert_new_course(
                        course_id=course_id,
                        name=name,
                        url=url,
                        status="active",
                        start_date=start_date,
                        end_date=end_date,
                    )
                    if new_course:
                        new_courses.append(course_id)
                        logger.info(f"Added new course: {course_id} - {name}")

            except Exception as e:
                logger.error(f"Error processing course {course_id}: {e}", exc_info=True)
                failed_course_count += 1
                continue

        logger.info(
            f"Sync complete - Total: {len(course_ids)}, "
            f"New: {len(new_courses)}, "
            f"Existing: {len(existing_courses)}, "
            f"Updated: {len(updated_courses)}, "
            f"Failed: {failed_course_count}"
        )

        # Update sync status to completed
        SyncStatuses.update_sync(
            sync_id=sync_id,
            status=SyncStatusEnum.COMPLETED.value,
            total_scraped=len(course_ids),
            new_courses=len(new_courses),
            updated_courses=len(updated_courses),
            existing_courses=len(existing_courses),
            failed_courses=failed_course_count,
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in background course sync: {error_msg}", exc_info=True)

        # Update sync status to failed
        SyncStatuses.update_sync(
            sync_id=sync_id,
            status=SyncStatusEnum.FAILED.value,
            error_message=error_msg,
            failed_courses=failed_course_count,
        )
