-- On-demand test notifications: the app asks the runner (which holds the VAPID private key)
-- to send a test Web Push to every subscribed device. Payload/result shapes:
-- packages/schema/schemas/notify_test_{request,result}.schema.json. Test sends are never
-- written to notifications, so its dedup key is untouched.

alter table public.pending_live_requests
  drop constraint pending_live_requests_kind_check,
  add constraint pending_live_requests_kind_check check (kind in (
    'setup_assistant', 'replan', 'quest_review', 'voice_fallback', 'notify_test'));
