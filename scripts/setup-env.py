"""Generate ignored local secrets. Never overwrites an existing .env."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    print(".env already exists; left unchanged.")
else:
    password = secrets.token_hex(24)
    content = (
        (root / ".env.example")
        .read_text(encoding="utf-8")
        .replace("replace-with-a-random-hex-password", password)
        .replace("replace-with-at-least-32-random-bytes", secrets.token_hex(32))
    )
    target.write_text(content, encoding="utf-8")
    print("Generated ignored .env with local secrets.")
