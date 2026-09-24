-- Behavioural checks for the migrations. Run by supabase/tests/run.sh after shim + migrations.
\set ON_ERROR_STOP 1

create function pg_temp.expect_error(stmt text, label text) returns void
language plpgsql as $$
begin
  execute stmt;
  raise exception 'expected failure: %', label;
exception
  when others then
    if sqlerrm like 'expected failure:%' then
      raise;
    end if;
end;
$$;

create function pg_temp.expect_eq(actual bigint, expected bigint, label text) returns void
language plpgsql as $$
begin
  if actual is distinct from expected then
    raise exception '%: expected %, got %', label, expected, actual;
  end if;
end;
$$;

-- Sign-up seeds config + runner_state; a second user is rejected.
insert into auth.users (id, email) values ('11111111-1111-1111-1111-111111111111', 'me@example.test');
select pg_temp.expect_eq((select count(*) from public.config), 1, 'config seeded');
select pg_temp.expect_eq((select count(*) from public.runner_state), 1, 'runner_state seeded');
select pg_temp.expect_error(
  $$insert into auth.users (id) values ('22222222-2222-2222-2222-222222222222')$$,
  'second user');

-- Every public table has RLS on.
select pg_temp.expect_eq(
  (select count(*) from pg_tables where schemaname = 'public' and not rowsecurity), 0,
  'tables without RLS');

-- Realtime publishes exactly the board, dialogue cache and status pill.
select pg_temp.expect_eq(
  (select count(*) from pg_publication_tables where pubname = 'supabase_realtime'
     and tablename in ('quests', 'persona_lines', 'runner_state')), 3,
  'realtime tables');

-- As the owner: defaults fill user_id; rows are visible.
set role authenticated;
set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';

insert into public.quests (title, persona, cadence, estimate_min, source)
values ('Easy 5 km run', 'coach', 'daily', 40, 'manual');
select pg_temp.expect_eq((select count(*) from public.quests), 1, 'owner sees quest');
select pg_temp.expect_eq((select count(*) from public.config), 1, 'owner sees config');

-- Idempotency: one successful run per (job, slot, date), including slot-less jobs.
insert into public.llm_runs (job, slot, date, trigger, attempt, status)
values ('daily_am', 'AM', '2026-09-25', 'tick', 1, 'succeeded'),
       ('weekly', null, '2026-09-27', 'tick', 1, 'succeeded');
select pg_temp.expect_error(
  $$insert into public.llm_runs (job, slot, date, trigger, attempt, status)
    values ('daily_am', 'AM', '2026-09-25', 'manual', 2, 'succeeded')$$,
  'second daily success');
select pg_temp.expect_error(
  $$insert into public.llm_runs (job, slot, date, trigger, attempt, status)
    values ('weekly', null, '2026-09-27', 'manual', 2, 'succeeded')$$,
  'second weekly success');
select pg_temp.expect_error(
  $$insert into public.llm_runs (job, slot, date, trigger, attempt, status)
    values ('daily_am', null, '2026-09-26', 'tick', 1, 'queued')$$,
  'daily job without slot');

-- Amounts are tokens only (invariant 5).
select pg_temp.expect_error(
  $$insert into public.extracted_records (dedup_key, category, kind, entity_token, amount, confidence)
    values ('k1', 'utilities', 'obligation', 'ORG_3', '184500', 0.9)$$,
  'plain amount');
insert into public.extracted_records (dedup_key, category, kind, entity_token, amount, confidence)
values ('k1', 'utilities', 'obligation', 'ORG_3', 'AMOUNT_2', 0.9);

-- Notifications dedup by (kind, target, date).
insert into public.notifications (kind, target, dedup_date)
values ('quest_due', 'questboard://quest/1', '2026-09-25');
select pg_temp.expect_error(
  $$insert into public.notifications (kind, target, dedup_date, channels)
    values ('quest_due', 'questboard://quest/1', '2026-09-25', '{push}')$$,
  'duplicate notification');

-- A different identity sees nothing and cannot write into the owner's rows.
set request.jwt.claim.sub = '33333333-3333-3333-3333-333333333333';
select pg_temp.expect_eq((select count(*) from public.quests), 0, 'stranger sees quests');
select pg_temp.expect_eq((select count(*) from public.config), 0, 'stranger sees config');
select pg_temp.expect_error(
  $$insert into public.quests (user_id, title, persona, cadence, estimate_min, source)
    values ('11111111-1111-1111-1111-111111111111', 'x', 'coach', 'daily', 5, 'manual')$$,
  'stranger writes owner quest');

-- Anonymous clients get nothing.
reset request.jwt.claim.sub;
set role anon;
select pg_temp.expect_error($$select 1 from public.quests$$, 'anon reads quests');
reset role;

\echo 'assertions passed'
