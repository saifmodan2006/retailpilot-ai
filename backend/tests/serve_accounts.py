"""Loopback-only browser harness; disposable SQLite, mocked provider, no real users.

Run from backend with RETAILPILOT_SAAS_TEST=1. This entrypoint is NEVER used by
Render, Docker or app.main; production has no mock-provider configuration flag.
"""

import os
import secrets
import sys
import tempfile
from pathlib import Path

if os.environ.get("RETAILPILOT_SAAS_TEST") != "1":
    raise SystemExit("Explicit RETAILPILOT_SAAS_TEST=1 is required for this isolated test harness")

from cryptography.fernet import Fernet  # noqa: E402

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
temporary = Path(tempfile.mkdtemp(prefix="retailpilot-saas-browser-"))
os.environ.update(
    {
        "DATABASE_URL": "sqlite:///" + (temporary / "browser.db").as_posix(),
        "JWT_SECRET": secrets.token_hex(32),
        "PUBLIC_DEMO": "false",
        "ACCOUNTS_ENABLED": "true",
        "REGISTRATION_ENABLED": "true",
        "REGISTRATION_ALLOWLIST": "owner@example.test,member@example.test,other@example.test,links@example.test,google@example.test",
        "GOOGLE_AUTH_ENABLED": "true",
        "SUPABASE_URL": "https://fictional-test.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "test-only-publishable",
        "SESSION_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "APP_ORIGIN": "http://127.0.0.1:5174",
        "CORS_ORIGINS": "http://127.0.0.1:5174",
        "ACCOUNT_COOKIE_SECURE": "false",
        "REAL_UPLOADS_ENABLED": "false",
    }
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

config = Config(str(root / "alembic.ini"))
config.set_main_option("script_location", str(root / "alembic"))
command.upgrade(config, "head")

from app.account_auth import provider  # noqa: E402
from identity_stub import FakeIdentity  # noqa: E402
from app.main import app  # noqa: E402
import uvicorn  # noqa: E402

fake = FakeIdentity()
provider.call = fake.call
provider.exchange = fake.exchange
uvicorn.run(app, host="127.0.0.1", port=8002)
