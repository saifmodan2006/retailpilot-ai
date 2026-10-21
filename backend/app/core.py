import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )
    database_url: str = "sqlite:///./retailpilot.db"
    jwt_secret: str = secrets.token_hex(32)
    demo_enabled: bool = True
    public_demo: bool = False
    demo_ttl_hours: int = Field(default=2, ge=1, le=8)
    demo_max_tenants: int = Field(default=8, ge=1, le=30)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    erp_url: str = "http://127.0.0.1:8001"
    erp_token: str = "local-simulator-only"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_enabled: bool = False
    accounts_enabled: bool = False
    registration_enabled: bool = False
    registration_allowlist: str = ""
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    session_encryption_key: str = ""
    account_cookie_secure: bool = True
    app_origin: str = "http://localhost:5173"
    account_max_users: int = Field(default=10, ge=1, le=100)
    account_max_organizations: int = Field(default=4, ge=1, le=10)
    real_uploads_enabled: bool = False

    @field_validator("database_url")
    @classmethod
    def psycopg_url(cls, value):
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @model_validator(mode="after")
    def public_boundary(self):
        if self.accounts_enabled:
            from cryptography.fernet import Fernet
            from urllib.parse import urlsplit

            host = urlsplit(self.supabase_url)
            if (
                host.scheme != "https"
                or not host.netloc.endswith(".supabase.co")
                or host.path not in ("", "/")
                or host.username
                or host.password
                or host.query
                or host.fragment
            ):
                raise ValueError("Accounts require an HTTPS Supabase project URL")
            if not self.supabase_publishable_key:
                raise ValueError("Accounts require a Supabase publishable key")
            Fernet(self.session_encryption_key.encode())
            if self.app_origin not in self.cors_origins.split(","):
                raise ValueError("Account origin must be an explicit CORS origin")
            if self.public_demo and (
                not self.account_cookie_secure or not self.app_origin.startswith("https://")
            ):
                raise ValueError("Public account cookies require HTTPS")
        if self.registration_enabled and (
            not self.accounts_enabled or not self.registration_allowlist.strip()
        ):
            raise ValueError(
                "Registration requires configured accounts and an explicit pilot email allowlist"
            )
        if self.real_uploads_enabled and self.public_demo:
            raise ValueError("Real uploads remain disabled on the public portfolio deployment")
        if self.public_demo:
            if (
                not self.demo_enabled
                or len(self.jwt_secret) < 32
                or "jwt_secret" not in self.model_fields_set
            ):
                raise ValueError(
                    "Public demo requires demo mode and a stable 32+ character JWT secret"
                )
            if self.llm_enabled or self.llm_api_key:
                raise ValueError("Public demo cannot enable an outbound LLM provider")
            if self.erp_url not in ["", "http://erp:8001"]:
                raise ValueError(
                    "Public demo ERP must be disabled or the isolated Compose simulator"
                )
            if self.database_url.startswith("sqlite"):
                raise ValueError("Public demo requires a dedicated PostgreSQL database")
            if (
                ".neon.tech" in self.database_url
                and "sslmode=require" not in self.database_url
                and "sslmode=verify-full" not in self.database_url
            ):
                raise ValueError("Neon connections require TLS")
            if "*" in self.cors_origins:
                raise ValueError("Public demo CORS must use explicit origins")
        return self


settings = Settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    **(
        {"connect_args": {"check_same_thread": False}}
        if settings.database_url.startswith("sqlite")
        else {
            "pool_size": 2 if settings.public_demo else 5,
            "max_overflow": 0 if settings.public_demo else 5,
            "pool_timeout": 30,
            "pool_recycle": 300,
            "connect_args": {"connect_timeout": 15, "prepare_threshold": None},
        }
    ),
)
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def enable_fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def get_db():
    with SessionLocal() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
)
