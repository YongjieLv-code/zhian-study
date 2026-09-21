import os
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROOT = Path(__file__).resolve().parent.parent
LOCAL_ACCOUNT = "local"
STUDY_TIMEZONE = ZoneInfo(os.getenv("ZHIAN_TIMEZONE", "Asia/Shanghai"))


def today():
    return datetime.now(STUDY_TIMEZONE).date()


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def identifier():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=identifier)
    username: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Owned:
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), primary_key=True)


class Profile(Owned, Base):
    __tablename__ = "profile"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(40), default="备考者")
    exam_name: Mapped[str] = mapped_column(String(100), default="我的备考计划")
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_goal_minutes: Mapped[int] = mapped_column(Integer, default=120)


class Subject(Owned, Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("account_id", "name"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20), default="practice")
    color: Mapped[str] = mapped_column(String(20), default="#859d79")
    position: Mapped[int] = mapped_column(Integer, default=0)


class Plan(Owned, Base):
    __tablename__ = "plans"
    __table_args__ = (ForeignKeyConstraint(["account_id", "subject_id"], ["subjects.account_id", "subjects.id"]),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=identifier)
    title: Mapped[str] = mapped_column(String(150))
    subject_id: Mapped[str] = mapped_column(String(40))
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    minutes: Mapped[int] = mapped_column(Integer, default=30)
    note: Mapped[str] = mapped_column(Text, default="")
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StudyLog(Owned, Base):
    __tablename__ = "study_logs"
    __table_args__ = (
        ForeignKeyConstraint(["account_id", "subject_id"], ["subjects.account_id", "subjects.id"]),
        ForeignKeyConstraint(["account_id", "plan_id"], ["plans.account_id", "plans.id"]),
    )
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=identifier)
    title: Mapped[str] = mapped_column(String(150))
    subject_id: Mapped[str] = mapped_column(String(40))
    study_date: Mapped[date] = mapped_column(Date, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    plan_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewItem(Owned, Base):
    __tablename__ = "review_items"
    __table_args__ = (ForeignKeyConstraint(["account_id", "subject_id"], ["subjects.account_id", "subjects.id"]),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=identifier)
    title: Mapped[str] = mapped_column(String(150))
    subject_id: Mapped[str] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(500), default="")
    due_date: Mapped[date] = mapped_column(Date, index=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    last_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewAttempt(Owned, Base):
    __tablename__ = "review_attempts"
    __table_args__ = (
        ForeignKeyConstraint(["account_id", "review_id"], ["review_items.account_id", "review_items.id"]),
        ForeignKeyConstraint(["account_id", "log_id"], ["study_logs.account_id", "study_logs.id"]),
    )
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(40), index=True)
    log_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rating: Mapped[str] = mapped_column(String(20))
    next_interval_days: Mapped[int] = mapped_column(Integer)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MiniSession(Base):
    __tablename__ = "mini_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WechatIdentity(Base):
    __tablename__ = "wechat_identities"
    __table_args__ = (UniqueConstraint("appid", "account_id"),)
    appid: Mapped[str] = mapped_column(String(64), primary_key=True)
    openid: Mapped[str] = mapped_column(String(128), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WechatBinding(Base):
    __tablename__ = "wechat_bindings"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    appid: Mapped[str] = mapped_column(String(64))
    openid: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthThrottle(Base):
    __tablename__ = "auth_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BackupSnapshot(Base):
    __tablename__ = "backup_snapshots"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=identifier)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(30))
    filename: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=identifier)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    mode: Mapped[str] = mapped_column(String(10))
    base_hash: Mapped[str] = mapped_column(String(64))
    projected_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def make_engine(url=None):
    if not url:
        (ROOT / "data").mkdir(exist_ok=True)
        url = os.getenv("ZHIAN_DATABASE_URL", f"sqlite:///{(ROOT / 'data' / 'zhian.db').as_posix()}")
    options = {"connect_args": {"check_same_thread": False, "timeout": 15}} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, **options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
    return engine
