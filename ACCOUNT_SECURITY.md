# TripRescue accounts and saved data

Implemented October 25, 2026. Username-and-password sign-in is available on the local website. The existing SQLite database is reused; existing trips are preserved.

## Create your account and keep your trips

1. Open [My Account](http://127.0.0.1:5173/account) in the **same browser where your existing trips appear**.
2. Choose **Create account**. If your old local profile is open, leave **Keep my current profile and saved data** selected.
3. Choose your own username and a unique password or passphrase. Confirm the password, then choose **Create account & keep my data**.
4. Open **My Trips**. The original trips remain attached to the same owner, now protected by account sign-in.

Usernames are case-insensitive, 3–30 characters, begin with a letter or number, and may contain letters, numbers, dots, underscores, and hyphens. New passwords must be 15–128 characters. There is no default username or password. Do not send your password through Pip or chat with the coding assistant.

If you do not have an old profile, registration creates a new account with its own empty trip collection. Signing in to an existing account opens that account's data. It does not merge unrelated profiles. An unlinked local profile is preserved in this browser when you sign into another account; after signing out, **Reopen my previous local profile** explicitly reopens it.

If the original local profile token has already been lost, entering its display name cannot recover or claim its trips. Existing records are retained, but this update does not guess ownership.

## What belongs to the account

An account links to the existing `users.id`. That same ID owns trips, itinerary activities, proposals, simulated recovery records through their trips, and the encrypted traveler vault. Linking does not copy, delete, or renumber those records. The old browser access token is retired when a profile is explicitly linked.

You can sign in from another browser that can reach this same running server and reopen the same saved records. This remains a local application at `127.0.0.1`; it has not been publicly hosted or synchronized to a cloud service. Another computer's `127.0.0.1` refers to that other computer.

Pip's transcript still lives in tab-scoped session storage. Signing out clears the displayed trip/chat state and cached chat. Conversations are not permanent account history or automatically shared between browsers.

## How passwords and sessions work

The database stores a random-salt **Argon2id hash**, not the account password. Current parameters are 64 MiB of memory, three iterations, and one lane. A hash lets the server check a password without storing the original text. This follows the password-hashing approach described by [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

The sign-in form accepts long passphrases. Failed sign-ins use a generic message. Five failed attempts for the same username/client-address combination cause a fifteen-minute cooldown; that counter persists across backend restarts. A separate process-local limiter permits up to thirty account authentication requests per client address per minute. These controls address the password length and guessing concerns discussed in [OWASP authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).

Successful sign-in creates a random cookie with `HttpOnly` and `SameSite=Strict`. SQLite stores a hash of its bearer value. Account API requests also require a session-specific proof through `X-Profile-Token`; the frontend keeps this proof in memory. It is not a replacement for the cookie. JSON-only account changes, origin checks, and that proof protect account-changing requests. Passwords and raw account session values are not saved in application local/session storage.

Server-side sessions expire after **30 minutes without owned API activity**, or **eight hours total**. Passive session checks do not prolong the idle timeout. Sign out revokes the current session. Changing the account password requires the current password, ends other sessions, and rotates the current session. Cookie flags and server-side expiry follow the principles in [OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

The current site uses local HTTP. For a future HTTPS deployment, set backend `AUTH_COOKIE_SECURE=true` and configure HTTPS, permitted origins, and routing appropriately. Do not expose the local development server as a finished production service.

## Your private traveler vault keeps its separate password

The account password controls account access. The vault password decrypts private traveler/contact/ticket details. Linking an account preserves the encrypted vault and its existing password. Account sign-in or a password change does not decrypt it. Open **Settings → Private traveler details** and unlock it with the original vault password.

Account changes clear the current vault unlock session; changing the account password locks that owner's vault sessions. Changing the account password does not change the vault encryption password. Neither password currently has a recovery service. Keep both safe and use different passwords.

## Database changes and API

Migration `0005_accounts` adds four tables:

| Table | Purpose |
| --- | --- |
| `accounts` | Unique normalized username, password hash, and link to an existing owner. |
| `account_sessions` | Hashed cookie values, session proof, expiry, activity, and revocation. |
| `account_attempts` | Failed-sign-in counters and cooldowns keyed by a hash. |
| `account_audit` | Account event metadata without passwords or private traveler payloads. |

The migration does not rebuild existing tables, seed accounts, or assign a default password. It is already applied on this computer. All records in the eleven pre-existing application tables were compared afterward and remained unchanged: two profiles, three trips, sixteen itinerary items, two proposals, and the existing empty recovery/vault tables. The pre-update backup is `.artifacts/accounts/before-accounts.db`. Backups contain application data and should stay private.

| Method | Address | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Create an account, optionally linking the proven current local profile. |
| POST | `/api/auth/login` | Verify credentials and establish a cookie session. |
| GET | `/api/auth/session` | Restore the current account without extending idle activity. |
| POST | `/api/auth/logout` | Revoke the current session. |
| POST | `/api/auth/change-password` | Verify the current password, replace its hash, and rotate sessions. |

Ownership is checked in the backend for trips, selected-trip chat, proposals, recovery, and private details. Knowing another trip ID does not grant access. The legacy profile API remains for compatibility with unlinked profiles; retired tokens cannot bypass account sign-in.

Key implementation files are `backend/app/services/accounts.py`, `backend/app/api/accounts.py`, `backend/app/schemas/accounts.py`, `backend/app/api/private_route.py`, `backend/app/models.py`, `backend/alembic/versions/0005_accounts.py`, `backend/tests/test_accounts.py`, `frontend/src/features/accounts/`, and `frontend/src/features/trips/trips-provider.tsx`.

## Run it and review the checks

From the project folder in PowerShell:

```powershell
Set-Location -LiteralPath "C:\Users\pobba\Downloads\Trip ahckathon"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-triprescue.ps1 -OpenBrowser
```

Then open [My Account](http://127.0.0.1:5173/account). The servers are already running after this update. Installation and separate-server commands remain in [README.md](README.md). On another checkout, install backend requirements and run `python.exe -m alembic upgrade head` with the project's virtual environment before starting the backend. Do not delete the database.

Checks actually completed for this update:

- **396 backend tests passed**, with one existing upstream deprecation warning. The suite includes 24 account tests covering linking, password hashing, ownership, cookies/proof, retired tokens, restart/expiry, throttling, session rotation, concurrency, and preserved planning/recovery behavior.
- **Frontend production build passed**, including TypeScript checks.
- **Eleven isolated browser checks passed**, including linking a legacy trip and vault, another browser signing into the same account, account separation, sign-out, password changes, simulated repair, mobile layouts, reopening an unlinked profile, and preserving Pip's conversation and unsent draft after refreshing the same account.
- **Eight accessibility scans detected no violations** at desktop/tablet/phone widths, including 320 pixels. No browser JavaScript errors were reported.
- The running main API exposes all five account routes. The frontend account page and API proxy responded correctly. No accounts or QA fixtures were inserted into the real application database.

Browser evidence is `.artifacts/accounts/browser-results.json` and its screenshots. Tests used temporary or isolated databases and fictional credentials. This update made no paid provider calls, real booking changes, or public deployment.

## Remaining limits

Email/password reset, forgotten-username recovery, MFA, account deletion, invitations, a production security review, and public hosting are not implemented. Database/file administrators can still access unencrypted trip records and metadata. The vault encrypts its private payload; it does not encrypt the entire SQLite file. Accounts do not grant airline servicing authority or enable real automatic rebooking.
