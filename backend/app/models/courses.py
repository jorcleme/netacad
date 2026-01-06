import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.internal.db import Base, JSONField, get_db
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.orm import relationship


class Course(Base):
    __tablename__ = "courses"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    course_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=True)
    status = Column(String, nullable=True, default="active")
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class CourseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str
    name: str
    url: Optional[str]
    status: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: int
    updated_at: int


class CourseTable:

    def insert_new_course(
        self,
        *,
        course_id: str,
        name: str,
        url: str,
        status: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> CourseModel:
        with get_db() as db:

            id = str(uuid4())
            course = CourseModel(
                **{
                    "id": id,
                    "course_id": course_id,
                    "name": name,
                    "url": url,
                    "status": status,
                    "start_date": start_date,
                    "end_date": end_date,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )

            result = Course(**course.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)

            if result:
                return CourseModel.model_validate(result)
            else:
                return None

    def insert_bulk_courses(self, courses: List[Dict[str, Any]]) -> List[CourseModel]:
        try:
            with get_db() as db:
                course_models = []
                for course_data in courses:
                    id = str(uuid4())
                    course = CourseModel(
                        **{
                            "id": id,
                            "course_id": course_data["course_id"],
                            "name": course_data["name"],
                            "url": course_data["url"],
                            "status": course_data.get("status", "inactive"),
                            "start_date": course_data.get("start_date"),
                            "end_date": course_data.get("end_date"),
                            "created_at": int(time.time()),
                            "updated_at": int(time.time()),
                        }
                    )
                    course_models.append(course)

                result = [Course(**course.model_dump()) for course in course_models]
                db.bulk_save_objects(result)
                db.commit()

                return [CourseModel.model_validate(r) for r in result]
        except Exception as e:
            logging.error(f"Error inserting bulk courses: {e}")
            return []

    def get_course_by_id(self, id: str) -> Optional[CourseModel]:
        with get_db() as db:
            result = db.query(Course).filter(Course.id == id).first()
            if result:
                return CourseModel.model_validate(result)
            else:
                return None

    def get_course_by_course_id(self, course_id: str) -> Optional[CourseModel]:
        with get_db() as db:
            result = db.query(Course).filter(Course.course_id == course_id).first()
            if result:
                return CourseModel.model_validate(result)
            else:
                return None

    def get_all_courses(
        self, skip: int = 0, limit: int = 100, status: Optional[str] = None
    ) -> List[CourseModel]:
        """
        Get all courses with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Filter by course status (optional)

        Returns:
            List of CourseModel objects
        """
        with get_db() as db:
            query = db.query(Course)

            # Apply status filter if provided
            if status:
                query = query.filter(Course.status == status)

            # Apply pagination
            results = query.offset(skip).limit(limit).all()

            return [CourseModel.model_validate(r) for r in results]

    def update_course(
        self,
        course_id: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[CourseModel]:
        """
        Update an existing course.

        Args:
            course_id: The course_id to update
            name: New name (optional)
            url: New URL (optional)
            status: New status (optional)
            start_date: New start date as datetime object (optional)
            end_date: New end date as datetime object (optional)

        Returns:
            Updated CourseModel or None if not found
        """
        with get_db() as db:
            result = db.query(Course).filter(Course.course_id == course_id).first()

            if not result:
                return None

            # Update fields if provided
            if name is not None:
                result.name = name
            if url is not None:
                result.url = url
            if status is not None:
                result.status = status
            if start_date is not None:
                result.start_date = start_date
            if end_date is not None:
                result.end_date = end_date

            # Update timestamp
            result.updated_at = int(time.time())

            db.commit()
            db.refresh(result)

            return CourseModel.model_validate(result)

    def get_course_count(self, status: Optional[str] = None) -> int:
        """
        Get total count of courses, optionally filtered by status.

        Args:
            status: Filter by course status (optional)

        Returns:
            Total count of courses
        """
        with get_db() as db:
            query = db.query(Course)

            if status:
                query = query.filter(Course.status == status)

            return query.count()


Courses = CourseTable()
