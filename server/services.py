from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select

from .database import LOCAL_ACCOUNT, Profile, ReviewAttempt, ReviewItem, STUDY_TIMEZONE, StudyLog, Subject, today, utc

DEFAULT_SUBJECTS = [
    ("language", "言语理解", "practice", "#7d9871"),
    ("reasoning", "判断推理", "practice", "#92aeb8"),
    ("data", "资料分析", "practice", "#bba272"),
    ("math", "数量关系", "practice", "#ad95b2"),
    ("knowledge", "常识判断", "practice", "#cc947a"),
    ("politics", "政治理论", "practice", "#c1b267"),
    ("essay", "申论", "essay", "#789c94"),
]


def scope(model, owner):
    return select(model).where(model.account_id == owner)


def get_owned(session, model, owner, key):
    return session.scalar(scope(model, owner).where(model.id == key))


def seed(session, owner=LOCAL_ACCOUNT):
    if get_owned(session, Profile, owner, 1) is None:
        session.add(Profile(account_id=owner, id=1))
    if session.scalar(scope(Subject, owner).limit(1)) is None:
        session.add_all(Subject(account_id=owner, id=key, name=name, kind=kind, color=color, position=i)
                        for i, (key, name, kind, color) in enumerate(DEFAULT_SUBJECTS))
    session.flush()


def serialize(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns if column.name != "account_id"}


def intervals(interval):
    steps = [1, 3, 7, 14, 30, 60, 90, 180]
    good = next((step for step in steps if step > max(interval, 1)), 180)
    easy = next((step for step in steps if step > good), 180)
    return {"again": 1, "hard": max(1, min(3, interval)), "good": good, "easy": easy}


def serialize_review(row):
    return {**serialize(row), "interval_options": intervals(row.interval_days)}


def overview(session, owner=LOCAL_ACCOUNT):
    current = today()
    profile = get_owned(session, Profile, owner, 1)
    logs = session.scalars(scope(StudyLog, owner)).all()
    daily = defaultdict(lambda: {"minutes": 0, "sessions": 0, "questions": 0, "correct": 0})
    subjects = defaultdict(lambda: {"minutes": 0, "questions": 0, "correct": 0, "sessions": 0})
    for log in logs:
        for item in (daily[log.study_date], subjects[log.subject_id]):
            item["minutes"] += log.duration_minutes
            item["sessions"] += 1
            item["questions"] += log.question_count
            item["correct"] += log.correct_count
    active_days = {day for day, value in daily.items() if value["minutes"] > 0}
    streak = 0
    cursor = current if current in active_days else current - timedelta(days=1)
    while cursor in active_days:
        streak += 1
        cursor -= timedelta(days=1)
    attempts = session.scalars(scope(ReviewAttempt, owner)).all()
    completed_today = sum(1 for attempt in attempts
                          if utc(attempt.reviewed_at)
                          .astimezone(STUDY_TIMEZONE).date() == current)
    return {
        "date": current,
        "timezone": str(STUDY_TIMEZONE),
        "profile": serialize(profile),
        "today": {**daily[current], "reviews": completed_today},
        "total_minutes": sum(log.duration_minutes for log in logs),
        "total_days": len(active_days),
        "streak": streak,
        "days_until_exam": (profile.exam_date - current).days if profile.exam_date else None,
        "daily": [{"date": day, **value} for day, value in sorted(daily.items())],
        "subject_totals": [{"subject_id": key, **value} for key, value in subjects.items()],
        "review_due": len(session.scalars(scope(ReviewItem, owner).where(
            ReviewItem.due_date <= current, ReviewItem.archived.is_(False))).all()),
    }
