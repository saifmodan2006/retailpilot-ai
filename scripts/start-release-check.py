"""Run a loopback-only 512 MB release container against a separate local DB."""
import secrets
import json
import subprocess
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy.engine import URL

root = Path(__file__).resolve().parents[1]
env = dotenv_values(root / ".env")
database_url = URL.create("postgresql+psycopg", username="retailpilot", password=env["POSTGRES_PASSWORD"], host="db", port=5432, database="retailpilot_release").render_as_string(hide_password=False)
def run(args):
    return subprocess.run(args, cwd=root, check=True, capture_output=True, text=True)
exists = run(["docker","compose","exec","-T","db","psql","-U","retailpilot","-d","postgres","-tAc","SELECT 1 FROM pg_database WHERE datname='retailpilot_release'"]).stdout.strip()
if not exists:
    run(["docker","compose","exec","-T","db","createdb","-U","retailpilot","retailpilot_release"])
db_container = run(["docker", "compose", "ps", "-q", "db"]).stdout.strip()
network = next(iter(json.loads(run(["docker", "inspect", db_container]).stdout)[0]["NetworkSettings"]["Networks"]))
result = run(["docker","run","-d","--name","retailpilot-release-check","--memory","512m","--memory-swap","512m",
    "--network",network,"-p","127.0.0.1:5180:10000",
    "--mount",f"type=bind,source={root / 'backend'},target=/app/backend,readonly",
    "-e", "DATABASE_URL=" + database_url,
    "-e",f"JWT_SECRET={secrets.token_hex(32)}","-e","PUBLIC_DEMO=true","-e","DEMO_MAX_TENANTS=4",
    "-e","ERP_URL=","-e","CORS_ORIGINS=http://127.0.0.1:5180",
    "-e","OPENBLAS_NUM_THREADS=1","-e","OMP_NUM_THREADS=1","-e","MALLOC_ARENA_MAX=2",
    "retailpilot-release:local"])
print("Started loopback-only release check at http://127.0.0.1:5180 (512 MB hard memory limit).")
