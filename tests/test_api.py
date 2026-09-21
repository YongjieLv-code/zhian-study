from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from server.database import today
from server.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(f"sqlite:///{(tmp_path / 'test.db').as_posix()}"), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as instance:
        yield instance


def log_payload(**overrides):
    return {"id": str(uuid4()), "title": "比重变化专项练习", "subject_id": "data",
            "study_date": str(today()), "duration_minutes": 40,
            "question_count": 20, "correct_count": 16, "note": "先比较部分与整体增长率", **overrides}


def plan_payload(**overrides):
    return {"title": "比重变化专项练习", "subject_id": "data", "scheduled_date": str(today()), "minutes": 30, **overrides}


def review_payload(**overrides):
    return {"title": "比重变化如何判断", "subject_id": "data", "due_date": str(today()), "note": "先回忆再验证", **overrides}


def test_clean_first_launch_has_real_empty_statistics(client):
    result = client.get("/api/overview").json()
    assert result["today"]["minutes"] == result["streak"] == result["total_days"] == 0
    assert result["days_until_exam"] is None
    assert len(client.get("/api/subjects").json()) == 7
    assert client.get("/api/logs").json() == []
    assert client.get("/api/health").json()["mode"] == "account-ready"


def test_plan_record_checkin_review_transaction_and_retry(client):
    plan = client.post("/api/plans", json=plan_payload()).json()
    payload = log_payload(plan_id=plan["id"], add_to_review=True)
    assert client.post("/api/logs", json=payload).status_code == 201
    assert client.post("/api/logs", json=payload).status_code == 201
    result = client.get("/api/overview").json()
    assert result["today"]["minutes"] == 40
    assert result["today"]["questions"] == 20
    assert result["today"]["correct"] == 16
    assert result["streak"] == result["total_days"] == 1
    assert client.get("/api/plans").json()[0]["completed"] is True
    assert len(client.get("/api/logs").json()) == 1
    cards = client.get("/api/reviews").json()
    assert len(cards) == 1
    assert cards[0]["due_date"] == str(today() + timedelta(days=1))
    assert client.delete(f"/api/logs/{payload['id']}").status_code == 204
    assert client.get("/api/plans").json()[0]["completed"] is False
    assert client.get("/api/overview").json()["streak"] == 0


@pytest.mark.parametrize("override", [
    {"correct_count": 21}, {"duration_minutes": 0}, {"duration_minutes": -1},
    {"duration_minutes": 1441}, {"question_count": -1}, {"title": "   "},
    {"study_date": str(today() + timedelta(days=1))}, {"subject_id": "not-a-subject"},
    {"id": "bad-id"}, {"subject_id": "essay", "question_count": 5, "correct_count": 2},
])
def test_invalid_learning_records_are_rejected_without_writes(client, override):
    assert client.post("/api/logs", json=log_payload(**override)).status_code == 422
    assert client.get("/api/logs").json() == []


def test_essay_record_keeps_feedback_out_of_accuracy(client):
    response = client.post("/api/logs", json=log_payload(subject_id="essay", question_count=0, correct_count=0, note="对策需要明确实施主体"))
    assert response.status_code == 201
    result = client.get("/api/overview").json()
    assert result["today"]["minutes"] == 40
    assert result["today"]["questions"] == 0
    assert client.get("/api/logs").json()[0]["note"] == "对策需要明确实施主体"


def test_backfilled_dates_determine_streak_not_creation_date(client):
    for offset in [-3, -2, -1]:
        client.post("/api/logs", json=log_payload(study_date=str(today() + timedelta(days=offset))))
    result = client.get("/api/overview").json()
    assert result["streak"] == 3
    assert result["today"]["minutes"] == 0
    client.post("/api/logs", json=log_payload())
    client.post("/api/logs", json=log_payload())
    result = client.get("/api/overview").json()
    assert result["streak"] == result["total_days"] == 4
    assert result["today"]["minutes"] == 80


def test_edit_record_recalculates_totals_and_days(client):
    payload = log_payload()
    client.post("/api/logs", json=payload)
    payload.update(duration_minutes=65, study_date=str(today() - timedelta(days=3)), correct_count=12)
    assert client.put(f"/api/logs/{payload['id']}", json=payload).status_code == 200
    result = client.get("/api/overview").json()
    assert result["today"]["minutes"] == 0
    assert result["total_minutes"] == 65
    assert result["streak"] == 0
    assert result["total_days"] == 1


def test_reusing_submission_id_with_changed_content_does_not_silently_discard_changes(client):
    payload = log_payload()
    client.post("/api/logs", json=payload)
    payload["duration_minutes"] = 75
    assert client.post("/api/logs", json=payload).status_code == 409
    assert client.get("/api/overview").json()["total_minutes"] == 40


def test_plan_subject_must_match_and_completed_plan_preserves_original(client):
    plan = client.post("/api/plans", json=plan_payload()).json()
    assert client.post("/api/logs", json=log_payload(plan_id=plan["id"], subject_id="math")).status_code == 422
    client.post("/api/logs", json=log_payload(plan_id=plan["id"]))
    assert client.put(f"/api/plans/{plan['id']}", json=plan_payload(minutes=55)).status_code == 409


def test_delete_plan_preserves_its_learning_records(client):
    plan = client.post("/api/plans", json=plan_payload()).json()
    client.post("/api/logs", json=log_payload(plan_id=plan["id"]))
    assert client.delete(f"/api/plans/{plan['id']}").status_code == 204
    records = client.get("/api/logs").json()
    assert len(records) == 1 and records[0]["plan_id"] is None
    assert client.get("/api/overview").json()["total_minutes"] == 40


@pytest.mark.parametrize("rating, interval", [("again", 1), ("hard", 1), ("good", 3), ("easy", 7)])
def test_review_scheduling_history_and_idempotent_retry(client, rating, interval):
    card = client.post("/api/reviews", json=review_payload()).json()
    payload = {"id": str(uuid4()), "rating": rating, "duration_minutes": 8, "expected_version": card["version"]}
    response = client.post(f"/api/reviews/{card['id']}/complete", json=payload)
    assert response.status_code == 200
    assert response.json()["due_date"] == str(today() + timedelta(days=interval))
    assert response.json()["review_count"] == 1
    assert client.post(f"/api/reviews/{card['id']}/complete", json=payload).status_code == 200
    assert len(client.get("/api/logs").json()) == 1
    history = client.get(f"/api/reviews/{card['id']}/history").json()
    assert len(history) == 1 and history[0]["rating"] == rating
    result = client.get("/api/overview").json()
    assert result["today"]["minutes"] == 8
    assert result["today"]["reviews"] == 1
    assert result["review_due"] == 0
    payload["id"] = str(uuid4())
    assert client.post(f"/api/reviews/{card['id']}/complete", json=payload).status_code == 409


def test_stale_review_submission_is_rejected_atomically(client):
    card = client.post("/api/reviews", json=review_payload()).json()
    client.put(f"/api/reviews/{card['id']}", json=review_payload(note="已更新笔记"))
    payload = {"id": str(uuid4()), "rating": "good", "duration_minutes": 6, "expected_version": 1}
    assert client.post(f"/api/reviews/{card['id']}/complete", json=payload).status_code == 409
    assert client.get("/api/logs").json() == []
    assert client.get("/api/reviews").json()[0]["review_count"] == 0


def test_archive_and_restore_preserve_card(client):
    card = client.post("/api/reviews", json=review_payload()).json()
    assert client.get("/api/overview").json()["review_due"] == 1
    client.patch(f"/api/reviews/{card['id']}/archive", json={"archived": True})
    assert client.get("/api/overview").json()["review_due"] == 0
    assert client.get("/api/reviews").json()[0]["archived"] is True
    client.patch(f"/api/reviews/{card['id']}/archive", json={"archived": False})
    assert client.get("/api/overview").json()["review_due"] == 1


def test_profile_custom_subject_and_exports(client):
    profile = {"name": "小知", "exam_name": "我的省考目标", "exam_date": str(today() + timedelta(days=75)), "daily_goal_minutes": 180}
    assert client.put("/api/profile", json=profile).status_code == 200
    assert client.get("/api/overview").json()["days_until_exam"] == 75
    subject = client.post("/api/subjects", json={"name": "面试训练", "kind": "essay"})
    assert subject.status_code == 201
    assert client.post("/api/subjects", json={"name": "面试训练", "kind": "essay"}).status_code == 409
    payload = log_payload(title="=1+1", note="中文心得，含逗号\n第二行")
    client.post("/api/logs", json=payload)
    backup = client.get("/api/backup")
    assert backup.status_code == 200
    assert "attachment" in backup.headers["content-disposition"]
    assert backup.json()["format"] == "zhian-backup"
    assert backup.json()["logs"][0]["note"] == payload["note"]
    csv = client.get("/api/logs/export.csv")
    assert "'" + payload["title"] in csv.text
    assert "中文心得" in csv.text


def test_data_survives_service_restart(tmp_path):
    url = f"sqlite:///{(tmp_path / 'persistent.db').as_posix()}"
    with TestClient(create_app(url), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        client.post("/api/logs", json=log_payload())
    with TestClient(create_app(url), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/overview").json()["total_minutes"] == 40
        assert len(client.get("/api/subjects").json()) == 7
