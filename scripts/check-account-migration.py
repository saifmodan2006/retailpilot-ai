"""Verify additive migration + pg_dump/restore using disposable LOCAL databases.

Never reads a production URL; never touches Neon. No database credentials printed.
Requires the existing loopback Compose PostgreSQL service and root .env.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from urllib.parse import quote

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
from_accounts = "--from-accounts" in sys.argv
suffix = secrets.token_hex(4)
source = "retailpilot_acct_migration_" + suffix
recovered = "retailpilot_acct_restore_" + suffix
environment = {**os.environ, "JWT_SECRET": secrets.token_hex(32), "ACCOUNTS_ENABLED": "false",
               "REGISTRATION_ENABLED": "false", "PUBLIC_DEMO": "false"}
password = dotenv_values(root / ".env")["POSTGRES_PASSWORD"]
environment["DATABASE_URL"] = "postgresql+psycopg://retailpilot:" + quote(password, safe="") + "@127.0.0.1:5433/" + source


def docker(*args, content=None):
    return subprocess.run(["docker", "compose", "exec", "-T", "db", *args], cwd=root,
                          input=content, capture_output=True, check=True).stdout


def alembic(*args):
    subprocess.run([sys.executable, "-m", "alembic", *args], cwd=root / "backend", env=environment,
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def sql(query, database=source):
    return docker("psql", "-U", "retailpilot", "-d", database, "-At", "-v", "ON_ERROR_STOP=1", "-c", query).decode().strip()


def fingerprints(database):
    tables = sql("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version' ORDER BY tablename", database).splitlines()
    return {table: {"rows": int(sql(f'SELECT count(*) FROM "{table}"', database)),
                    "sha256": hashlib.sha256(sql(f'SELECT row_to_json(t)::text FROM "{table}" t ORDER BY row_to_json(t)::text', database).encode()).hexdigest()}
            for table in tables}


created = []
try:
    for database in (source, recovered):
        docker("createdb", "-U", "retailpilot", database)
        created.append(database)
    alembic("upgrade", "b7c2_public_demo_boundary")
    sql("""
    INSERT INTO organizations VALUES ('migration-fixture','Fictional recovery fixture',now(),'{"safety_days":7,"dead_days":90,"cover_days":14}',false);
    INSERT INTO users (id,org_id,created_at,name,role) VALUES (1,'migration-fixture',now(),'Fictional manager','manager');
    INSERT INTO stores (id,org_id,created_at,code,name,city) VALUES (1,'migration-fixture',now(),'F01','Fictional store','Fictional city');
    INSERT INTO brands (id,org_id,created_at,name) VALUES (1,'migration-fixture',now(),'Fictional brand');
    INSERT INTO categories (id,org_id,created_at,name) VALUES (1,'migration-fixture',now(),'Fictional category');
    INSERT INTO suppliers (id,org_id,created_at,name,lead_days,moq,pack_size) VALUES (1,'migration-fixture',now(),'Fictional supplier',10,6,6);
    INSERT INTO products (id,org_id,created_at,name,brand_id,category_id,supplier_id) VALUES (1,'migration-fixture',now(),'Fictional product',1,1,1);
    INSERT INTO skus (id,org_id,created_at,code,product_id,size,color,cost,price) VALUES (1,'migration-fixture',now(),'RP-FIX',1,'M','Ivory',40,100);
    INSERT INTO sales (id,org_id,created_at,transaction_id,date,store_id,sku_id,quantity,revenue,cogs) VALUES (1,'migration-fixture',now(),'FIX-SALE','2026-10-18',1,1,2,200,80);
    INSERT INTO inventory_snapshots (id,org_id,created_at,date,store_id,sku_id,quantity,reserved,received_date) VALUES (1,'migration-fixture',now(),'2026-10-18',1,1,5,0,'2026-10-01');
    INSERT INTO recommendations (id,org_id,created_at,store_id,sku_id,quantity,cost,severity,rationale,evidence,status) VALUES (1,'migration-fixture',now(),1,1,6,240,'Review','Fictional evidence','{}','Awaiting Approval');
    INSERT INTO approvals (id,org_id,created_at,recommendation_id,requested_by,status,reason) VALUES (1,'migration-fixture',now(),1,1,'Awaiting Approval','');
    INSERT INTO generated_reports (id,org_id,created_at,kind,filters,rows,metrics) VALUES (1,'migration-fixture',now(),'Daily sales MIS','{}','[{"revenue":200}]','{"revenue":200}');
    INSERT INTO audit_events (id,org_id,created_at,actor,action,entity,detail) VALUES (1,'migration-fixture',now(),'Fictional manager','fixture.created','1','{}');
    """)
    if from_accounts:
        alembic("upgrade", "c8d3_persistent_accounts")
        sql("""
        INSERT INTO accounts (id,provider_id,email,name,job_title,phone,timezone,language,onboarding,created_at,last_login)
        VALUES ('fixture-account','fixture-provider','fixture@example.test','Fictional member','','','UTC','en','{}',now(),now());
        INSERT INTO organization_memberships (id,org_id,created_at,account_id,actor_id,role,active)
        VALUES (1,'migration-fixture',now(),'fixture-account',1,'manager',true);
        INSERT INTO account_sessions (digest,account_id,org_id,provider_tokens,recovery,created_at,expires_at)
        VALUES (repeat('a',64),'fixture-account','migration-fixture','fictional-session-ciphertext',false,now(),now()+interval '8 hours');
        """)
    before = fingerprints(source)
    backup = docker("pg_dump", "-U", "retailpilot", "-d", source, "--format=custom", "--no-owner", "--no-privileges")
    backup_path = Path(tempfile.mkdtemp(prefix="retailpilot-account-recovery-")) / "fictional-baseline.dump"
    backup_path.write_bytes(backup)
    docker("pg_restore", "-U", "retailpilot", "-d", recovered, "--exit-on-error", "--no-owner", "--no-privileges", content=backup_path.read_bytes())
    assert fingerprints(recovered) == before, "Recovery changed legacy table fingerprints"
    alembic("upgrade", "head")
    after = fingerprints(source)
    assert all(after[table] == result for table, result in before.items()), "Migration changed existing business facts"
    assert len(after) - len(before) == (1 if from_accounts else 7)
    alembic("check")
    result = {"scope": "Disposable local Compose PostgreSQL; NOT a Neon production checkpoint",
              "postgres_version": sql("SHOW server_version"),
              "migration": ("c8d3_persistent_accounts" if from_accounts else "b7c2_public_demo_boundary") + " -> d9e4_google_oauth",
              "legacy_tables_verified": len(before), "legacy_fingerprints_unchanged": True,
              "backup_restored_and_compared": True, "backup_bytes": len(backup),
              "new_tables": sorted(set(after) - set(before)), "alembic_drift": False,
              "fixtures": "Fictional sales, inventory, actors, approvals, report rows and audit evidence"}
    output = "oauth-account-preservation.json" if from_accounts else "public-auth-migration-verification.json"
    (root / "docs" / output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
finally:
    # Only the two fresh, randomized, local test databases created by this process.
    for database in created:
        docker("dropdb", "-U", "retailpilot", database)
