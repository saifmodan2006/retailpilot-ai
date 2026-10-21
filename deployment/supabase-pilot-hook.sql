-- Dedicated Supabase Auth project ONLY; never the Neon business database.
-- No emails are admitted automatically. Operator-managed restricted pilot.
-- https://supabase.com/docs/guides/auth/auth-hooks/before-user-created-hook
begin;
create schema if not exists auth_hooks;
revoke all on schema auth_hooks from public, anon, authenticated;
grant usage on schema auth_hooks to supabase_auth_admin;
create table if not exists auth_hooks.pilot_allowlist (
    email text primary key check (email = lower(btrim(email))),
    enabled boolean not null default false
);
alter table auth_hooks.pilot_allowlist enable row level security;
revoke all on auth_hooks.pilot_allowlist from public, anon, authenticated;
grant select on auth_hooks.pilot_allowlist to supabase_auth_admin;
create policy "auth_service_reads_enabled_pilot_addresses"
    on auth_hooks.pilot_allowlist for select to supabase_auth_admin using (enabled);
create or replace function auth_hooks.retailpilot_before_user_created(event jsonb)
returns jsonb language plpgsql security invoker set search_path = '' as $$
begin
    if not exists (
        select 1 from auth_hooks.pilot_allowlist
        where enabled and email = lower(btrim(coalesce(event->'user'->>'email','')))
    ) or (select count(*) from auth.users) >= 10 then
        return jsonb_build_object('error',jsonb_build_object(
            'http_code',403,'message','Registration is restricted to the approved RetailPilot pilot.'));
    end if;
    return '{}'::jsonb;
end;
$$;
revoke execute on function auth_hooks.retailpilot_before_user_created(jsonb) from public, anon, authenticated;
grant execute on function auth_hooks.retailpilot_before_user_created(jsonb) to supabase_auth_admin;
commit;
-- Configure Before User Created hook to use this function before enabling signups.
