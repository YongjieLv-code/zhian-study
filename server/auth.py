import hashlib
import hmac
import ipaddress
import secrets
from dataclasses import dataclass
from datetime import timedelta

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select, update

from .database import Account, AuthThrottle, LOCAL_ACCOUNT, LoginSession, MiniSession, WechatIdentity, now, utc
from .services import seed

COOKIE = "zhian_session"
SESSION_SECONDS = 7 * 24 * 3600
ITERATIONS = 600000


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=10, max_length=128)
    bootstrap_token: str = Field(default="", max_length=256)

    @field_validator("username", mode="before")
    @classmethod
    def normalize(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    encoded = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${encoded}"


def verify_password(password, stored):
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (AttributeError, ValueError):
        return False


def local_request(request):
    try:
        return ipaddress.ip_address(request.client.host).is_loopback and request.url.hostname in {"localhost", "127.0.0.1", "::1"}
    except (ValueError, AttributeError):
        return False


def session_for(db, request):
    # An explicit Authorization header never falls back to a browser cookie.
    # Separate tables prevent a cookie token from being used to bypass CSRF.
    authorization = request.headers.get("authorization")
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer":
            return None
        model = MiniSession
    else:
        token = request.cookies.get(COOKIE)
        model = LoginSession
    if not token or len(token) > 256:
        return None
    row = db.get(model, hashlib.sha256(token.encode()).hexdigest())
    return row if row and utc(row.expires_at) > now() else None


def status(db, request, settings):
    login = session_for(db, request)
    account = db.get(Account, login.account_id) if login else None
    local = db.get(Account, LOCAL_ACCOUNT)
    first = local.username is None
    anonymous = account is None and first and not settings.auth_required and local_request(request) and "authorization" not in request.headers
    return {"account": {"id": account.id, "username": account.username} if account else ({"id": LOCAL_ACCOUNT, "username": None} if anonymous else None),
            "local_mode": anonymous,
            "csrf_token": login.csrf_token if isinstance(login, LoginSession) else None,
            "can_register": (local_request(request) or bool(settings.bootstrap_token)) if first else settings.allow_registration,
            "first_account": first,
            "requires_bootstrap": first and not local_request(request),
            "registration_open": settings.allow_registration}


@dataclass
class Context:
    owner: str
    login: LoginSession | MiniSession | None


def require_context(db, request, settings):
    current = status(db, request, settings)
    if current["account"] is None:
        raise HTTPException(401, "请登录后打开你的学习空间")
    owner = current["account"]["id"]
    login = session_for(db, request) if not current["local_mode"] else None
    workspace = request.headers.get("X-Workspace-ID")
    download_workspace = request.query_params.get("workspace_id")
    if any(value is not None and value != owner for value in (workspace, download_workspace)):
        raise HTTPException(409, "账户已在其他页面切换，请刷新后重试", headers={"X-Zhian-Reason": "workspace-changed"})
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if login and (workspace != owner or (isinstance(login, LoginSession) and
                      not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), login.csrf_token))):
            raise HTTPException(403, "登录状态已更新，请刷新页面后重试", headers={"X-Zhian-Reason": "session-changed"})
        # Every workspace writer shares this lock, including preview/apply and auth changes.
        db.execute(update(Account).where(Account.id == owner).values(revision=Account.revision + 1))
    return Context(owner, login)


def start_session(db, response, account, settings):
    token = secrets.token_urlsafe(32)
    db.execute(delete(LoginSession).where(LoginSession.expires_at < now()))
    login = LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), account_id=account.id,
                         csrf_token=secrets.token_hex(32), expires_at=now() + timedelta(seconds=SESSION_SECONDS))
    db.add(login)
    db.commit()
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=settings.secure_cookie, samesite="lax", path="/")
    return {"account": {"id": account.id, "username": account.username}, "local_mode": False, "csrf_token": login.csrf_token,
            "can_register": settings.allow_registration, "first_account": False, "requires_bootstrap": False,
            "registration_open": settings.allow_registration}


def create_account(db, request, payload, settings):
    # Lock the sentinel account so concurrent first registrations cannot both claim local data.
    db.execute(update(Account).where(Account.id == LOCAL_ACCOUNT).values(revision=Account.revision + 1))
    local = db.get(Account, LOCAL_ACCOUNT, populate_existing=True)
    first = local.username is None
    if first:
        if not local_request(request) and (not settings.bootstrap_token or not hmac.compare_digest(payload.bootstrap_token, settings.bootstrap_token)):
            raise HTTPException(403, "创建首个账户需要在服务所在电脑操作，或输入部署时设置的初始化口令")
    elif not settings.allow_registration:
        raise HTTPException(403, "当前服务未开放新账户注册")
    if db.scalar(select(Account).where(Account.username == payload.username)):
        raise HTTPException(409, "此用户名已被使用")
    account = local if first else Account()
    account.username = payload.username
    account.password_hash = hash_password(payload.password)
    db.add(account)
    db.flush()
    if not first:
        seed(db, account.id)
    return account


def register(db, request, response, payload, settings):
    return start_session(db, response, create_account(db, request, payload, settings), settings)


def throttle(db, request, namespace="login", limit=8):
    key = hashlib.sha256(f"{namespace}:{request.client.host if request.client else 'unknown'}".encode()).hexdigest()
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
        db.execute(insert(AuthThrottle).values(key=key, failures=0, reset_at=now() + timedelta(minutes=15)).on_conflict_do_nothing(index_elements=["key"]))
        row = db.scalar(select(AuthThrottle).where(AuthThrottle.key == key).with_for_update())
    else:
        row = db.get(AuthThrottle, key)
    if row and utc(row.reset_at) <= now():
        row.failures = 0
        row.reset_at = now() + timedelta(minutes=15)
    if row and row.failures >= limit:
        raise HTTPException(429, "尝试次数较多，请 15 分钟后再试", headers={"Retry-After": "900"})
    if row is None:
        row = AuthThrottle(key=key, failures=0, reset_at=now() + timedelta(minutes=15))
        db.add(row)
    return row


def authenticate(db, request, payload):
    attempts = throttle(db, request)
    account = db.scalar(select(Account).where(Account.username == payload.username))
    stored = account.password_hash if account else f"pbkdf2_sha256${ITERATIONS}${'00' * 16}${'00' * 32}"
    if not verify_password(payload.password, stored):
        attempts.failures += 1
        db.commit()
        raise HTTPException(401, "用户名或密码不正确")
    attempts.failures = 0
    return account


def login(db, request, response, payload, settings):
    account = authenticate(db, request, payload)
    previous = session_for(db, request)
    if previous:
        db.delete(previous)
    return start_session(db, response, account, settings)


def mini_identity(db, account, settings):
    bound = db.scalar(select(WechatIdentity).where(WechatIdentity.appid == settings.wechat_appid,
                                                  WechatIdentity.account_id == account.id)) is not None
    return {"account": {"id": account.id, "username": account.username}, "wechat_bound": bound}


def start_mini_session(db, account, settings):
    token = secrets.token_urlsafe(32)
    db.execute(delete(MiniSession).where(MiniSession.expires_at < now()))
    expires = now() + timedelta(seconds=SESSION_SECONDS)
    db.add(MiniSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), account_id=account.id, expires_at=expires))
    result = {**mini_identity(db, account, settings), "access_token": token, "token_type": "Bearer", "expires_at": expires}
    db.commit()
    return result


def change_password(db, request, response, ctx, payload, settings):
    if not ctx.login:
        raise HTTPException(401, "请先创建账户")
    attempts = throttle(db, request)
    account = db.get(Account, ctx.owner)
    if not verify_password(payload.current_password, account.password_hash):
        attempts.failures += 1
        db.commit()
        raise HTTPException(422, "当前密码不正确")
    attempts.failures = 0
    account.password_hash = hash_password(payload.new_password)
    db.execute(delete(LoginSession).where(LoginSession.account_id == ctx.owner))
    db.execute(delete(MiniSession).where(MiniSession.account_id == ctx.owner))
    if isinstance(ctx.login, MiniSession):
        return start_mini_session(db, account, settings)
    return start_session(db, response, account, settings)
