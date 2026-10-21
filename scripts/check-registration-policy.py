"""Exercise the actual Supabase admission SQL in disposable LOCAL PostgreSQL.

No production credentials or provider APIs are used. Roles and fixtures roll back.
"""
import json
from pathlib import Path
import secrets
import subprocess

root = Path(__file__).resolve().parents[1]
database = "retailpilot_hook_check_" + secrets.token_hex(4)


def docker(*args, content=None):
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "db", *args], cwd=root,
        input=content, capture_output=True, check=True,
    ).stdout


policy = (root / "deployment/supabase-registration-policy.sql").read_text()
# Enclose the supplied migration in a transaction that also rolls back fixture roles.
policy = policy.replace("begin;", "", 1).replace("commit;", "", 1)
setup = """
begin;
do $$ begin
  if not exists(select 1 from pg_roles where rolname='anon') then create role anon; end if;
  if not exists(select 1 from pg_roles where rolname='authenticated') then create role authenticated; end if;
  if not exists(select 1 from pg_roles where rolname='supabase_auth_admin') then create role supabase_auth_admin; end if;
end $$;
create schema auth;
create schema auth_hooks;
create table auth.users (id integer primary key);
create table auth_hooks.pilot_allowlist(email text primary key, enabled boolean);
insert into auth_hooks.pilot_allowlist values ('owner@example.test',true);
grant usage on schema auth,auth_hooks to supabase_auth_admin;
grant select on auth.users,auth_hooks.pilot_allowlist to supabase_auth_admin;
"""
checks = """
set local role supabase_auth_admin;
do $$ begin
  assert auth_hooks.retailpilot_before_user_created('{"user":{"email":"owner@example.test"}}') = '{}'::jsonb;
  assert auth_hooks.retailpilot_before_user_created('{"user":{"email":"other@example.test"}}')->'error'->>'http_code' = '403';
  assert not has_table_privilege('anon','auth_hooks.registration_policy','select');
  assert not has_function_privilege('anon','auth_hooks.retailpilot_before_user_created(jsonb)','execute');
end $$;
reset role;
update auth_hooks.registration_policy set mode='open',email_signup=false;
set local role supabase_auth_admin;
do $$ begin
  assert auth_hooks.retailpilot_before_user_created('{"user":{"email":"other@example.test","app_metadata":{"provider":"google"}}}') = '{}'::jsonb;
  assert auth_hooks.retailpilot_before_user_created('{"user":{"email":"other@example.test","app_metadata":{"provider":"email"}}}')->'error'->>'http_code' = '403';
end $$;
reset role;
update auth_hooks.registration_policy set email_signup=true;
set local role supabase_auth_admin;
do $$ begin
  assert auth_hooks.retailpilot_before_user_created('{"user":{"email":"other@example.test","app_metadata":{"provider":"email"}}}') = '{}'::jsonb;
  assert auth_hooks.retailpilot_before_user_created('{"user":{"email":""}}')->'error'->>'http_code' = '403';
end $$;
reset role;
update auth_hooks.registration_policy set max_users=1;
insert into auth.users values (1);
set local role supabase_auth_admin;
do $$ begin
  assert auth_hooks.retailpilot_before_user_created('{"user":{"email":"other@example.test"}}')->'error'->>'http_code' = '429';
end $$;
reset role;
update auth_hooks.registration_policy set mode='closed';
set local role supabase_auth_admin;
do $$ begin
  assert auth_hooks.retailpilot_before_user_created('{"user":{"email":"owner@example.test"}}')->'error'->>'http_code' = '403';
end $$;
rollback;
"""
docker("createdb", "-U", "retailpilot", database)
try:
    docker("psql", "-U", "retailpilot", "-d", database, "-v", "ON_ERROR_STOP=1",
           content=(setup + policy + checks).encode())
    result = {"scope": "Disposable local PostgreSQL, actual policy SQL under Auth service role",
              "restricted_allowlist": True, "google_only": True, "open_verified_email_admission": True,
              "blank_email_denied": True, "capacity_enforced": True, "closed_denied": True,
              "anonymous_table_and_function_denied": True, "production_policy_changed": False}
    (root / "docs/registration-policy-verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
finally:
    docker("dropdb", "-U", "retailpilot", database)
