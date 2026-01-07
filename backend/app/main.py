import logging
import mimetypes
import os
import sys
import time
from contextlib import asynccontextmanager

from app.config import APP_DIR, FRONTEND_BUILD_DIR, SECRET_KEY, STATIC_DIR, VERSION
from app.internal.db import Session
from app.routers import auths, courses, users
from app.utils.auth import get_http_authorization_credentials
from app.utils.oauth import OAuthManager
from app.socket.main import app as socket_app
from fastapi import FastAPI, HTTPException, Request, Response, applications, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print(
    rf"""NETACAD GRADEBOOK MANAGER

v{VERSION} - NETACAD GRADEBOOK MANAGER.
https://github.com/cisco-des/netacad-gradebook-manager-ui
"""
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


class SPAStaticFiles(StaticFiles):
    """Serve a Single Page Application (SPA) from static files."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (HTTPException, StarletteHTTPException) as exc:
            if exc.status_code == 404:
                if path.endswith(".js"):
                    raise exc
                else:
                    return await super().get_response("index.html", scope)
            else:
                raise exc


app = FastAPI(
    title="netacad-gradebook-manager",
    version="0.0.1",
    lifespan=lifespan,
    docs_url="/docs",
)

oauth_manager = OAuthManager(app)

origins = [
    "http://localhost:8000",
    "http://localhost:5173",  # Vite dev server
    "https://netacad.cisco.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # Important for file downloads
)


@app.middleware("http")
async def commit_session_after_request(request: Request, call_next):
    response = await call_next(request)
    Session.commit()
    return response


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = int(time.time())
    request.state.token = get_http_authorization_credentials(
        request.headers.get("Authorization")
    )
    response = await call_next(request)
    process_time = int(time.time()) - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.middleware("http")
async def inspect_websocket(request: Request, call_next):
    if (
        "/ws/socket.io" in request.url.path
        and request.query_params.get("transport") == "websocket"
    ):
        upgrade = (request.headers.get("Upgrade") or "").lower()
        connection = (request.headers.get("Connection") or "").lower().split(",")
        # Check that there's the correct headers for an upgrade, else reject the connection
        # This is to work around this upstream issue: https://github.com/miguelgrinberg/python-engineio/issues/367
        if upgrade != "websocket" or "upgrade" not in connection:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid WebSocket upgrade request"},
            )
    return await call_next(request)


app.add_middleware(
    SessionMiddleware, secret_key=SECRET_KEY, session_cookie="session", https_only=False
)

app.mount("/ws", socket_app)
app.include_router(courses.router, prefix="/api/v1/courses", tags=["Courses"])
app.include_router(auths.router, prefix="/api/v1/auths", tags=["Auths"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health", tags=["Health"])
async def healthcheck():
    return {"status": "ok"}


@app.get("/oauth/oidc/login", tags=["OAuth", "auth", "login"])
async def oauth_login(request: Request):
    return await oauth_manager.handle_login(request)


@app.get("/oauth/oidc/callback", tags=["OAuth"])
async def oauth_callback(request: Request):
    return await oauth_manager.handle_callback(request)


def swagger_ui_html_custom(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
        swagger_favicon_url="/static/swagger-ui/favicon.png",
    )


applications.get_swagger_ui_html = swagger_ui_html_custom


if os.path.exists(FRONTEND_BUILD_DIR):
    mimetypes.add_type("text/javascript", ".js")
    app.mount("/", SPAStaticFiles(directory=FRONTEND_BUILD_DIR, html=True), name="spa")
    logger.info(f"SPAStaticFiles mounted from {FRONTEND_BUILD_DIR}")
else:
    logger.warning(
        f"Frontend build directory {FRONTEND_BUILD_DIR} does not exist. Serving API only."
    )
