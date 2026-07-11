# DML Resource Manager

Fair, transparent GPU-time scheduling for the DML (Data science and Machine learning Laboratory)
research lab. Students reserve a specific GPU, on a specific server, for a specific RAM amount and
time window, instead of grabbing whatever's free and holding it indefinitely. The lab admin manages
users, servers/GPUs, and the regulation (limits) that govern every reservation.

The app is a scheduling/coordination layer, not a live resource monitor: it does not connect to
the lab's servers. "Usage" in admin reports and schedules means *booked* time and RAM, not
real-time `nvidia-smi` telemetry. Compliance with reserved time slots is enforced by lab policy,
not by the software.

The app is a FastAPI backend (`src/dml_web/`) + React SPA (`web/frontend/`), talking to a
framework-agnostic core (`src/dml_core/`) that holds the database models and business logic. A rule
enforced in `services/` (e.g. a new regulation field) takes effect everywhere from one place.

## How it works

- **Students** register with the admin, then reserve a GPU, browse the schedule, cancel a
  reservation, or watch a busy time range for freed capacity (see
  [Watches and auto-booking](#watches-and-auto-booking)) — an ordinary set of pages (see
  [Web interface](#web-interface)).
- **Admins** manage users, servers/GPUs, the global regulation (RAM/duration/booking-horizon
  limits), usage charts, and can override-cancel any reservation lab-wide. The bootstrap admin
  (`WEB_ADMIN_USERNAME` in `.env`) always has admin rights and can't be revoked through the app
  itself, from which further admins (e.g. a TA) can be promoted without touching `.env` or
  redeploying (see [Multiple admins](#multiple-admins)).
- A reservation is **self-service and auto-confirmed**: if it fits the GPU's free capacity and the
  regulation's limits, it's created immediately — no admin approval step.
- Multiple students can share one GPU concurrently as long as their combined RAM never exceeds
  its total RAM at any point in time.
- By default a student can only hold one reservation at a time across all servers/GPUs; the admin
  can grant individual students a "multi-GPU" privilege that lifts this restriction for them.

## Architecture

```
main.py                  Entry point: loads .env + Hydra config, boots the web backend
configs/                 Hydra configuration tree (web, database, logging, regulation,
                           scheduler, schedule_chart, ...)
src/dml_core/
  config/                Structured (dataclass) config schema, validated by Hydra at startup
  db/                    SQLAlchemy models + session management (SQLite)
  services/               Framework-agnostic business logic (reservation conflict checking,
                           regulation, users, servers, watches, usage aggregation, auth/credential
                           management) — unit-tested independently of the web layer
  utils/                 Shared helpers (all datetimes are stored/compared as naive UTC, since
                           SQLite drops timezone info on round-trip)
src/dml_web/             FastAPI web backend
  main.py                App factory + process entrypoint
  routers/               One module per feature area (auth, schedule, reservations, watches,
                           admin_users, admin_servers, admin_regulation, admin_reservations,
                           admin_usage) -- each route is a thin wrapper over a services/ function
  chart_data.py           Pure JSON-shaping for the SPA's interactive charts
  scheduler.py            Background job: auto-book-only watch matching, plus stale-watch cleanup
web/frontend/             React + TypeScript + Vite SPA talking to dml_web's JSON API
logs/                    Rotating log files (created at runtime)
data/                    SQLite database file (created at runtime)
tests/
  unit/                  Service-layer tests (in-memory SQLite)
  web/                   Drives the FastAPI app via TestClient against a real (in-memory) DB
```

The reservation engine's core algorithm (`services/reservation_service.py`) validates slot
alignment, duration/RAM/booking-horizon limits against the regulation, then runs a sweep-line over
overlapping reservations on the target GPU to find peak concurrent RAM usage, rejecting the
request if it would exceed the GPU's total RAM at any point in the requested window. The
reservation flow and the watch auto-booking path both call this exact same function, so there is
exactly one place reservation rules are enforced.

**Per-server access control**: admins implicitly have access to every server; students only see
and can reserve/watch GPUs on servers an admin has explicitly granted them (`server_access`
table, `src/dml_core/services/server_access_service.py`). Access is opt-in and per-student, not
inherited from anywhere else — a student added before this feature shipped, or a server created
afterward, grants nobody access by default; an admin must explicitly check it off from
**Manage Users → (select student) → Server Access**.

## Setup

1. **Create and activate a virtualenv, then install dependencies:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install -e .
   ```

   The last step installs the `dml_core` package itself (from `src/`) in editable mode, which is
   what makes `import dml_core` work from anywhere — including `python main.py` run directly from
   the project root. Without it you'll get `ModuleNotFoundError: No module named 'dml_core'`.

2. **Configure secrets** — copy `.env.example` to `.env` and fill it in:

   ```bash
   cp .env.example .env
   ```

   | Variable             | Description                                                          |
   |----------------------|-----------------------------------------------------------------------|
   | `WEB_JWT_SECRET`     | Signs/verifies the web UI's login session tokens — generate with `openssl rand -hex 32` |
   | `WEB_ADMIN_USERNAME` / `WEB_ADMIN_PASSWORD` | Bootstrap web admin, seeded once on first startup (see [Web interface](#web-interface)) |
   | `TZ`                 | IANA timezone used to display times to users (e.g. `Asia/Tehran`)     |

3. **Review tunables** in `configs/` (all non-secret, all overridable on the command line via
   Hydra, e.g. `python main.py regulation.booking_horizon_days=60`):

   - `configs/web/default.yaml` — web host/port, CORS origins, login session lifetime
   - `configs/database/default.yaml` — SQLite file path
   - `configs/logging/default.yaml` — log level, rotation size/backups, log directory
   - `configs/regulation/default.yaml` — seed values for the global regulation (only used to
     populate the database on first run; after that, admins edit it live in the web UI)
   - `configs/scheduler/default.yaml` — background job poll interval and stale watch-subscription
     retention window (reservations are never auto-deleted; see
     [Historical availability](#historical-availability-reservations-are-kept-forever))
   - `configs/schedule_chart/default.yaml` — occupancy chart bucket width

4. **Run it:**

   ```bash
   python main.py
   ```

   On first run this creates `data/dml.sqlite3` and seeds the regulation from
   `configs/regulation/default.yaml`.

### Registering a student

The app does not connect to any lab directory service. The admin (or any promoted admin) creates
accounts directly from **Manage Users → Add users**, setting each one's username and password —
the form accepts multiple rows so a whole class/cohort can be created in one submission. A student
changes their own password later from **Change Password**; an admin can also reset any user's
password from **Manage Users**.

### Multiple admins

`WEB_ADMIN_USERNAME`/`WEB_ADMIN_PASSWORD` in `.env` seed a fixed **bootstrap admin** the first time
the backend starts — they always have admin rights (`auth_service.ensure_admin_seeded`) regardless
of anything stored in the database, so there's always at least one way in even if the database is
wiped. Existing accounts are left untouched on later restarts even if you change these values.

A bootstrap admin can additionally promote any already-registered user to admin from **Manage
Users → (select user) → Grant admin** — this sets a DB-stored `User.is_admin` flag
(`user_service.set_admin`) rather than editing `.env`, so it takes effect immediately with no
redeploy, and can be revoked the same way. An admin can't revoke their own admin role if they're
the last remaining admin (`admin_users.py` checks the active-admin count before allowing a
demotion) — the app's equivalent of "there's always at least one way in."

### Deploying with Docker

`docker-compose.yml` defines two services: `dml-api` (the FastAPI backend, built from the root
`Dockerfile`) and `dml-web` (an nginx container serving the built React SPA and proxying `/api/*`
to `dml-api`). Both keep `data/` (the SQLite file) and `logs/` on the host via bind mounts so they
survive container rebuilds and stay directly inspectable on the server.

1. **Configure secrets**, same as manual setup:

   ```bash
   cp .env.example .env
   # then fill in WEB_JWT_SECRET, WEB_ADMIN_USERNAME, WEB_ADMIN_PASSWORD, TZ
   ```

2. **Build and start:**

   ```bash
   docker compose up -d --build
   ```

   Creates `./data` and `./logs` on the host if they don't exist, mounts them into the
   container(s), and starts with `restart: unless-stopped` (so it comes back up automatically after
   a server reboot or crash). The site is reachable at `http://<server>:8080/` — remap the host
   port in `docker-compose.yml`'s `dml-web.ports` if you want it on 80 instead (needs a host that
   can bind privileged ports).

3. **Check it's running / follow logs:**

   ```bash
   docker compose ps
   docker compose logs -f
   ```

4. **Apply a config or code change:**

   ```bash
   docker compose up -d --build
   ```

   Rebuilds the image(s) and recreates the container(s); `data/` and `logs/` are untouched since
   they live on the host, not inside the container.

5. **Stop:**

   ```bash
   docker compose down
   ```

   The container(s) are removed but `./data` and `./logs` remain on the host.

Hydra command-line overrides (e.g. changing a regulation default) can be passed by editing the
`command:` key in `docker-compose.yml`'s `dml-api` service, since Hydra reads `sys.argv` the same
way whether it's invoked directly or inside a container:

```yaml
services:
  dml-api:
    command: ["python", "main.py", "regulation.booking_horizon_days=60"]
```

Without Docker Compose, the equivalent manual command for the backend is:

```bash
docker build -t dml-resource-manager .
docker run -d --name dml-resource-manager-api --restart unless-stopped \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  dml-resource-manager
```

## Watches and auto-booking

**Watches** let a student ask to be automatically booked into a GPU's free capacity over a
specific window, without polling the schedule themselves. Creating one steps through the same
inputs as reserving (GPU, date/time range, RAM), but instead of immediately reserving the window
it's held as a pending watch: the instant that much RAM is actually free throughout the window,
the backend books it on the student's behalf — from whenever it frees through the watch's range
end, capped by the regulation's max reservation duration, at the RAM amount the student asked for.

Auto-booking reuses the exact same `reservation_service.create_reservation` validation as a normal
reservation (slot alignment, RAM/duration/booking-horizon limits, the per-user active-reservation
cap, the single-GPU-at-a-time rule) — it adds no rules of its own. If any of them reject the
attempt (most commonly: the student is already at their active-reservation limit), the watch stays
active and is retried on the next poll instead of being consumed, since there's no notification
channel to fall back to. A watch only makes sense while the GPU can't currently satisfy the
request — if it already has enough free RAM for the whole window, reserve directly instead.

## Web interface

### Authentication

- **Bootstrap admin**: see [Multiple admins](#multiple-admins) above.
- **Everyone else**: an admin creates accounts from **Manage Users → Add users** (see
  [Registering a student](#registering-a-student) above).
- Sessions are JWT bearer tokens (`WEB_JWT_SECRET` signs them, `web.access_token_expire_minutes`
  in `configs/web/default.yaml` controls their lifetime), stored client-side in `localStorage` and
  sent as an `Authorization: Bearer ...` header — there's no server-side session store.

### Charts

Occupancy and usage charts are rendered client-side from a JSON payload
(`dml_web/chart_data.py` → `OccupancyChart`/`UsageBarChart` in `web/frontend/src/components/`) —
always interactive, no server-side image rendering.

#### Historical availability (reservations are kept forever)

The daily background cleanup job (`dml_web/scheduler.py::run_cleanup`) never deletes `Reservation`
rows — only long-since-consumed `WatchSubscription` rows are pruned after
`scheduler.cleanup_retention_days`. Reservation history is kept indefinitely so an admin can
always look back via **Admin Panel → Usage Report → Historical Availability**, picking a GPU and
an arbitrary date window.

The chart's time-bucket width matches the live schedule view's `schedule_chart.bucket_hours` for
windows up to a week, so the two charts read the same way for the same range. Beyond a week it
scales up (`dml_web/chart_data.py::historical_bucket_hours`: 12h buckets up to 30 days, 24h up to
120 days, weekly beyond that), so a multi-month lookback doesn't render as thousands of unreadable
buckets.

### Local development

1. Run the backend (needs `WEB_JWT_SECRET` and, for the first run,
   `WEB_ADMIN_USERNAME`/`WEB_ADMIN_PASSWORD` in `.env`):

   ```bash
   python main.py
   ```

   Serves the JSON API on `http://localhost:8000` (`web.host`/`web.port` in
   `configs/web/default.yaml`).

2. In another terminal, run the SPA's dev server:

   ```bash
   cd web/frontend
   npm install
   npm run dev
   ```

   Serves on `http://localhost:5173` with `/api/*` proxied to `http://localhost:8000` (see
   `vite.config.ts`) — the SPA always calls relative `/api/...` paths, so it works unmodified in
   both dev (via the Vite proxy) and production (via the nginx proxy described in
   [Deploying with Docker](#deploying-with-docker)).

3. `npm run build` produces the static production bundle (`web/frontend/dist/`); this is what the
   `dml-web` Docker image serves.

## Testing

```bash
pytest                      # unit + web tests
pytest tests/unit            # service-layer logic only
pytest tests/web             # full FastAPI route flows against a real (in-memory) DB
```

`tests/web` drives the FastAPI app via real HTTP requests through
`fastapi.testclient.TestClient` (which also runs the app's real startup/shutdown lifespan,
including the auto-book scheduler) against a real in-memory SQLite DB — nothing about routing,
auth, or validation is mocked. The React SPA has no automated test suite (an internal lab tool at
this scale); changes to it should be checked with `npm run dev` against a running backend.

## Project conventions

- All datetimes are stored and compared as **naive UTC** throughout the codebase (see
  `src/dml_core/utils/time_utils.py`); conversion to/from the configured display timezone happens
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
- The web routers never duplicate business logic: they call the same functions in `services/`, so
  a rule change (e.g. a new regulation field) only needs to be enforced once.
- See `TODO.md` for design alternatives that were considered but deferred for a later version.
