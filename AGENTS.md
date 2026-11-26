# JARVIS OS — project instructions

## Authoritative master plan and progress journal

Owner instruction: at the start of every session, first read the current `JARVIS_MASTER_PLAN.txt` in the repository root and then `JARVIS_MASTER_PLAN.md`. The supplied master plan takes precedence over the historical task queue below. Preserve all supplied task definitions and IDs; keep TXT and MD byte-identical when recording progress. Never invent completion statuses. If the local source is unavailable, inspect the current origin repository before declaring it missing; record a genuine remaining blocker in the journal.

Execute the 45 tasks in order according to their dependencies. After each task, update its status in `JARVIS_MASTER_PLAN.md`, record the exact implementation, changed files and executed test results, refresh the progress summary, and commit the changes together with a README update. Then continue automatically with the next eligible task. Mark blocked tasks with their reasons and continue independent tasks only when their prerequisites and scope are known. Do not mark incomplete or unverified functionality complete. Existing tests or older release labels alone do not establish completion against the new master plan.

Do not modify production AutoLogika OS or Supabase without separate owner authorization. Continue authorized, reversible JARVIS development and tests without repeatedly asking permission. The current blockers and verified delivery are recorded in the journal.

Read 00_START_HERE.md, PROJECT_STATUS.json, docs/DECISIONS.md and docs/NEXT_TASKS.md first, then README.md, docs/RAPORT.md and docs/CODEX-HANDOFF.md before changing scope. Follow M0–M8 in the master plan; the earlier R01–R07 queue describes historical work only; do not redesign the application from scratch. Work in this JARVIS repository; the separate production AutoLogika repository is read-only unless the owner explicitly authorizes changes there.

## Runtime and verification

- Python 3.12 is required (Wyoming uses audioop). On Windows use .venv/Scripts/python.exe; on Linux .venv/bin/python.
- Setup: python3.12 scripts/cloud_setup.py, or create .venv and install requirements-dev.txt with Python 3.12.
- Required checks for backend changes: .venv/bin/python -m pytest -q, .venv/bin/python -m pip check. For UI changes: node --check jarvis/app.js, plus an appropriate behavior check. Do not claim browser/Windows/Docker/model/hardware checks that were not executed.
- Keep data, .env, credentials, model weights and temporary files out of git. The tests use temporary databases and synthetic data. Real integrations are opt-in.

## Development behavior

The owner authorized continued implementation without asking permission to continue. Implement sensible, reversible changes and test them. Ask only for genuinely missing product decisions; do not ask for another approval to code or run local tests.

The authorization does not activate carriers, buy numbers, place/send real calls/messages, change Play forwarding, expose services publicly, operate a physical gate or modify production AutoLogika. Keep these behind explicit integration activation and the relevant owner rules. No parallel agents are required.

## Boundaries

- Customer reception is separate from owner chat, private memory, settings authority and device control.
- Model output is data, never executable instructions. Only backend rules decide eligibility. Re-evaluate current schedule/DND/vacation at acceptance, and require owner acceptance for handoff.
- Owner-only receptionist laboratory endpoints return internal briefing data. Do not expose them directly to callers or connect them to the PSTN as a shortcut.
- Customer-facing generated text must not confirm prices, bookings or repairs without verified data and an authorized action.
- Revisions, idempotency, SQLite transactions, bounded network requests and auth must be preserved. Schema changes need migration/backup and a meaningful migration test.
- Update docs/RAPORT.md, CHANGELOG.md and the handoff when shipping a stage. Keep limitations explicit.
- Every commit must include a README.md update describing its concrete changes, executed verification and remaining limitations (owner instruction). Do not create a second bookkeeping commit merely to document the previous one.

## Handoff snapshot

Before the first edit to an imported delivery, run python3 scripts/verify_handoff.py if HANDOFF-MANIFEST.json is present. The manifest is a checksum of delivered bytes, not a signature and not a permanent test after development changes. Update PROJECT_STATUS.json and docs/NEXT_TASKS.md when an implementation stage is completed. Historical documents are not proof of current implementation.

## GitHub publication authorization — 2026-10-26

The owner explicitly requested pushing the current project and all project files to endiszyd-rgb/JARVIS-OS. This authorization persists; do not request another routine approval to push these JARVIS changes. The first attempt failed authentication (Git username unavailable; gh/API401). Obtain a working GitHub connection, fetch/reconcile any new remote commits without force, then push and verify remote HEAD. Keep secrets, local databases, caches and virtual environments excluded. Until remote verification succeeds, local_commits_pushed must remain false.

## Current owner scope — 2026-10-27

Continue only through the end of M3. Complete M3.4 and M3.5 where verifiable, then stop. Do not start M4 or later stages without a new owner instruction. This overrides the master plan automatic continuation beyond M3.

## Owner delivery scope — 2026-10-28

The owner explicitly requested a Windows installer to install and view the existing interface. Package and verify the current M3 release as a separate delivery task. This does not authorize M4 integrations or declare the whole M8 stage complete.

## Owner UI scope — 2026-10-29
The owner authorized a JARVIS-style interface and refreshed installer. Preserve existing functionality and role checks; this does not start M4.

## Current owner scope — 2026-10-29 (supersedes M3 STOP)
The owner explicitly authorized M4 and later stages. Continue eligible tasks in order. Production AutoLogika/Supabase changes, paid services, real calls/messages and physical devices remain outside authorization.

## Owner scope — 2026-11-13 (gate and voice)
The owner explicitly requested real control of the workshop Wi‑Fi gate from the application and by voice command ("Jarvis, otwórz/zamknij bramę"), plus an installer, in-app settings and a development plan. This authorizes gate drivers (HTTP, Tuya Cloud, Home Assistant) and sending commands from the Control Center and the voice view; it supersedes the earlier "operate a physical gate" exclusion for this gate only. Hardware verification is performed by the owner at the workshop; keep M5.5 at DONE until that test is recorded. Production AutoLogika/Supabase, paid services and real calls/messages remain outside authorization. Roadmap: docs/PLAN-ROZWOJU.md.

## Owner scope — 2026-11-26 (remote access, operator, cameras)
The owner asked for the Control Center to work like a "Jarvis website": log in from a phone outside the workshop and use voice commands (gate), parts to order and camera previews, and authorized work on the whole program. This authorizes: TOTP second factor, the `operator` role, a remote-access policy for use behind a tunnel (off by default; the tunnel itself is set up by the owner), camera preview through a local go2rtc server, a PWA manifest and the parts voice command from the AutoLogika snapshot. Exposing the service publicly remains the owner's explicit action (JARVIS_REMOTE_ACCESS + tunnel); production AutoLogika/Supabase, paid services and real calls/messages remain outside authorization. Guide: docs/DOSTEP-ZDALNY.md.
