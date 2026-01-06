import logging
import uuid
from typing import Optional

from app.internal.db import Base, get_db
from app.models.users import UsersModel, Users

from pydantic import BaseModel
from sqlalchemy import Boolean, Column, String, Text

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

####################
# DB MODEL
####################


class Auth(Base):
    __tablename__ = "auths"

    id = Column(String, primary_key=True)
    email = Column(String)
    password = Column(Text)
    active = Column(Boolean)


class AuthModel(BaseModel):
    id: str
    email: str
    password: str
    active: bool = True


class Token(BaseModel):
    token: str
    token_type: str


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    settings: Optional[dict] = None

    @staticmethod
    def from_user_model(user: UsersModel) -> "UserResponse":
        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            settings=user.settings,
        )


class AuthsTable:
    def insert_new_auth(
        self, email: str, password: str, name: str, oauth_sub: Optional[str] = None
    ) -> Optional[UsersModel]:
        with get_db() as db:
            print(
                f"Inserting new auth for email: {email}, name: {name}, oauth_sub: {oauth_sub}"
            )
            id = str(uuid.uuid4())
            auth = AuthModel(
                **{"id": id, "email": email, "password": password, "active": True}
            )
            result = Auth(**auth.model_dump())
            db.add(result)

            user = Users.insert_new_user(
                id=id, name=name, email=email, oauth_sub=oauth_sub
            )
            print(f"Inserted new user: {user}")
            db.commit()
            db.refresh(result)

            if result and user:
                return user
            else:
                return None


Auths = AuthsTable()
