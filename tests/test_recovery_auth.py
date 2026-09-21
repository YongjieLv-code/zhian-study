import copy
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from server import backups, migrations
from server.config import Settings
from server.database import Account, ImportJob, LoginSession, make_engine, now, today
from server.main import create_app
from test_api import log_payload, plan_payload, review_payload

PASSWORD = "Study-test-password-42"


@pytest.fixture
def client(tmp_path):
    app = create_app(f"sqlite:///{(tmp_path / 'v2.db').as_posix()}", Settings(allow_registration=True))
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as instance:
        yield instance


def use_account(client, name, route="register", password=PASSWORD):
    response = client.post(f"/api/auth/{route}", json={"username": name, "password": password})
    assert response.status_code in {200, 201}, response.text
    result = response.json()
    client.headers.update({"X-CSRF-Token": result["csrf_token"], "X-Workspace-ID": result["account"]["id"]})
    return result


def prepare_backup(client):
    plan = client.post("/api/plans", json=plan_payload()).json()
    client.post("/api/logs", json=log_payload(plan_id=plan["id"]))
    card = client.post("/api/reviews", json=review_payload()).json()
    response = client.post(f"/api/reviews/{card['id']}/complete", json={"id": str(uuid4()), "rating": "good", "duration_minutes": 8, "expected_version": 1})
    assert response.status_code == 200
    return client.get("/api/backup").json()


def preview(client, data, mode="merge"):
    return client.post("/api/backups/preview", json={"mode": mode, "backup": data})


def apply(client, job, acknowledged=True):
    return client.post("/api/backups/apply", json={"id": job["id"], "acknowledged": acknowledged})


def test_merge_duplicates_replace_recovery_and_idempotent_receipt(client):
    empty = client.get("/api/backup").json()
    original = prepare_backup(client)
    job = preview(client, original).json()
    assert job["counts"]["logs"] == {"current": 2, "incoming": 2, "new": 0, "duplicate": 2, "conflict": 0}
    assert apply(client, job).status_code == 200
    assert len(client.get("/api/logs").json()) == 2
    job = preview(client, empty, "replace").json()
    assert apply(client, job, False).status_code == 422
    receipt = apply(client, job).json()
    assert client.get("/api/overview").json()["total_minutes"] == 0
    saved = client.get(f"/api/backups/{receipt['backup_id']}/download")
    assert saved.status_code == 200
    assert backups.digest(saved.json()) == backups.digest(original)
    client.post("/api/logs", json=log_payload(title="恢复后新学的内容"))
    assert apply(client, job).json() == receipt
    assert len(client.get("/api/logs").json()) == 1
    restore = preview(client, saved.json(), "replace").json()
    assert apply(client, restore).status_code == 200
    assert backups.digest(client.get("/api/backup").json()) == backups.digest(original)
    assert client.get("/api/overview").json()["today"]["reviews"] == 1
    assert len(client.get("/api/backups/history").json()) == 3


def test_merge_keeps_conflicts_adds_new_records_and_recalculates_plan(client):
    original = prepare_backup(client)
    incoming = copy.deepcopy(original)
    incoming["profile"]["name"] = "导入的名字"
    incoming["logs"][0]["title"] = "旧备份里的同编号内容"
    added = {**incoming["logs"][0], "id": str(uuid4()), "title": "备份独有的练习", "plan_id": None}
    incoming["logs"].append(added)
    job = preview(client, incoming).json()
    assert job["counts"]["logs"]["conflict"] == 1
    assert job["counts"]["logs"]["new"] == 1
    assert job["profile_changed"] is True
    assert apply(client, job).status_code == 200
    actual = client.get("/api/backup").json()
    assert actual["profile"]["name"] == original["profile"]["name"]
    assert len(actual["logs"]) == 3
    assert {row["title"] for row in original["logs"]}.issubset({row["title"] for row in actual["logs"]})


@pytest.mark.parametrize("damage", ["version", "format", "duplicate-id", "missing-subject", "missing-plan", "missing-review", "missing-log", "counts", "essay", "history", "boolean", "uuid", "name", "future", "color", "extra"])
def test_malformed_backups_never_change_learning_data(client, damage):
    original = prepare_backup(client)
    data = copy.deepcopy(original)
    if damage == "version": data["version"] = 2
    elif damage == "format": data["format"] = "different-format"
    elif damage == "duplicate-id": data["logs"].append(copy.deepcopy(data["logs"][0]))
    elif damage == "missing-subject": data["subjects"] = [row for row in data["subjects"] if row["id"] != "data"]
    elif damage == "missing-plan": data["plans"] = []
    elif damage == "missing-review": data["reviews"] = []
    elif damage == "missing-log": data["logs"] = []
    elif damage == "counts": data["logs"][0]["correct_count"] = 5001
    elif damage == "essay": next(row for row in data["logs"] if row["question_count"])["subject_id"] = "essay"
    elif damage == "history": data["reviews"][0]["review_count"] = 3
    elif damage == "boolean": data["logs"][0]["duration_minutes"] = True
    elif damage == "uuid": data["logs"][0]["id"] = "arbitrary"
    elif damage == "name": data["subjects"][0]["name"] = data["subjects"][1]["name"]
    elif damage == "future": data["logs"][0]["study_date"] = str(today() + timedelta(days=1))
    elif damage == "color": data["subjects"][0]["color"] = "url(https://untrusted)"
    elif damage == "extra": data["password_hash"] = "must-not-be-imported"
    result = preview(client, data)
    assert result.status_code == 422, result.text
    assert backups.digest(client.get("/api/backup").json()) == backups.digest(original)
    assert client.get("/api/backups/history").json() == []


def test_preview_expires_and_stale_workspace_rejects_apply(client):
    original = prepare_backup(client)
    job = preview(client, original, "replace").json()
    client.post("/api/logs", json=log_payload())
    assert apply(client, job).status_code == 409
    assert len(client.get("/api/logs").json()) == 3
    job = preview(client, original, "replace").json()
    with Session(client.app.state.engine) as db:
        db.get(ImportJob, job["id"]).expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert apply(client, job).status_code == 409


def test_backup_write_failure_and_database_failure_preserve_existing_data(client, monkeypatch):
    original = prepare_backup(client)
    incoming = copy.deepcopy(original)
    incoming["profile"]["name"] = "恢复的名字"
    job = preview(client, incoming, "replace").json()
    directory = client.app.state.backup_dir
    directory.write_text("a file blocks this directory", encoding="utf-8")
    assert apply(client, job).status_code == 503
    assert backups.digest(client.get("/api/backup").json()) == backups.digest(original)
    directory.unlink()
    def fail_after_delete(db, owner, data):
        from sqlalchemy import delete
        from server.database import ReviewAttempt
        db.execute(delete(ReviewAttempt).where(ReviewAttempt.account_id == owner))
        raise RuntimeError("simulated write failure")
    monkeypatch.setattr(backups, "replace_data", fail_after_delete)
    with pytest.raises(RuntimeError, match="simulated write failure"):
        apply(client, job)
    assert backups.digest(client.get("/api/backup").json()) == backups.digest(original)
    assert client.get("/api/backups/history").json() == []


def test_simultaneous_apply_and_log_retries_are_safe(client):
    original = prepare_backup(client)
    job = preview(client, original).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: apply(client, job), range(2)))
    assert [row.status_code for row in results] == [200, 200]
    assert results[0].json() == results[1].json()
    assert len(client.get("/api/backups/history").json()) == 1
    payload = log_payload()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post("/api/logs", json=payload), range(2)))
    assert [row.status_code for row in results] == [201, 201]
    assert len(client.get("/api/logs").json()) == 3


def test_corrupted_snapshot_is_detected_and_path_is_scoped(client):
    original = prepare_backup(client)
    receipt = apply(client, preview(client, original).json()).json()
    path = next(client.app.state.backup_dir.glob("*.json"))
    path.write_bytes(b"corrupt")
    assert client.get(f"/api/backups/{receipt['backup_id']}/download").status_code == 409
    assert client.get(f"/api/backups/{uuid4()}/download").status_code == 404
    assert client.post("/api/backups/preview", content=b"x" * (backups.MAX_BACKUP_BYTES + 1), headers={"content-type": "application/json"}).status_code == 413


def test_deleting_review_log_retains_history_and_backup_can_roundtrip(client):
    original = prepare_backup(client)
    attempt = original["review_history"][0]
    assert client.delete(f"/api/logs/{attempt['log_id']}").status_code == 204
    result = client.get("/api/overview").json()
    assert result["total_minutes"] == 40 and result["today"]["reviews"] == 1
    history = client.get(f"/api/reviews/{attempt['review_id']}/history").json()
    assert history[0]["log_id"] is None
    updated = client.get("/api/backup").json()
    assert apply(client, preview(client, updated, "replace").json()).status_code == 200


def test_boolean_backup_version_and_mismatched_review_feedback_rejected(client):
    original = prepare_backup(client)
    broken = copy.deepcopy(original)
    broken["version"] = True
    assert preview(client, broken).status_code == 422
    broken = copy.deepcopy(original)
    broken["reviews"][0]["last_rating"] = "again"
    assert preview(client, broken).status_code == 422


def test_account_claims_local_data_hashes_password_and_requires_auth(client):
    original = prepare_backup(client)
    result = use_account(client, "Alice_01")
    assert result["account"] == {"id": "local", "username": "alice_01"}
    assert backups.digest(client.get("/api/backup").json()) == backups.digest(original)
    assert "password" not in client.get("/api/backup").text
    cookie = client.cookies.get("zhian_session")
    with Session(client.app.state.engine) as db:
        account = db.get(Account, "local")
        assert account.password_hash != PASSWORD and account.password_hash.startswith("pbkdf2_sha256$")
        assert db.get(LoginSession, hashlib.sha256(cookie.encode()).hexdigest()) is not None
        assert db.get(LoginSession, cookie) is None
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/workspace").status_code == 401
    for path in ["/profile", "/overview", "/plans", "/logs", "/subjects", "/reviews", "/backup", "/logs/export.csv", "/backups/history"]:
        assert client.get("/api" + path).status_code == 401
    use_account(client, "ALICE_01", "login")
    assert client.get("/api/overview").json()["total_minutes"] == 48


def test_accounts_isolate_ids_queries_relations_history_and_imports(client):
    use_account(client, "alice")
    original = prepare_backup(client)
    job_a = preview(client, original).json()
    receipt_a = apply(client, job_a).json()
    use_account(client, "bob")
    bundle = client.get("/api/workspace", headers={"X-Workspace-ID": client.headers["X-Workspace-ID"]}).json()
    assert bundle["overview"]["total_minutes"] == 0 and len(bundle["subjects"]) == 7
    assert client.get("/api/backups/history").json() == []
    assert apply(client, job_a).status_code == 404
    assert client.get(f"/api/backups/{receipt_a['backup_id']}/download").status_code == 404
    plan = original["plans"][0]
    card = original["reviews"][0]
    record = original["logs"][0]
    assert client.delete(f"/api/plans/{plan['id']}").status_code == 404
    assert client.put(f"/api/plans/{plan['id']}", json=plan_payload()).status_code == 404
    assert client.delete(f"/api/logs/{record['id']}").status_code == 404
    assert client.get(f"/api/reviews/{card['id']}/history").status_code == 404
    assert client.patch(f"/api/reviews/{card['id']}/archive", json={"archived": True}).status_code == 404
    assert client.post("/api/logs", json=log_payload(plan_id=plan["id"])).status_code == 404
    # Explicitly importing A's exported file into B keeps the same IDs without ownership collision.
    job_b = preview(client, original, "replace").json()
    assert apply(client, job_b).status_code == 200
    client.delete(f"/api/plans/{plan['id']}")
    assert all(row["plan_id"] is None for row in client.get("/api/logs").json())
    use_account(client, "alice", "login")
    assert len(client.get("/api/plans").json()) == 1
    assert backups.digest(client.get("/api/backup").json()) == backups.digest(original)


def test_origin_csrf_workspace_guard_session_rotation_and_password_change(client):
    result = use_account(client, "alice")
    assert client.get("/api/backup?workspace_id=another-account").status_code == 409
    assert client.get("/api/logs/export.csv?workspace_id=local").status_code == 200
    assert client.post("/api/logs", json=log_payload(), headers={"X-CSRF-Token": "bad"}).status_code == 403
    assert client.post("/api/logs", json=log_payload(), headers={"X-Workspace-ID": "other"}).status_code == 409
    assert client.post("/api/logs", json=log_payload(), headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}, headers={"Origin": "null"}).status_code == 403
    assert client.get("/api/workspace", headers={"host": "attacker.example"}).status_code == 400
    old_cookie = client.cookies.get("zhian_session")
    changed = client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "Another-study-password-42"})
    assert changed.status_code == 200
    assert "HttpOnly" in changed.headers["set-cookie"] and "SameSite=lax" in changed.headers["set-cookie"]
    assert client.post("/api/logs", json=log_payload()).status_code == 403
    client.headers["X-CSRF-Token"] = changed.json()["csrf_token"]
    assert client.post("/api/logs", json=log_payload()).status_code == 201
    with Session(client.app.state.engine) as db:
        assert db.get(LoginSession, hashlib.sha256(old_cookie.encode()).hexdigest()) is None
    assert client.post("/api/auth/logout").status_code == 204
    assert client.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 401
    use_account(client, "alice", "login", "Another-study-password-42")


def test_login_attempts_throttled_and_expired_sessions_denied(client):
    use_account(client, "alice")
    with Session(client.app.state.engine) as db:
        db.scalar(select(LoginSession)).expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/workspace").status_code == 401
    for _ in range(8):
        assert client.post("/api/auth/login", json={"username": "alice", "password": "wrong-password-42"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 429


def test_remote_first_account_requires_bootstrap_and_registration_defaults_closed(tmp_path):
    settings = Settings(auth_required=True, secure_cookie=True, bootstrap_token="test-only-bootstrap-token", allowed_hosts=["study.example"], allowed_origins=[])
    with TestClient(create_app(f"sqlite:///{(tmp_path / 'remote.db').as_posix()}", settings), base_url="https://study.example", client=("198.51.100.5", 50000)) as client:
        assert client.get("/api/workspace").status_code == 401
        status = client.get("/api/auth/status").json()
        assert status["requires_bootstrap"] is True
        payload = {"username": "alice", "password": PASSWORD}
        assert client.post("/api/auth/register", json=payload).status_code == 403
        result = client.post("/api/auth/register", json={**payload, "bootstrap_token": settings.bootstrap_token})
        assert result.status_code == 201 and "Secure" in result.headers["set-cookie"]
        assert client.get("/api/workspace").status_code == 200
        assert client.post("/api/auth/register", json={"username": "bob", "password": PASSWORD}).status_code == 403


LEGACY_DDL = """
CREATE TABLE profile (id INTEGER PRIMARY KEY, name TEXT NOT NULL, exam_name TEXT NOT NULL, exam_date DATE, daily_goal_minutes INTEGER NOT NULL);
CREATE TABLE subjects (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, color TEXT NOT NULL, position INTEGER NOT NULL);
CREATE TABLE plans (id TEXT PRIMARY KEY, title TEXT NOT NULL, subject_id TEXT NOT NULL REFERENCES subjects(id), scheduled_date DATE NOT NULL, minutes INTEGER NOT NULL, note TEXT NOT NULL, completed BOOLEAN NOT NULL, created_at DATETIME NOT NULL);
CREATE TABLE study_logs (id TEXT PRIMARY KEY, title TEXT NOT NULL, subject_id TEXT NOT NULL REFERENCES subjects(id), study_date DATE NOT NULL, duration_minutes INTEGER NOT NULL, question_count INTEGER NOT NULL, correct_count INTEGER NOT NULL, note TEXT NOT NULL, plan_id TEXT REFERENCES plans(id) ON DELETE SET NULL, created_at DATETIME NOT NULL);
CREATE TABLE review_items (id TEXT PRIMARY KEY, title TEXT NOT NULL, subject_id TEXT NOT NULL REFERENCES subjects(id), note TEXT NOT NULL, source TEXT NOT NULL, due_date DATE NOT NULL, interval_days INTEGER NOT NULL, review_count INTEGER NOT NULL, last_rating TEXT, archived BOOLEAN NOT NULL, version INTEGER NOT NULL, created_at DATETIME NOT NULL);
CREATE TABLE review_attempts (id TEXT PRIMARY KEY, review_id TEXT NOT NULL REFERENCES review_items(id), log_id TEXT REFERENCES study_logs(id) ON DELETE SET NULL, rating TEXT NOT NULL, next_interval_days INTEGER NOT NULL, reviewed_at DATETIME NOT NULL);
"""


def legacy_database(path, data):
    with sqlite3.connect(path) as connection:
        connection.executescript(LEGACY_DDL)
        rows = {"profile": [data["profile"]], **{model.__tablename__: data[key] for key, model in backups.COLLECTIONS.items()}}
        for table, records in rows.items():
            for row in records:
                fields = list(row)
                connection.execute(f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [row[field] for field in fields])


def test_legacy_upgrade_preserves_every_record_and_creates_downloadable_snapshot(client, tmp_path):
    original = prepare_backup(client)
    path = tmp_path / "legacy.db"
    legacy_database(path, original)
    url = f"sqlite:///{path.as_posix()}"
    with TestClient(create_app(url), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as upgraded:
        assert backups.digest(upgraded.get("/api/backup").json()) == backups.digest(original)
        history = upgraded.get("/api/backups/history").json()
        assert len(history) == 1 and history[0]["purpose"] == "before-upgrade"
        assert backups.digest(upgraded.get(f"/api/backups/{history[0]['id']}/download").json()) == backups.digest(original)
        use_account(upgraded, "upgraded_user")
        assert upgraded.get("/api/overview").json()["total_minutes"] == 48
    with TestClient(create_app(url), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as restarted:
        use_account(restarted, "upgraded_user", "login")
        assert backups.digest(restarted.get("/api/backup").json()) == backups.digest(original)
        assert len(restarted.get("/api/backups/history").json()) == 1


def test_upgrade_failure_rolls_back_ddl_and_retains_original_file(client, tmp_path, monkeypatch):
    original = prepare_backup(client)
    path = tmp_path / "rollback.db"
    legacy_database(path, original)
    engine = make_engine(f"sqlite:///{path.as_posix()}")
    def fail(*_args, **_kwargs):
        raise RuntimeError("simulated migration failure")
    monkeypatch.setattr(migrations, "seed", fail)
    with pytest.raises(RuntimeError, match="simulated migration failure"):
        migrations.initialize(engine, tmp_path / "rollback-backups")
    assert "account_id" not in {row["name"] for row in inspect(engine).get_columns("subjects")}
    assert not inspect(engine).has_table("accounts")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM study_logs").fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM review_attempts").fetchone()[0] == 1
    saved = next((tmp_path / "rollback-backups").glob("*.json"))
    assert backups.digest(json.loads(saved.read_text(encoding="utf-8"))) == backups.digest(original)
    engine.dispose()
