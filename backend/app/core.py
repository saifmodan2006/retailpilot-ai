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

    @field_validator("database_url")
    @classmethod
    def psycopg_url(cls, value):
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @model_validator(mode="after")
    def public_boundary(self):
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
            "pool_size": 2,
            "max_overflow": 0,
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
