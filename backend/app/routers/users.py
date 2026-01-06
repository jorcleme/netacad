import logging
from typing import Annotated, Any, Optional, List, Dict

from app.models.auths import Auths
from app.models.users import (
    UsersModel,
    Users,
)


from app.socket.main import get_active_status_by_user_id
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.utils.auth import get_password_hash, get_current_user

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter()


class UserResponse(BaseModel):
    name: str
    profile_image_url: Optional[str] = None
    active: bool = False


@router.get("/", response_model=List[UsersModel])
async def get_all_users(skip: Optional[int] = None, limit: Optional[int] = None):
    """
    Retrieve all users with optional pagination.
    """
    users = Users.get_users(skip=skip, limit=limit)
    return users


@router.get("/user/settings", response_model=Optional[Dict[str, Any]])
async def get_user_settings_by_session_user(
    user: Annotated[UsersModel, Depends(get_current_user)],
):
    user = Users.get_user_by_id(user.id)
    if user:
        return user.settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str, user: Annotated[UsersModel, Depends(get_current_user)]
):

    user = Users.get_user_by_id(user_id)

    if user:
        return UserResponse(
            **{
                "name": user.name,
                "profile_image_url": user.profile_image_url,
                "active": get_active_status_by_user_id(user_id),
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )
