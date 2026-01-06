import logging
import uuid
import jwt
import base64
import hmac
import hashlib
import requests
import os


from datetime import datetime, timedelta
from pytz import UTC
from typing import Annotated, Optional, Union

from app.models.users import Users, UsersModel
from app.config import SECRET_KEY

from fastapi import BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

logging.getLogger("passlib").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

SESSION_SECRET = SECRET_KEY
ALGORITHM = "HS256"

bearer_security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_http_authorization_credentials(header: Optional[str]):
    if not header:
        return None
    try:
        scheme, credentials = header.split(" ")
        return HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials)
    except Exception as e:
        logger.error(f"Error parsing authorization header: {e}")
        return None


def create_access_token(
    data: dict, expires_delta: Union[timedelta, None] = None
) -> str:
    payload = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
        payload.update({"exp": expire})

    encoded_jwt = jwt.encode(payload, SESSION_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        return None
    except jwt.PyJWTError as e:
        logger.error(f"JWT error: {e}")
        return None


def get_current_user(
    request: Request,
    background_tasks: BackgroundTasks,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_security)
    ],
) -> Optional[UsersModel]:
    token = None

    if credentials:
        token = credentials.credentials

    if token is None and "token" in request.cookies:
        token = request.cookies.get("token")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated"
        )

    try:
        payload = decode_access_token(token)
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    if payload is not None and "id" in payload:
        user = Users.get_user_by_id(payload["id"])
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        else:
            if background_tasks:
                background_tasks.add_task(Users.update_user_last_active_by_id, user.id)
        return user
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
