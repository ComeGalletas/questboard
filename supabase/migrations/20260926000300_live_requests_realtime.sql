-- Phase 3: the app waits on P1 answers (setup assistant) over realtime instead of polling.
alter publication supabase_realtime add table public.pending_live_requests;
