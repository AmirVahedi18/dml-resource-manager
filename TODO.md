# Roadmap

This file tracks design alternatives that came up while planning the bot but were deliberately
deferred for v1 in favor of the simpler option. Each was a real, considered trade-off — not a
missing feature — recorded here so they aren't relitigated from scratch later. Versions are a
rough sequencing guide, not a commitment.

## v1.x — polish, no architecture change

- **Configurable cancellation cutoff window.** v1 lets students cancel anytime before a
  reservation's start, with no penalty. A regulation field for a minimum-notice cutoff (e.g. "no
  cancellations within 2h of start") would discourage last-minute flaking that blocks others from
  booking that slot.
- **Structured JSON logging.** v1 uses plain rotating text logs. A JSON-line format would make
  logs easier to grep/parse programmatically or feed into a future dashboard, at the cost of
  human readability of the raw files.

## v2.0 — auth & admin scaling

- **Self-service registration via one-time invite codes.** v1 requires the admin to manually
  collect each student's Telegram ID (via `/myid`) before registering them. An invite-code flow
  (`/start <code>`) would let students self-link without the admin needing to look up IDs first —
  better if the lab grows.
- **Multiple admins via a DB-stored role.** v1 has a single bootstrap admin set (`ADMIN_IDS` in
  `.env`). A promotable DB role would let the bootstrap admin grant admin rights to e.g. a TA
  without redeploying.
- **Numeric per-user GPU concurrency override.** v1's privilege is a boolean
  (`can_use_multiple_gpus`). A numeric cap (e.g. "this user may hold reservations on up to 3 GPUs
  at once") would be more precise than unlimited/1.

## v2.x — regulation flexibility

- **Per-role regulations.** v1 has one global regulation for every student. Separate limits per
  role/group (e.g. Master vs PhD) would need a role field on `User` and per-role regulation rows.
- **Global regulation + per-user overrides.** Keep one global default but let the admin override
  individual fields for specific students — a middle ground between "one size fits all" and full
  per-role regulations, and a more direct way to express ad hoc privilege grants.
- **Optional per-user "needs approval" flag.** v1 reservations are always auto-confirmed. A flag
  the admin can set on a specific (e.g. previously abusive) user would require manual approval
  just for them, without reintroducing an approval bottleneck for everyone.

## v3.0 — scheduling & fairness

- **Opt-in auto-booking waitlist.** v1's freed-slot watch is notify-only: the student gets a
  push and must manually re-reserve, first to act wins. An auto-booking queue would book the slot
  for the first subscriber automatically the instant it frees, removing the notify-then-race
  friction — at the cost of meaningfully more queue/validation logic.
- **Free-form (non-slot-aligned) reservation times.** v1 reservations snap to a fixed slot grid
  (`regulation.min_reservation_slot_minutes`) to keep free/busy calculation and calendar
  rendering simple. Fully free-form start/end times would be more flexible per request but harder
  to visualize and more prone to fragmentation.
- **Plotly-based usage charts.** v1 renders admin usage reports with Matplotlib (no extra system
  dependencies). Plotly would give nicer styling at the cost of a heavier dependency (kaleido
  bundles a Chromium-like binary for PNG export).

## v2.x — Mini App refinements

- **Real domain + TLS instead of a tunnel.** The Mini App currently defaults to a Cloudflare
  Tunnel/ngrok URL for `WEBAPP_PUBLIC_URL` since the lab didn't have a domain+TLS setup decided
  yet. Migrating to a real domain with a Let's Encrypt cert is a pure config change (just update
  the env var) — no code changes needed, but worth tracking as the "real" production step.
- **Inline "Open Mini App" button in the classic menu.** v1 only exposes the Mini App via the
  persistent Menu Button (next to the message input). Adding a second entry point as a button in
  the classic `/start` menu would help first-time discoverability, at the cost of one more button
  in an already-simple menu.
- **Own-session/JWT auth instead of stateless initData re-validation.** v1 re-validates Telegram's
  `initData` on every single API request (no server-side session). A conventional "log in once,
  get a cookie" model would feel more like a typical web app, but adds session storage/expiry
  logic for a benefit that doesn't clearly apply here — the Mini App is always relaunched fresh
  from Telegram anyway.
- **Browser-level tests (e.g. Playwright).** v1 tests the Mini App at the API level only
  (FastAPI's `TestClient`, simulated signed `initData`) plus manual verification in real Telegram.
  Playwright would catch real frontend bugs (the grid-picker's drag interaction, htmx swaps,
  rendering) that API tests structurally can't see, at the cost of much heavier/slower tooling.

## v3.x — i18n & deployment

- **Multi-language UI.** v1 ships English-only. Farsi (or full per-user language selection) would
  need a string-table/gettext layer; deferred since it's a real engineering investment and v1's
  flat message templates make it straightforward to retrofit later.
- **Dockerfile / docker-compose.** A containerized, repeatable deployment path for the lab
  server. Out of scope for v1 since it wasn't requested and doesn't affect the bot's architecture.
- **Username/password login.** Considered as an identity-verification alternative to
  admin-pre-registers-Telegram-ID. More flexible in theory, but requires secure credential
  storage and a reset flow for a benefit that doesn't clearly apply here — the lab admin already
  trusts itself to provision accounts, so this is unlikely to ever be worth the complexity, kept
  here only for completeness.

## Architecture alternatives considered (not roadmap items — recorded for reference)

These were real options at the planning stage but aren't "add later" features — adopting any of
them would mean rewriting rather than extending v1, so they're not sequenced into a version:

- **aiogram v3** instead of python-telegram-bot (equally viable async framework, different FSM
  idioms).
- **Raw `sqlite3` or Peewee** instead of SQLAlchemy for the DB layer.
- **Persistent reply keyboard or slash-commands+free-text** instead of inline-keyboard wizards for
  the bot's primary interaction style.
- **External cron + standalone CLI script** instead of in-process APScheduler for background jobs.
- **Flask or aiohttp** instead of FastAPI for the Mini App's backend.
- **Separate process for the Mini App's web server** instead of running it alongside the bot's
  polling loop on one shared event loop.
- **A small SPA framework (Preact/Svelte) with a build step** instead of server-rendered Jinja2
  templates + htmx for the Mini App's frontend.
- **Mirroring the classic bot's step-by-step wizard as web forms** instead of the richer
  click-and-drag visual time grid the Mini App actually ships with.
