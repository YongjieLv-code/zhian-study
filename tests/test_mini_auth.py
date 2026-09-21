import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from server import auth, backups, mini_auth
from server.config import Settings
from server.database import Account, MiniSession, WechatBinding, WechatIdentity, now
from server.main import create_app
from test_api import log_payload, plan_payload, review_payload

PASSWORD = "Study-mini-test-42"


@pytest.fixture
def client(tmp_path):
    settings = Settings(allow_registration=True, wechat_appid="wx-test-app", wechat_secret="server-only-test-secret")
    app = create_app(f"sqlite:///{(tmp_path / 'mini.db').as_posix()}", settings)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as instance:
        yield instance


def credentials(name="alice", password=PASSWORD):
    return {"username": name, "password": password}


def create_mini(client, name="alice"):
    result = client.post("/api/mini/auth/register", json=credentials(name))
    assert result.status_code == 201, result.text
    assert "set-cookie" not in result.headers
    return result.json()


def headers(session):
    return {"Authorization": f"Bearer {session['access_token']}", "X-Workspace-ID": session["account"]["id"]}


def proof(client, monkeypatch, openid="openid-alice", purpose="login"):
    monkeypatch.setattr(mini_auth, "exchange_code", lambda code, settings: openid)
    result = client.post("/api/mini/auth/wechat", json={"code": "one-use-wechat-code", "purpose": purpose})
    assert result.status_code == 200, result.text
    assert "openid" not in result.text and "session_key" not in result.text
    return result.json()


def bind(client, ticket, name="alice", password=PASSWORD):
    return client.post("/api/mini/auth/wechat/bind", json={**credentials(name, password), "binding_token": ticket["binding_token"]})


def test_mini_and_web_share_learning_records_without_changing_cookie(client):
    original = client.post("/api/logs", json=log_payload(title="网页已有的记录")).json()
    browser = client.post("/api/auth/register", json=credentials()).json()
    cookie = client.cookies.get(auth.COOKIE)
    response = client.post("/api/mini/auth/login", json=credentials())
    assert response.status_code == 200 and "set-cookie" not in response.headers
    mini = response.json()
    assert "csrf_token" not in mini
    assert client.cookies.get(auth.COOKIE) == cookie
    assert mini["account"] == browser["account"]
    assert client.get("/api/workspace", headers=headers(mini)).json()["logs"][0]["id"] == original["id"]
    plan = client.post("/api/plans", headers=headers(mini), json=plan_payload()).json()
    payload = log_payload(plan_id=plan["id"], title="手机完成的学习")
    for _ in range(2):
        assert client.post("/api/logs", headers=headers(mini), json=payload).status_code == 201
    web_workspace = client.get("/api/workspace").json()
    assert len(web_workspace["logs"]) == 2
    assert web_workspace["plans"][0]["completed"] is True
    assert web_workspace["overview"]["today"]["minutes"] == original["duration_minutes"] + payload["duration_minutes"]
    with Session(client.app.state.engine) as db:
        token = mini["access_token"]
        assert db.get(MiniSession, token) is None
        assert db.get(MiniSession, hashlib.sha256(token.encode()).hexdigest()) is not None


def test_bearer_and_cookie_sessions_are_not_interchangeable(client):
    client.post("/api/auth/register", json=credentials())
    cookie = client.cookies.get(auth.COOKIE)
    mini = client.post("/api/mini/auth/login", json=credentials()).json()
    assert client.get("/api/mini/auth/session").status_code == 401
    assert client.get("/api/overview", headers={"Authorization": f"Bearer {cookie}"}).status_code == 401
    assert client.post("/api/logs", json=log_payload()).status_code == 403
    client.cookies.clear()
    client.cookies.set(auth.COOKIE, mini["access_token"])
    assert client.get("/api/overview").status_code == 401
    assert client.get("/api/overview", headers=headers(mini)).status_code == 200


@pytest.mark.parametrize("authorization", ["", "Basic random", "Bearer bad-token", "Bearer ", "Bearer " + "a" * 257])
def test_invalid_authorization_never_falls_back_to_local_or_cookie(client, authorization):
    assert client.get("/api/overview", headers={"Authorization": authorization}).status_code == 401
    client.post("/api/auth/register", json=credentials())
    assert client.get("/api/overview", headers={"Authorization": authorization}).status_code == 401
    assert client.get("/api/overview").status_code == 200


def test_mini_workspace_isolation_and_write_guard(client):
    alice = create_mini(client)
    bob = create_mini(client, "bob")
    plan = client.post("/api/plans", headers=headers(alice), json=plan_payload()).json()
    saved = client.post("/api/logs", headers=headers(alice), json=log_payload()).json()
    assert client.get("/api/logs", headers=headers(bob)).json() == []
    assert client.get("/api/backup", headers=headers(bob)).json()["logs"] == []
    assert client.delete(f"/api/logs/{saved['id']}", headers=headers(bob)).status_code == 404
    assert client.post("/api/logs", headers=headers(bob), json=log_payload(plan_id=plan["id"])).status_code == 404
    assert client.post("/api/logs", headers={"Authorization": headers(alice)["Authorization"]}, json=log_payload()).status_code == 403
    wrong = {**headers(alice), "X-Workspace-ID": bob["account"]["id"]}
    assert client.get("/api/workspace", headers=wrong).status_code == 409
    assert client.post("/api/logs", headers={**headers(alice), "Origin": "https://untrusted.invalid"}, json=log_payload()).status_code == 403


def test_registration_rules_also_apply_to_mini_program(tmp_path):
    app = create_app(f"sqlite:///{(tmp_path / 'remote.db').as_posix()}", Settings(auth_required=True, allowed_hosts=["study.example.com"], bootstrap_token="initialize-only-on-server"))
    with TestClient(app, base_url="https://study.example.com", client=("192.0.2.10", 50000)) as client:
        assert client.get("/api/mini/auth/config").json()["requires_bootstrap"] is True
        assert client.post("/api/mini/auth/register", json=credentials()).status_code == 403
        result = client.post("/api/mini/auth/register", json={**credentials(), "bootstrap_token": "initialize-only-on-server"})
        assert result.status_code == 201
        assert result.json()["account"]["id"] == "local"
        assert client.post("/api/mini/auth/register", json=credentials("bob")).status_code == 403


def test_mini_login_throttling_is_shared_with_web(client):
    create_mini(client)
    for _ in range(8):
        assert client.post("/api/mini/auth/login", json=credentials(password="incorrect-password")).status_code == 401
    assert client.post("/api/mini/auth/login", json=credentials()).status_code == 429
    assert client.post("/api/auth/login", json=credentials()).status_code == 429


def test_mini_expiry_and_logout_revoke_tokens(client):
    mini = create_mini(client)
    assert client.post("/api/mini/auth/logout", headers=headers(mini)).status_code == 204
    assert client.get("/api/workspace", headers=headers(mini)).status_code == 401
    mini = client.post("/api/mini/auth/login", json=credentials()).json()
    with Session(client.app.state.engine) as db:
        db.get(MiniSession, hashlib.sha256(mini["access_token"].encode()).hexdigest()).expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/workspace", headers=headers(mini)).status_code == 401


@pytest.mark.parametrize("platform", ["web", "mini"])
def test_password_change_revokes_both_platform_sessions(client, platform):
    mini = create_mini(client)
    browser = client.post("/api/auth/login", json=credentials()).json()
    web_headers = {"X-CSRF-Token": browser["csrf_token"], "X-Workspace-ID": browser["account"]["id"]}
    cookie = client.cookies.get(auth.COOKIE)
    route = "/api/mini/auth/password" if platform == "mini" else "/api/auth/password"
    changed = client.post(route, headers=headers(mini) if platform == "mini" else web_headers,
                          json={"current_password": PASSWORD, "new_password": "changed-password-42"})
    assert changed.status_code == 200, changed.text
    assert client.get("/api/workspace", headers=headers(mini)).status_code == 401
    if platform == "mini":
        assert "set-cookie" not in changed.headers
        assert client.get("/api/workspace").status_code == 401
        assert client.get("/api/workspace", headers=headers(changed.json())).status_code == 200
    else:
        assert client.cookies.get(auth.COOKIE) != cookie
        assert client.get("/api/workspace").status_code == 200
    assert client.post("/api/mini/auth/login", json=credentials()).status_code == 401


def test_wechat_binding_requires_password_preserves_data_and_consumes_ticket(client, monkeypatch):
    mini = create_mini(client)
    client.post("/api/logs", headers=headers(mini), json=log_payload())
    before = client.get("/api/backup", headers=headers(mini)).json()
    ticket = proof(client, monkeypatch)
    assert ticket["needs_binding"] is True and "access_token" not in ticket
    with Session(client.app.state.engine) as db:
        assert db.get(WechatBinding, ticket["binding_token"]) is None
    assert bind(client, ticket, password="wrong-password-42").status_code == 401
    result = bind(client, ticket)
    assert result.status_code == 200 and result.json()["wechat_bound"] is True
    assert backups.digest(client.get("/api/backup", headers=headers(result.json())).json()) == backups.digest(before)
    assert bind(client, ticket).status_code == 400
    logged_in = proof(client, monkeypatch)
    assert logged_in["needs_binding"] is False
    assert logged_in["account"] == mini["account"]
    assert "server-only-test-secret" not in str(logged_in)


def test_wechat_identity_cannot_rebind_another_account_or_replace_existing_wechat(client, monkeypatch):
    create_mini(client)
    create_mini(client, "bob")
    assert bind(client, proof(client, monkeypatch)).status_code == 200
    same_wechat = proof(client, monkeypatch, purpose="bind")
    assert bind(client, same_wechat, "bob").status_code == 409
    other_wechat = proof(client, monkeypatch, "another-openid")
    assert bind(client, other_wechat).status_code == 409
    with Session(client.app.state.engine) as db:
        identities = db.scalars(select(WechatIdentity)).all()
        assert len(identities) == 1 and identities[0].account_id == "local"


def test_wechat_proofs_expire_and_are_scoped_to_appid(client, monkeypatch):
    create_mini(client)
    ticket = proof(client, monkeypatch)
    with Session(client.app.state.engine) as db:
        db.get(WechatBinding, hashlib.sha256(ticket["binding_token"].encode()).hexdigest()).expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert bind(client, ticket).status_code == 400
    ticket = proof(client, monkeypatch)
    client.app.state.settings.wechat_appid = "another-app"
    assert bind(client, ticket).status_code == 400


def test_wechat_unbinding_revokes_mobile_sessions_and_outstanding_proofs(client, monkeypatch):
    original = create_mini(client)
    bound = bind(client, proof(client, monkeypatch)).json()
    outstanding = proof(client, monkeypatch, purpose="bind")
    assert client.post("/api/mini/auth/wechat/unbind", headers=headers(bound), json={"current_password": "wrong-password-42"}).status_code == 422
    result = client.post("/api/mini/auth/wechat/unbind", headers=headers(bound), json={"current_password": PASSWORD})
    assert result.status_code == 200 and result.json()["wechat_bound"] is False
    assert client.get("/api/mini/auth/session", headers=headers(original)).status_code == 401
    assert client.get("/api/mini/auth/session", headers=headers(bound)).status_code == 401
    assert client.get("/api/mini/auth/session", headers=headers(result.json())).status_code == 200
    assert bind(client, outstanding).status_code == 400
    assert proof(client, monkeypatch)["needs_binding"] is True


def test_concurrent_binding_consumes_proof_once(client, monkeypatch):
    create_mini(client)
    ticket = proof(client, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: bind(client, ticket), range(2)))
    assert sorted(result.status_code for result in results) == [200, 400]


def test_wechat_network_exchange_does_not_hold_workspace_write_lock(client, monkeypatch):
    def exchange(code, settings):
        with client.app.state.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            connection.rollback()
        return "openid-without-lock"
    monkeypatch.setattr(mini_auth, "exchange_code", exchange)
    assert client.post("/api/mini/auth/wechat", json={"code": "test-code"}).status_code == 200


def test_wechat_rate_limit_and_disabled_configuration(client, monkeypatch):
    monkeypatch.setattr(mini_auth, "exchange_code", lambda code, settings: "openid-rate-limit")
    for _ in range(30):
        assert client.post("/api/mini/auth/wechat", json={"code": "test-code"}).status_code == 200
    assert client.post("/api/mini/auth/wechat", json={"code": "test-code"}).status_code == 429
    client.app.state.settings.wechat_secret = ""
    assert client.get("/api/mini/auth/config").json()["wechat_enabled"] is False
    assert client.post("/api/mini/auth/wechat", json={"code": "test-code"}).status_code == 503


@pytest.mark.parametrize("data, status", [({"errcode": 40029}, 400), ({"errcode": 40163}, 400), ({"errcode": 45011}, 429), ({"errcode": 40013, "errmsg": "private-configuration-detail"}, 503), ({"session_key": "private-session"}, 503), ([], 503)])
def test_wechat_exchange_rejects_upstream_errors_without_leaking_details(monkeypatch, data, status):
    response = httpx.Response(200, json=data, request=httpx.Request("GET", "https://api.weixin.qq.com/sns/jscode2session"))
    monkeypatch.setattr(mini_auth.httpx, "get", lambda *args, **kwargs: response)
    with pytest.raises(HTTPException) as caught:
        mini_auth.exchange_code("code", Settings(wechat_appid="wx-test", wechat_secret="private-secret"))
    assert caught.value.status_code == status
    assert "private-" not in caught.value.detail


def test_wechat_exchange_keeps_credentials_server_side_and_has_timeout(monkeypatch):
    captured = {}
    def get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, json={"openid": "openid-result", "session_key": "private-session", "unionid": "unused-union"}, request=httpx.Request("GET", url))
    monkeypatch.setattr(mini_auth.httpx, "get", get)
    assert mini_auth.exchange_code("temporary-code", Settings(wechat_appid="wx-test", wechat_secret="private-secret")) == "openid-result"
    assert captured["url"] == "https://api.weixin.qq.com/sns/jscode2session"
    assert captured["params"] == {"appid": "wx-test", "secret": "private-secret", "js_code": "temporary-code", "grant_type": "authorization_code"}
    assert captured["timeout"] == 8.0 and captured["follow_redirects"] is False
    def fail(*args, **kwargs):
        raise httpx.ConnectTimeout("https://example.invalid?secret=private-secret")
    monkeypatch.setattr(mini_auth.httpx, "get", fail)
    with pytest.raises(HTTPException) as caught:
        mini_auth.exchange_code("temporary-code", Settings(wechat_appid="wx-test", wechat_secret="private-secret"))
    assert caught.value.status_code == 503 and "private-secret" not in caught.value.detail


def test_wechat_compatible_archive_route_keeps_ownership_checks(client):
    mini = create_mini(client)
    card = client.post("/api/reviews", headers=headers(mini), json=review_payload()).json()
    archived = client.post(f"/api/reviews/{card['id']}/archive", headers=headers(mini), json={"archived": True})
    assert archived.status_code == 200 and archived.json()["archived"] is True
    bob = create_mini(client, "bob")
    assert client.post(f"/api/reviews/{card['id']}/archive", headers=headers(bob), json={"archived": False}).status_code == 404
