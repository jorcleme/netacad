import re
import uuid
import time
import datetime
import logging
from aiohttp import ClientSession
from typing import Annotated, Optional, List
from app.models.auths import (
    Auths,
    Token,
    UserResponse,
)
from app.models.users import Users, UsersModel


from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from app.config import OAUTH_DISCOVERY_URL
from pydantic import BaseModel
from app.utils.misc import parse_duration
from app.utils.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
)


router = APIRouter()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class SessionUserResponse(Token, UserResponse):
    expires_at: Optional[int] = None
    permissions: Optional[dict] = None


@router.get("/session-user", response_model=SessionUserResponse)
async def get_session_user(
    request: Request,
    response: Response,
    user: Annotated[UsersModel, Depends(get_current_user)],
):
    """
    Get the current session user information along with a new access token.
    """
    expires_delta = parse_duration("7d")
    expires_at = None

    if expires_delta:
        expires_at = int(time.time()) + int(expires_delta.total_seconds())

    token = create_access_token(data={"id": user.id}, expires_delta=expires_delta)

    datetime_expires_at = (
        datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
        if expires_at
        else None
    )

    response.set_cookie(
        key="token", value=token, httponly=True, expires=datetime_expires_at
    )

    return SessionUserResponse(
        token=token,
        token_type="bearer",
        expires_at=expires_at,
        id=user.id,
        name=user.name,
        email=user.email,
        settings=user.settings,
    )


@router.get("/signout")
async def signout(request: Request, response: Response):
    response.delete_cookie("token")

    oauth_id_token = request.cookies.get("oauth_id_token")
    if oauth_id_token:
        try:
            async with ClientSession() as session:
                async with session.get(OAUTH_DISCOVERY_URL) as resp:
                    if resp.status == 200:
                        openid_data = await resp.json()
                        logout_url = openid_data.get("end_session_endpoint")
                        if logout_url:
                            response.delete_cookie("oauth_id_token")
                            return RedirectResponse(
                                headers=response.headers,
                                url=f"{logout_url}?id_token_hint={oauth_id_token}",
                            )
                    else:
                        raise HTTPException(
                            status_code=resp.status,
                            detail="Failed to fetch OpenID configuration",
                        )
        except Exception as e:
            logger.error(f"OpenID signout error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to sign out from the OpenID provider.",
            )

    return {"status": True}
