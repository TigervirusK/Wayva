# Real Travel: integration plan and first implemented phase

Research and implementation snapshot: October 25, 2026. This extends the existing TripRescue project; it does not replace its demo, database, saved trips, or AI provider.

## 1. The goal and the essential booking boundary

The goal is to monitor explicitly selected flights, find legitimate replacements, obtain approval for an exact offer, execute through an authorized provider, verify the result, and repair dependent plans without claiming unconfirmed external changes succeeded.

**Tickets do not have to be bought through TripRescue to be saved in Settings.** A traveler can enter details for an existing airline or agency purchase. However, a booking reference and passenger name do not grant TripRescue ticket-servicing authority. The first live integration must establish who issued the ticket, which provider can retrieve/service it, which actions the specific order supports, and whether the traveler is authorized. An unsupported existing ticket uses the original airline/seller handoff; it must not be silently turned into an API-managed order.

An exchange of an existing ticket is different from buying a new ticket. Booking a replacement through another seller does not automatically cancel or refund the original. These must be distinct operations with separate approval and confirmed financial outcomes.

## 2. Inspection of the current application

The existing React/TypeScript/Vite frontend and FastAPI/SQLAlchemy/SQLite backend already support local profiles, saved trips, itinerary editing, local Ollama conversation, reviewed itinerary additions, and the Domino Rescue simulation.

The recovery engine has a saved directed dependency graph, finite fictional alternatives, schedule/budget checks, explicit approval, duplicate protection, and audit history. Its mock execution is atomic within SQLite. That transaction can roll back simulated records; it cannot roll back a real airline sale. The real workflow must have a different execution and reconciliation design.

The existing browser profile token is a local access mechanism. It is not a production account, MFA, identity verification, or an airline authorization. There is no authorized flight-status, flight-booking, hotel-change, pickup-change, payment, or notification provider connected.

## 3. Real booking providers: capability, access, and costs

### Duffel: first candidate for eligible provider-managed orders

Duffel documents order-change search, review, pending change creation, and confirmation. An order must advertise `change` in `available_actions`; some orders cannot be changed through the API. The original order is retrieved before evaluating eligibility. [Changing an order](https://duffel.com/docs/guides/changing-an-order), [order capabilities](https://duffel.com/docs/api/orders).

Change requests are sent to the airline originally booked with and can return zero alternatives. This is not a universal cross-airline exchange service or a way to take control of any externally bought ticket. [Order change requests](https://duffel.com/docs/api/order-change-requests).

Live account activation requires email verification and business/personal/KYC verification. The project's eligibility must be confirmed with Duffel; a university project must not assume that receiving a test key grants commercial live access. [Getting started and verification](https://duffel.com/guides/getting-started).

Published USD pricing reviewed for this plan: $3 per confirmed order; Managed Content 1% of order value; $2 per paid ancillary; excess searches above a 1500:1 search/order ratio cost $0.005 each. Published FX fees are 2% where currency conversion applies. Airfare, airline penalties, payment arrangements, and applicability of fees still require confirmation for the intended account and workflow. Do not assume this list is an all-in price for a rebooking. [Duffel pricing](https://duffel.com/pricing).

The API exposes change totals/currency, penalties, expiry, live/test mode, and `confirmed_at`. Re-fetch the pending change before approval, bind approval to its latest exact total, and retrieve the resulting order after confirmation. An accepted request alone is not enough to claim the new itinerary was confirmed. [Order changes](https://duffel.com/docs/api/order-changes).

**Recommendation:** evaluate Duffel in its test environment first, then request written eligibility for the desired ticket-servicing use case. Treat externally issued tickets as unsupported unless the provider explicitly supplies a documented authorized import/servicing path.

### Travelport: contract-based exchange integration

Travelport's current Air API reference includes GDS exchange eligibility, exchange search, payment/commit, and NDC change/reprice/modify operations. Coverage varies between GDS and NDC; having a general search integration does not establish permission to service every ticket. [Current Air API references](https://support.travelport.com/webhelp/jsonapis/airv11/content/air11/APIReferences.htm).

Running real requests requires provisioned TripServices credentials. Authorization includes organization/access-group information such as PCC and enabled content. Obtain access and servicing requirements from an account manager or sales. [Provisioning](https://developer.travelport.com/resources/devkits-and-downloads), [authentication and access groups](https://developer.travelport.com/docs/getting-started/authentication).

The reviewed official pages do not provide a complete public price for this exchange use case. **Cost: commercial quote required**, including API access, transaction/ticketing arrangements, support, and any carrier requirements. Do not present it as a free hackathon connection.

**Recommendation:** an alternative if a travel agency/consolidator partner already has appropriate provisioned access. It is a larger integration than the initial local project needs.

### Amadeus: avoid relying on legacy Self-Service tutorials

The official Self-Service Python SDK was archived on July 17, 2026. Older official documentation also says issued-ticket modifications require the consolidator rather than those Self-Service APIs. Do not follow old “free API key → automatic ticket exchange” tutorials as a current implementation plan. [Official archived SDK](https://github.com/amadeus4dev/amadeus-python), [legacy booking FAQ](https://admin.developers.amadeus.com/self-service/apis-docs/guides/developer-guides/faq/).

If considering Amadeus, obtain current Enterprise/consolidator access, supported servicing scope, onboarding/certification requirements, and a commercial quote directly. No current applicable Enterprise price or approval has been verified for TripRescue.

### Direct airline or original agency

Existing tickets may need their original issuer. An authorized airline/agency integration could eventually support them, but coverage, servicing authority, identity checks, and costs must be established individually. The implemented fallback uses fixed official airline links and asks the traveler to contact the original seller when appropriate. It never submits forms or automates purchases through consumer websites.

## 4. Flight status is a separate integration

FlightAware AeroAPI supplies flight-status data, not replacement-ticket sales. Its official page lists Personal usage for personal/academic purposes with no minimum and up to $5 monthly usage credit; this is not unlimited free use. Standard includes alerting/business/B2C use with a $100 monthly minimum; Premium has a $1,000 minimum. Per-query/result-set charges and license restrictions apply. [Official AeroAPI tiers and fees](https://www.flightaware.com/commercial/aeroapi/).

For illustration, the listed `/flights/{ident}` rate is $0.005 per result set. Polling one flight every five minutes for 24 hours is 288 requests, or about $1.44 if every call returns one billable set. This is a planning calculation, not a provider quote; pagination, other endpoints, minimums, and licensing can change the total. No paid status calls have been made for this project.

Begin with test fixtures and assess an eligible academic account or another licensed source before enabling any polling. A worker must honor explicit opt-in, the exact operating flight/date/airports, polling windows, deduplicated status changes, provider timestamps, cancellation/delay evidence, call budgets, and unsubscribe. “Immediate” notifications depend on feed latency and polling/delivery; do not promise zero delay.

## 5. Phase R1 implemented now: private settings and assisted Real Travel Mode

- **Settings:** a password-encrypted private traveler vault stores optional ticket-name/contact fields, home airport, country code, preferred currency, and user-entered flight details. A ticket can have an airline, flight number, departure date, route, booking reference, original seller, and an optional owned non-demo trip link.
- **Privacy:** new private details are encrypted at rest using Fernet authenticated encryption with an Argon2id-derived key and a random salt. The password is not stored. Unlock keys have bounded, short-lived process-memory sessions. The browser uses an HttpOnly, SameSite cookie plus its existing profile access header; the app does not put private form data or passwords in browser storage or Pip context. [Fernet](https://cryptography.io/en/latest/fernet/), [Argon2id](https://cryptography.io/en/latest/hazmat/primitives/key-derivation-functions/#argon2id).
- **Controls:** create/unlock, edit/save, remove saved flight entries, lock, automatic timeout, and change password. Mutating routes check browser origin. Private responses are not cacheable; validation errors omit raw submitted inputs. Failed unlock attempts are limited. A backend restart requires unlocking again.
- **Real Travel Mode:** `/rescue/real` reports actual capabilities. All live monitoring/search/rebooking/confirmation/automatic-repair capabilities remain unavailable. Select an entered ticket and prepare an original-seller handoff with official airline links. References and personal details are not embedded in URLs or submitted to a third party.
- **Separation:** the existing demo stays at `/rescue`; real details live in separate encrypted tables and cannot be attached to simulated demo reservations. Saving a ticket never creates a confirmed reservation or changes the itinerary.

Migration `0004_private_traveler` adds only `traveler_vaults` and `traveler_vault_audit`. It changes none of the original trip/recovery tables and seeds no details. Audit records contain access/change metadata, not the private payload.

No passport scan/number, airline password, raw card data, or unnecessary identity information is collected. Additional legally required passenger fields should be requested only through a specific authorized provider workflow, with a clear purpose and consent.

The private-vault phase alone did not provide account authentication. The subsequent [account update](ACCOUNT_SECURITY.md) adds username/password sign-in and explicit linking of existing local profiles. This still does not establish production readiness or airline servicing authority. The vault password remains separate and has no recovery service. Unlinked legacy profiles still depend on their original browser token.

## 6. Remaining small implementation phases

| Phase | Work | Completion evidence / prerequisite |
| --- | --- | --- |
| R2 — production identity and provider contract | Basic username/password accounts and owned cookie sessions are implemented separately. Recovery, MFA where appropriate, action reauthentication, consent, HTTPS, least-privilege access, secret/key management, threat review, and provider eligibility/cost agreements remain. | An owned booking can be linked to a verified authorized user without relying solely on a local browser token. User approves any paid service before activation. |
| R3 — read-only live sources | One status adapter and one authorized inventory/order-read adapter, opt-in tracking, durable worker/outbox, source timestamps, deduplicated disruptions, in-app updates. | Recorded contract tests plus authorized integration checks; no purchase endpoints. API-call budgets and data-license limits enforced. |
| R4 — quote and approval | Provider eligibility, current exact offer, expiry, baggage/fare rules, complete additional charges, impact preview, approval bound to an immutable quote/version/currency and affected order. | Price changes, expiry, no inventory, and unsupported tickets tested. No confirmation is inferred from a quote. |
| R5 — authorized submission and reconciliation | Hosted/tokenized payment, durable operation/idempotency records, single submission, provider confirmation verification, signed events, reconciliation worker, audited uncertain/partial outcomes. | Sandbox success/failure/timeout/duplicate cases pass. A separately authorized, explicitly approved real booking must be verified before claiming live rebooking works. |
| R6 — dependency-aware confirmed repair | Destination timezones, connection/buffer constraints, confirmed flight replacement, proposed versus confirmed downstream changes, independent provider outcomes, pending manual tasks, budget ledger, UI notifications. | A confirmed flight can coexist with a failed pickup/hotel change without falsely reporting a complete repair. |

The first live adapter should be chosen after the provider confirms the external-ticket servicing use case. Until then, entered tickets use the assisted path. Mock contract tests are useful but do not prove production authority, actual inventory, or real ticket issuance.

## 7. Proposed live data and API architecture

Keep the demo data model and atomic mock executor separate. Add reviewed forward migrations for these real-workflow concepts when their phase begins:

- **Provider connections:** account/organization, adapter, test/live environment, granted capabilities, verification timestamp, key-vault reference. Never expose the credential to the frontend or model.
- **Verified booking links:** owner, original issuer, opaque provider order ID, encrypted necessary details, authority proof, provider-confirmed segments and timestamps. User-entered details are not automatically promoted to this table.
- **Tracking subscriptions and source events:** explicit owner consent, exact flight identity, status source, observation time, delivery/event IDs, deduplication key and polling budget.
- **Quotes and approvals:** immutable provider offer, totals/currency/conditions/expiry, impact preview, approval actor/time, request fingerprint.
- **Booking operations and child actions:** unique logical operation key, request hash, state, provider correlation IDs, attempt count, confirmation evidence, unresolved reason, and reconciliation schedule.
- **Outbox/inbox and audit:** durable jobs, verified inbound events, retries only for safe operations, redacted/encrypted necessary evidence and access records.

Use UTC instants plus airport/destination IANA timezones, provider-specific money/currency precision, explicit connection windows, and versioned trip snapshots. Do not reuse a fixed Tokyo offset or one-day arrival-window representation as a general international flight engine.

Suggested future endpoints are owned tracking subscriptions, observed disruptions, provider quotes, quote approval, operation submission/status, provider event callbacks, reconciled confirmation, and downstream repair review. They must expose capabilities from actual connected adapters and order eligibility. A nonblank API key must never be treated as proof that rebooking works.

The initial password-derived local vault cannot support unattended background decryption after its unlock session expires. A production automated workflow will need a separately reviewed, consented encrypted-data/key-management design; migration of private contents requires the user to unlock and authorize it. Do not bypass the local vault password or silently copy its data into jobs.

## 8. Handling failures without blind retries

```text
observed disruption → provider quote → explicit approval → submitting
    ├─ confirmed evidence → flight confirmed → downstream repair actions
    │                                      ├─ all verified → repaired
    │                                      └─ some unresolved → partially repaired
    ├─ known rejection → failed / re-quote
    └─ timeout or uncertain result → outcome unknown → reconciliation
```

Persist the logical operation and its approval before any external side effect. Use a local uniqueness constraint and a durable claimed-job lease to prevent concurrent submissions. Use provider idempotency only where the specific endpoint documents its guarantee; do not assume that sending an invented header makes a purchase safe to retry.

On an uncertain result, do not submit another purchase. Reconcile using provider-supported order/change IDs, correlation metadata, verified events, and read APIs; escalate unresolved ambiguity for manual support. Retrying requires evidence that it is safe and permitted. A lost response is not proof that a charge failed.

If a flight is confirmed but a hotel modification fails, preserve the confirmed flight, record the hotel as unresolved, and show the next options. Do not simulate rolling back the airline sale with a database rollback. Do not automatically cancel/refund a successful booking to compensate without separate authorization and confirmed provider support.

## 9. Tests required before each live capability

Keep all automated tests isolated from the user's database and paid endpoints. Cover order ownership, test/live separation, explicit consent, encryption/tamper rejection, expired auth, safe validation errors, no private AI context, provider eligibility, quote expiry and price change, no inventory, baggage/fare rendering, exact approval binding, payment failure, confirmed booking retrieval, duplicate requests, concurrent jobs, crash/restart, timeout with eventual confirmation, webhook signature/replay/out-of-order events, and reconciliation.

For downstream repair, cover timezone/date boundaries, missed connections, conflicts, budget/currency precision, unchangeable reservations, mixed provider outcomes, and notifications that say exactly which actions are confirmed versus unresolved. No automated test should purchase a real ticket. No public deployment or paid provider activation is authorized by this implementation.

## 10. What the user should do next

1. Open Settings → Private traveler details. Create a strong vault password and keep it safe.
2. Save only the contact and existing-ticket details you need. An entry is unverified; this does not book or change anything.
3. Open Real Travel Mode to prepare the original-seller handoff. Keep using Demo Mode to demonstrate the connected recovery engine.
4. Before paid/live integration, identify the original ticket sellers to support and obtain written provider confirmation of servicing authority, commercial eligibility, and costs. Do not paste provider keys or booking references into chat.
5. Approve a specific provider budget and later a specific real transaction before either can incur charges. Until those gates are met, real rebooking remains unavailable.

## 11. Verification of the implemented first phase

- The full backend suite ran: **372 passed**, with the existing upstream deprecation warning. The owner-binding encryption case was also run separately after making its fixture selection deterministic.
- The frontend TypeScript/Vite production build passed.
- Nine browser checks passed against an isolated database, with no browser JavaScript errors. They exercised vault creation, actual save/reopen, absence of automatic private browser storage, cross-tab lock, wrong passwords, client expiry, password rotation, seller handoff, entry removal, mode separation, and the preserved demo cancellation/approved repair flow.
- Seven accessibility scans detected no violations at desktop and phone widths, including 320 pixels. These automated checks do not replace a complete accessibility or security audit.
- The main website serves Settings and Real Travel Mode, and its API reports `assisted_only`, no connected provider, and rebooking disabled.
- Every row in all nine pre-existing application tables was unchanged after migration. A backup is `.artifacts/real-travel/before-private-traveler.db`; QA data was isolated.
- Paid provider calls: **zero**. Real booking actions: **zero**. Public deployment: **none**. These checks do not verify real flight search, monitoring, or rebooking.

Key implementation files: `backend/app/services/traveler_vault.py`, `backend/app/services/real_travel.py`, `backend/app/api/traveler.py`, `backend/app/schemas/traveler.py`, `backend/app/models.py`, `backend/alembic/versions/0004_private_traveler.py`, `backend/tests/test_traveler_vault.py`, and `frontend/src/features/traveler/`. Existing app routes, Settings, and the demo page were extended to expose the new phase. The only new direct backend dependency is `cryptography==50.0.2`.

To start the existing local services:

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-triprescue.ps1 -OpenBrowser
```

The additive migration has been applied on this computer. On a separate checkout, install the updated backend requirements and run `python -m alembic upgrade head` in the backend virtual environment before starting it.
