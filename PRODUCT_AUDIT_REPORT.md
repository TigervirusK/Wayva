# TripRescue product audit and fixes

Completed October 25, 2026. This report describes a local development application, not a public production release. Existing architecture, accounts, trips, and private data were preserved.

## A. What was audited

| Area | Verified status after this pass |
| --- | --- |
| Landing page/navigation | Working; desktop and phone routes checked. Future-feature labels remain visible on tablets. |
| Accounts | Registration, sign-in/out, duplicate/invalid credentials, hashing, cookie/session proof, expiry, password changes, ownership, and explicit legacy linking covered by backend tests. Browser checks cover registration, protected trip access, sign-in persistence, and account isolation. |
| Saved trips | Creation and editing, dates, travelers, currencies, budgets, persistence, invalid inputs, and ownership covered by tests. Browser flow creates a trip through the form. |
| Itinerary management | Add/edit/reschedule/cancel/remove and conflict validation work. Browser flow verifies saved state and budget changes. |
| Pip/general chat | Real local Qwen conversation verified separately from deterministic mocks. Trip facts now include backend-calculated inclusive dates and budget scopes. Generated advice still needs real-world verification. |
| AI itinerary flow | Actual review cards, revision, replacement, approval, rejection, stale checks, ownership, persistence, and duplicate-approval protection verified. |
| Tokyo regression | Real local model produced a six-day, 24-stop draft for two travelers, within the 09:00–21:00 window. Backend checks geography/reference coverage, buffers, dates, duplicates, and arithmetic. Real revision, approval, sign-in persistence, and rejection also ran. |
| Domino Rescue | Existing fictional cancellation/dependency graph/options/approval/rollback/history preserved and exercised through the browser and backend tests. |
| Traveler Vault | Encryption, ownership, incorrect passwords, save/edit, revision control, locking, timeout, password changes, and sensitive-data handling tested. Browser flow saves fictional contact/ticket details and prepares a manual handoff. |
| Real Travel assistance | Assisted-only, entered/unverified ticket details, fixed official links, and external manual actions remain clearly separated from the simulation. No live provider was invented. |
| SideQuest | Preview/conversation starter; dedicated location/route/time-window tools are not implemented. |
| Group Harmony | Preview/conversation starter; member management and explainable fairness scoring are not implemented. |
| SplitQuest | Preview/conversation starter; subgroup schedules and reunion feasibility are not implemented. |
| Security/reliability | Authorization, unsafe AI output, validation, body size, concurrent local inference, session revocation during generation, dependency advisories, XSS-safe rendering, and fixed external-reference links reviewed/tested. This is not a penetration-test certification. |

The project remains React/TypeScript/Vite/Tailwind in `frontend/`, FastAPI/SQLAlchemy/SQLite/Alembic in `backend/`, and local Ollama/Qwen for AI. Fifteen application tables and the existing API families remain in place. See [the current status guide](TRIPRESCUE_CURRENT_STATUS.md) for the full page/API/database inventory.

## B. Confirmed problems and their causes

| Problem | Severity | Root cause | Main files |
| --- | --- | --- | --- |
| A proposal could be stored after its account session was revoked while the model was running. | High | Authorization ran before the asynchronous generation, without a fresh session check under the final write lock. | `api/buddy.py`, `api/planning.py`, `services/planning.py`, `services/accounts.py`, `services/trips.py`. |
| Gion could be proposed for Tokyo; Omoide Yokocho could be mislabeled as Shibuya. | High product accuracy | Model instructions were the only geographic safeguard; there was no independent place-reference report. | New `services/travel_quality.py`, `data/place_references.json`, local/cloud planning adapters. |
| Requested time windows, transfer buffers, and repeated attractions were insufficiently checked. | High product accuracy | Date/overlap checks existed, but a non-overlapping plan could still violate the user's hours or leave no travel time. | `travel_quality.py`, new `compact_planning.py`, `planning.py`. |
| Local Qwen used an entire day's window as individual visit times and sometimes described a draft without returning one. | High product reliability | Long free-form schedule generation and optional planning data were unreliable for the small model. Repeating the malformed draft in correction prompts did not reliably repair it. | `ollama_ai.py`, `compact_planning.py`. |
| Prose could assert a total unrelated to the line-item sum. | Medium | Model-written summaries were shown alongside calculated totals without a deterministic summary. | `planning.py`, proposal review card. |
| Unsupported restaurant costs could look like venue quotes. | Medium | Generic estimate disclaimers did not distinguish a whole-group allowance from an actual menu price. | Reference/quality services and proposal UI. |
| A one-meal request could become an obligation for every trip day; traveler counts could look like requested sightseeing counts. | Medium | Broad word matching in the direct/demo daily-coverage helper. | `daily_planning.py`. |
| Backend and frontend disagreed at the maximum trip-duration boundary. | Medium | Backend counted elapsed days; frontend counted dates inclusively. | `schemas/trips.py`. |
| Current vault-password input lacked the new-password length bound. | Medium | The change-password schema did not reuse the password validator. | `schemas/traveler.py`. |
| API bodies and simultaneous local generations lacked overall bounds. | Medium | Field-level validators did not prevent oversized parsing or concurrent GPU requests. | New `api/body_limit.py`, `main.py`, `ollama_ai.py`. |
| Three trip/dashboard text styles fell just below required contrast. | Medium accessibility | Muted green text on pale green surfaces produced ratios around 4.4:1. | `features/trips/trips.css`. |
| Some account and authentication-error copy still described browser-only profiles. | Low | Copy had not fully caught up with the earlier account update. | Trip/account-related UI and API clients. |
| Several backend/tooling packages had published advisories. | High maintenance/security | Old FastAPI constrained an old Starlette; pytest and pip were also outdated. Some advisory records describe API paths the app does not use, but the affected versions still needed replacement. | Backend requirements and project virtual environment. |

The first ten new product regressions were run against the original implementation and failed as expected. The evidence is `.artifacts/product-audit/confirmed-regressions-before.txt`. Assertions were not removed to manufacture success. One existing mocked-provider fixture gained the new semantic-intent response; its invalid-draft, correction, pending-state, and approval assertions remain, with an additional provider-call-count assertion.

## C. What changed

### Local AI selects; the backend schedules and calculates

For destinations covered by the reference index, a small model request first classifies whether the conversation calls for an answer, a clarification, or a draft. This decision uses the conversation's meaning rather than a list of planning command words.

For a draft, Qwen scores the supplied sightseeing/meal IDs and selects requested dates and counts. The backend selects distinct positively ranked sights, prefers matching areas when possible, counts fixed saved activities, preserves saved blocks, and assigns visit slots. It leaves at least thirty minutes between stops, or sixty minutes between different indexed areas. These are conservative planning allowances, not verified transport times. Long inter-city hops in a single day are refused by this limited planner.

The backend rejects invalid IDs/categories, dates, missing requested coverage, geographic contradictions, excessive visit durations, unavailable time slots, and budget violations. A limited correction loop can request revised model data. A failed generation does not silently become a demo or a different provider's response.

For partial draft revisions, unchanged dates are retained. The cost divisor uses the full draft counts so revising one day does not allocate the whole trip's allowance to that one day. Model text cannot substitute for a real review card. Existing saved itinerary edits still use the manual controls.

Local structured requests use non-reasoning output to reserve tokens for useful data, with at least a 16,384-token context for selected-trip planning. General local text uses the configured context. Planning/corrections remain bounded by the existing 240-second overall deadline. Only one local inference request per backend process runs at a time; others receive a retryable busy response.

### Honest geography and spending

`backend/app/data/place_references.json` is a small manually maintained identity/city/area index, reviewed for this audit. It is not worldwide geocoding or live restaurant discovery. Entries link to official tourism/venue sources, including [GO TOKYO's Omoide Yokocho listing](https://www.gotokyo.org/en/spot/63/index.html), [Kyoto City's Gion guide](https://kyoto.travel/en/areas/gion-kiyomizu/), and [the official Tsukiji Outer Market site](https://www.tsukiji.or.jp/english/).

The review card distinguishes a named reference match, an area-only reference, and an unverified place. Matching an area never verifies an invented business there. Strict city-only drafts must have reference coverage. The specifically problematic Sushi Saito suggestion is blocked without a verified provider quote; no new price was fabricated for it. The index can be extended with reviewed sources without adding a city-specific canned itinerary.

Budget sums and category breakdowns use backend decimal arithmetic. Model-written arithmetic is replaced in the proposal summary. The review shows whole-group totals, an approximate per-person division, category allowances, exclusions, references, and warnings.

For reference-backed ranked plans, standard illustrative envelopes allocate 10% of the remaining saved budget across sightseeing and 20% across meals, rounded down to cents. An explicitly cheaper/economy draft uses 5% and 10%. These are transparent **spending envelopes**, not what a restaurant will charge, an admission fee, or a currency conversion. The remainder is not proof that flights and lodging will fit. Actual prices, business hours, availability, dietary suitability, and routes still require verification.

### Security and compatibility

The generation endpoints recheck authorization after inference, under the write lock, using freshly loaded session state. They do not refresh activity by committing halfway through that lock. Revocation during generation prevents proposal persistence.

JSON API bodies are capped at 128 KiB, including streamed bodies. The vault's current password is length-bounded, and errors continue to omit raw submitted private inputs. React still renders model HTML as escaped text. New reference links require HTTPS, no embedded credentials, and an approved reference host, including when a proposal comes from browser storage.

Published [OSV](https://google.github.io/osv.dev/api/) advisory results prompted these compatible pinned updates: FastAPI `0.162.0`, Starlette `1.10.0`, and pytest `9.1.1`. The project virtual environment's pip was updated to `26.2.2`. No new application feature dependency or paid service was added; dependencies required by the patched packages were resolved normally. A subsequent scan found no advisories for the installed backend package versions.

No migration was required. New quality reports and constraints use the existing proposal JSON payload. Old proposals without those fields remain readable. Existing private-vault encryption and account password protections were retained.

## D. Checks actually run

| Check | Actual result |
| --- | --- |
| Original backend baseline | 396 passed; one upstream warning. |
| Original frontend production build | Passed. No frontend unit-test script existed at baseline. |
| Final backend suite | 426 passed; one upstream Starlette test-client deprecation warning. Includes existing API integration tests and thirty new product/planning regression cases. |
| Frontend unit tests | Four passed: inclusive/invalid dates, exact money display, unsafe reference URLs, and corrupt quality metadata. |
| Frontend production build | Passed: TypeScript plus Vite. |
| Browser product flows | Eleven passed against an isolated database. AI decisions were explicitly mocked; backend validation, ownership, persistence, forms, approval, vault, and recovery operations were real. |
| Browser accessibility/layout | 41 scans; no detected violations or horizontal page overflow; desktop 1440, phone 390/320. Thirteen routes including an unknown-page recovery were checked at each width, plus proposal-review states. No browser JavaScript errors reported. |
| Real local model | Separate actual Qwen test: six-day draft, geographic explanation, partial cheaper revision, approval exactly once, sign-out/sign-in persistence, and rejection without saved items. |
| npm dependency audit | Zero reported vulnerabilities across installed frontend dependency metadata. |
| Backend OSV version audit | Zero findings after patching; 34 installed packages queried. This does not certify custom code or future package safety. |
| `pip check` | No broken requirements at the dependency review. |
| Data preservation | All sixteen existing tables including Alembic bookkeeping preserved; no rows added/deleted by this audit in the application database. Only routine `account_sessions.last_seen_at` activity timestamps changed while the browser was open. All other fields/records compared to the pre-audit backup matched; foreign-key check passed. |

Commands used from the project root:

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon"
.\backend\.venv\Scripts\python.exe -m pytest -q .\backend\tests
.\backend\.venv\Scripts\python.exe -m pip check
.\backend\.venv\Scripts\python.exe .\.tools\audit-dependencies.py
Set-Location -LiteralPath .\frontend
$env:Path = (Resolve-Path '..\.tools\node').Path + ';' + $env:Path
npm.cmd test
npm.cmd run build
npm.cmd audit
```

The implementation checks used the backend directory for Pytest. The explicit test-path command above works from the project root too.

Evidence is under `.artifacts/product-audit/`: baseline results, the initially failing regressions, `backend-after.txt`, `browser-results.json`, screenshots, `real-model-results.json`, provider-response fixtures from the fictional local-model scenario, npm/OSV results, a source fingerprint, and data comparison. Earlier failed model attempts are retained separately; they are not presented as successful tests. `real-model-results.json` distinguishes the initial draft timing from the additional explanation/revision/rejection calls.

The pre-audit database backup is `.artifacts/product-audit/before-audit.db`. QA databases contain only fictional records and were not pointed at the user's database. No paid inference request, purchase, real cancellation/rebooking, or public deployment occurred.

## E. Remaining limitations

| Category | What remains |
| --- | --- |
| Fixed | Reproduced authorization, geographic contradiction, time-window, buffer, duration, duplicate-sight, arithmetic-display, input-bound, inclusive-date, contrast, and stale-copy issues described above. |
| Partially fixed | Travel accuracy: the limited index constrains reference-backed planning; worldwide place identity, routes, operating hours, real prices, and availability are not independently verified. Ordinary model prose can still be wrong. |
| Partially fixed | Natural conversation: real representative requests now work, but ambiguous instructions, very long trips, unsupported time-window wording, tight schedules, or insufficient positively ranked reference choices can still require clarification or fail safely. |
| Not implemented | Whole new trip creation through chat; editing/removing already-saved activities through chat; permanent preference memory/history; dedicated SideQuest/group/subgroup workflows; voice. |
| Requires external integration | Real flight status, ticket servicing authority, live inventory/quotes, purchases/refunds, provider confirmations, real routing, and verified venue information. Entered ticket details do not supply that authority. |
| Not verified | Every possible prompt/destination/device, a comprehensive penetration test, public hosting, TLS/proxy operations, backup restoration drills, production load, provider contracts, and production incident handling. External airline link domains are fixed/official; bot access or provider changes can still make a particular destination page unavailable. |

A finite reference index cannot supply unlimited distinct attractions for long trips. Ask for fewer stops, a shorter date range, explicitly permitted revisits, or expanded reviewed coverage. Do not read a passing Tokyo regression as proof that all destinations and future travel facts are correct.

## F. What to do next

Start the local application:

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-triprescue.ps1 -OpenBrowser
```

Open [TripRescue](http://127.0.0.1:5173/) and sign in through [My Account](http://127.0.0.1:5173/account). A backend restart locks any previously unlocked private vault; it does not change its password or contents.

For a manual check, create a fictional trip named Tokyo Adventure 2027, destination Tokyo, Japan, departure Columbus, Ohio, USA, May 1–6, 2027, two travelers, USD 3,000. Select it in Pip and send:

> Plan a relaxed six-day Tokyo vacation for two people. Include Japanese food, photography, anime, Shibuya, Asakusa, Akihabara, and Shinjuku. Keep activities between 9 AM and 9 PM. Stay within Tokyo and our $3,000 total budget. Do not save anything until I approve.

Inspect **Place checks, costs & assumptions**, the group budget, all six dates, and the actual **Approve and save** / **Reject proposal** controls. Ask “Keep all other days the same. Make just the first day cheaper.” Verify that the draft changes before approving. Refresh or sign out/in after approval and reopen the saved itinerary.

Then try [Domino Rescue](http://127.0.0.1:5173/rescue): open a demo, cancel its fictional flight, compare choices, review one, and explicitly approve. Use a fresh demo to show failure rollback. In Settings, use fictional vault details to inspect Real Travel assistance; it will not rebook a real ticket.

## G. Production readiness

**TripRescue is not ready for public production deployment.** It is a stronger, tested local hackathon application with clear action boundaries and demonstrable saved workflows.

Before publishing, complete production identity/recovery decisions, HTTPS/cookie/proxy configuration, deployment isolation and rate controls, operational backups and recovery, monitoring, abuse/load testing, dependency maintenance, privacy/retention controls, and an independent security review. External booking features also require provider permission, exact quotes, approval bound to those quotes, payment handling, verified confirmations, and reconciliation after partial external failures. The [real-travel plan](REAL_TRAVEL_INTEGRATION_PLAN.md) describes that separate integration work.
