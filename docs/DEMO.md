# Demo Script (5 min + failure)

## Accounts (System Admin `admin@gmail.com` / `12345`, others password `password123`)
admin@gmail.com · admin@citycare-general.org · doc0@example.org · aarav@example.org

## Happy path (patient)
1. Login `aarav@example.org` → AI Assistant → send: "I need to see a doctor for my shoulder pain sometime this week."
2. Observe trace (`intent=book`, `search_doctors`, `check_availability`) + doctor cards + real slots.
3. Book a slot → confirmation shows appointment #, verified=yes, correlation ID.
4. Upcoming → details → verification + timeline → questionnaire → conversational fill → submit.
5. Login `doc0@example.org` → Today → open visit → answers visible.

## Failure/recovery
Option A (UI): platform admin → Reconciliation → seeded `unknown_outcome_not_found` → "Probe EHR + sync".
Option B (API): `POST /api/v1/appointments` with `"simulate":"timeout_after_create"` (valid slot) → returns `recovered:true, verified:true, no duplicate`; check Integrations (operation `unknown_outcome→success`) + appointment `confirmed` + verification `probe_by_idempotency=matched`.

## Admin tour
Hospital admin: overview → doctors → schedules → AI activity → integrations → workflows → analytics. Platform admin: applications (approve northgate) → ops wall → audit → ops health.
