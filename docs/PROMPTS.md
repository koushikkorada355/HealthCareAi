
## B1 — Platform admin governance

Build platform admin login with a seeded system admin account and role guard.

Implement hospital application review queue showing submitted and under-review states.

Add approve hospital action that creates default calendars, connections, and fires the approved event.

Add reject hospital action with a required reason field and applicant notification.
    
Add request-corrections action that returns the application to the applicant with a note.

Implement suspend hospital that blocks new bookings but keeps history visible.

Implement reactivate hospital that restores approved status and re-enables booking.

Build platform health wall showing service, AI, integration, and workflow status.

Build AI activity view with conversation count, latency, tool success rate, and escalations.

Build integration activity view listing today's EHR operations by status.

Build workflow runs view with running, completed, failed, and scheduled filters.

Build analytics overview with bookings, cancellations, utilization, and no-show counts.

Build audit log view showing actor, action, target, time, and correlation reference.

Enforce tenant isolation so platform admin sees all but hospital admins stay scoped.

Add AI evaluation summary showing intent accuracy, clarification rate, and safety refusals.

## B2 — Hospital onboarding lifecycle

Build hospital registration form capturing name, address, contact, and admin info.

Implement draft save so applicants can resume an incomplete hospital application.

Add submit action moving draft to submitted with required-field validation.

Build application status page showing draft, submitted, under review, approved, or rejected.

Implement under-review state with reviewer notes visible to the applicant.

Add corrections-resubmit flow returning the application to submitted after fixes.

Build departments manager with add, rename, and archive per hospital.

Build specialties manager linked to departments with multi-select support.

Add services list with free-text services like X-ray and physiotherapy.

Implement operating hours editor with weekday open-close ranges.

Add hospital admin contact editor with name, email, and phone validation.

Implement healthcare-system selector defaulting to the mock connector.

Add integration config form for facility ID, vendor, and API key with test button.

Build rejected-state explainer showing reason plus a re-apply as new draft button.

Implement suspended-state banner explaining why bookings are blocked.

Build approved-hospitals public list showing only bookable hospitals.

Add hospital address update with audit logging.

Implement withdraw application action with confirm dialog.

Add approval-decision notification for applicants via in-app record.

Build multi-hospital seed with three hospitals in distinct lifecycle states.

## B3 — Hospital and doctor configuration

Implement add-doctor form with name, specialty, department, and experience.

Create invited status for new doctors with accept and decline actions.

Implement invite accept moving doctor to active with calendar auto-creation.

Implement invite decline moving doctor to inactive and blocking booking.

Add deactivate doctor action preserving history while hiding future slots.

Build consultation duration setting per doctor defaulting to thirty minutes.

Add qualifications editor supporting degrees like MBBS and MS Ortho.

Add languages multi-select with English, Hindi, and Marathi options.

Add consult-type selector for in-person and video visits.

Implement create-calendar per doctor with active flag.

Build working-hours rule editor with weekday, start, end, and slot minutes.

Implement blocked-slot creator for meetings with start and end datetime.

Add doctor leave manager blocking whole days from availability.

Build appointment-type catalog with name and duration per hospital.

Implement external provider ID linking field for EHR mapping.

Add doctor photo upload with fallback avatar on empty.

Build active-only doctor list filter scoped to the admin's hospital.

Implement inactive-booking guard refusing slots with an alternatives offer.

Add calendar deactivate that hides its slots without deleting history.

Build staff access note explaining receptionist schedule permissions.

## B4 — Discovery and scheduling truth

Build hospital search with city filter sorted by doctor count and rating.

Implement doctor search by specialty with active-only results.

Build doctor detail card showing specialty, hospital, experience, and rating.

Build hospital detail page with cover stats, doctors, and reviews.

Implement real availability fetcher calling the slot engine only, never mocked.

Add date normalizer handling today, tomorrow, this week, and next week.

Add day-part filter for morning, afternoon, and evening slots.

Implement empty-slots message with three alternative suggestions.

Add typo repair mapping misspelled symptoms to the correct specialty.

Implement did-you-mean prompt when repaired spelling differs from raw input.

Enforce leave blackout so leave days return zero slots with explanation.

Enforce blocked-period exclusion removing meeting windows from results.

Reject past-date requests with today and tomorrow alternatives.

Build top-rated sort using average rating then review count.

Add language filter intersecting doctor languages with patient preference.

Implement exclude-hospital search for outside-X queries without a hospital filter.

Add surname matcher resolving short names to known doctors before availability.

Implement single-retry with repaired spelling after an empty search.

Build slot label formatter rendering weekday, date, and time consistently.

Add session caching for discovery results within one conversation.

## B5 — Booking, reschedule, cancel

Implement book-from-verified-slot using exact engine-returned start and end times.

Add reason capture storing patient-reported text truncated safely.

Wire card-tap booking resolving the slot without retyping.

Add missing-date clarification asking one question before planning tools.

Add missing-doctor clarification requesting specialty or doctor plus date.

Implement yes-book-it confirmation booking the last offered verified slot.

Build my-appointments list showing own visits with status and verified badge.

Build visit-history list with completed and cancelled filter.

Implement reschedule with new-slot revalidation plus verify and notify.

Add reschedule clarification asking which visit and new time preference.

Implement cancel booking calling internal cancel plus EHR cancel.

Add which-visit disambiguation listing two to three upcoming visits.

Enforce double-booking rejection returning coded SLOT_TAKEN with alternatives.

Enforce overlap rejection keeping zero rows for the loser.

Implement idempotency-key dedup returning the same row on retry.

Handle reschedule-to-taken by rejecting and preserving the original booking.

Explain already-cancelled status with a new-booking offer.

Implement mark-completed restricted to doctor and admin roles.

Implement mark-no-show restricted to doctor and admin roles.

Enforce ownership check so patients see only their own appointments.

Enforce cross-tenant denial for hospital admins querying other hospitals.

Add video-mode filter booking only video-compatible doctors and slots.

Truncate overlong reasons safely while still completing verified booking.

Block confirm-without-verify shortcuts with an explanatory refusal.

Build booking receipt showing appointment number plus correlation reference.

## B6 — EHR verify and sync

Implement external patient lookup by name query through the connector.

Implement external provider lookup by name query through the connector.

Build EHR create call attaching the idempotency key header every time.

Implement mandatory read-back verify comparing returned IDs before confirming.

Add external retrieve by ID with matched, not-found, and error outcomes.

Implement external update for time changes followed by re-verify.

Implement external cancel mirroring internal cancel status.

Add external reschedule with revalidation plus update plus verify.

Build mapping view showing internal ID linked to external ID and vendor.

Implement verify-now action reporting matched or opening recovery on mismatch.

Add sync-now setting synced plus confirmed only after matched verification.

Map external 409 conflict to coded SLOT_TAKEN with three alternatives.

Handle missing external patient with admin-fix guidance plus alternatives.

Handle missing external provider with mapping-fix guidance plus alternatives.

Build facility-link display naming the booking's external facility.

## B7 — Recovery, reconciliation, escalation

Implement timeout-after-create simulator creating in EHR then raising timeout.

Build probe-by-idempotency-key querying the EHR list endpoint for the key.

Implement found-path sync storing external ID and marking probe-matched verified.

Implement not-found path opening a reconciliation record with needs-action status.

Build open-reconciliation list restricted to admin roles with references.

Implement resolve-reconciliation transitioning the visit and logging audit.

Handle network failure as unknown outcome with single probe then reconcile.

Handle EHR auth failure marking failed with fix-connection guidance.

Handle rate limiting with wait-and-retry messaging keeping the row safe.

Handle EHR outage by marking unknown plus opening an ops alert.

Handle validation errors by re-asking for clear date plus hour.

Handle mapping errors directing to admin fix with alternative doctor offer.

Map external slot conflict to SLOT_TAKEN without any second write.

Deduplicate rapid double-taps by idempotency key returning one visit.

Treat partial success as unknown outcome with probe before any confirm.

Build unknown-outcome explainer stating sent but reply lost in one line.

Implement transfer-to-human logging a tracked request with reference number.

Implement safe retry with a fresh key only after probe found nothing.

Fire ops alerts to hospital admins on every integration failure.

Build no-duplicate proof view showing one internal row plus one external record.

## B8 — Questionnaire pre-visit

Build pending-questionnaires list with title, status, and fill action.

Implement questionnaire detail rendering questions in order by type.

Add yes-no question renderer saving structured boolean answers.

Add single-choice renderer validating against allowed options.

Add multi-choice renderer saving multi-select arrays.

Implement numeric answer with range validation for scores.

Add date answer normalizing phrases like 10th March to ISO dates.

Build short-text saver storing patient-reported strings verbatim.

Build long-text saver for descriptions without clinical interpretation.

Implement conversational fill asking questions one by one with progress.

Add submit action validating required fields then firing completed workflow.

Build doctor-side answers view restricted to own appointment doctors.

Flag urgent answers escalating per policy plus emergency-services direction.

Refuse diagnosis-from-answers with admin help plus tracked-request offer.

Add finish-form reminder scheduling an in-app notification.

## B9 — Workflows and notifications

Fire appointment-booked workflow auto-assigning forms plus notifications on confirm.

Emit questionnaire-assigned event with title and due hint on booking.

Emit questionnaire-completed event notifying the doctor on submit.

Send patient plus doctor notifications on every cancel.

Send both-side notifications with the new time on every reschedule.

Schedule day-before reminder as an in-app notification record.

Emit EHR start, complete, and fail events with correlation references.

Emit verification-completed events with matched, not-found, or error results.

Emit reconciliation-required events linked to appointments.

Emit human-escalation events with queue plus reference number.

Implement idempotent workflow retry creating a new run without duplicates.

Add conditional reminder step checking confirmed status first.

Build booking-confirmation sender including verified badge plus reference.

Add doctor new-booking ping on every confirmed visit.

Fire hospital ops alerts with error summaries and no secrets on failures.

## B10 — Dashboards, ops, audit

Build patient home with upcoming visits, quick book, forms, and activity.

Implement doctor today view with time, patient, status, and form state.

Build doctor upcoming-week list with calendar hints.

Implement hospital overview cards for visits, doctors, integrations, and alerts.

Build platform ops wall with counts plus health across all entities.

Implement AI activity wall with latency and tool success charts.

Build integration wall with success, fail, and unknown pie data.

Implement appointments table with status-pill filter scoped by tenant.

Build appointment timeline showing created, verified, confirmed, and later moves.

Add verified badge component with method plus timestamp.

Build utilization analytics with booked versus free plus cancellations.

Implement review summary with count, average, distribution, and titles.

Allow completed-only reviews enforcing one per visit target.

Deny raw chat-log access offering aggregate activity instead for privacy.

Surface the timeout demo on reconciliation plus integrations walls with evidence.

## B11 — Voice, telephone, safety

Wire voice orb recording through speech-to-text into the same chat graph.

Implement voice reschedule clarifying visit plus time then speaking confirmation.

Implement voice cancel confirming which visit then speaking the reference.

Build voice next-visit lookup replying short plus showing the on-screen list.

Add barge-in stopping speech on new tap before listening again.

Implement two-second silence auto-stop transcribing partial audio.

Handle empty audio with a tap-and-retry text message and no crash.

Explain microphone-blocked with enable steps plus type-instead fallback.

Narrate long bookings with brief checking patter then spoken result plus card.

Fall back to typing with a safe error when speech services are down.

Verify login identity before reading visits on inbound voice requests.

Refuse diagnosis requests echoing reported words only plus admin offer.

Refuse prescription requests with booking plus tracked-request offer.

Refuse dosage-change questions directing to an in-person doctor visit.

Escalate chest pain plus breathing trouble to emergency services immediately.

Escalate uncontrolled bleeding to emergency services plus tracked request.

Log human requests as tracked with reference and no live-agent promises.

Redirect unrelated questions to appointment help in one brief line.

Acknowledge unsupported capabilities naming the closest available alternative.

Answer greetings listing find, slots, booking, forms, and reminders capability.
