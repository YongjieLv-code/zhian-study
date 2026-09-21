import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError, field_validator, model_validator
from sqlalchemy import delete, select

from .database import BackupSnapshot, ImportJob, Plan, Profile, ReviewAttempt, ReviewItem, StudyLog, Subject, now, today, utc
from .services import DEFAULT_SUBJECTS, get_owned, scope, serialize

MAX_BACKUP_BYTES = 10 * 1024 * 1024
COLLECTIONS = {"subjects": Subject, "plans": Plan, "logs": StudyLog, "reviews": ReviewItem, "review_history": ReviewAttempt}
DELETE_ORDER = [ReviewAttempt, StudyLog, ReviewItem, Plan, Subject, Profile]
DEFAULT_IDS = {entry[0] for entry in DEFAULT_SUBJECTS}


def record_id(value):
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        raise ValueError("记录编号必须是 UUID")


def subject_id(value):
    return value if value in DEFAULT_IDS else record_id(value)


RecordID = Annotated[str, AfterValidator(record_id)]
SubjectID = Annotated[str, AfterValidator(subject_id)]
Title = Annotated[str, Field(min_length=1, max_length=150)]
Rating = Literal["again", "hard", "good", "easy"]
Timestamp = Annotated[datetime, AfterValidator(utc)]


class BackupRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def date_types(cls, value, info):
        if (info.field_name == "version" or (info.field_name == "id" and cls.__name__ == "BackupProfile")) and type(value) is not int:
            raise ValueError("版本和目标编号必须是整数")
        if info.field_name in {"exam_date", "scheduled_date", "study_date", "due_date", "exported_date", "created_at", "reviewed_at"}:
            if value is not None and not isinstance(value, (str, date, datetime)):
                raise ValueError("日期须使用 ISO 格式")
        if info.field_name in {"title", "name", "exam_name"} and isinstance(value, str) and not value.strip():
            raise ValueError("名称或标题不能为空")
        return value


class BackupProfile(BackupRow):
    id: Literal[1]
    name: str = Field(min_length=1, max_length=40)
    exam_name: str = Field(min_length=1, max_length=100)
    exam_date: date | None
    daily_goal_minutes: StrictInt = Field(ge=5, le=1440)


class BackupSubject(BackupRow):
    id: SubjectID
    name: str = Field(min_length=1, max_length=40)
    kind: Literal["practice", "essay"]
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    position: StrictInt = Field(ge=0, le=100000)


class BackupPlan(BackupRow):
    id: RecordID
    title: Title
    subject_id: SubjectID
    scheduled_date: date
    minutes: StrictInt = Field(ge=1, le=1440)
    note: str = Field(max_length=2000)
    completed: StrictBool
    created_at: Timestamp


class BackupLog(BackupRow):
    id: RecordID
    title: Title
    subject_id: SubjectID
    study_date: date
    duration_minutes: StrictInt = Field(ge=1, le=1440)
    question_count: StrictInt = Field(ge=0, le=5000)
    correct_count: StrictInt = Field(ge=0, le=5000)
    note: str = Field(max_length=5000)
    plan_id: RecordID | None
    created_at: Timestamp

    @model_validator(mode="after")
    def check_counts(self):
        if self.study_date > today():
            raise ValueError("备份中包含晚于今天的学习记录")
        if self.correct_count > self.question_count:
            raise ValueError("正确题数不能超过题量")
        return self


class BackupReview(BackupRow):
    id: RecordID
    title: Title
    subject_id: SubjectID
    note: str = Field(max_length=5000)
    source: str = Field(max_length=500)
    due_date: date
    interval_days: StrictInt = Field(ge=0, le=180)
    review_count: StrictInt = Field(ge=0, le=100000)
    last_rating: Rating | None
    archived: StrictBool
    version: StrictInt = Field(ge=1)
    created_at: Timestamp


class BackupAttempt(BackupRow):
    id: RecordID
    review_id: RecordID
    log_id: RecordID | None
    rating: Rating
    next_interval_days: StrictInt = Field(ge=1, le=180)
    reviewed_at: Timestamp


class BackupDocument(BackupRow):
    format: Literal["zhian-backup"]
    version: Literal[1]
    exported_date: date
    profile: BackupProfile
    subjects: list[BackupSubject] = Field(min_length=1, max_length=10000)
    plans: list[BackupPlan] = Field(max_length=100000)
    logs: list[BackupLog] = Field(max_length=100000)
    reviews: list[BackupReview] = Field(max_length=100000)
    review_history: list[BackupAttempt] = Field(max_length=100000)

    @model_validator(mode="after")
    def relationships(self):
        for key in COLLECTIONS:
            ids = [row.id for row in getattr(self, key)]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{key} 中存在重复编号")
        names = [row.name for row in self.subjects]
        if len(names) != len(set(names)):
            raise ValueError("存在同名的不同科目，请先处理科目名称冲突")
        subjects = {row.id: row for row in self.subjects}
        plans = {row.id: row for row in self.plans}
        logs = {row.id: row for row in self.logs}
        reviews = {row.id: row for row in self.reviews}
        for row in [*self.plans, *self.logs, *self.reviews]:
            if row.subject_id not in subjects:
                raise ValueError("记录关联的科目不存在")
        for row in self.logs:
            if subjects[row.subject_id].kind == "essay" and (row.question_count or row.correct_count):
                raise ValueError("主观题科目不能包含客观题题量")
            if row.plan_id and (row.plan_id not in plans or plans[row.plan_id].subject_id != row.subject_id):
                raise ValueError("学习记录关联的计划不存在或科目不一致")
        for row in self.review_history:
            if row.review_id not in reviews or (row.log_id is not None and row.log_id not in logs):
                raise ValueError("复习历史关联的卡片或学习记录不存在")
        counts = Counter(row.review_id for row in self.review_history)
        feedback = {(row.review_id, row.rating, row.next_interval_days) for row in self.review_history}
        for row in self.reviews:
            if row.review_count != counts[row.id] or row.version < row.review_count + 1:
                raise ValueError("卡片复习次数与复习历史不一致；合并冲突时可改用完整替换")
            if (row.review_count == 0) != (row.last_rating is None):
                raise ValueError("卡片复习反馈与复习次数不一致")
            if (row.review_count == 0 and row.interval_days != 0) or (row.review_count > 0 and (row.id, row.last_rating, row.interval_days) not in feedback):
                raise ValueError("卡片复习反馈与排期间隔无法对应复习历史")
        completed = {row.plan_id for row in self.logs if row.plan_id}
        for row in self.plans:
            row.completed = row.id in completed
        return self


def validate_document(value):
    try:
        return BackupDocument.model_validate(value)
    except ValidationError as exc:
        details = []
        for error in exc.errors()[:5]:
            location = ".".join(str(part) for part in error["loc"])
            details.append(f"{location}: {error['msg'].removeprefix('Value error, ')}")
        raise HTTPException(422, "备份校验未通过：" + "；".join(details)) from exc


def export_data(db, owner):
    return jsonable_encoder({"format": "zhian-backup", "version": 1, "exported_date": today(),
                             "profile": serialize(get_owned(db, Profile, owner, 1)),
                             **{key: [serialize(row) for row in db.scalars(scope(model, owner).order_by(model.id))]
                                for key, model in COLLECTIONS.items()}})


def canonical(value):
    data = validate_document(value).model_dump(mode="json")
    for key in COLLECTIONS:
        data[key].sort(key=lambda row: row["id"])
    return data


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value):
    data = canonical(value)
    data.pop("exported_date")
    return hashlib.sha256(encode(data)).hexdigest()


def snapshot(db, owner, data, directory: Path, purpose="before-restore"):
    """The file must be durable before any destructive database operation."""
    content = encode(data)
    snapshot_id = str(uuid4())
    filename = f"{owner}-{snapshot_id}.json"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".pending-", delete=False) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            except BaseException:
                handle.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, directory / filename)
        finally:
            temporary.unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(503, "自动备份未能写入，原有数据未修改。请检查备份目录权限和磁盘空间") from exc
    row = BackupSnapshot(id=snapshot_id, account_id=owner, filename=filename, purpose=purpose,
                         size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
    db.add(row)
    db.flush()
    return row


def preview(db, owner, incoming, mode):
    incoming = canonical(incoming)
    current = canonical(export_data(db, owner))
    projected = {**incoming} if mode == "replace" else {**current}
    counts = {}
    for key in COLLECTIONS:
        saved = {row["id"]: row for row in current[key]}
        duplicate = sum(saved.get(row["id"]) == row for row in incoming[key])
        conflict = sum(row["id"] in saved and saved[row["id"]] != row for row in incoming[key])
        added = [row for row in incoming[key] if row["id"] not in saved]
        counts[key] = {"current": len(saved), "incoming": len(incoming[key]), "new": len(added), "duplicate": duplicate, "conflict": conflict}
        if mode == "merge":
            projected[key] = [*current[key], *added]
    projected = canonical(projected)
    db.execute(delete(ImportJob).where(ImportJob.account_id == owner, ImportJob.expires_at < now(), ImportJob.result_json.is_(None)))
    job = ImportJob(account_id=owner, mode=mode, base_hash=digest(current), projected_json=encode(projected).decode(),
                    expires_at=now() + timedelta(minutes=10))
    db.add(job)
    db.flush()
    result = {"id": job.id, "mode": mode, "counts": counts, "expires_at": job.expires_at,
              "profile_changed": current["profile"] != incoming["profile"], "profile": projected["profile"]}
    db.commit()
    return result


def replace_data(db, owner, data):
    document = validate_document(data)
    for model in DELETE_ORDER:
        db.execute(delete(model).where(model.account_id == owner))
    db.flush()
    db.add(Profile(account_id=owner, **document.profile.model_dump()))
    db.flush()
    for key, model in COLLECTIONS.items():
        db.add_all(model(account_id=owner, **row.model_dump()) for row in getattr(document, key))
        db.flush()


def apply_import(db, owner, key, acknowledged, directory):
    job = db.scalar(select(ImportJob).where(ImportJob.id == key, ImportJob.account_id == owner))
    if not job:
        raise HTTPException(404, "导入预览不存在")
    if job.result_json:
        return json.loads(job.result_json)
    if utc(job.expires_at) < now():
        raise HTTPException(409, "导入预览已过期，请重新选择备份")
    if job.mode == "replace" and not acknowledged:
        raise HTTPException(422, "请确认用备份完整替换当前学习数据")
    current = export_data(db, owner)
    if digest(current) != job.base_hash:
        raise HTTPException(409, "预览后学习数据发生了变化，请重新预览，避免覆盖新记录")
    data = json.loads(job.projected_json)
    validate_document(data)
    saved = snapshot(db, owner, current, directory)
    replace_data(db, owner, data)
    result = {"id": job.id, "mode": job.mode, "backup_id": saved.id,
              "counts": {key: len(data[key]) for key in COLLECTIONS}}
    job.result_json = json.dumps(result)
    db.commit()
    return result


def snapshot_content(db, owner, key, directory):
    row = db.scalar(select(BackupSnapshot).where(BackupSnapshot.id == key, BackupSnapshot.account_id == owner))
    if not row:
        raise HTTPException(404, "备份不存在")
    path = (directory / row.filename).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise HTTPException(404, "备份不存在")
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise HTTPException(404, "备份文件无法读取，请检查服务端备份目录") from exc
    if hashlib.sha256(content).hexdigest() != row.sha256:
        raise HTTPException(409, "备份文件校验失败，请使用其他备份")
    return content
