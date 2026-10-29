"""Short-lived browser sessions; API keys exist only in this process's memory."""

from contextvars import ContextVar
from dataclasses import dataclass
from http.cookies import SimpleCookie
import secrets
from time import monotonic

from starlette.exceptions import HTTPException

from app.config import Settings


SESSION_COOKIE = "careerpilot_session"
SESSION_TTL = 8 * 60 * 60
MAX_SESSIONS = 2048
current_session: ContextVar[str] = ContextVar("careerpilot_session", default="system")


@dataclass
class BrowserSession:
    touched: float
    model_settings: Settings | None = None
    default_disabled: bool = False


_sessions: dict[str, BrowserSession] = {}
_attempts: dict[str, list[float]] = {}


def model_settings(default: Settings) -> Settings:
    session = _sessions.get(current_session.get())
    if session is None:
        return default
    if session.model_settings is not None:
        return session.model_settings
    return default.model_copy(update={"qwen_api_key": ""}) if session.default_disabled else default


def save_model_settings(config: Settings) -> None:
    session = _sessions[current_session.get()]
    session.model_settings = config
    session.default_disabled = False


def clear_model_settings() -> None:
    session = _sessions[current_session.get()]
    session.model_settings = None
    session.default_disabled = True


def allow_configuration_attempt(ip: str) -> bool:
    now = monotonic()
    # A modest global map avoids an unbounded attacker-controlled address cache.
    for key, timestamps in list(_attempts.items()):
        if not timestamps or timestamps[-1] <= now - 60:
            _attempts.pop(key, None)
    if len(_attempts) >= MAX_SESSIONS * 2:
        return False
    keys = [f"session:{current_session.get()}", f"ip:{ip}"]
    for key, limit in zip(keys, (6, 20)):
        recent = [stamp for stamp in _attempts.get(key, []) if stamp > now - 60]
        _attempts[key] = recent
        if len(recent) >= limit:
            return False
    for key in keys:
        _attempts[key].append(now)
    return True


class BrowserSessionMiddleware:
    def __init__(self, app, api_prefix: str = "/api/v1", public_paths: tuple[str, ...] = ()):
        self.app = app
        self.configuration_path = f"{api_prefix}/model/configure"
        self.public_paths = frozenset(public_paths)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope.get("method") in {"GET", "HEAD"} and scope.get("path") in self.public_paths:
            async def public_send(message):
                if message["type"] == "http.response.start":
                    message["headers"] = [*message.get("headers", []), (b"cache-control", b"no-store")]
                await send(message)

            return await self.app(scope, receive, public_send)
        now = monotonic()
        for key, session in list(_sessions.items()):
            if session.touched < now - SESSION_TTL:
                _sessions.pop(key, None)
        headers = dict(scope.get("headers", []))
        cookie = SimpleCookie()
        try:
            cookie.load(headers.get(b"cookie", b"").decode("latin-1"))
            supplied = cookie[SESSION_COOKIE].value if SESSION_COOKIE in cookie else ""
        except Exception:
            supplied = ""
        session_id = supplied if supplied in _sessions else secrets.token_urlsafe(32)
        is_new = session_id != supplied
        if is_new:
            if len(_sessions) >= MAX_SESSIONS:
                _sessions.pop(min(_sessions, key=lambda key: _sessions[key].touched))
            _sessions[session_id] = BrowserSession(touched=now)
        _sessions[session_id].touched = now
        token = current_session.set(session_id)

        async def session_send(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                # API responses contain private resumes and must never enter shared caches.
                response_headers.append((b"cache-control", b"no-store"))
                if is_new:
                    secure = scope.get("scheme") == "https" or headers.get(b"x-forwarded-proto") == b"https"
                    value = f"{SESSION_COOKIE}={session_id}; Path=/; Max-Age={SESSION_TTL}; HttpOnly; SameSite=Lax"
                    if secure:
                        value += "; Secure"
                    response_headers.append((b"set-cookie", value.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        received_bytes = 0

        async def bounded_receive():
            nonlocal received_bytes
            message = await receive()
            if scope.get("path") == self.configuration_path:
                received_bytes += len(message.get("body", b""))
                if received_bytes > 4096:
                    raise HTTPException(status_code=413, detail="模型配置请求不能超过 4 KB")
            return message

        try:
            await self.app(scope, bounded_receive, session_send)
        finally:
            current_session.reset(token)
