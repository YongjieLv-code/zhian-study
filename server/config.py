import os
from dataclasses import dataclass, field
from pathlib import Path


def flag(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes"}


def entries(name, default):
    return [item.strip().rstrip("/") for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass
class Settings:
    auth_required: bool = field(default_factory=lambda: flag("ZHIAN_AUTH_REQUIRED"))
    allow_registration: bool = field(default_factory=lambda: flag("ZHIAN_ALLOW_REGISTRATION"))
    secure_cookie: bool = field(default_factory=lambda: flag("ZHIAN_SECURE_COOKIE"))
    bootstrap_token: str = field(default_factory=lambda: os.getenv("ZHIAN_BOOTSTRAP_TOKEN", ""))
    wechat_appid: str = field(default_factory=lambda: os.getenv("ZHIAN_WECHAT_APPID", "").strip())
    wechat_secret: str = field(default_factory=lambda: os.getenv("ZHIAN_WECHAT_SECRET", "").strip())
    allowed_hosts: list[str] = field(default_factory=lambda: entries("ZHIAN_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"))
    allowed_origins: list[str] = field(default_factory=lambda: entries("ZHIAN_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174"))
    backup_dir: Path | None = field(default_factory=lambda: Path(os.environ["ZHIAN_BACKUP_DIR"]) if os.getenv("ZHIAN_BACKUP_DIR") else None)
