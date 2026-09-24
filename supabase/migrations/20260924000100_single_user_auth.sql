-- Single-user auth, row-level security and realtime (Phase 0).
--
-- Sign-ups are disabled in the Supabase dashboard / config.toml; the trigger below is the
-- database-side backstop. The web app and the runner both authenticate as the user, so the
-- same owner policy covers every client (no service-role key needed on the PC).

-- One user only ----------------------------------------------------------------------------

create or replace function public.enforce_single_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if exists (select 1 from auth.users where id <> new.id) then
    raise exception 'questboard is single-user; sign-ups are disabled'
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

create trigger enforce_single_user
  before insert on auth.users
  for each row execute function public.enforce_single_user();

-- Seed per-user rows on first sign-in ------------------------------------------------------
-- The default config must validate against packages/schema/schemas/config.schema.json
-- (checked by supabase/tests/run.sh).

create or replace function public.default_config() returns jsonb
language sql immutable as $$
  select '{
    "timezone": "America/Bogota",
    "goals": [],
    "capacity": { "weekday_hours": 3, "weekend_hours": 5, "focus_factor": 0.7 },
    "quiet_hours": { "start": "22:00", "end": "07:00" },
    "xp_weights": {},
    "llm": { "providers": ["claude-cli", "ollama", "claude-api"], "per_job": {} },
    "persona_order": ["coach", "teacher", "mom", "quartermaster"],
    "integrations": { "gmail": false, "gcal": false },
    "features": { "three_d": false, "mobile_rehydration": false },
    "notifications": { "persona_speech_per_day": 2, "persona_speech_on_mobile": false }
  }'::jsonb
$$;

create or replace function public.seed_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.config (user_id, data) values (new.id, public.default_config())
    on conflict (user_id) do nothing;
  insert into public.runner_state (user_id) values (new.id)
    on conflict (user_id) do nothing;
  return new;
end;
$$;

create trigger seed_user
  after insert on auth.users
  for each row execute function public.seed_user();

-- Row-level security: owner-only on every table --------------------------------------------

do $$
declare
  t text;
begin
  foreach t in array array[
    'config', 'integrations', 'goals', 'personas', 'quests', 'quest_feedback', 'progress',
    'persona_lines', 'llm_runs', 'runner_state', 'pending_live_requests', 'senders',
    'extracted_records', 'sanitization_log', 'notifications'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
    execute format(
      'create policy owner_all on public.%I for all to authenticated '
      'using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()))',
      t
    );
  end loop;
end;
$$;

revoke execute on function public.enforce_single_user() from public, anon, authenticated;
revoke execute on function public.seed_user() from public, anon, authenticated;

-- Realtime: the board, the dialogue cache and the status pill ------------------------------

alter publication supabase_realtime add table public.quests, public.persona_lines, public.runner_state;
