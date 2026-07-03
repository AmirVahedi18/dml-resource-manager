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

- **Students** register with the admin (see [Registering a student](#registering-a-student)),
  then use inline-button wizards to reserve a GPU, browse the schedule, cancel a reservation, or
  get notified when a busy time range frees up.
- **Admins** (configured via `ADMIN_IDS` in `.env`) manage users, servers/GPUs, the global
  regulation (RAM/duration/booking-horizon limits), usage charts, and can override-cancel any
  reservation lab-wide.
- A reservation is **self-service and auto-confirmed**: if it fits the GPU's free capacity and the
  regulation's limits, it's created immediately — no admin approval step.
- Multiple students can share one GPU concurrently as long as their combined RAM never exceeds
  its total RAM at any point in time.
- By default a student can only hold one reservation at a time across all servers/GPUs; the admin
  can grant individual students a "multi-GPU" privilege that lifts this restriction for them.

## Architecture

```
main.py                  Entry point: loads .env + Hydra config, wires DB/logging/bot/scheduler
configs/                 Hydra configuration tree (bot, database, logging, regulation, scheduler)
src/dml_bot/
  config/                Structured (dataclass) config schema, validated by Hydra at startup
  db/                    SQLAlchemy models + session management (SQLite)
  services/               Framework-agnostic business logic (reservation conflict checking,
                           regulation, users, servers, watches, usage aggregation) — unit-tested
                           independently of Telegram
  bot/                   python-telegram-bot wiring: inline keyboards, conversation wizards,
                           admin/student handlers
  scheduling/            APScheduler jobs: freed-slot notifications, pre-start reminders, cleanup
  charts/                Matplotlib rendering for admin usage reports
  utils/                 Shared helpers (all datetimes are stored/compared as naive UTC, since
                           SQLite drops timezone info on round-trip)
logs/                    Rotating log files (created at runtime)
data/                    SQLite database file (created at runtime)
tests/
  unit/                  Service-layer and scheduling-job tests against an in-memory SQLite DB
  integration/           Drives real bot handler coroutines (real DB, real conversation logic,
                           real Telegram object classes) with only the network layer stubbed out
```

The reservation engine's core algorithm (`services/reservation_service.py`) validates slot
alignment, duration/RAM/booking-horizon limits against the regulation, then runs a sweep-line over
overlapping reservations on the target GPU to find peak concurrent RAM usage, rejecting the
request if it would exceed the GPU's total RAM at any point in the requested window.

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

   | Variable             | Description                                                        |
   |----------------------|---------------------------------------------------------------------|
   | `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather)                |
   | `ADMIN_IDS`          | Comma-separated Telegram numeric IDs of lab admins                  |
   | `TZ`                 | IANA timezone used to display times to users (e.g. `Asia/Tehran`)   |

3. **Review tunables** in `configs/` (all non-secret, all overridable on the command line via
   Hydra, e.g. `python main.py regulation.booking_horizon_days=60`):

   - `configs/bot/default.yaml` — display timezone, date-picker window, Telegram parse mode
   - `configs/database/default.yaml` — SQLite file path
   - `configs/logging/default.yaml` — log level, rotation size/backups, log directory
   - `configs/regulation/default.yaml` — seed values for the global regulation (only used to
     populate the database on first run; after that, admins edit it live via the bot)
   - `configs/scheduler/default.yaml` — background job poll interval, reminder lead time, cleanup
     retention window

4. **Run the bot:**

   ```bash
   python main.py
   ```

   On first run this creates `data/dml_bot.sqlite3`, seeds the regulation from
   `configs/regulation/default.yaml`, and starts polling Telegram.

### Registering a student

The bot does not connect to any lab directory service, so registration is manual:

1. The student sends `/myid` to the bot, which replies with their numeric Telegram ID.
2. The student gives that ID (and their name) to the lab admin.
3. The admin opens **🛠 Admin Panel → 👤 Manage Users → ➕ Add User** and enters the ID and name.

The student can now use `/start` to access the full menu.

## Testing

```bash
pytest                      # unit + integration tests
pytest tests/unit            # service-layer and scheduling-job logic only
pytest tests/integration     # full handler/conversation flows against a real (in-memory) DB
```

Integration tests construct real `python-telegram-bot` `Update`/`Message`/`CallbackQuery` objects
and call the actual handler coroutines, so they exercise real conversation logic, real database
writes, and real keyboard/callback-data parsing — only the network-facing `Bot` methods
(`send_message`, `edit_message_text`, `send_photo`, `answer_callback_query`) are replaced with
recording mocks.

## Project conventions

- All datetimes are stored and compared as **naive UTC** throughout the codebase (see
  `src/dml_bot/utils/time_utils.py`); conversion to/from the configured display timezone happens
  only at the bot's presentation layer.
- Reservations use a configurable fixed time-slot grid (`regulation.min_reservation_slot_minutes`)
  so free/busy calculations and calendar rendering stay simple.
- See `TODO.md` for design alternatives that were considered but deferred for a later version.
