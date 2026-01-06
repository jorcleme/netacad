import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

from app.models.courses import CourseModel, Courses
from app.models.sync_status import SyncStatusEnum, SyncStatuses, SyncStatusModel
from app.utils.course_collector import CourseCollector
from app.utils.course_gradebook import GradebookManager
from app.utils.tasks import sync_courses_background
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()


class AllCoursesResponse(BaseModel):
    """Response model for getting all courses"""

    courses: List[CourseModel]
    total: int
    skip: int
    limit: int
    has_more: bool


class SyncResponse(BaseModel):
    """Response model for sync operation"""

    message: str
    status: str = "processing"


class SyncResult(BaseModel):
    """Result model for completed sync"""

    total_scraped: int
    new_courses: int
    existing_courses: int
    updated_courses: int
    failed_courses: int = 0


@router.get("/", response_model=AllCoursesResponse)
async def get_all_courses(
    skip: int = 0, limit: int = 100, status: Optional[str] = None
):
    """
    Get all courses from the database.
    Fast response - returns cached data from DB.

    Query Parameters:
    - skip: Number of records to skip (pagination)
    - limit: Maximum number of records to return
    - status: Filter by course status (e.g., 'active', 'inactive')
    """
    try:
        courses = Courses.get_all_courses(skip=skip, limit=limit, status=status)
        total = Courses.get_course_count(status=status)

        return {
            "courses": [course.model_dump() for course in courses],
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + len(courses)) < total,
        }
    except Exception as e:
        logger.error(f"Error fetching courses from DB: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch courses from database",
        )


@router.post("/sync", response_model=Dict[str, Any])
async def sync_courses_from_netacad(background_tasks: BackgroundTasks):
    """
    Trigger a background sync of courses from NetAcad.
    This endpoint returns immediately while the sync runs in the background.

    Use this when:
    - New courses may have been added to NetAcad
    - You want to refresh the course list
    - Initial setup/seeding of the database

    Returns:
        sync_id: ID to track the sync progress
        message: Confirmation message
        status: Current status (processing)
    """
    try:
        # Check if there's already a sync running
        active_sync = SyncStatuses.get_active_sync()
        if active_sync:
            return {
                "sync_id": active_sync.id,
                "message": "A sync is already in progress",
                "status": active_sync.status,
                "started_at": active_sync.started_at,
            }

        # Create new sync status record
        sync_status = SyncStatuses.create_sync()

        # Add the sync task to background tasks with sync_id
        background_tasks.add_task(sync_courses_background, sync_status.id)

        logger.info(f"Course sync task queued successfully (ID: {sync_status.id})")

        return {
            "sync_id": sync_status.id,
            "message": "Course sync started. This may take a few minutes.",
            "status": sync_status.status,
            "started_at": sync_status.started_at,
        }

    except Exception as e:
        logger.error(f"Error queuing course sync: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start course sync",
        )


@router.get("/sync/status", response_model=SyncStatusModel)
async def get_sync_status(sync_id: Optional[str] = None):
    """
    Get the status of a sync operation.

    Query Parameters:
    - sync_id: Specific sync ID to check (optional, defaults to latest)

    Returns sync status with:
    - status: idle/processing/completed/failed
    - statistics: courses scraped, added, updated
    - duration: time taken for sync
    """
    try:
        if sync_id:
            # Get specific sync by ID
            sync_status = SyncStatuses.get_sync_by_id(sync_id)
            if not sync_status:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Sync with ID {sync_id} not found",
                )
        else:
            # Get latest sync
            sync_status = SyncStatuses.get_latest_sync()
            if not sync_status:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No sync records found",
                )

        return sync_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching sync status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch sync status",
        )


@router.get("/sync/history", response_model=List[SyncStatusModel])
async def get_sync_history(limit: int = 10):
    """
    Get history of sync operations.

    Query Parameters:
    - limit: Number of recent syncs to return (default: 10)

    Returns list of sync records ordered by most recent first.
    """
    try:
        history = SyncStatuses.get_sync_history(limit=limit)
        return history

    except Exception as e:
        logger.error(f"Error fetching sync history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch sync history",
        )


class GradebookDownloadRequest(BaseModel):
    """Request model for gradebook downloads"""

    course_id: str
    course_name: str
    course_url: str


class BulkGradebookDownloadRequest(BaseModel):
    """Request model for bulk gradebook downloads"""

    courses: List[GradebookDownloadRequest]


class GradebookDownloadResponse(BaseModel):
    """Response model for gradebook download"""

    success: bool
    course_id: str
    course_name: str
    csv_path: Optional[str] = None
    markdown_path: Optional[str] = None
    error: Optional[str] = None


@router.post("/gradebook/download")
async def download_gradebook(request: GradebookDownloadRequest):
    """
    Download gradebook data for a single course.

    This endpoint:
    1. Logs into NetAcad (if needed)
    2. Navigates to the course
    3. Exports the gradebook
    4. Processes and saves both CSV and Markdown formats
    5. Returns the CSV file as a download

    Returns the CSV file as a downloadable attachment.
    """
    try:
        logger.info(f"Gradebook download requested for: {request.course_name}")

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
            )

            # Create context with downloads enabled
            context = await browser.new_context(
                accept_downloads=True,
                viewport={"width": 1920, "height": 1080},
            )

            # Create page
            page = await context.new_page()

            try:
                # Create gradebook manager
                manager = GradebookManager(page=page, headless=True)

                # Download gradebook
                result = await manager.download_gradebook(
                    course_id=request.course_id,
                    course_name=request.course_name,
                    course_url=request.course_url,
                )

                # If successful, return the CSV file as a download
                if result["success"] and result["csv_path"]:
                    csv_path = Path(result["csv_path"])

                    if not csv_path.exists():
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="Gradebook file not found after download",
                        )

                    # Extract filename from path
                    filename = csv_path.name

                    # Return file as download
                    return FileResponse(
                        path=str(csv_path),
                        media_type="text/csv",
                        filename=filename,
                        headers={
                            "Content-Disposition": f'attachment; filename="{filename}"'
                        },
                    )
                else:
                    # Download failed
                    error_msg = result.get("error", "Unknown error occurred")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Gradebook download failed: {error_msg}",
                    )

            finally:
                await context.close()
                await browser.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading gradebook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download gradebook: {str(e)}",
        )


@router.post("/gradebook/download/bulk")
async def download_multiple_gradebooks(request: BulkGradebookDownloadRequest):
    """
    Download gradebooks for multiple courses as a zip file.

    This endpoint:
    1. Logs into NetAcad once
    2. Downloads gradebooks for each course sequentially
    3. Creates a zip file with all gradebooks (CSV and Markdown)
    4. Returns the zip file for download

    Returns a zip file containing all gradebook CSVs, Markdown files, and a summary.
    """
    try:
        logger.info(
            f"Bulk gradebook download requested for {len(request.courses)} courses"
        )

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
            )

            # Create context
            context = await browser.new_context(
                accept_downloads=True,
                viewport={"width": 1920, "height": 1080},
            )

            # Create page
            page = await context.new_page()

            try:
                # Create gradebook manager
                manager = GradebookManager(page=page, headless=True)

                # Convert request courses to dict format
                courses = [
                    {
                        "course_id": c.course_id,
                        "course_name": c.course_name,
                        "course_url": c.course_url,
                    }
                    for c in request.courses
                ]

                # Download all gradebooks
                results = await manager.download_multiple_gradebooks(courses)

                # Create zip file
                zip_buffer = GradebookManager.create_gradebook_zip(
                    results, include_markdown=True
                )

                if not zip_buffer:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create zip file - no successful downloads",
                    )

                # Generate filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"netacad_gradebooks_{timestamp}.zip"

                # Return zip file as streaming response
                return StreamingResponse(
                    zip_buffer,
                    media_type="application/zip",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"'
                    },
                )

            finally:
                await context.close()
                await browser.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading gradebooks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download gradebooks: {str(e)}",
        )


@router.get("/gradebook/file/{file_type}/{filename}")
async def get_gradebook_file(file_type: str, filename: str):
    """
    Retrieve a downloaded gradebook file.

    Path Parameters:
    - file_type: Type of file ('csv' or 'markdown')
    - filename: Name of the file to retrieve

    Returns the file for download.
    """
    try:
        from app.config import DATA_DIR

        # Construct file path based on type
        if file_type == "csv":
            file_path = DATA_DIR / "gradebooks" / "csv" / filename
        elif file_type == "markdown":
            file_path = DATA_DIR / "gradebooks" / "markdown" / filename
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Must be 'csv' or 'markdown'",
            )

        # Check if file exists
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {filename}",
            )

        # Return file
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/octet-stream",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving gradebook file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve gradebook file",
        )
