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
  reserve a GPU, browse the schedule, cancel a reservation, or watch a busy time range for freed
  capacity — opting in to either a plain notification or automatic booking the instant it frees
  (see [Watches and auto-booking](#watches-and-auto-booking)). The bot is a persistent
  reply-keyboard menu (a flat button grid docked below the message box, rather than buttons
  attached to individual messages) — see [Using the bot](#using-the-bot).
- **Admins** manage users, servers/GPUs, the global regulation (RAM/duration/booking-horizon
  limits), usage charts, and can override-cancel any reservation lab-wide. `ADMIN_IDS` in `.env`
  is a fixed set of **bootstrap admins** that always have admin rights and can't be revoked
  through the bot; a bootstrap admin can additionally promote any registered user to a
  **DB-stored admin role** (e.g. a TA) from Manage Users, without touching `.env` or redeploying
  (see [Multiple admins](#multiple-admins)).
- A reservation is **self-service and auto-confirmed**: if it fits the GPU's free capacity and the
  regulation's limits, it's created immediately — no admin approval step.
- Multiple students can share one GPU concurrently as long as their combined RAM never exceeds
  its total RAM at any point in time.
- By default a student can only hold one reservation at a time across all servers/GPUs; the admin
  can grant individual students a "multi-GPU" privilege that lifts this restriction for them.

## Architecture

```
main.py                  Entry point: loads .env + Hydra config, runs the bot's polling loop
configs/                 Hydra configuration tree (bot, database, logging, regulation, scheduler)
src/dml_bot/
  config/                Structured (dataclass) config schema, validated by Hydra at startup
  db/                    SQLAlchemy models + session management (SQLite)
  services/               Framework-agnostic business logic (reservation conflict checking,
                           regulation, users, servers, watches, usage aggregation) — unit-tested
                           independently of Telegram
  bot/                   Shared identity/permission checks (auth.py) and message formatting
                           (formatting.py), used by bot_reply/ and the scheduler alike
  bot_reply/             python-telegram-bot wiring: a persistent reply-keyboard menu (flat
                           button grid docked below the message box), conversation wizards,
                           admin/student handlers
  scheduling/            APScheduler jobs: freed-slot notifications, pre-start reminders, cleanup
  charts/                Plotly rendering for admin usage reports (ranked horizontal bar chart)
  utils/                 Shared helpers (all datetimes are stored/compared as naive UTC, since
                           SQLite drops timezone info on round-trip)
logs/                    Rotating log files (created at runtime)
data/                    SQLite database file (created at runtime)
tests/
  unit/                  Service-layer and scheduling-job tests (in-memory SQLite)
  integration/           Drives real bot handler coroutines against a real (in-memory) DB, only
                           the Telegram network layer is stubbed
```

The reservation engine's core algorithm (`services/reservation_service.py`) validates slot
alignment, duration/RAM/booking-horizon limits against the regulation, then runs a sweep-line over
overlapping reservations on the target GPU to find peak concurrent RAM usage, rejecting the
request if it would exceed the GPU's total RAM at any point in the requested window. The
reservation wizard and the watch auto-booking path both call this exact same function, so there is
exactly one place reservation rules are enforced.

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
   | `ADMIN_IDS`          | Comma-separated Telegram numeric IDs of bootstrap admins (see [Multiple admins](#multiple-admins)) |
   | `TZ`                 | IANA timezone used to display times to users (e.g. `Asia/Tehran`)     |

3. **Review tunables** in `configs/` (all non-secret, all overridable on the command line via
   Hydra, e.g. `python main.py regulation.booking_horizon_days=60`):

   - `configs/bot/default.yaml` — display timezone, date-picker window, Telegram parse mode
   - `configs/database/default.yaml` — SQLite file path
   - `configs/logging/default.yaml` — log level, rotation size/backups, log directory
   - `configs/regulation/default.yaml` — seed values for the global regulation (only used to
     populate the database on first run; after that, admins edit it live via the bot)
   - `configs/scheduler/default.yaml` — background job poll interval, reminder lead time, cleanup
     retention window
   - `configs/ram_input/default.yaml`, `configs/schedule_chart/default.yaml`,
     `configs/list_grids/default.yaml` — bot UI tunables, described in
     [Using the bot](#using-the-bot) below

4. **Run the bot:**

   ```bash
   python main.py
   ```

   On first run this creates `data/dml_bot.sqlite3`, seeds the regulation from
   `configs/regulation/default.yaml`, and starts polling Telegram.

### Using the bot

The bot (`src/dml_bot/bot_reply/`) is a persistent reply keyboard: a flat grid of buttons docked
below the message box, rather than buttons attached to individual messages. Every list-selection
screen (GPUs, dates, reservations, users, ...) that could exceed one screen is paginated with
◀ Prev / ▶ Next controls. Reservation duration and RAM, and a watch's minimum-RAM threshold, are
all entered as typed whole numbers (validated against the regulation's limits / the GPU's free or
total RAM) rather than picking from preset buttons, since an arbitrary integer has no natural
bounded button set. The RAM unit students type in (whole GB by default, or MB) is configurable via
`ram_input.unit` in `configs/ram_input/default.yaml` — stored/validated values are always MB
regardless of the configured input unit. Every other typed input is genuinely free-form data with
no bounded set of choices (a new user's full name, a new server/GPU's name, a regulation field's
new value).

Right after Step 1/5 (choosing a GPU) in **Reserve GPU**, the bot automatically sends that GPU's
RAM-occupancy chart (same renderer as 🗓 Schedule — see [Chart renderer](#chart-renderer)) for
today through `bot.date_picker_days_visible` days ahead — the same window the next step's
date-picker offers — so a student can see free space before picking a date/time, with no extra tap
required. It reuses `bot.date_picker_days_visible` (`configs/bot/default.yaml`, capped by the
regulation's booking horizon) for the day count and
`schedule_chart.bucket_hours`/`schedule_chart.max_width_chars` for the chart's resolution/width —
no separate config was added for this.

**❓ Help** (`/help` or the main-menu button) sends a full step-by-step walkthrough of every
student option (Reserve GPU, My Reservations, Schedule, Watches) in one message
(`HELP_TEXT_STUDENT` in `src/dml_bot/bot_reply/handlers/common.py`). If the requester is an
admin, a second message follows covering every Admin Panel option (Manage Users, Manage Servers,
Regulation, Usage Report, All Reservations) in the same step-by-step style
(`HELP_TEXT_ADMIN`) — students never see the admin message.

Every wizard screen has a **◀ Back** button that steps back exactly one screen (re-showing the
previous step, not the wizard's first screen), plus a separate **🏠 Main Menu** button that exits
to the main menu instantly from any depth. Pressing ◀ Back on a student wizard's first screen
exits to the main menu, since there's nothing earlier to step back to. The five admin sub-flows
(Manage Users, Manage Servers, Regulation, Usage Report, All Reservations) sit one level deeper,
behind **🛠 Admin Panel** — pressing ◀ Back on *their* first screen steps back up to the Admin
Panel menu instead, consistent with the "one screen at a time" rule; 🏠 Main Menu still exits all
the way out from any of these screens.

The admin panel's **Manage Users** and **Manage Servers** screens support renaming and permanently
deleting users, servers, and GPUs (each behind a confirmation step) in addition to the existing
activate/deactivate toggle. Deleting a user/server/GPU also deletes its reservations and watch
subscriptions, since this project doesn't enable SQLite FK cascade — those dependent rows are
removed explicitly in `user_service`/`server_service` to avoid leaving orphaned rows behind.

**All Reservations** starts with a scope choice: **🗂 All Reservations** (every upcoming
reservation lab-wide, as before) or **👤 By User** (a picker listing only students who currently
hold at least one upcoming reservation, then that student's reservations only). Either list adds
a bulk-cancel button on top of the existing "tap one reservation to cancel it" behavior:
**🗑 Cancel All (this user)** in the by-user view uses the same Confirm/Back step as a single
cancellation, while **🗑 Cancel ALL Reservations** in the all-reservations view additionally
requires typing the phrase `CANCEL ALL` (case-insensitive) given its much larger blast radius —
◀ Back at that prompt backs out without cancelling anything. Whenever an admin cancels a
reservation from this screen — one at a time, all of one student's, or all lab-wide — the
affected student gets a Telegram DM for each individual reservation cancelled, so a bulk cancel
sends one message per reservation rather than a single combined summary.

**Per-server access control**: admins implicitly have access to every server; students only see
and can reserve/watch GPUs on servers an admin has explicitly granted them (`server_access`
table, `src/dml_bot/services/server_access_service.py`). Access is opt-in and per-student, not
inherited from anywhere else:
- When adding a student (**➕ Add User**), picking at least one accessible server is a required
  step before the account is created.
- A student added before this feature shipped, or a server created afterward, grants nobody
  access by default — an admin must explicitly check it off.
- An existing student's access can be changed any time from **Manage Users → (select student) →
  🔐 Server Access**, a checklist of every server toggled on/off, applied on **✅ Done**.
- A student with no granted servers sees "You don't have access to any servers yet" instead of a
  GPU list when they try to reserve, watch, or view a schedule.

**Button grid layout**: most paginated list screens show one button per row with ◀ Prev / ▶ Next
controls once the list overflows a page, same as always. Four screens instead lay their page out
as a multi-column grid (still paginating with ◀ Prev / ▶ Next if there are more items than fit on
one page) — the reservation date and start-time pickers (4 columns), and the admin's user and
server lists (2 columns). The 🛠 Admin Panel menu itself (its 5 options — Manage Users, Manage
Servers, Regulation, Usage Report, All Reservations) is also a grid (3 columns); it's a small
fixed list rather than a paginated one, so it only has a `columns` setting, no `rows`/pagination.
Column/row counts per screen are configurable in `configs/list_grids/default.yaml`
(`start_time`, `date`, `user_list`, `server_list`, each with a `columns`/`rows` pair; page size is
`columns * rows`; `admin_menu` has just `columns`). The GPU list, reservation lists, and the watch
list are unaffected and always stay one button per row.

"View Schedule" offers a configurable set of date ranges — always "Today", plus a list of day-counts
(default `[3, 5, 7, 10, 14]`, configurable via `schedule_chart.range_days_options`) with any option
longer than the regulation's booking horizon hidden from the menu. It also renders a fixed-width
monospace RAM-occupancy bar chart (`src/dml_bot/bot_reply/ram_chart.py`, wrapped in Telegram `<pre>`
blocks), showing how a GPU's RAM is split between concurrently overlapping reservations over the
chosen range — bar length is proportional to RAM used, not time, so two students sharing a GPU show
up as two partial fills. Every time bucket is shown (including fully-free ones) at the exact same
configured size regardless of the selected range — buckets are never merged or auto-widened. Each
bucket is always one line: occupant names are abbreviated (`Ali Ahmadi` → `A.Ahmadi`) and truncated
with `…` if a bucket still doesn't fit, rather than wrapping onto a second line. Because a long range
at a small bucket size can produce more text than fits in one Telegram message (4096-char hard
limit), the chart is sent as multiple sequential messages when needed — page breaks only ever land
between two calendar days (never mid-day), so a day's buckets always stay together on one message.
The exact reservation list below the chart shows each reservation's full start and end date+time
(not just the time-of-day). Configurable in `configs/schedule_chart/default.yaml`:
- `bucket_hours` — width of each time bucket, applied uniformly no matter how long the selected
  range is.
- `max_width_chars` — every rendered line is laid out to this width so it can't wrap on a phone
  screen; raise/lower it to match your users' typical device width.
- `range_days_options` — the day-count choices offered by "View Schedule" (besides "Today").

The display timezone (`bot.timezone`) can be overridden without touching `configs/` by setting `TZ`
in `.env` (e.g. `TZ=Asia/Tehran`) — if set, it takes precedence over `configs/bot/default.yaml`.

#### Chart renderer

The RAM-occupancy chart above appears in three places: "View Schedule", the availability chart
Reserve GPU shows right after picking a GPU, and the equivalent chart in the New Watch wizard. All
three are driven by the one admin-controlled setting below rather than each picking independently
(`src/dml_bot/bot_reply/chart_delivery.py`), with four choices:

- **`legacy`** (default) — the monospace text chart described above.
- **`plotly_bars`** — a Plotly stacked bar chart: one bar per time bucket (same bucketing as
  `legacy`), segmented and colored by user, with a dashed line at the GPU's total capacity. The
  closest visual analog to `legacy`, just with real color identity per user instead of abbreviated
  initials.
- **`plotly_area`** — a Plotly stacked area chart that changes exactly at each reservation's
  start/end (not snapped to buckets), colored by user, same capacity line.
- **`plotly_gantt`** — a Plotly per-user timeline: one row per user, bars spanning each
  reservation's exact start/end labeled with the RAM amount — easiest for tracing whose
  reservation is whose, at the cost of not directly showing combined RAM load.

The three Plotly renderers are sent as a single PNG photo (rendered via `kaleido`) rather than
text, since Telegram can't show an interactive Plotly chart inline in chat; `legacy` is still sent
as one or more `<pre>`-wrapped text messages, same as before. Colors follow a fixed 8-hue
categorical order, assigned to the top 7 users by RAM usage in the shown window; any additional
user folds into a shared gray "Other" series rather than generating a 9th hue.

Seed value: `schedule_chart.default_renderer` in `configs/schedule_chart/default.yaml`, used only
to populate the database on first run. After that, a bootstrap or DB-promoted admin switches it
live from **🛠 Admin Panel → 🎨 Chart Style** — no redeploy needed, same pattern as **⚖️
Regulation**.

### Registering a student

The bot does not connect to any lab directory service. Registration is self-service via a one-time
invite code, so the admin never needs to look up the student's Telegram ID:

1. The admin opens **🛠 Admin Panel → 👤 Manage Users → ➕ Add User**, types the student's full name,
   then picks which server(s) they may use — at least one is required to finish. The bot replies
   with a one-time invite code.
2. The admin sends that code to the student (by any channel — chat, email, in person).
3. The student sends `/start <code>` to the bot, which links their Telegram ID to the pre-filled
   registration and consumes the code.

A pending (not yet redeemed) invite is listed alongside registered students in **Manage Users**,
with a 🗑 to revoke it if it was mistyped or is no longer needed.

### Multiple admins

`ADMIN_IDS` in `.env` is a fixed, comma-separated set of **bootstrap admins** — they always have
admin rights (`src/dml_bot/bot/auth.py::is_bootstrap_admin`) regardless of anything stored in the
database, so there's always at least one way in even if the database is wiped.

A bootstrap admin can additionally promote any already-registered user to admin from **Manage
Users → (select user) → 🛡 Grant admin** — this sets a DB-stored `User.is_admin` flag
(`user_service.set_admin`) rather than editing `.env`, so it takes effect immediately with no
redeploy, and can be revoked the same way (**🛡 Revoke admin**). A registered user must exist first
(register them via an invite code, same as any student, then promote them).

The 🛡 Grant/Revoke admin button is only shown to, and only actionable by, bootstrap admins — a
user promoted via the DB role sees and uses every other admin feature identically, but cannot
promote or demote anyone else's admin status. Deactivating a promoted admin's account
(**🚫 Deactivate**) also removes their admin rights while inactive, same as it would for a student.

A bootstrap admin can use every student feature too (Reserve GPU, My Reservations, Schedule,
Watches), but — unlike a student — is never issued an invite code, so there's no `User` row to
attach a reservation to until they've used one of those features once. The first time a bootstrap
admin opens any student feature, the bot asks for the name to show on their reservations, creates
their `User` row from that reply, then resumes straight into the feature they opened (no invite
code or admin action needed — they're already trusted by virtue of being in `ADMIN_IDS`).

### Deploying with Docker

A `Dockerfile` and `docker-compose.yml` give the lab server a repeatable deployment path that
doesn't depend on a hand-configured virtualenv. The image installs `requirements.txt` and the
`dml_bot` package (same two steps as the manual [Setup](#setup)), runs as a non-root user, and
keeps `data/` (the SQLite file) and `logs/` on the host via bind mounts so they survive container
rebuilds and stay directly inspectable on the server.

1. **Configure secrets**, same as manual setup:

   ```bash
   cp .env.example .env
   # then fill in TELEGRAM_BOT_TOKEN, ADMIN_IDS, TZ
   ```

2. **Build and start the bot:**

   ```bash
   docker compose up -d --build
   ```

   This builds the image, creates `./data` and `./logs` on the host if they don't exist, mounts
   them into the container, and starts the bot in the background with `restart: unless-stopped` (so
   it comes back up automatically after a server reboot or crash).

3. **Check it's running / follow logs:**

   ```bash
   docker compose ps
   docker compose logs -f
   ```

4. **Apply a config or code change:**

   ```bash
   docker compose up -d --build
   ```

   Rebuilds the image and recreates the container; `data/` and `logs/` are untouched since they
   live on the host, not inside the container.

5. **Stop the bot:**

   ```bash
   docker compose down
   ```

   The container is removed but `./data` and `./logs` remain on the host.

Hydra command-line overrides (e.g. changing a regulation default) can be passed by editing the
`command:` key in `docker-compose.yml`, since Hydra reads `sys.argv` the same way whether it's
invoked directly or inside a container:

```yaml
services:
  dml-bot:
    command: ["python", "main.py", "regulation.booking_horizon_days=60"]
```

Without Docker Compose, the equivalent manual commands are:

```bash
docker build -t dml-resource-manager .
docker run -d --name dml-resource-manager --restart unless-stopped \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  dml-resource-manager
```

### Watches and auto-booking

**🔔 Watches** let a student ask to hear about free capacity on a GPU over a specific window,
without polling the schedule themselves. Creating one steps through the same screens, in the same
order, as **📅 Reserve GPU** (same availability chart after picking the GPU, same date picker, same
start-time grid, same typed duration/RAM prompts) — the only difference is the final step, where
instead of immediately reserving the window the student chooses what happens once that much RAM is
actually free throughout it:

- **Just notify** (the default) — the student gets a push the instant enough capacity frees, and
  must manually reserve it themselves; first to act wins if multiple students are watching the
  same capacity.
- **Auto-book** — instead of notifying, the bot books the freed window on the student's behalf the
  instant a match is found: from whenever it frees through the watch's range end, capped by the
  regulation's max reservation duration, at the RAM amount the student asked to be notified about.
  The student still gets a push, now confirming the booking instead of asking them to act.

Auto-booking reuses the exact same `reservation_service.create_reservation` validation as a normal
reservation (slot alignment, RAM/duration/booking-horizon limits, the per-user active-reservation
cap, the single-GPU-at-a-time rule) — it adds no rules of its own. If any of them reject the
attempt (most commonly: the student is already at their active-reservation limit), the watch
silently falls back to a plain notification instead of failing outright, so the student is never
left without a signal that capacity is free. Either way — auto-booked or just notified — the watch
is then consumed; a student who wants to keep watching after that must create a new one.

## Testing

```bash
pytest                      # unit + integration tests
pytest tests/unit            # service-layer and scheduling-job logic only
pytest tests/integration     # full handler/conversation flows against a real (in-memory) DB
```

Integration tests (`test_reply_*.py`) construct real `python-telegram-bot`
`Update`/`Message`/`CallbackQuery` objects and call the actual handler coroutines, so they exercise
real conversation logic, real database writes, and real keyboard/callback-data (or button-label)
parsing — only the network-facing `Bot` methods (`send_message`, `edit_message_text`,
`send_photo`, `answer_callback_query`) are replaced with recording mocks.

## Project conventions

- All datetimes are stored and compared as **naive UTC** throughout the codebase (see
  `src/dml_bot/utils/time_utils.py`); conversion to/from the configured display timezone happens
  only at the presentation layer.
- Reservations use a configurable fixed time-slot grid (`regulation.min_reservation_slot_minutes`)
  so free/busy calculations and calendar rendering stay simple.
- `regulation.min_cancellation_notice_minutes` (default `0`, i.e. disabled) sets how much advance
  notice a student must give to self-cancel a reservation; cancelling inside that window is
  rejected with an explanation (`reservation_service.assert_cancellable`).
  Admin-initiated cancellations (single, per-user bulk, lab-wide bulk, and override) always bypass
  this check by design — the cutoff only discourages last-minute student flaking, it isn't a lock
  admins need to work around. `0` is a valid value for this field alone (every other regulation
  field requires a positive whole number), since it's the natural way to turn the cutoff off
  entirely.
- The bot's handlers never duplicate business logic: they call the same functions in `services/`,
  so a rule change (e.g. a new regulation field) only needs to be enforced once.
- See `TODO.md` for design alternatives that were considered but deferred for a later version.
