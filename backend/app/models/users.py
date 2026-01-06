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


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String)
    email = Column(String, unique=True, nullable=False)
    settings = Column(JSONField, nullable=True)
    oauth_sub = Column(Text, unique=True, nullable=True)
    last_active_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class UsersModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    settings: Optional[Dict[str, Any]] = None
    oauth_sub: Optional[str] = None
    last_active_at: Optional[int] = None
    created_at: int
    updated_at: int


class UsersTable:
    def insert_new_user(
        self, id: str, name: str, email: str, oauth_sub: Optional[str] = None
    ) -> Optional[UsersModel]:
        with get_db() as db:
            user = UsersModel(
                **{
                    "id": id,
                    "name": name,
                    "email": email,
                    "oauth_sub": oauth_sub,
                    "last_active_at": int(time.time()),
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )
            result = User(**user.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)
            if result:
                return user
            else:
                return None

    def get_user_by_id(self, id: str) -> Optional[UsersModel]:
        with get_db() as db:
            user = db.query(User).filter(User.id == id).first()
            if user:
                return UsersModel.model_validate(user)
            else:
                return None

    def get_user_by_email(self, email: str) -> Optional[UsersModel]:
        with get_db() as db:
            user = db.query(User).filter(User.email == email).first()
            if user:
                return UsersModel.model_validate(user)
            else:
                return None

    def get_user_by_oauth_sub(self, oauth_sub: str) -> Optional[UsersModel]:
        with get_db() as db:
            user = db.query(User).filter(User.oauth_sub == oauth_sub).first()
            if user:
                return UsersModel.model_validate(user)
            else:
                return None

    def get_users(
        self, skip: Optional[int] = None, limit: Optional[int] = None
    ) -> List[UsersModel]:
        with get_db() as db:

            query = db.query(User).order_by(User.created_at.desc())

            if skip:
                query = query.offset(skip)

            if limit:
                query = query.limit(limit)

            users = query.all()
            return [UsersModel.model_validate(user) for user in users]

    def get_users_by_ids(self, ids: List[str]) -> List[UsersModel]:
        with get_db() as db:
            users = db.query(User).filter(User.id.in_(ids)).all()
            return [UsersModel.model_validate(user) for user in users]

    def update_user_by_id(
        self,
        id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Optional[UsersModel]:
        try:
            with get_db() as db:
                update_data = {"updated_at": int(time.time())}
                if name is not None:
                    update_data["name"] = name
                if email is not None:
                    update_data["email"] = email
                if settings is not None:
                    update_data["settings"] = settings

                db.query(User).filter_by(id=id).update(update_data)
                db.commit()
                user = db.query(User).filter(User.id == id).first()
                if user:
                    return UsersModel.model_validate(user)
                else:
                    return None
        except Exception as e:
            logging.error(f"Error updating user: {e}")
            return None

    def update_user_oauth_sub_by_id(self, id: str, oauth_sub: str) -> None:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update(
                    {"oauth_sub": oauth_sub, "updated_at": int(time.time())}
                )
                db.commit()
                user = db.query(User).filter(User.id == id).first()
                if user:
                    return UsersModel.model_validate(user)
                else:
                    return None
        except Exception as e:
            logging.error(f"Error updating user oauth_sub: {e}")
            return None

    def update_user_settings_by_id(
        self, id: str, settings: Dict[str, Any]
    ) -> Optional[UsersModel]:
        try:
            with get_db() as db:
                user_settings = db.query(User).filter_by(id=id).first().settings

                if user_settings is None:
                    user_settings = {}

                user_settings.update(settings)

                db.query(User).filter_by(id=id).update(
                    {"settings": user_settings, "updated_at": int(time.time())}
                )
                db.commit()
                user = db.query(User).filter(User.id == id).first()
                if user:
                    return UsersModel.model_validate(user)
                else:
                    return None
        except Exception as e:
            logging.error(f"Error updating user settings: {e}")
            return None

    def update_user_last_active_by_id(self, id: str) -> Optional[UsersModel]:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update(
                    {"last_active_at": int(time.time())}
                )
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UsersModel.model_validate(user)
        except Exception:
            return None


Users = UsersTable()
