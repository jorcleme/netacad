import logging
import sys
import uuid

from app.config import (
    OAUTH_CLIENT_ID,
    OAUTH_CLIENT_SECRET,
    OAUTH_DISCOVERY_URL,
    OAUTH_PROVIDER_NAME,
    OAUTH_SCOPES,
)
from app.models.auths import Auths
from app.models.users import User, Users, UsersModel
from app.utils.auth import create_access_token, get_password_hash
from app.utils.misc import parse_duration
from authlib.integrations.starlette_client import OAuth
from authlib.oidc.core import UserInfo
from fastapi import FastAPI, HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class OAuthManager:
    def __init__(self, app: FastAPI):
        self.oauth = OAuth()
        self.app = app
        self.oauth.register(
            name="oidc",
            client_id=OAUTH_CLIENT_ID,
            client_secret=OAUTH_CLIENT_SECRET,
            server_metadata_url=OAUTH_DISCOVERY_URL,
            client_kwargs={"scope": OAUTH_SCOPES},
        )

    def get_client(self):
        return self.oauth.create_client("oidc")

    async def handle_login(self, request: Request):
        redirect_uri = request.url_for("oauth_callback")
        client = self.get_client()
        if client is None:
            logger.error("OAuth client not found or registered incorrectly.")
            raise HTTPException(status_code=500, detail="OAuth client not configured.")
        return await client.authorize_redirect(request, redirect_uri)

    async def handle_callback(self, request: Request):
        client = self.get_client()
        try:
            token = await client.authorize_access_token(request)
        except Exception as e:
            logger.error(f"Error during OAuth callback: {e}")
            raise HTTPException(status_code=400, detail="OAuth authorization failed.")

        user_info: UserInfo = token.get("userinfo")
        access_token = token.get("access_token")

        if not user_info or "email" not in user_info:
            user_info: UserInfo = await client.userinfo(token=token)

        if not user_info:
            logger.warning(f"Failed to fetch user info with token: {token}")
            raise HTTPException(status_code=400, detail="Failed to fetch user info.")

        sub = user_info.get("sub")
        if not sub:
            logger.warning(f"User info missing 'sub' field: {user_info}")
            raise HTTPException(status_code=400, detail="Invalid user info received.")
        provider_sub = f"oidc:{sub}"
        email = user_info.get("email", "")
        email = email.lower()
        print("UserInfo: ", user_info)
        print(f"Access Token: {access_token}")

        # Try to find user by OAuth sub
        user = Users.get_user_by_oauth_sub(provider_sub)
        print(f"User by OAuth sub: {user}")

        # If not found, try to find by email and update OAuth sub
        if not user:
            user = Users.get_user_by_email(email)
            if user:
                print(f"Found user by email, updating OAuth sub: {user}")
                Users.update_user_oauth_sub_by_id(user.id, provider_sub)

        # If still no user, create a new one
        if not user:
            print(f"No existing user found, creating new user for email: {email}")

            name = user_info.get("fullname")
            if not name:
                firstname = user_info.get("firstname", "")
                lastname = user_info.get("lastname", "")
                name = f"{firstname} {lastname}".strip()

            if not name:
                name = email

            print(f"Creating user with name: {name}")

            try:
                # Generate a random password for OAuth users (they won't use it)
                # bcrypt has a 72 byte limit, so we truncate the UUID string
                random_password = str(uuid.uuid4())[:60]  # Safe length before hashing

                user = Auths.insert_new_auth(
                    email=email,
                    password="",
                    name=name,
                    oauth_sub=provider_sub,
                )
                print(f"User created successfully: {user}")
            except Exception as e:
                logger.error(f"Failed to create user: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500, detail=f"Failed to create user account: {str(e)}"
                )

        if not user:
            logger.error("User is still None after all attempts to find/create")
            raise HTTPException(
                status_code=500, detail="Failed to get or create user account"
            )

        print(f"Final user object: {user}")
        print(f"User ID: {user.id}")

        jwt_token = create_access_token(
            data={"id": user.id}, expires_delta=parse_duration("7d")
        )

        print(f"JWT token created: {jwt_token[:50]}...")

        redirect_url = f"{request.base_url}login#token={jwt_token}"
        print(f"Redirecting to: {redirect_url}")

        redirect_response = RedirectResponse(url=redirect_url)
        redirect_response.set_cookie(key="token", value=jwt_token, httponly=True)
        redirect_response.set_cookie(
            key="oauth_id_token", value=access_token, httponly=True
        )

        return redirect_response
