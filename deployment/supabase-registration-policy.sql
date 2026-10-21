-- Dedicated RetailPilot Supabase Auth project ONLY, never the Neon business DB.
-- Install closed/restricted first. Open only after SMTP/CAPTCHA or Google checks.
begin;
create table if not exists auth_hooks.registration_policy (
    singleton boolean primary key default true check (singleton),
    mode text not null default 'restricted' check (mode in ('closed','restricted','open')),
    max_users integer not null default 100 check (max_users between 1 and 100),
    email_signup boolean not null default false
);
insert into auth_hooks.registration_policy (singleton, mode, max_users, email_signup)
values (true, 'restricted', 100, false) on conflict (singleton) do nothing;
alter table auth_hooks.registration_policy enable row level security;
revoke all on auth_hooks.registration_policy from public, anon, authenticated;
grant select on auth_hooks.registration_policy to supabase_auth_admin;
drop policy if exists "auth_service_reads_registration_policy" on auth_hooks.registration_policy;
create policy "auth_service_reads_registration_policy"
    on auth_hooks.registration_policy for select to supabase_auth_admin using (true);

create or replace function auth_hooks.retailpilot_before_user_created(event jsonb)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
    policy auth_hooks.registration_policy%rowtype;
    address text := lower(btrim(coalesce(event->'user'->>'email','')));
    identity_provider text := coalesce(event->'user'->'app_metadata'->>'provider','');
begin
    perform pg_catalog.pg_advisory_xact_lock(7319289);
    select * into policy from auth_hooks.registration_policy where singleton;
    if not found or policy.mode = 'closed' or address = '' then
        return jsonb_build_object('error',jsonb_build_object(
            'http_code',403,'message','Registration is currently unavailable.'));
    end if;
    if (select count(*) from auth.users) >= policy.max_users then
        return jsonb_build_object('error',jsonb_build_object(
            'http_code',429,'message','This free deployment is at account capacity. Please retry later.'));
    end if;
    if policy.mode = 'restricted' and not exists (
        select 1 from auth_hooks.pilot_allowlist where enabled and email = address
    ) then
        return jsonb_build_object('error',jsonb_build_object(
            'http_code',403,'message','Registration is restricted to the approved pilot.'));
    end if;
    if policy.mode = 'open' and not policy.email_signup and identity_provider <> 'google' then
        return jsonb_build_object('error',jsonb_build_object(
            'http_code',403,'message','Please use Google while email delivery is being configured.'));
    end if;
    return '{}'::jsonb;
end;
$$;
revoke execute on function auth_hooks.retailpilot_before_user_created(jsonb) from public, anon, authenticated;
grant execute on function auth_hooks.retailpilot_before_user_created(jsonb) to supabase_auth_admin;
commit;
-- To open verified email signup after SMTP and CAPTCHA tests:
-- UPDATE auth_hooks.registration_policy SET mode='open',email_signup=true WHERE singleton;
-- Google-only opening uses email_signup=false. Keep backend flags in agreement.
-- To stop new registrations without revoking existing accounts: set mode='closed'.
