import logging
import time
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from app.internal.db import Base, get_db
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, Integer, String, Text


class SyncStatusEnum(str, Enum):
    """Enum for sync status states"""

    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncStatus(Base):
    """SQLAlchemy model for sync status tracking"""

    __tablename__ = "sync_status"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    status = Column(String, nullable=False, default=SyncStatusEnum.IDLE.value)
    started_at = Column(BigInteger, nullable=True)
    completed_at = Column(BigInteger, nullable=True)
    total_scraped = Column(Integer, nullable=False, default=0)
    new_courses = Column(Integer, nullable=False, default=0)
    updated_courses = Column(Integer, nullable=False, default=0)
    existing_courses = Column(Integer, nullable=False, default=0)
    failed_courses = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class SyncStatusModel(BaseModel):
    """Pydantic model for sync status"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    total_scraped: int = 0
    new_courses: int = 0
    updated_courses: int = 0
    existing_courses: int = 0
    failed_courses: int = 0
    error_message: Optional[str] = None
    created_at: int
    updated_at: int

    @property
    def duration_seconds(self) -> Optional[int]:
        """Calculate duration of sync in seconds"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return int(time.time()) - self.started_at
        return None

    @property
    def is_running(self) -> bool:
        """Check if sync is currently running"""
        return self.status == SyncStatusEnum.PROCESSING.value


class SyncStatusTable:
    """Database operations for sync status"""

    def create_sync(self) -> SyncStatusModel:
        """Create a new sync status record"""
        with get_db() as db:
            sync_id = str(uuid4())
            now = int(time.time())

            sync_status = SyncStatus(
                id=sync_id,
                status=SyncStatusEnum.PROCESSING.value,
                started_at=now,
                created_at=now,
                updated_at=now,
            )

            db.add(sync_status)
            db.commit()
            db.refresh(sync_status)

            return SyncStatusModel.model_validate(sync_status)

    def update_sync(
        self,
        sync_id: str,
        status: Optional[str] = None,
        total_scraped: Optional[int] = None,
        new_courses: Optional[int] = None,
        updated_courses: Optional[int] = None,
        existing_courses: Optional[int] = None,
        failed_courses: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[SyncStatusModel]:
        """Update sync status record"""
        with get_db() as db:
            sync_status = db.query(SyncStatus).filter(SyncStatus.id == sync_id).first()

            if not sync_status:
                return None

            # Update fields if provided
            if status is not None:
                sync_status.status = status

                # Set completed_at if status is completed or failed
                if status in [
                    SyncStatusEnum.COMPLETED.value,
                    SyncStatusEnum.FAILED.value,
                ]:
                    sync_status.completed_at = int(time.time())

            if total_scraped is not None:
                sync_status.total_scraped = total_scraped
            if new_courses is not None:
                sync_status.new_courses = new_courses
            if updated_courses is not None:
                sync_status.updated_courses = updated_courses
            if existing_courses is not None:
                sync_status.existing_courses = existing_courses
            if failed_courses is not None:
                sync_status.failed_courses = failed_courses
            if error_message is not None:
                sync_status.error_message = error_message

            sync_status.updated_at = int(time.time())

            db.commit()
            db.refresh(sync_status)

            return SyncStatusModel.model_validate(sync_status)

    def get_sync_by_id(self, sync_id: str) -> Optional[SyncStatusModel]:
        """Get sync status by ID"""
        with get_db() as db:
            sync_status = db.query(SyncStatus).filter(SyncStatus.id == sync_id).first()

            if sync_status:
                return SyncStatusModel.model_validate(sync_status)
            return None

    def get_latest_sync(self) -> Optional[SyncStatusModel]:
        """Get the most recent sync status"""
        with get_db() as db:
            sync_status = (
                db.query(SyncStatus).order_by(SyncStatus.created_at.desc()).first()
            )

            if sync_status:
                return SyncStatusModel.model_validate(sync_status)
            return None

    def get_active_sync(self) -> Optional[SyncStatusModel]:
        """Get currently running sync if any"""
        with get_db() as db:
            sync_status = (
                db.query(SyncStatus)
                .filter(SyncStatus.status == SyncStatusEnum.PROCESSING.value)
                .order_by(SyncStatus.started_at.desc())
                .first()
            )

            if sync_status:
                return SyncStatusModel.model_validate(sync_status)
            return None

    def get_sync_history(self, limit: int = 10) -> list[SyncStatusModel]:
        """Get sync history"""
        with get_db() as db:
            sync_statuses = (
                db.query(SyncStatus)
                .order_by(SyncStatus.created_at.desc())
                .limit(limit)
                .all()
            )

            return [SyncStatusModel.model_validate(s) for s in sync_statuses]


SyncStatuses = SyncStatusTable()
