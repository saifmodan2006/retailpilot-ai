"""Scan staged files (or tracked files in CI) without printing secret values."""

import io
import re
import subprocess
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
patterns = [
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{20,}",
    rb"npg_[A-Za-z0-9]{10,}",
    rb"gh[pousr]_[A-Za-z0-9]{30,}",
    rb"github_pat_[A-Za-z0-9_]{40,}",
    rb"AKIA[0-9A-Z]{16}",
    rb"sb_secret_[A-Za-z0-9_-]{20,}",
    rb"GOCSPX-[A-Za-z0-9_-]{20,}",
    rb"postgres(?:ql)?(?:\+psycopg)?://[^\s:@]+:(?!replace-with-|ci-only-)[^\s@${}]{16,}@",
]
local_secrets = []
env = root / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        key, _, value = line.partition("=")
        if key in {"JWT_SECRET", "POSTGRES_PASSWORD", "LLM_API_KEY", "SESSION_ENCRYPTION_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY"} and len(value) >= 20:
            local_secrets.append(value.encode())
issues = []
scanned = 0


def inspect(data, name, depth=0):
    global scanned
    scanned += 1
    if any(re.search(p, data) for p in patterns) or any(s in data for s in local_secrets):
        issues.append(name + ": credential pattern or local secret")
    if depth < 2 and data.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                if member.file_size <= 20_000_000:
                    inspect(archive.read(member), name + "!" + member.filename, depth + 1)


for name in filter(None, files):
    p = Path(name)
    if (
        (p.name.startswith(".env") and p.name != ".env.example")
        or p.suffix in {".pem", ".key", ".db"}
        or name.startswith(".agents/")
    ):
        issues.append(name + ": forbidden release path")
    inspect(subprocess.check_output(["git", "show", ":" + name], cwd=root), name)
print(
    f"Scanned {len(list(filter(None, files)))} tracked files / {scanned} payloads (including ZIP/XLSX members)."
)
for issue in sorted(set(issues)):
    print(issue)
print("FAIL" if issues else "PASS: no credential patterns or local secrets found.")
raise SystemExit(bool(issues))
