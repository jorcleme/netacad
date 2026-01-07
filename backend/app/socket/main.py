import asyncio
import logging
import sys
import time

import socketio

from app.utils.auth import decode_access_token
from app.models.users import Users

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

sio = socketio.AsyncServer(
    cors_allowed_origins=[],
    async_mode="asgi",
    transports=(["websocket"]),
    allow_upgrades=True,
    always_connect=True,
)

TIMEOUT_DURATION = 3
SESSION_POOL = {}
USER_POOL = {}


app = socketio.ASGIApp(sio, socketio_path="/ws/socket.io")


@sio.event
async def connect(sid: str, environ, auth):
    user = None
    if auth and "token" in auth:
        data = decode_access_token(auth["token"])

        if data is not None and "id" in data:
            user = Users.get_user_by_id(data["id"])

        if user is not None:
            SESSION_POOL[sid] = user.model_dump()
            if user.id in USER_POOL:
                USER_POOL[user.id] = USER_POOL[user.id] + [sid]
            else:
                USER_POOL[user.id] = [sid]

            await sio.emit("user-list", {"user_ids": list(USER_POOL.keys())})


@sio.on("user-join")
async def user_join(sid: str, data: dict):
    auth = data["auth"] if "auth" in data else None
    if not auth or "token" not in auth:
        return

    data = decode_access_token(auth["token"])

    if data is None or "id" not in data:
        return

    user = Users.get_user_by_id(data["id"])
    if not user:
        return

    SESSION_POOL[sid] = user.model_dump()
    if user.id in USER_POOL:
        USER_POOL[user.id] = USER_POOL[user.id] + [sid]
    else:
        USER_POOL[user.id] = [sid]

    await sio.emit("user-list", {"user_ids": list(USER_POOL.keys())})


@sio.on("user-list")
async def user_list(sid: str):
    await sio.emit("user-list", {"user_ids": list(USER_POOL.keys())})


@sio.event
async def disconnect(sid: str):
    if sid in SESSION_POOL:
        user = SESSION_POOL[sid]
        del SESSION_POOL[sid]

        user_id = user["id"]
        USER_POOL[user_id] = [_sid for _sid in USER_POOL[user_id] if _sid != sid]

        if len(USER_POOL[user_id]) == 0:
            del USER_POOL[user_id]

        await sio.emit("user-list", {"user_ids": list(USER_POOL.keys())})
    else:
        pass


def get_active_status_by_user_id(user_id):
    if user_id in USER_POOL:
        return True
    return False


def get_user_id_from_session_pool(sid):
    user = SESSION_POOL.get(sid)
    if user:
        return user["id"]
    return None
