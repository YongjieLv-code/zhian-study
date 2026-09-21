import csv
import io
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import auth, backups, mini_auth
from .config import Settings
from .database import Account, BackupSnapshot, LoginSession, Plan, Profile, ReviewAttempt, ReviewItem, ROOT, StudyLog, Subject, make_engine, today
from .migrations import backup_directory, initialize
from .schemas import ArchiveInput, LogInput, PlanInput, ProfileInput, ReviewAction, ReviewInput, SubjectInput
from .services import get_owned, intervals, overview, scope, serialize, serialize_review
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from uuid import UUID


class PreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["merge", "replace"] = "merge"
    backup: dict


class ApplyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    acknowledged: bool = False


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > backups.MAX_BACKUP_BYTES:
                return await JSONResponse({"detail": "文件过大，请使用 10 MB 以内的 JSON 备份"}, status_code=413)(scope, receive, send)
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        sent = False

        async def buffered_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, send)


def create_app(database_url=None, settings=None):
    engine = make_engine(database_url)
    settings = settings or Settings()
    directory = backup_directory(engine, settings)

    @asynccontextmanager
    async def lifespan(_app):
        initialize(engine, directory)
        yield
        engine.dispose()

    app = FastAPI(title="知岸 · 学习记录 API", version="0.3.0", lifespan=lifespan,
                  docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
    app.state.engine = engine
    app.state.backup_dir = directory
    app.state.settings = settings
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Content-Type", "X-CSRF-Token", "X-Workspace-ID", "Authorization"], expose_headers=["X-Zhian-Reason"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            same_origin = f"{request.url.scheme}://{request.url.netloc}"
            if origin and origin != same_origin and origin not in settings.allowed_origins:
                return JSONResponse({"detail": "请求来源不受信任"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def get_db(request: Request):
        with Session(engine) as session:
            if engine.dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN" if request.method in {"GET", "HEAD", "OPTIONS"} else "BEGIN IMMEDIATE")
            elif request.method in {"GET", "HEAD", "OPTIONS"}:
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            yield session

    Db = Annotated[Session, Depends(get_db)]

    def get_context(db: Db, request: Request):
        return auth.require_context(db, request, settings)

    Ctx = Annotated[auth.Context, Depends(get_context)]

    def require(session, model, key, ctx):
        row = get_owned(session, model, ctx.owner, key)
        if row is None:
            raise HTTPException(404, "这条内容不存在或已被删除，请刷新后重试")
        return row

    def validate_subject(session, key, ctx):
        subject = get_owned(session, Subject, ctx.owner, key)
        if subject is None:
            raise HTTPException(422, "请选择有效的学习科目")
        return subject

    def validate_log(session, payload, ctx):
        subject = validate_subject(session, payload.subject_id, ctx)
        if subject.kind == "essay" and (payload.question_count or payload.correct_count):
            raise HTTPException(422, "申论按作答与反馈记录，不参与客观题正确率统计")
        if payload.plan_id:
            plan = require(session, Plan, payload.plan_id, ctx)
            if plan.subject_id != payload.subject_id:
                raise HTTPException(422, "学习记录的科目需要与关联计划一致")

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_request: Request, exc: RequestValidationError):
        message = "；".join(error["msg"].removeprefix("Value error, ") for error in exc.errors())
        return JSONResponse(status_code=422, content={"detail": message})

    @app.exception_handler(IntegrityError)
    async def integrity_error(_request: Request, _exc: IntegrityError):
        return JSONResponse(status_code=409, content={"detail": "内容已更新或存在重复，请刷新后重试"})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.3.0", "mode": "account-ready"}

    @app.get("/api/auth/status")
    def auth_status(request: Request, db: Db):
        return auth.status(db, request, settings)

    @app.post("/api/auth/register", status_code=201)
    def register(payload: auth.Credentials, request: Request, response: Response, db: Db):
        return auth.register(db, request, response, payload, settings)

    @app.post("/api/auth/login")
    def login(payload: auth.Credentials, request: Request, response: Response, db: Db):
        return auth.login(db, request, response, payload, settings)

    @app.post("/api/auth/logout", status_code=204)
    def logout(response: Response, db: Db, ctx: Ctx):
        if ctx.login:
            db.delete(ctx.login)
        db.commit()
        if not ctx.login or isinstance(ctx.login, LoginSession):
            response.delete_cookie(auth.COOKIE, path="/", secure=settings.secure_cookie, httponly=True, samesite="lax")

    @app.post("/api/auth/password")
    def change_password(payload: auth.PasswordChange, request: Request, response: Response, db: Db, ctx: Ctx):
        return auth.change_password(db, request, response, ctx, payload, settings)

    @app.get("/api/mini/auth/config")
    def mini_config(request: Request, db: Db):
        current = auth.status(db, request, settings)
        return {**{key: current[key] for key in ("can_register", "first_account", "requires_bootstrap", "registration_open")},
                "wechat_enabled": mini_auth.enabled(settings)}

    @app.post("/api/mini/auth/login")
    def mini_login(payload: auth.Credentials, request: Request, db: Db):
        return auth.start_mini_session(db, auth.authenticate(db, request, payload), settings)

    @app.post("/api/mini/auth/register", status_code=201)
    def mini_register(payload: auth.Credentials, request: Request, db: Db):
        return auth.start_mini_session(db, auth.create_account(db, request, payload, settings), settings)

    @app.get("/api/mini/auth/session")
    def mini_session(db: Db, ctx: Ctx):
        mini_auth.require_mini(ctx)
        return {**auth.mini_identity(db, db.get(Account, ctx.owner), settings), "expires_at": ctx.login.expires_at}

    @app.post("/api/mini/auth/logout", status_code=204)
    def mini_logout(db: Db, ctx: Ctx):
        mini_auth.require_mini(ctx)
        db.delete(ctx.login)
        db.commit()

    @app.post("/api/mini/auth/password")
    def mini_password(payload: auth.PasswordChange, request: Request, response: Response, db: Db, ctx: Ctx):
        mini_auth.require_mini(ctx)
        return auth.change_password(db, request, response, ctx, payload, settings)

    def wechat_proof(payload: mini_auth.WechatCode, request: Request):
        if not mini_auth.enabled(settings):
            raise HTTPException(503, "微信登录尚未配置，请先使用知岸账号登录")
        # Commit the rate-limit reservation before the outbound request; network
        # delays must not hold SQLite's workspace write lock.
        with Session(engine) as session:
            if engine.dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            attempts = auth.throttle(session, request, namespace="wechat", limit=30)
            attempts.failures += 1
            session.commit()
        return mini_auth.exchange_code(payload.code, settings), payload.purpose

    WechatProof = Annotated[tuple[str, str], Depends(wechat_proof)]

    @app.post("/api/mini/auth/wechat")
    def mini_wechat(proof: WechatProof, db: Db):
        return mini_auth.wechat_login(db, proof[0], proof[1], settings)

    @app.post("/api/mini/auth/wechat/bind")
    def mini_bind(payload: mini_auth.BindingCredentials, request: Request, db: Db):
        return mini_auth.bind_wechat(db, request, payload, settings)

    @app.post("/api/mini/auth/wechat/unbind")
    def mini_unbind(payload: mini_auth.VerifyPassword, request: Request, db: Db, ctx: Ctx):
        return mini_auth.unbind_wechat(db, request, ctx, payload, settings)

    @app.get("/api/workspace")
    def workspace(request: Request, db: Db, ctx: Ctx):
        return {"auth": auth.status(db, request, settings), "overview": overview(db, ctx.owner),
                "subjects": [serialize(row) for row in db.scalars(scope(Subject, ctx.owner).order_by(Subject.position, Subject.id))],
                "plans": [serialize(row) for row in db.scalars(scope(Plan, ctx.owner).order_by(Plan.scheduled_date, Plan.created_at))],
                "logs": [serialize(row) for row in db.scalars(scope(StudyLog, ctx.owner).order_by(StudyLog.study_date.desc(), StudyLog.created_at.desc()))],
                "reviews": [serialize_review(row) for row in db.scalars(scope(ReviewItem, ctx.owner).order_by(ReviewItem.due_date, ReviewItem.created_at))]}

    @app.get("/api/profile")
    def get_profile(db: Db, ctx: Ctx):
        return serialize(require(db, Profile, 1, ctx))

    @app.put("/api/profile")
    def update_profile(payload: ProfileInput, db: Db, ctx: Ctx):
        profile = require(db, Profile, 1, ctx)
        for key, value in payload.model_dump().items():
            setattr(profile, key, value)
        db.commit()
        return serialize(profile)

    @app.get("/api/subjects")
    def subjects(db: Db, ctx: Ctx):
        return [serialize(row) for row in db.scalars(scope(Subject, ctx.owner).order_by(Subject.position))]

    @app.post("/api/subjects", status_code=201)
    def add_subject(payload: SubjectInput, db: Db, ctx: Ctx):
        if db.scalar(scope(Subject, ctx.owner).where(Subject.name == payload.name)):
            raise HTTPException(409, "这个科目已存在")
        position = db.scalar(select(func.count()).select_from(Subject).where(Subject.account_id == ctx.owner))
        colors = ["#7d9871", "#92aeb8", "#bba272", "#ad95b2", "#cc947a", "#789c94"]
        row = Subject(account_id=ctx.owner, **payload.model_dump(), position=position, color=colors[position % len(colors)])
        db.add(row)
        db.commit()
        return serialize(row)

    @app.get("/api/overview")
    def get_overview(db: Db, ctx: Ctx):
        return overview(db, ctx.owner)

    @app.get("/api/plans")
    def plans(db: Db, ctx: Ctx):
        return [serialize(row) for row in db.scalars(scope(Plan, ctx.owner).order_by(Plan.scheduled_date, Plan.created_at))]

    @app.post("/api/plans", status_code=201)
    def add_plan(payload: PlanInput, db: Db, ctx: Ctx):
        validate_subject(db, payload.subject_id, ctx)
        row = Plan(account_id=ctx.owner, **payload.model_dump())
        db.add(row)
        db.commit()
        return serialize(row)

    @app.put("/api/plans/{key}")
    def update_plan(key: str, payload: PlanInput, db: Db, ctx: Ctx):
        row = require(db, Plan, key, ctx)
        validate_subject(db, payload.subject_id, ctx)
        if row.completed:
            raise HTTPException(409, "已完成的计划保留原始安排，可在学习记录中修改实际学习情况")
        for field, value in payload.model_dump().items():
            setattr(row, field, value)
        db.commit()
        return serialize(row)

    @app.delete("/api/plans/{key}", status_code=204)
    def delete_plan(key: str, db: Db, ctx: Ctx):
        row = require(db, Plan, key, ctx)
        db.execute(update(StudyLog).where(StudyLog.account_id == ctx.owner, StudyLog.plan_id == key).values(plan_id=None))
        db.delete(row)
        db.commit()

    @app.get("/api/logs")
    def logs(db: Db, ctx: Ctx):
        return [serialize(row) for row in db.scalars(scope(StudyLog, ctx.owner).order_by(StudyLog.study_date.desc(), StudyLog.created_at.desc()))]

    @app.post("/api/logs", status_code=201)
    def add_log(payload: LogInput, db: Db, ctx: Ctx):
        existing = get_owned(db, StudyLog, ctx.owner, str(payload.id))
        if existing:
            expected = payload.model_dump(exclude={"id", "add_to_review"})
            if any(getattr(existing, field) != value for field, value in expected.items()):
                raise HTTPException(409, "这次提交已经保存。请关闭窗口，在学习记录中修改已保存的内容")
            return serialize(existing)
        validate_log(db, payload, ctx)
        values = payload.model_dump(exclude={"add_to_review"})
        values["id"] = str(payload.id)
        row = StudyLog(account_id=ctx.owner, **values)
        db.add(row)
        if payload.plan_id:
            require(db, Plan, payload.plan_id, ctx).completed = True
        if payload.add_to_review:
            db.add(ReviewItem(account_id=ctx.owner, title=payload.title, subject_id=payload.subject_id, note=payload.note,
                              source="学习记录", due_date=max(today(), payload.study_date + timedelta(days=1))))
        db.commit()
        return serialize(row)

    @app.put("/api/logs/{key}")
    def update_log(key: str, payload: LogInput, db: Db, ctx: Ctx):
        row = require(db, StudyLog, key, ctx)
        validate_log(db, payload, ctx)
        if str(payload.id) != key or payload.plan_id != row.plan_id:
            raise HTTPException(422, "不能改变记录编号或关联的计划")
        for field, value in payload.model_dump(exclude={"id", "add_to_review"}).items():
            setattr(row, field, value)
        db.commit()
        return serialize(row)

    @app.delete("/api/logs/{key}", status_code=204)
    def delete_log(key: str, db: Db, ctx: Ctx):
        row = require(db, StudyLog, key, ctx)
        plan_id = row.plan_id
        db.execute(update(ReviewAttempt).where(ReviewAttempt.account_id == ctx.owner, ReviewAttempt.log_id == key).values(log_id=None))
        db.delete(row)
        db.flush()
        if plan_id and db.scalar(select(func.count()).select_from(StudyLog).where(StudyLog.account_id == ctx.owner, StudyLog.plan_id == plan_id)) == 0:
            plan = get_owned(db, Plan, ctx.owner, plan_id)
            if plan:
                plan.completed = False
        db.commit()

    @app.get("/api/reviews")
    def reviews(db: Db, ctx: Ctx):
        return [serialize_review(row) for row in db.scalars(scope(ReviewItem, ctx.owner).order_by(ReviewItem.due_date, ReviewItem.created_at))]

    @app.post("/api/reviews", status_code=201)
    def add_review(payload: ReviewInput, db: Db, ctx: Ctx):
        validate_subject(db, payload.subject_id, ctx)
        row = ReviewItem(account_id=ctx.owner, **payload.model_dump())
        db.add(row)
        db.commit()
        return serialize_review(row)

    @app.put("/api/reviews/{key}")
    def update_review(key: str, payload: ReviewInput, db: Db, ctx: Ctx):
        row = require(db, ReviewItem, key, ctx)
        validate_subject(db, payload.subject_id, ctx)
        for field, value in payload.model_dump().items():
            setattr(row, field, value)
        row.version += 1
        db.commit()
        return serialize_review(row)

    @app.patch("/api/reviews/{key}/archive")
    @app.post("/api/reviews/{key}/archive")
    def archive_review(key: str, payload: ArchiveInput, db: Db, ctx: Ctx):
        row = require(db, ReviewItem, key, ctx)
        row.archived = payload.archived
        row.version += 1
        db.commit()
        return serialize_review(row)

    @app.get("/api/reviews/{key}/history")
    def review_history(key: str, db: Db, ctx: Ctx):
        require(db, ReviewItem, key, ctx)
        return [serialize(row) for row in db.scalars(scope(ReviewAttempt, ctx.owner).where(ReviewAttempt.review_id == key)
                .order_by(ReviewAttempt.reviewed_at.desc()))]

    @app.post("/api/reviews/{key}/complete")
    def complete_review(key: str, payload: ReviewAction, db: Db, ctx: Ctx):
        item = require(db, ReviewItem, key, ctx)
        attempt_id = str(payload.id)
        existing = get_owned(db, ReviewAttempt, ctx.owner, attempt_id)
        if existing:
            if existing.review_id != key or existing.rating != payload.rating:
                raise HTTPException(409, "此提交编号已用于另一条复习记录")
            return serialize_review(item)
        if item.archived or item.due_date > today():
            raise HTTPException(409, "这张卡片已复习或尚未到期，请刷新复习列表")
        interval = intervals(item.interval_days)[payload.rating]
        result = db.execute(update(ReviewItem).where(ReviewItem.account_id == ctx.owner, ReviewItem.id == key,
                            ReviewItem.version == payload.expected_version).values(
                            due_date=today() + timedelta(days=interval), interval_days=interval,
                            review_count=ReviewItem.review_count + 1, last_rating=payload.rating,
                            version=ReviewItem.version + 1))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "这张卡片已经更新，请刷新后重试")
        log = StudyLog(account_id=ctx.owner, id=attempt_id, title=f"复习 · {item.title}"[:150], subject_id=item.subject_id,
                       study_date=today(), duration_minutes=payload.duration_minutes,
                       note=f"复习反馈：{ {'again': '不会', 'hard': '模糊', 'good': '掌握', 'easy': '熟练'}[payload.rating] }")
        db.add(log)
        db.flush()
        db.add(ReviewAttempt(account_id=ctx.owner, id=attempt_id, review_id=key, log_id=log.id, rating=payload.rating, next_interval_days=interval))
        db.commit()
        db.refresh(item)
        return serialize_review(item)

    @app.get("/api/backup")
    def backup(db: Db, ctx: Ctx):
        content = backups.export_data(db, ctx.owner)
        return JSONResponse(jsonable_encoder(content), headers={"Content-Disposition": f'attachment; filename="zhian-backup-{today()}.json"'})

    @app.post("/api/backups/preview")
    def preview_backup(payload: PreviewInput, db: Db, ctx: Ctx):
        return backups.preview(db, ctx.owner, payload.backup, payload.mode)

    @app.post("/api/backups/apply")
    def apply_backup(payload: ApplyInput, db: Db, ctx: Ctx):
        return backups.apply_import(db, ctx.owner, str(payload.id), payload.acknowledged, directory)

    @app.get("/api/backups/history")
    def backup_history(db: Db, ctx: Ctx):
        rows = db.scalars(select(BackupSnapshot).where(BackupSnapshot.account_id == ctx.owner).order_by(BackupSnapshot.created_at.desc()).limit(100))
        return [{"id": row.id, "purpose": row.purpose, "size_bytes": row.size_bytes, "created_at": row.created_at} for row in rows]

    @app.get("/api/backups/{key}/download")
    def download_backup(key: str, db: Db, ctx: Ctx):
        return Response(backups.snapshot_content(db, ctx.owner, key, directory), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="zhian-snapshot-{key}.json"'})

    @app.get("/api/logs/export.csv")
    def export_logs(db: Db, ctx: Ctx):
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["学习日期", "科目", "学习内容", "时长（分钟）", "题量", "正确数", "心得与反馈"])
        names = {row.id: row.name for row in db.scalars(scope(Subject, ctx.owner))}
        def safe(value):
            text = str(value)
            return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
        for row in db.scalars(scope(StudyLog, ctx.owner).order_by(StudyLog.study_date.desc())):
            writer.writerow([safe(value) for value in [row.study_date, names[row.subject_id], row.title,
                            row.duration_minutes, row.question_count, row.correct_count, row.note]])
        return Response(content="\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="zhian-records-{today()}.csv"'})

    mini_static = ROOT / "miniapp" / "dist" / "build" / "h5"
    if mini_static.exists():
        app.mount("/mini", StaticFiles(directory=mini_static, html=True), name="mini-preview")

    static = ROOT / "dist"
    if static.exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/{path:path}")
        def frontend(path: str):
            if path == "api" or path.startswith("api/"):
                raise HTTPException(404, "接口不存在")
            candidate = (static / path).resolve()
            if candidate.is_relative_to(static.resolve()) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})
    return app


app = create_app()
