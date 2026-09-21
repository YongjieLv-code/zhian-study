"""WeChat identity exchange and explicit binding to existing study accounts."""

import hashlib
import secrets
from datetime import timedelta
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, update

from . import auth
from .database import Account, MiniSession, WechatBinding, WechatIdentity, now, utc

BINDING_SECONDS = 300


class WechatCode(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=512)
    purpose: Literal["login", "bind"] = "login"


class BindingCredentials(auth.Credentials):
    binding_token: str = Field(min_length=32, max_length=256)


class VerifyPassword(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)


def enabled(settings):
    return bool(settings.wechat_appid and settings.wechat_secret)


def exchange_code(code, settings):
    if not enabled(settings):
        raise HTTPException(503, "微信登录尚未配置，请先使用知岸账号登录")
    try:
        response = httpx.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={"appid": settings.wechat_appid, "secret": settings.wechat_secret,
                    "js_code": code, "grant_type": "authorization_code"},
            timeout=8.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        # Exception URLs may contain AppSecret: never send them to the client.
        raise HTTPException(503, "暂时无法连接微信登录服务，请稍后重试") from None
    if not isinstance(data, dict):
        raise HTTPException(503, "微信登录服务返回异常，请稍后重试")
    if data.get("errcode") in {40029, 40163}:
        raise HTTPException(400, "微信登录凭证已失效，请重新点击微信登录")
    if data.get("errcode") == 45011:
        raise HTTPException(429, "微信登录操作过于频繁，请稍后重试")
    openid = data.get("openid")
    if data.get("errcode") or not isinstance(openid, str) or not 1 <= len(openid) <= 128:
        raise HTTPException(503, "微信登录暂不可用，请使用知岸账号登录")
    # session_key and unionid are deliberately neither stored nor returned.
    return openid


def wechat_login(db, openid, purpose, settings):
    identity = db.get(WechatIdentity, (settings.wechat_appid, openid))
    if identity and purpose == "login":
        return {"needs_binding": False, **auth.start_mini_session(db, db.get(Account, identity.account_id), settings)}
    db.execute(delete(WechatBinding).where(WechatBinding.expires_at < now()))
    ticket = secrets.token_urlsafe(32)
    expires = now() + timedelta(seconds=BINDING_SECONDS)
    db.add(WechatBinding(token_hash=hashlib.sha256(ticket.encode()).hexdigest(),
                         appid=settings.wechat_appid, openid=openid, expires_at=expires))
    db.commit()
    return {"needs_binding": True, "binding_token": ticket, "expires_at": expires}


def bind_wechat(db, request, payload, settings):
    if not enabled(settings):
        raise HTTPException(503, "微信登录尚未配置")
    account = auth.authenticate(db, request, payload)
    ticket = db.scalar(select(WechatBinding).where(
        WechatBinding.token_hash == hashlib.sha256(payload.binding_token.encode()).hexdigest()).with_for_update())
    if not ticket or utc(ticket.expires_at) <= now() or ticket.appid != settings.wechat_appid:
        raise HTTPException(400, "绑定凭证已失效，请重新获取微信登录凭证")
    db.execute(update(Account).where(Account.id == account.id).values(revision=Account.revision + 1))
    identity = db.get(WechatIdentity, (ticket.appid, ticket.openid))
    account_identity = db.scalar(select(WechatIdentity).where(WechatIdentity.appid == ticket.appid,
                                                            WechatIdentity.account_id == account.id))
    if identity and identity.account_id != account.id:
        raise HTTPException(409, "这个微信已绑定其他知岸账号，请先在原账号解除绑定")
    if account_identity and account_identity.openid != ticket.openid:
        raise HTTPException(409, "此知岸账号已绑定另一个微信，请先解除原绑定")
    if not identity:
        db.add(WechatIdentity(appid=ticket.appid, openid=ticket.openid, account_id=account.id))
    # Consume all outstanding proofs for this identity, including older devices.
    db.execute(delete(WechatBinding).where(WechatBinding.appid == ticket.appid, WechatBinding.openid == ticket.openid))
    return auth.start_mini_session(db, account, settings)


def require_mini(ctx):
    if not isinstance(ctx.login, MiniSession):
        raise HTTPException(401, "请使用小程序账号登录")


def unbind_wechat(db, request, ctx, payload, settings):
    require_mini(ctx)
    account = db.get(Account, ctx.owner)
    attempts = auth.throttle(db, request)
    if not auth.verify_password(payload.current_password, account.password_hash):
        attempts.failures += 1
        db.commit()
        raise HTTPException(422, "当前密码不正确")
    identity = db.scalar(select(WechatIdentity).where(WechatIdentity.appid == settings.wechat_appid,
                                                    WechatIdentity.account_id == ctx.owner))
    if not identity:
        raise HTTPException(404, "此账号尚未绑定微信")
    attempts.failures = 0
    db.execute(delete(WechatBinding).where(WechatBinding.appid == identity.appid, WechatBinding.openid == identity.openid))
    db.delete(identity)
    db.execute(delete(MiniSession).where(MiniSession.account_id == ctx.owner))
    return auth.start_mini_session(db, account, settings)
