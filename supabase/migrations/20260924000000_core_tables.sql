-- Questboard core tables (Phase 0).
--
-- Every row is owned by a user (user_id = auth.uid()); the app is single-user today, but
-- multi-user later needs no model change. Enums are text + CHECK so they can evolve with
-- packages/schema without enum-type migrations; keep the value lists in sync with the schemas.
--
-- Invariant 5: the cloud DB holds pseudonymized data only. No raw email, OAuth tokens,
-- vault values or transcripts go in any column below.

create extension if not exists pgcrypto with schema extensions;

-- Shared helpers ---------------------------------------------------------------------------

create or replace function public.set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- config: one JSON row per user. Shape = packages/schema/schemas/config.schema.json ----------

create table public.config (
  user_id    uuid primary key default auth.uid() references auth.users (id) on delete cascade,
  data       jsonb not null check (jsonb_typeof(data) = 'object'),
  updated_at timestamptz not null default now()
);

-- integrations: connection status only. OAuth tokens live in the OS keychain on the PC. --------

create table public.integrations (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  kind         text not null check (kind in ('gmail', 'gcal')),
  status       text not null default 'disconnected'
               check (status in ('disconnected', 'connected', 'error', 'revoked')),
  scopes       text[] not null default '{}',
  last_sync_at timestamptz,
  error        text check (char_length(error) <= 500),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (user_id, kind)
);

-- goals ------------------------------------------------------------------------------------

create table public.goals (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title       text not null check (char_length(title) between 1 and 120),
  horizon     text not null check (horizon in ('week', 'month', 'quarter', 'year')),
  persona     text check (persona ~ '^[a-z][a-z0-9_-]{1,31}$'),
  status      text not null default 'active' check (status in ('active', 'done', 'dropped')),
  target_date date,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- personas: installed packs (built-in and custom). Assets stay in the pack / storage. ---------

create table public.personas (
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  slug         text not null check (slug ~ '^[a-z][a-z0-9_-]{1,31}$'),
  name         text not null check (char_length(name) between 1 and 40),
  accent       text not null check (accent ~ '^#[0-9a-f]{6}$'),
  intensity    smallint not null default 1 check (intensity between 0 and 3),
  quiet_hours  jsonb,
  owns         text[] not null default '{}',
  priority     smallint not null default 0,
  builtin      boolean not null default false,
  enabled      boolean not null default true,
  pack_version text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  primary key (user_id, slug)
);

-- quests. Shape = packages/schema/schemas/quest.schema.json -------------------------------

create table public.quests (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title           text not null check (char_length(title) between 1 and 120),
  notes           text check (char_length(notes) <= 2000),
  persona         text not null check (persona ~ '^[a-z][a-z0-9_-]{1,31}$'),
  cadence         text not null check (cadence in ('daily', 'weekly', 'monthly')),
  category        text not null default 'general' check (category in (
                    'general', 'ics', 'utilities', 'government', 'health', 'delivery',
                    'subscription', 'jobs', 'learning', 'personal', 'travel')),
  status          text not null default 'open' check (status in (
                    'open', 'in_progress', 'done', 'partial', 'snoozed', 'deferred',
                    'skipped', 'forgotten', 'overdue', 'abandoned')),
  estimate_min    integer not null check (estimate_min between 1 and 1440),
  actual_min      integer check (actual_min >= 0),
  scheduled_for   date,
  deadline        timestamptz,
  hard_deadline   boolean not null default false,
  priority        smallint not null default 2 check (priority between 1 and 3),
  xp              integer not null default 0 check (xp >= 0),
  carries         integer not null default 0 check (carries >= 0),
  source          text not null check (source in (
                    'manual', 'llm', 'llm-proposed', 'extractor', 'calendar', 'voice')),
  reference_token text check (reference_token ~ '^[A-Z]+_[0-9]+$'),
  parent_id       uuid references public.quests (id) on delete set null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index quests_board_idx on public.quests (user_id, cadence, scheduled_for);
create index quests_status_idx on public.quests (user_id, status);
create index quests_reference_idx on public.quests (user_id, reference_token)
  where reference_token is not null;

-- quest_feedback: what the user did with a quest or a proposed diff op ---------------------

create table public.quest_feedback (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  quest_id   uuid references public.quests (id) on delete cascade,
  action     text not null check (action in (
               'accepted', 'rejected', 'edited', 'too_long', 'too_short', 'not_relevant',
               'comment')),
  diff_op    jsonb,
  comment    text check (char_length(comment) <= 500),
  created_at timestamptz not null default now()
);

create index quest_feedback_quest_idx on public.quest_feedback (quest_id);

-- progress: one row per user per day; XP/level/streak are computed in code (P2) ----------

create table public.progress (
  user_id         uuid not null default auth.uid() references auth.users (id) on delete cascade,
  date            date not null,
  xp_earned       integer not null default 0,
  xp_total        integer not null default 0 check (xp_total >= 0),
  level           integer not null default 1 check (level >= 1),
  streak          integer not null default 0 check (streak >= 0),
  quests_planned  integer not null default 0 check (quests_planned >= 0),
  quests_done     integer not null default 0 check (quests_done >= 0),
  planned_min     integer not null default 0 check (planned_min >= 0),
  actual_min      integer not null default 0 check (actual_min >= 0),
  stats           jsonb not null default '{}' check (jsonb_typeof(stats) = 'object'),
  updated_at      timestamptz not null default now(),
  primary key (user_id, date)
);

-- llm_runs. Shape = packages/schema/schemas/llm_run.schema.json ---------------------------

create table public.llm_runs (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  job           text not null check (job in (
                  'ingest', 'daily_am', 'daily_pm', 'weekly', 'monthly', 'persona_digest')),
  slot          text check (slot in ('AM', 'PM')),
  date          date not null,
  trigger       text not null check (trigger in ('tick', 'start', 'network_up', 'manual')),
  provider_used text check (provider_used in ('claude-cli', 'ollama', 'claude-api')),
  attempt       smallint not null check (attempt between 1 and 3),
  status        text not null check (status in (
                  'queued', 'running', 'succeeded', 'failed', 'invalid_output', 'skipped')),
  tokens_input  integer check (tokens_input >= 0),
  tokens_output integer check (tokens_output >= 0),
  error         text check (char_length(error) <= 500),
  started_at    timestamptz,
  finished_at   timestamptz,
  created_at    timestamptz not null default now(),
  check ((slot is not null) = (job in ('daily_am', 'daily_pm'))),
  unique nulls not distinct (user_id, job, slot, date, attempt)
);

-- Idempotency guard: at most one successful run per (job, slot, date).
create unique index llm_runs_one_success_idx on public.llm_runs (user_id, job, slot, date)
  nulls not distinct where status = 'succeeded';

-- persona_lines. Shape = packages/schema/schemas/persona_line.schema.json -----------------

create table public.persona_lines (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  quest_id   uuid references public.quests (id) on delete cascade,
  run_id     uuid references public.llm_runs (id) on delete set null,
  persona    text not null check (persona ~ '^[a-z][a-z0-9_-]{1,31}$'),
  trigger    text not null check (trigger in (
               'assigned', 'reminder_am', 'reminder_mid', 'reminder_pm', 'started',
               'completed_early', 'completed_on_time', 'completed_late', 'partial', 'snoozed',
               'deferred', 'skipped', 'forgotten', 'overdue_1d', 'overdue_3d', 'overdue_7d',
               'carried_over', 'abandoned', 'all_done', 'half_by_noon', 'nothing_by_15',
               'over_capacity')),
  variant    smallint not null check (variant between 1 and 3),
  condition  text not null default 'any'
             check (condition in ('any', 'pleased', 'neutral', 'concerned')),
  text       text not null check (char_length(text) between 1 and 280),
  used_at    timestamptz,
  created_at timestamptz not null default now()
);

create index persona_lines_lookup_idx on public.persona_lines (quest_id, trigger, condition);
create index persona_lines_board_idx on public.persona_lines (user_id, persona, trigger)
  where quest_id is null;

-- runner_state: one row per user; the status pill reads heartbeat_at -----------------------

create table public.runner_state (
  user_id         uuid primary key default auth.uid() references auth.users (id) on delete cascade,
  heartbeat_at    timestamptz,
  last_am_success timestamptz,
  last_pm_success timestamptz,
  lock_holder     text,
  lock_acquired_at timestamptz,
  provider_health jsonb not null default '{}' check (jsonb_typeof(provider_health) = 'object'),
  runner_version  text,
  updated_at      timestamptz not null default now()
);

-- pending_live_requests: P1 work queued for the runner (e.g. from the phone) ---------------

create table public.pending_live_requests (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  kind       text not null check (kind in (
               'setup_assistant', 'replan', 'quest_review', 'voice_fallback')),
  status     text not null default 'pending'
             check (status in ('pending', 'running', 'done', 'failed', 'cancelled')),
  payload    jsonb not null default '{}',
  result     jsonb,
  error      text check (char_length(error) <= 500),
  origin     text not null default 'mobile' check (origin in ('mobile', 'pc')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index pending_live_requests_queue_idx on public.pending_live_requests (user_id, created_at)
  where status = 'pending';

-- senders: sender domain -> category, plus allow/deny lists --------------------------------

create table public.senders (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  domain        text not null check (domain ~ '^[a-z0-9.-]+\.[a-z]{2,}$'),
  category      text check (category in (
                  'general', 'ics', 'utilities', 'government', 'health', 'delivery',
                  'subscription', 'jobs', 'learning', 'personal', 'travel')),
  list          text check (list in ('allow', 'deny')),
  classified_by text not null default 'rule' check (classified_by in ('rule', 'llm', 'user')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (user_id, domain)
);

-- extracted_records. Shape = packages/schema/schemas/extracted_record.schema.json ---------
-- Tokens only: amounts, entities and references are vault pseudonyms.

create table public.extracted_records (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid() references auth.users (id) on delete cascade,
  dedup_key       text not null,
  category        text not null check (category in (
                    'general', 'ics', 'utilities', 'government', 'health', 'delivery',
                    'subscription', 'jobs', 'learning', 'personal', 'travel')),
  kind            text not null check (kind in ('obligation', 'completion')),
  entity_token    text not null check (entity_token ~ '^[A-Z]+_[0-9]+$'),
  amount          text check (amount ~ '^AMOUNT_[0-9]+$'),
  due_at          timestamptz,
  event_at        timestamptz,
  location        text check (char_length(location) <= 200),
  instructions    text[] not null default '{}' check (cardinality(instructions) <= 10),
  reference_token text check (reference_token ~ '^[A-Z]+_[0-9]+$'),
  confidence      real not null check (confidence between 0 and 1),
  quest_id        uuid references public.quests (id) on delete set null,
  created_at      timestamptz not null default now(),
  unique (user_id, dedup_key)
);

create index extracted_records_reference_idx on public.extracted_records (user_id, reference_token)
  where reference_token is not null;

-- sanitization_log: rule hits and counts, never values -------------------------------------

create table public.sanitization_log (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  run_id     uuid references public.llm_runs (id) on delete set null,
  profile    text not null check (profile ~ '^[a-z_]{1,32}$'),
  rule       text not null check (rule ~ '^[A-Za-z0-9_.-]{1,64}$'),
  hits       integer not null check (hits >= 0),
  messages   integer not null default 1 check (messages >= 0),
  created_at timestamptz not null default now()
);

-- notifications: dedup by (kind, target, date) --------------------------------------------

create table public.notifications (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  kind       text not null check (kind in (
               'day_ready', 'day_recap', 'week_ready', 'month_ready', 'quest_due',
               'quest_overdue', 'capacity_alert', 'streak_risk', 'persona_speech',
               'runner_stale', 'live_pending')),
  target     text not null check (target ~ '^questboard://'),
  persona    text check (persona ~ '^[a-z][a-z0-9_-]{1,31}$'),
  dedup_date date not null,
  channels   text[] not null default '{pc}' check (channels <@ array['pc', 'push']),
  title      text check (char_length(title) <= 80),
  body       text check (char_length(body) <= 280),
  sent_at    timestamptz,
  created_at timestamptz not null default now(),
  unique (user_id, kind, target, dedup_date)
);

-- updated_at triggers ----------------------------------------------------------------------

do $$
declare
  t text;
begin
  foreach t in array array[
    'config', 'integrations', 'goals', 'personas', 'quests', 'progress', 'runner_state',
    'pending_live_requests', 'senders'
  ] loop
    execute format(
      'create trigger %I before update on public.%I for each row execute function public.set_updated_at()',
      t || '_updated_at', t
    );
  end loop;
end;
$$;
