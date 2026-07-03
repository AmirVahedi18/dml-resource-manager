# DML Resource Manager

A Telegram bot that brings fair, transparent GPU-time scheduling to the DML (Data science and
Machine learning Laboratory) research lab. Students reserve a specific GPU, on a specific server,
for a specific RAM amount and time window, instead of grabbing whatever's free and holding it
indefinitely. The lab admin manages users, servers/GPUs, and the regulation (limits) that govern
every reservation.

The bot is a scheduling/coordination layer, not a live resource monitor: it does not connect to
the lab's servers. "Usage" in admin reports and schedules means *booked* time and RAM, not
real-time `nvidia-smi` telemetry. Compliance with reserved time slots is enforced by lab policy,
not by the software.

## How it works

- **Students** register with the admin (see [Registering a student](#registering-a-student)), then
  reserve a GPU, browse the schedule, cancel a reservation, or get notified when a busy time range
  frees up. There are two interfaces for this — the classic inline-button chat wizards, and a
  **Telegram Mini App** (see [Mini App](#mini-app)) with a richer drag-to-select time grid — but
  only one is active in a given deployment, chosen via `interface` in `configs/config.yaml` (see
  [Choosing an interface](#choosing-an-interface)). Both call the exact same reservation logic, so
  switching between them changes nothing about the rules.
- **Admins** (configured via `ADMIN_IDS` in `.env`) manage users, servers/GPUs, the global
  regulation (RAM/duration/booking-horizon limits), usage charts, and can override-cancel any
  reservation lab-wide — in whichever interface is active.
- A reservation is **self-service and auto-confirmed**: if it fits the GPU's free capacity and the
  regulation's limits, it's created immediately — no admin approval step.
- Multiple students can share one GPU concurrently as long as their combined RAM never exceeds
  its total RAM at any point in time.
- By default a student can only hold one reservation at a time across all servers/GPUs; the admin
  can grant individual students a "multi-GPU" privilege that lifts this restriction for them.

## Architecture

```
main.py                  Entry point: loads .env + Hydra config, runs the bot's polling loop and
                          the Mini App's web server concurrently on one event loop
configs/                 Hydra configuration tree (bot, database, logging, regulation, scheduler, webapp)
src/dml_bot/
  config/                Structured (dataclass) config schema, validated by Hydra at startup
  db/                    SQLAlchemy models + session management (SQLite)
  services/               Framework-agnostic business logic (reservation conflict checking,
                           regulation, users, servers, watches, usage aggregation) — unit-tested
                           independently of Telegram, and shared by both interfaces below
  bot/                   python-telegram-bot wiring: inline keyboards, conversation wizards,
                           admin/student handlers (the classic chat interface)
  api/                   FastAPI app powering the Mini App: initData validation (auth.py),
                           request dependencies (deps.py), routers/ per feature area
  scheduling/            APScheduler jobs: freed-slot notifications, pre-start reminders, cleanup
  charts/                Matplotlib rendering for admin usage reports (reused by both interfaces)
  utils/                 Shared helpers (all datetimes are stored/compared as naive UTC, since
                           SQLite drops timezone info on round-trip)
templates/               Jinja2 templates for the Mini App (shell.html + htmx partials/)
static/                  Mini App static assets: bootstrap.js (Telegram SDK + htmx wiring),
                          grid-picker.js (drag-to-select time grid), style.css
logs/                    Rotating log files (created at runtime)
data/                    SQLite database file (created at runtime)
tests/
  unit/                  Service-layer, scheduling-job, and initData-auth tests (in-memory SQLite)
  integration/           Drives real bot handler coroutines and real FastAPI routes (real DB, only
                           the Telegram network layer / initData signing is stubbed or simulated)
```

The reservation engine's core algorithm (`services/reservation_service.py`) validates slot
alignment, duration/RAM/booking-horizon limits against the regulation, then runs a sweep-line over
overlapping reservations on the target GPU to find peak concurrent RAM usage, rejecting the
request if it would exceed the GPU's total RAM at any point in the requested window. Both the
classic bot's reservation wizard and the Mini App's grid picker call this exact same function, so
there is exactly one place reservation rules are enforced.

## Setup

1. **Create and activate a virtualenv, then install dependencies:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install -e .
   ```

   The last step installs the `dml_bot` package itself (from `src/`) in editable mode, which is
   what makes `import dml_bot` work from anywhere — including `python main.py` run directly from
   the project root. Without it you'll get `ModuleNotFoundError: No module named 'dml_bot'`.

2. **Configure secrets** — copy `.env.example` to `.env` and fill it in:

   ```bash
   cp .env.example .env
   ```

   | Variable             | Description                                                          |
   |----------------------|-----------------------------------------------------------------------|
   | `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather)                  |
   | `ADMIN_IDS`          | Comma-separated Telegram numeric IDs of lab admins                    |
   | `TZ`                 | IANA timezone used to display times to users (e.g. `Asia/Tehran`)     |
   | `WEBAPP_PUBLIC_URL`  | HTTPS URL the Mini App is reachable at; required only when `interface: webapp` (see [Mini App](#mini-app)) |

3. **Review tunables** in `configs/` (all non-secret, all overridable on the command line via
   Hydra, e.g. `python main.py regulation.booking_horizon_days=60`):

   - `configs/config.yaml` — top-level `interface` setting (see
     [Choosing an interface](#choosing-an-interface))
   - `configs/bot/default.yaml` — display timezone, date-picker window, Telegram parse mode
   - `configs/database/default.yaml` — SQLite file path
   - `configs/logging/default.yaml` — log level, rotation size/backups, log directory
   - `configs/regulation/default.yaml` — seed values for the global regulation (only used to
     populate the database on first run; after that, admins edit it live via the bot)
   - `configs/scheduler/default.yaml` — background job poll interval, reminder lead time, cleanup
     retention window
   - `configs/webapp/default.yaml` — host/port the Mini App's web server binds to (only used when
     `interface: webapp`)

4. **Run the bot:**

   ```bash
   python main.py
   ```

   On first run this creates `data/dml_bot.sqlite3`, seeds the regulation from
   `configs/regulation/default.yaml`, and starts polling Telegram. What else runs depends on
   `interface` — see below.

### Choosing an interface

`configs/config.yaml` has a single top-level `interface` setting that decides which UI is active.
Exactly one runs at a time — not both, and not neither:

```yaml
interface: webapp   # or: legacy
```

- **`webapp`** (default) — starts the Mini App's FastAPI server on
  `configs/webapp/default.yaml`'s host/port and registers it as the persistent Mini App menu
  button next to the message input. Requires `WEBAPP_PUBLIC_URL` to be set in `.env` (see
  [Mini App](#mini-app)) — startup fails fast with a clear error if it isn't. The classic
  inline-button wizards are not registered at all in this mode; `/start` and `/help` point users
  at the Mini App instead.
- **`legacy`** — runs only the classic chat-based wizards (inline-button menus for reserving,
  browsing the schedule, cancelling, watches, and the admin panel). The Mini App's web server is
  never started, `WEBAPP_PUBLIC_URL` is not required, and the menu button is reset to Telegram's
  default (removed) on startup.

You can also override it from the command line without editing the file:
`python main.py interface=legacy`.

### Registering a student

The bot does not connect to any lab directory service, so registration is manual:

1. The student sends `/myid` to the bot, which replies with their numeric Telegram ID.
2. The student gives that ID (and their name) to the lab admin.
3. The admin opens **🛠 Admin Panel → 👤 Manage Users → ➕ Add User** and enters the ID and name.

The student can now use `/start` to access the full menu.

## Mini App

The Mini App is a richer web UI to the exact same features, active when `interface: webapp` (see
[Choosing an interface](#choosing-an-interface)) — reached via a persistent button next to the
message input in the chat, opening a web page inside Telegram. It calls the same `services/` layer
as the classic bot, so switching `interface` back to `legacy` changes nothing about the reservation
rules, only which UI is exposed.

### Why it needs an HTTPS URL

Telegram requires a Mini App to be served over a real HTTPS URL with a valid (CA-signed)
certificate — it will not open a self-signed or plain-HTTP address. Until your lab server has a
real domain and TLS set up, the simplest path is a tunnel:

1. Run the bot locally (`python main.py`) — the Mini App is served on
   `configs/webapp/default.yaml`'s port (default `8080`).
2. Point a tunnel at that port to get a temporary public HTTPS URL, e.g. with
   [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/):
   `cloudflared tunnel --url http://localhost:8080`. ngrok works the same way if you already use it.
3. Put that HTTPS URL in `.env` as `WEBAPP_PUBLIC_URL`, set `interface: webapp` in
   `configs/config.yaml`, and restart the bot — it registers the Mini App's menu button
   automatically on startup.

Once the lab has a real domain with a certificate (e.g. via nginx/Caddy + Let's Encrypt), just
point `WEBAPP_PUBLIC_URL` at that instead — nothing else changes.

### How auth works

There's no separate login: Telegram signs a per-launch `initData` string identifying the user,
which the Mini App's JavaScript sends as a header (`X-Telegram-Init-Data`) on every request. The
backend (`src/dml_bot/api/auth.py`) verifies that signature with HMAC-SHA256 against the bot
token on every single request — the same trust model as the classic bot, just over HTTP instead
of Telegram's Update objects. There is no server-side session or cookie.

### Testing the Mini App locally without Telegram

Since it's just a FastAPI app, you can open `http://localhost:8080/` directly in a browser for
layout/styling checks, but the page will be stuck on "Loading…" — without Telegram's JS SDK
providing real `initData`, every `/api/*` call is correctly rejected with 401. Full testing needs
either the automated test suite (`pytest tests/integration/test_webapp_*.py`, which simulates
valid signed `initData`) or opening the real Mini App inside Telegram once `WEBAPP_PUBLIC_URL` is
set.

## Testing

```bash
pytest                      # unit + integration tests
pytest tests/unit            # service-layer and scheduling-job logic only
pytest tests/integration     # full handler/conversation flows against a real (in-memory) DB
```

Integration tests for the classic bot construct real `python-telegram-bot`
`Update`/`Message`/`CallbackQuery` objects and call the actual handler coroutines, so they
exercise real conversation logic, real database writes, and real keyboard/callback-data parsing —
only the network-facing `Bot` methods (`send_message`, `edit_message_text`, `send_photo`,
`answer_callback_query`) are replaced with recording mocks.

Integration tests for the Mini App (`tests/integration/test_webapp_*.py`) drive FastAPI's
`TestClient` against real routes with a real (in-memory) DB; `tests/webapp_signing.py` builds
genuinely HMAC-signed `initData` so these tests exercise the real auth path end-to-end rather than
bypassing it. No browser automation — the frontend's JS (grid drag-selection) isn't covered by
the automated suite, only manually in real Telegram.

## Project conventions

- All datetimes are stored and compared as **naive UTC** throughout the codebase (see
  `src/dml_bot/utils/time_utils.py`); conversion to/from the configured display timezone happens
  only at the presentation layer (both the bot's message formatting and the Mini App's templates).
- Reservations use a configurable fixed time-slot grid (`regulation.min_reservation_slot_minutes`)
  so free/busy calculations and calendar rendering stay simple, in both interfaces.
- The classic bot and the Mini App never duplicate business logic: both call the same functions
  in `services/`, so a rule change (e.g. a new regulation field) only needs to be enforced once.
- See `TODO.md` for design alternatives that were considered but deferred for a later version.
