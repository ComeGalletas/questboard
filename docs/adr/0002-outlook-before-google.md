# ADR 0002: Outlook / Microsoft 365 before Google

- Status: accepted
- Date: 2026-09-29

Touches invariant 5 in `CLAUDE.md` only in wording ("Gmail ingestion" becomes "mail
ingestion"); the rule itself (raw email never leaves the PC) is unchanged.

## Context

`CLAUDE.md` and `docs/PLAN.md` named Gmail and Google Calendar as the first integrations
(Phases 3 and 4) and put an Outlook / Microsoft 365 adapter in Phase 7. The mail and calendar
the owner actually uses first are on Outlook.

## Decision

- Phase 3 calendar ingest is Outlook calendar via Microsoft Graph (`runner/ingest/outlook_cal.py`).
- Phase 4 mail ingest is Outlook mail via Microsoft Graph (`runner/ingest/outlook_mail.py`).
- Google (Gmail + Calendar) moves to Phase 7, behind the same ingest interface. It is deferred,
  not dropped.
- Everything else holds as written for Gmail: read-only delegated scopes only (`Mail.Read`,
  `Calendars.Read`, `offline_access`), ingestion only in the runner, sanitizer before any
  storage or prompt, refresh token in the OS keychain, `.ics` attachments through the `ics`
  extractor.

## Consequences

- Open question 1 (Gmail restricted-scope verification) is deferred with Google. It is
  replaced by: personal Microsoft account or a work/school tenant, which may need admin
  consent for the mail scope.
- Graph returns HTML bodies and its own quoted-reply markup; the sanitizer fixtures already
  include an Outlook reply (`outlook_reply_en.json`), and new Graph-shaped fixtures join the
  release gate with the adapter.
- The ingest base class must not assume Gmail ids, labels or history ids, so Google can plug
  in later without changes to the extractors.
