# TripRescue

**Your Trip. Your People. Your AI Buddy.**

A university hackathon travel companion with **Pip the floating buddy, saved trips, reviewed itinerary proposals, and Domino Rescue**. Pip supports **free local AI through Ollama**, with no API key or paid inference service. Optional OpenAI and explicitly labeled offline demo modes remain available.

## Username-and-password accounts

**Product audit update:** local reference-backed planning now uses AI-ranked places with backend scheduling, explicit group spending envelopes, place/area checks, supported daily windows, and saved-block protection. Review **Place checks, costs & assumptions** before approval. The source index is limited; prices, routes, hours, and availability are unverified. Full findings and current verification are in [PRODUCT_AUDIT_REPORT.md](PRODUCT_AUDIT_REPORT.md): 426 backend tests, four frontend unit tests, production build, eleven browser workflows/41 accessibility scans, and a separate actual-model Tokyo planning/revision/approval/rejection flow. This remains a local hackathon application, not a production-ready public service.

Open **http://127.0.0.1:5173/account** in the same browser where your saved trips appear. Choose **Create account**, leave **Keep my current profile and saved data** selected, and choose your own username and a unique passphrase of at least 15 characters. The account keeps the existing owner ID, trips, itinerary, proposals, recovery records, and encrypted vault. Your separate vault password stays unchanged.

Passwords are salted Argon2id hashes in the existing SQLite database. Sign-in uses HttpOnly cookie sessions with backend ownership checks, session-specific request proof, guessing limits, expiry, sign-out, and password changes. You can sign in from another browser that reaches this same server. Account recovery, MFA, public hosting, and permanent account chat history are unfinished. See [ACCOUNT_SECURITY.md](ACCOUNT_SECURITY.md) for the complete guide and actual checks.

## Private traveler settings and Real Travel assistance

Open **http://127.0.0.1:5173/settings** and find **Private traveler details**. Create a separate vault password of at least 12 characters, keep it safe, and save the contact and existing-ticket details you want to keep locally. You can enter tickets bought directly from an airline or through another seller; they do not have to be bought through TripRescue.

The vault supports name/contact details, home airport/country codes, preferred currency, and up to twenty flight entries with route/date/number, booking reference, original seller, and optional owned non-demo trip link. These entries are **user-entered and not provider-verified**. Saving, editing, or removing one never purchases, changes, or cancels a ticket.

New private payloads are encrypted at rest with a password-derived key. They are not automatically sent to Pip, booking providers, local storage, or session storage. Unlock sessions expire within fifteen minutes; locking clears the displayed fields, and a backend restart requires unlocking again. A password change preserves saved contents. No passport, card, or airline-password fields are collected. **There is no vault password recovery:** keep the password safe. The vault password remains separate from the new account sign-in password.

Open **http://127.0.0.1:5173/rescue/real** to select a saved ticket and prepare an assisted original-seller handoff. Official airline links contain no personal details or booking reference. Live status monitoring, inventory search, rebooking, payments, provider confirmations, and automatic real-itinerary repair remain unavailable because no authorized live provider is connected. Demo Mode remains separate at `/rescue`.

The sourced provider comparison, current costs, commercial requirements, phased implementation, and partial-failure design are in [REAL_TRAVEL_INTEGRATION_PLAN.md](REAL_TRAVEL_INTEGRATION_PLAN.md). This phase makes no paid provider calls and does not deploy publicly. Entering a booking reference is not a grant of airline servicing authority.

## Try Domino Rescue

Open **http://127.0.0.1:5173/rescue** while the servers are running. Sign in or create an account, then:

1. Choose **Open rescue demo**. This creates or reopens a separate fictional Tokyo trip; it does not seed bookings into your existing trips.
2. Choose **Simulate flight cancellation**. Follow the chain: Chicago–Tokyo flight → airport pickup → hotel check-in → walking tour.
3. Choose **Compare recovery options**. Compare the fastest (+$435), balanced (+$250), and cheapest (+$80) fictional alternatives. These are demo amounts, not live fares. The backend checks the saved budget, itinerary overlaps, buffers, and ten hours of rest before the tour.
4. Choose **Review this option**. Inspect each before/after time and additional cost, check the approval box, then choose **Approve & apply simulated repair**.
5. Open the saved itinerary or refresh. Mock reservation changes, linked itinerary updates, approval, and execution history persist. Repeated approval cannot execute twice.

The optional provider-failure checkbox demonstrates an unsuccessful mock pickup change: the repair batch is rolled back, the cancellation stays open, and the failure is recorded. Choose another option afterward. **Create fresh demo** adds a new fictional trip and preserves the earlier trip and its history.

This is TripRescue's own recovery engine and visual workflow. It runs without an AI provider or API key. Pip can discuss the selected trip's read-only recovery facts; the workspace performs deterministic checks and requires explicit approval. Model explanations may still make mistakes: review the structured schedules and costs before approving.

Only the fictional flight-cancellation scenario is supported. There is no live monitoring, airline access, payment, refund, or real rebooking. See [DOMINO_RESCUE.md](DOMINO_RESCUE.md) for implementation details and limitations.

## Free local AI and the updated design

The selected local model is `qwen3:4b-q4_K_M`. On this computer, the Ollama runtime is in `.tools/ollama` and its downloaded model is in `.tools/ollama-models`. The launcher binds Ollama to this computer and disables its cloud features. Local prompts stay with the local model; no paid provider is contacted in `AI_MODE=ollama`.

Start the local AI, backend, and website together:

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-triprescue.ps1 -OpenBrowser
```

This starts missing services in hidden windows and reuses running ones. It does not reset or migrate the database. The execution-policy override applies only to that PowerShell process. Runtime logs are in `.artifacts/runtime`.

If the model is missing, download it once (about 2.6 GB), then select the local provider:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local-ai.ps1 -DownloadModel
.\backend\.venv\Scripts\python.exe .\backend\configure_local_ai.py
```

Restart a running backend after changing its provider. For a new computer without the project-local runtime, install [Ollama for Windows](https://docs.ollama.com/windows) first, then run the setup above. The script can use an installed `ollama.exe` as well.

The visual refresh adds contour-map backgrounds, warm paper surfaces, a framed destination photo, travel-journal details, terracotta accents, a forest-green journey section, and refined navigation/workspace cards. Domino Rescue now has its own connected simulation; group tools and real booking integrations remain unfinished.

Local inference has no API usage charges or key requirement. It uses your computer's memory/GPU and can be slower or less capable than a large hosted model. No model can guarantee every answer or every requested action; saved itinerary changes still require validation and approval.

Earlier account verification (October 25, 2026): **396 backend tests passed**, the frontend production build passed, and eleven account browser checks passed with eight accessibility scans detecting no violations. The account checks include original-profile linking, encrypted-vault continuity, another browser signing in, ownership isolation, password changes, and the preserved demo repair flow. Earlier private-settings verification also passed nine browser checks and seven accessibility scans. All pre-existing application records were unchanged after the additive migration. Earlier real local inference was verified through the website and in a separate one-day itinerary approval test with two sightseeing stops plus lunch and dinner. That itinerary test took about 64 seconds; longer local plans may need more time or shorter requests. See [TRIPRESCUE_CURRENT_STATUS.md](TRIPRESCUE_CURRENT_STATUS.md) for detailed evidence.

Local planning uses a constrained JSON response with saved-date/time/cost formatting. Semantically invalid drafts can receive up to two same-model corrections with specific validation feedback, within an overall 240-second planning budget. Invalid schemas or unsupported actions are rejected rather than normalized into success. No remote or paid fallback is used.

## What works now

- Responsive landing page with TripRescue branding, a local destination photograph, and an interactive overview of the six planned features.
- Pip, an animated floating companion on every page. Click Pip to open typed chat, minimize it while browsing, or reopen it without losing the current conversation.
- Travel conversation starters plus a working Domino Rescue entry from the landing page, workspace navigation, trip details, and Pip.
- Domino Rescue's persisted dependency graph, cancellation simulation, three coordinated recovery choices, explicit approval, atomic mock execution, and audit trail.
- Password-encrypted private traveler settings and user-entered existing flight details, with lock/unlock, timeout, password changes, ownership checks, and a separate assisted Real Travel Mode.
- A real backend chat endpoint supporting **local Ollama AI**, optional **OpenAI**, and clearly labeled deterministic **demo chat**.
- In live mode, Pip interprets conversation and follow-ups with the model instead of matching a list of command words. It can answer normally or prepare a validated itinerary draft for review.
- Username-and-password accounts, explicit linking of existing local profiles, sign-in/out, password changes, owned saved trips, editable trip details, and chronological itinerary activities that survive a page refresh.
- Add, edit, reschedule, cancel, and remove itinerary activities, with server-side schedule validation and budget totals.
- Pip uses the selected trip's destination, dates, travelers, budget, and existing activities to propose itinerary additions. Suggestions become saved activities only after **Approve and save**.
- Structured proposal cards, rejection without itinerary changes, protection against stale plans, and approval that cannot execute twice.
- Working navigation to Overview, My Trips, Domino Rescue, AI Travel Buddy, Explore / SideQuest, Groups, and Settings. Unknown addresses have a recovery link.
- A live frontend connection check, including loading, error, and retry states.
- FastAPI health endpoint and interactive API documentation.
- SQLAlchemy engine, model base, request sessions, and a persistent SQLite file with foreign-key enforcement.
- Environment templates, ignored secrets and generated files, and isolated backend tests.

**Not implemented yet:** account recovery, MFA, public hosting/cloud sync, persistent preference memory, group scoring, maps, real booking actions, structured destination discovery, and creating a new saved trip entirely from chat. AI itinerary proposals use the selected local or cloud provider. OpenAI requires its own valid key; local Ollama, manual saved trips, and the recovery simulation do not.

## Ask Pip for an itinerary

1. Open an existing trip, or pick it in Pip's **Plan for** menu.
2. Send **“Create an itinerary with food, nature, and photography.”** Common itinerary misspellings are accepted too. For a fuller schedule, try **“For each day I want multiple places to visit, plus places for lunch and dinner.”** Informal requests such as “I wanna” and meal follow-ups are supported.
3. Review the day-by-day suggestions, estimated additional spending, and remaining budget.
4. Choose **Approve and save** to add the activities, or **Reject proposal** to keep your itinerary unchanged.

Existing activities are preserved. Approval rechecks ownership, the saved trip, schedule overlaps, and the budget. If you edited the trip after generation, the old proposal becomes stale and you must generate a fresh one. Repeated approval does not duplicate activities. Pending proposals are stored separately and recent pending reviews return when reopening Pip after refresh.

In live mode, use your own wording. Follow up with “somewhere cheaper for dinner,” “less walking,” or “why that place?” without repeating the destination and dates. Pip sees the current valid unsaved draft and recent conversation. A revised draft replaces the older pending versions; those versions cannot be approved afterward. Ordinary questions do not automatically create another proposal. This tool proposes additions and revises unsaved drafts; changing or removing already-saved activities still uses the itinerary controls.

Generation currently supports trips of up to 21 days and proposals with at most 120 activities. A request for multiple activities plus lunch and dinner each day counts your saved sightseeing stops toward the daily schedule and proposes missing stops and meals. Full schedules or insufficient budgets produce an explanation instead of silently dropping requested meals. Suggested prices, opening hours, and travel timing are unverified estimates. Chat has no reservation or purchasing actions; mock reservation changes use the separate approved Domino Rescue workflow.

**Mode matters:** Ollama and OpenAI generate model responses. Local cards say **“Local AI proposal.”** Demo mode offers a deterministic curated Tokyo/Kyoto example, clearly labeled **“Curated demo · not AI.”** Unsupported demo destinations show the setup requirement rather than invented recommendations. A failed AI request never silently becomes a demo response or another provider's request.

## Save your first trip

1. Open **My Account** and create an account or sign in. Keep the current profile/data option checked when linking an existing local profile.
2. Choose **New trip** or **Create your first trip**. Enter a name, destination, dates, traveler count, total budget, and currency, then choose **Save trip**.
3. On the trip details page, choose **Add activity**. Enter its date, start/end times, title, and estimated cost, then save it.
4. Refresh the page. The profile, trip, and activity will still be there.
5. Click Pip and ask **“What is my budget?”** or **“Show my itinerary.”** The buddy reads the selected trip from the backend.

Use **Edit trip** to change the trip, or an activity's **Edit** control to reschedule it. **Remove** asks for confirmation before deleting that activity from the itinerary. Marking an activity **Cancelled** keeps the saved item but removes it from estimated spending and schedule conflicts. Neither action cancels a real-world booking. There is no trip deletion control in this phase.

Activities must stay within the trip dates and end after they start on the same day. Planned activities cannot overlap. Currency stays fixed while itinerary items exist, so existing estimated costs cannot accidentally be relabeled as another currency. The budget applies to the whole trip; all activity estimates use that trip's currency. Times are local to the destination, without live routing or opening-hour verification.

The dashboard shows saved current/upcoming trips using the browser's calendar. Its first planned activity is chosen by date, without pretending to convert between the browser's timezone and the destination's timezone.

Account access uses a server-validated HttpOnly cookie and an in-memory session proof. Passwords and raw account cookies are not stored by the application in local/session storage. Clearing browser storage does not delete saved account records; sign in again if necessary. Unlinked legacy profiles still depend on their browser token until explicitly connected to an account. Your display name can be changed in **Settings**. Password recovery is not implemented.

## Talk to Pip

Pip floats **inside the TripRescue website**, rather than over other desktop applications. Click the character in the lower-right corner, the landing page's **Meet your travel buddy** button, or **Talk to Pip about this** on a feature card.

Type a message and press **Enter** to send. **Shift+Enter** inserts a new line. The chat shows loading and error states; failed messages can be retried. **Escape** or the minimize control closes the panel. **New chat** clears this visit's conversation. Microphone and voice features are not included in this update.

Chat threads and unsent text are stored in this tab's `sessionStorage`, separately for each local profile and selected trip, including General chat. Refreshing or switching trips restores that thread instead of mixing conversations. **New chat** clears the current conversation and keeps it clear after refresh; it does not delete saved trips or reject a pending proposal. Chat is not saved to SQLite or persistent local storage. The cache is bounded to 40 messages per thread and 12 recent threads; old messages/threads may be dropped. Clearing tab storage loses this chat history. A pending reply from the previous trip is discarded when switching context.

Only bounded recent conversation is sent to the backend. It verifies trip ownership before contacting the selected provider. AI selected-trip conversation receives up to 200 planned activities and the latest owned pending draft whose fingerprint still matches the saved trip. Truncated schedules can be discussed but cannot generate a plan around invisible activities. Demo factual conversation uses up to 30 planned activities. General chat can brainstorm without a selected trip but has no saved-trip proposal tool. Profile tokens and unrelated trips are excluded from AI context and the chat cache. Ollama mode calls only the configured loopback server; OpenAI mode sends context to OpenAI; demo mode does not call a model. Generation saves a proposal record, never itinerary activities before approval.

Local selected-trip chat uses [Ollama structured output](https://docs.ollama.com/capabilities/structured-outputs): the model returns a normal answer or a complete plan in a constrained JSON response. Its generation schema restricts dates to the saved trip and enforces date/time/cost formatting; application services still check scheduling and budgets. Optional OpenAI mode uses one allowed [function-calling](https://developers.openai.com/api/docs/guides/function-calling) tool, `propose_itinerary`. Both paths keep approvals in the backend. No approval, deletion, booking, or arbitrary function execution tool is exposed to either model. Trip changes during generation are detected before storing a proposal. Draft supersession uses the existing proposal JSON payload, so no database migration or reset is required.

The demo is **not a general-purpose AI model**. It reports saved trip facts, gathers a travel brief, explains future tools, and produces curated examples. Only explicit proposal approval can add those activities; chat cannot claim a preference was remembered for future visits or a real reservation changed.

## Start the application on this computer

Dependencies have already been installed into `backend/.venv` and `frontend/node_modules`. A project-local Node.js runtime is available under `.tools/node`; it does not change the computer's system PATH.

Open **two PowerShell terminals**. Leave each running while using the application. Virtual-environment activation and PowerShell execution-policy changes are unnecessary.

**Terminal 1 — backend**

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon\backend"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — frontend**

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon\frontend"
if (Test-Path -LiteralPath "..\.tools\node\node.exe") {
    $env:Path = (Resolve-Path -LiteralPath "..\.tools\node").Path + ";" + $env:Path
}
npm.cmd run dev
```

Open **http://127.0.0.1:5173**. The Settings page should report that the backend and database are connected.

- Backend health: http://127.0.0.1:8000/api/health
- Interactive API documentation: http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json
- Chat mode: http://127.0.0.1:8000/api/buddy/config

Press **Ctrl+C** in each terminal to stop its server. These commands do not delete data.

## Install or recreate dependencies

This project uses **Python 3.12** and **Node.js 24 LTS**. The Python code requires 3.11 or newer. The frontend's supported Node versions are listed in `frontend/package.json`; Node 24 is the version tested here. Install runtimes from [Python](https://www.python.org/downloads/windows/) and [Node.js](https://nodejs.org/en/download) if setting up a new computer, then reopen PowerShell.

The `.tools` folder, Python environment, and `node_modules` are local generated files and will not be included in Git. The frontend lockfile **is** included; `npm ci` restores its exact versions.

From the project root on **this computer**, the installed Python interpreter can recreate the virtual environment if it is missing:

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon"
if (-not (Test-Path -LiteralPath ".\backend\.venv\Scripts\python.exe")) {
    & "$env:LOCALAPPDATA\Python\pythoncore-3.12-64\python.exe" -m venv .\backend\.venv
}
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-dev.txt

if (-not (Test-Path -LiteralPath ".\backend\.env")) {
    Copy-Item -LiteralPath ".\backend\.env.example" -Destination ".\backend\.env"
}
if (-not (Test-Path -LiteralPath ".\frontend\.env")) {
    Copy-Item -LiteralPath ".\frontend\.env.example" -Destination ".\frontend\.env"
}

if (Test-Path -LiteralPath ".\.tools\node\node.exe") {
    $env:Path = (Resolve-Path -LiteralPath ".\.tools\node").Path + ";" + $env:Path
}
Set-Location -LiteralPath ".\frontend"
npm.cmd ci
```

On another computer, open the repository's actual folder and use `py -3.12 -m venv .\backend\.venv` instead of the machine-specific Python command. The `py` launcher on this computer is currently unavailable, which is why the commands above use the real interpreter directly.

Environment files are optional for the default local setup. The copy commands preserve an existing `.env` file.

Before starting the backend, run the migration command shown in Terminal 1. It is safe to repeat when the database is already at the latest revision. The migration is explicit; starting Uvicorn or checking health does not silently change the database schema.

## Configuration

| File / variable | Default | Purpose |
| --- | --- | --- |
| `backend/.env`: `DATABASE_URL` | `sqlite:///./data/triprescue.db` | SQLite path; relative paths resolve from `backend/`, regardless of terminal location. |
| `backend/.env`: `CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | Explicit allowed frontend origins, as a JSON array. |
| `backend/.env`: `AI_MODE` | Code fallback: `demo`; template: `ollama` | `ollama` for no-key local AI, `openai` for optional cloud AI, or `demo` for scripted examples. |
| `backend/.env`: `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Loopback-only local model server; remote URLs and credentials are rejected. |
| `backend/.env`: `OLLAMA_MODEL` | `qwen3:4b-q4_K_M` | Downloaded local model, with cloud model suffixes rejected. |
| `backend/.env`: `OLLAMA_CONTEXT_LENGTH` | `8192` | Local context size; larger values require more memory. |
| `backend/.env`: `OPENAI_API_KEY` | Empty | Server-only credential, required only for optional OpenAI mode. |
| `backend/.env`: `OPENAI_MODEL` | `gpt-5.4-mini` | Configurable Responses API model for live AI. |
| `backend/.env`: `AUTH_COOKIE_SECURE` | `false` locally | Set `true` with a future HTTPS deployment; never expose the development server as a finished public service. |
| `frontend/.env`: `VITE_API_BASE_URL` | `/api` | Public browser configuration for API requests. |
| `frontend/.env`: `BACKEND_PROXY_TARGET` | `http://127.0.0.1:8000` | Vite development and preview proxy target; not bundled into browser code. |

Vite forwards `/api/health` to FastAPI, so the browser can communicate through the frontend's own origin. Restart the relevant server after changing its environment file. Use the default ports unless updating the proxy and CORS configuration too.

**Never put a secret in a `VITE_` variable:** Vite exposes those values to the browser. Optional cloud keys belong only in an ignored backend `.env`. Ollama and demo modes need no API key.

SQLite lives at `backend/data/triprescue.db`. Alembic revision `0001_saved_trips` adds `users`, `trips`, and `itinerary_items`. Revision `0002_itinerary_proposals` adds `proposals` without replacing existing tables or activities. Destructive migration downgrades are disabled. The health endpoint only runs `SELECT 1`.

Revision `0003_domino_rescue` adds `reservations`, `reservation_dependencies`, `disruption_events`, `recovery_plans`, and `rescue_audit_logs`. It does not rebuild or modify the original tables, and it inserts no demo data. A pre-migration backup is in `.artifacts/domino-rescue/before-migration.db`; all original rows were compared afterward and remained unchanged. On another checkout, apply the migration before starting the backend:

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon\backend"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Revision `0004_private_traveler` adds only `traveler_vaults` and `traveler_vault_audit`. `cryptography==50.0.2` is included in backend requirements. The private-update backup is `.artifacts/real-travel/before-private-traveler.db`; every pre-existing application table was compared after migration and remained unchanged. Vault encryption protects the new private payload, not all legacy trip fields or all database metadata.

This privacy foundation runs locally through Vite's same-origin `/api` proxy and short-lived HttpOnly/SameSite unlock cookies. It is not production account authentication, MFA, a recovery service, or production key management. A production release needs the separate identity/security/provider phases in the integration plan before handling real booking operations.

The existing application database was backed up before this update under `.artifacts/backups/triprescue-before-saved-trips-9f87b8e697.db`, then migrated and checked for integrity. Test profiles, trips, and activities are created only in temporary or isolated QA databases, not in your application database. Keep the application database and any backups when updating the project.

Before the proposal migration, another backup was created at `.artifacts/backups/triprescue-before-proposals-dd8c99cd20.db`. Every existing user, trip, and activity row was compared before and after migration and remained unchanged.

Revision `0005_accounts` adds `accounts`, `account_sessions`, `account_attempts`, and `account_audit`, linked to existing owner IDs. It is already applied here. All eleven pre-existing application tables were compared afterward and were unchanged. The backup is `.artifacts/accounts/before-accounts.db`. No account is created automatically and no default password is assigned.

## Saved-trip API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Create an account; optionally link a proven current local profile. |
| POST | `/api/auth/login` | Sign in and issue an HttpOnly cookie session. |
| GET | `/api/auth/session` | Restore the current account session. |
| POST | `/api/auth/logout` | Revoke the current session. |
| POST | `/api/auth/change-password` | Verify the current password, change it, and rotate sessions. |
| POST | `/api/profiles` | Legacy local-profile creation retained for compatibility. |
| GET / PATCH | `/api/profiles/me` | Read or rename the current profile. |
| GET / POST | `/api/trips` | List owned trips or create a trip. |
| GET / PUT | `/api/trips/{trip_id}` | Read or edit an owned trip. |
| POST | `/api/trips/{trip_id}/itinerary` | Add an activity. |
| PUT / DELETE | `/api/trips/{trip_id}/itinerary/{item_id}` | Edit or remove an activity. |
| GET / POST | `/api/trips/{trip_id}/proposals` | Retrieve recent proposals or generate a new one. |
| GET | `/api/trips/{trip_id}/proposals/{proposal_id}` | Retrieve an owned proposal. |
| POST | `/api/trips/{trip_id}/proposals/{proposal_id}/approve` | Revalidate and save approved additions once. |
| POST | `/api/trips/{trip_id}/proposals/{proposal_id}/reject` | Reject without changing the itinerary. |
| POST | `/api/buddy/chat` | Chat, optionally supplying a selected `trip_id`. |
| POST | `/api/rescue/demo` | Create/reopen an owned fictional demo (`fresh: true` creates another). |
| GET | `/api/trips/{trip_id}/rescue` | Read reservations, dependencies, disruption, options, and audit history. |
| POST | `/api/trips/{trip_id}/rescue/simulate-cancellation` | Cancel the fictional connection and flag descendants at risk. |
| POST | `/api/trips/{trip_id}/rescue/options` | Compare mock flight inventory against saved schedules and budget. |
| POST | `/api/trips/{trip_id}/rescue/plans/{plan_id}/approve-execute` | Require `approved: true`, revalidate, and execute a mock repair once. |
| GET | `/api/rescue/real/capabilities` | Report real connected capabilities; currently assisted handoff only. |
| GET | `/api/private-traveler/status` | Read vault existence/unlock state without private contents. |
| POST | `/api/private-traveler/create` or `/unlock` | Create or authenticate the password-encrypted private vault. |
| GET / PUT | `/api/private-traveler` | Read/save owned private data with a valid unlock cookie and revision. |
| POST | `/api/private-traveler/lock` or `/change-password` | Lock private details or rotate their password/key. |
| POST | `/api/private-traveler/rescue-assistance` | Prepare an unverified existing-ticket handoff using fixed official links. |

Account-owned requests require the HttpOnly session cookie and a session-specific proof in `X-Profile-Token`; the proof alone cannot authenticate. Unlinked legacy profiles use their original token until explicitly linked, after which that token is retired. General chat works without an account; selected-trip chat checks account/profile ownership. Supplying a forged trip snapshot is rejected: the server loads the trip itself. See `/docs` for exact request schemas. Money values are decimal strings with two places; overlapping plans return a clear HTTP 409 error.

## Enable OpenAI cloud AI (optional)

Local Ollama is the selected no-key option. To switch to the optional OpenAI provider instead, open a new PowerShell terminal and run:

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon"
.\backend\.venv\Scripts\python.exe .\backend\configure_ai.py
```

Enter your OpenAI API key at the **hidden terminal prompt**, then restart the backend with the startup command above. The helper preserves existing database and CORS settings, saves the key only in ignored `backend/.env`, and sets `AI_MODE=openai`. Blank input cancels without changes. It never prints the key. Do not paste your real key into chat or a shell command.

Alternatively, create `backend/.env` from the template if missing and edit these values there:

```dotenv
AI_MODE=openai
OPENAI_API_KEY=replace_with_your_own_key_locally
OPENAI_MODEL=gpt-5.4-mini
```

Restart the backend after changing the configuration. Pip's panel will identify live AI mode. Never paste a real key into the chat or put it in the frontend. Your OpenAI API account must have billing and access to the configured model. To return to scripted replies, set `AI_MODE=demo` and restart the backend.

The adapter uses the [OpenAI Responses API](https://developers.openai.com/api/docs/guides/text) and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) for itinerary JSON, with `store: false`, server-side credentials, timeouts, and safe provider errors. Pydantic validates the generated schema; backend services enforce dates, schedules, budgets, ownership, and approval. Provider behavior is tested with mocked responses. Full daily plans have a 150-second provider timeout and a 180-second browser timeout. An invalid key produces a private setup instruction instead of a demo response or a false success message.

## Project structure

```text
Trip ahckathon/
  PROJECT_SPEC.md                 Complete product specification (preserved)
  README.md                      Setup, startup, scope, and verification
  .gitignore                     Secrets, databases, caches, and build output
  frontend/
    package.json                 Runtime dependencies and npm scripts
    package-lock.json            Exact frontend dependency versions
    components.json              shadcn/ui configuration
    vite.config.ts               React, Tailwind, aliases, and API proxy
    .env.example                 Public frontend and proxy configuration
    public/                      Bundled destination photograph and favicon
    src/
      main.tsx                   React and browser router entry point
      App.tsx                    Landing page, routes, and connection UI
      index.css                  Responsive theme and Tailwind setup
      components/ui/             shadcn/ui Button and Badge primitives
      components/buddy/          Floating Pip, shared chat state, and styles
      features/accounts/         Registration, sign-in, password changes and account UI
      features/trips/            Account/profile state, trip and activity forms, pages and API
      features/planning/         Proposal review cards and approval API client
      lib/                       Typed API client and class-name utility
  backend/
    requirements.txt             Pinned direct runtime dependencies
    requirements-dev.txt         Test dependencies
    pyproject.toml               Pytest configuration
    .env.example                 Validated backend settings
    configure_ai.py              Hidden-input local AI key setup
    alembic.ini                  Database migration configuration
    alembic/                     Additive saved-trip schema migration
    app/
      main.py                    FastAPI factory, lifecycle, and CORS
      config.py                  Environment validation
      database.py                SQLAlchemy engine, Base, and sessions
      models.py                  Owners, accounts, trips, proposals, recovery and vault records
      schemas/trips.py           Validated profile, trip, and activity requests
      schemas/planning.py        Structured itinerary proposal schema
      api/health.py              Health response and safe failure handling
      api/buddy.py               Chat configuration, request validation, responses
      api/profiles.py            Local profile creation and name changes
      api/trips.py               Owned-trip and itinerary endpoints
      api/planning.py            Proposal generation, approval, and rejection
      services/buddy.py          Scripted guidance and optional live AI adapter
      services/trips.py          Ownership, schedules, budgets, and persistence
      services/planning.py       AI/curated generation and approved additions
    data/                        Local SQLite file (ignored)
    tests/                       Isolated backend tests
```

The frontend uses React, TypeScript, Vite, Tailwind CSS, React Router, Lucide, and shadcn/ui-style local components. The backend uses FastAPI, Pydantic settings, SQLAlchemy, SQLite, Alembic, and Pytest. No external database server is necessary.

## Run checks

**Backend tests and dependency consistency**

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon\backend"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
```

The tests cover health, configuration, persistence across database reopening, foreign keys, additive migrations, profile ownership boundaries, trip and activity validation, budget calculations, overlapping/concurrent schedule writes, read-only buddy trip context, and mocked live provider requests and failures. They use temporary SQLite files; they do not reset the application's database or call a paid AI service.

**Frontend TypeScript and production build**

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon\frontend"
if (Test-Path -LiteralPath "..\.tools\node\node.exe") {
    $env:Path = (Resolve-Path -LiteralPath "..\.tools\node").Path + ";" + $env:Path
}
npm.cmd run build
```

The build runs TypeScript checks before Vite creates `frontend/dist`. To check types alone, run `npm.cmd run typecheck`.

**Live communication check** (both servers must be running):

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health"
Invoke-RestMethod -Uri "http://127.0.0.1:5173/api/health"
```

Both should return `status: ok` and `database: connected`. The second request verifies Vite's proxy as well.

## Troubleshooting

- **Backend unavailable:** start Terminal 1, open its health URL, then choose **Check again** in Settings. The UI does not claim a working connection when the check fails.
- **Pip cannot connect:** check the backend terminal, then use the chat's retry control. Demo mode needs the backend running even though it does not need an API key.
- **Live chat configuration or rate-limit error:** check the backend `.env`, your API account's access/billing, and `OPENAI_MODEL`. The UI shows the failure; it does not claim that a reply or travel action succeeded.
- **`npm` is not recognized:** use the terminal-local PATH block above, or install Node 24 LTS and reopen PowerShell. Using `npm.cmd` avoids the PowerShell script execution-policy problem.
- **Python opens the Microsoft Store:** use the real Python path in the setup command above. On a new computer, install Python and confirm `py -3.12 --version` works.
- **Address already in use:** stop the server you previously started on port 8000 or 5173. Vite deliberately refuses to silently switch ports.
- **Database unavailable:** check that `DATABASE_URL` is a valid SQLite URL and that its parent folder is writable. Keep existing databases; no reset command is required.
- **Trip/profile requests fail with “no such table”:** stop the backend, run `python.exe -m alembic upgrade head` using the virtual-environment interpreter shown above, then restart it. Do not delete the database.
- **An activity cannot be saved:** check its date and time, and whether another planned activity overlaps it. The form keeps your input when the backend rejects a change.
- **An old profile cannot be opened:** use the same browser that still opens its trips and explicitly link that profile on My Account. A lost legacy token cannot be recovered by entering a display name. Signing into an unrelated account does not merge records. Existing database records are preserved.
- **Account sign-in expires:** sign in again after the 30-minute idle or eight-hour absolute timeout. Password changes end other account sessions. There is no password reset service yet; keep your credentials safe.
- **A test warning mentions AnyIO:** the installed upstream Starlette/AnyIO combination emits a deprecation warning. The tests still execute; failures are reported separately.
- **Production hosting:** this phase is a local application foundation. Hosting the build will also require a running backend and appropriate `/api` routing; Vite's development proxy is not a production server.

## Assets and implementation references

The bundled Mount Fuji photograph is by [Alberto Gallego on Unsplash](https://unsplash.com/photos/mount-fuji-is-reflected-beautifully-in-the-lake-J_7o0_1S-PM), used under the [Unsplash License](https://unsplash.com/license). It is inspiration imagery, not a saved user trip. The app does not need an external image or font service to render.

Frontend setup follows the official [Vite guide](https://vite.dev/guide/), [Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite), and [shadcn/ui installation guidance](https://ui.shadcn.com/docs/installation/vite).

## Next phase

Itinerary proposals for existing saved trips and local no-key AI support are implemented. Local inference requires Ollama and the selected downloaded model to be running. Structured destination discovery, creating trips entirely from a free-text request, persistent preferences, and the other advanced workflows remain future work; those are not silently simulated by this update.
