"""Structured config dataclasses registered with Hydra's ConfigStore for validation."""
from dataclasses import dataclass, field

from hydra.core.config_store import ConfigStore


@dataclass
class BotConfig:
    parse_mode: str = "HTML"
    timezone: str = "UTC"
    date_picker_days_visible: int = 14


@dataclass
class DatabaseConfig:
    path: str = "data/dml_bot.sqlite3"
    echo: bool = False


@dataclass
class InterfaceConfig:
    # Which interface main.py runs: "bot" (existing Telegram polling loop, untouched) or "web"
    # (FastAPI + SPA). Exactly one runs per deployment/process.
    mode: str = "bot"


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    # Origins allowed to call the API with credentials (the SPA's dev-server and/or production
    # origin). Secrets (JWT signing key, bootstrap admin credentials) live in .env, not here --
    # see WEB_JWT_SECRET / WEB_ADMIN_USERNAME / WEB_ADMIN_PASSWORD.
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    access_token_expire_minutes: int = 720


@dataclass
class LoggingConfig:
    level: str = "INFO"
    dir: str = "logs"
    filename: str = "bot.log"
    max_bytes: int = 1_048_576
    backup_count: int = 5
    console: bool = True


@dataclass
class RegulationConfig:
    max_ram_per_reservation_mb: int = 16384
    max_duration_hours: int = 12
    booking_horizon_days: int = 90
    min_reservation_slot_minutes: int = 30
    max_active_reservations_per_user: int = 3
    # Minimum notice (minutes) a student must give before a reservation's start to self-cancel it
    # without penalty; 0 disables the cutoff (students may cancel anytime before start, as in v1).
    # Admin-initiated cancellations (single/bulk/override) always bypass this cutoff.
    min_cancellation_notice_minutes: int = 0


@dataclass
class SchedulerConfig:
    poll_interval_seconds: int = 60
    reminder_minutes_before: int = 15
    # How long a cancelled/consumed watch subscription lingers before cleanup deletes it.
    # Reservations are never deleted by cleanup -- they're kept forever for Usage Report's
    # 📅 Historical Availability screen.
    cleanup_retention_days: int = 30


@dataclass
class RamInputConfig:
    # Unit typed by students for the reservation/watch RAM steps: "GB" (whole gigabytes) or "MB"
    # (whole megabytes). Purely a display/input convenience -- stored values are always MB.
    unit: str = "GB"


@dataclass
class ScheduleChartConfig:
    bucket_hours: float = 2.0
    max_width_chars: int = 30
    # "View Schedule" date-range choices, in days (besides the always-present "Today"); any
    # option exceeding the regulation's booking horizon is hidden.
    range_days_options: list[int] = field(default_factory=lambda: [3, 5, 7, 10, 14])
    # Seed value for the DB-stored chart renderer choice (see chart_settings_service), used only
    # on first run -- after that, admins change it live via the bot's Chart Style screen. One of
    # "legacy" (fixed-width text chart), "plotly_bars", "plotly_area", "plotly_gantt".
    default_renderer: str = "legacy"


@dataclass
class GridConfig:
    # How many buttons per row (columns) and how many rows are shown per page for a given
    # paginated list screen. page_size = columns * rows; columns=1 is the original one-button-
    # per-row layout.
    columns: int = 1
    rows: int = 6


@dataclass
class ListGridsConfig:
    # Per-screen button-grid dimensions for the reply_keyboard interface's paginated list
    # screens. Screens not listed here (GPU list, reservation list, watch list) keep the
    # original one-column layout and aren't configurable through this group.
    start_time: GridConfig = field(default_factory=lambda: GridConfig(columns=4, rows=6))
    date: GridConfig = field(default_factory=lambda: GridConfig(columns=4, rows=6))
    user_list: GridConfig = field(default_factory=lambda: GridConfig(columns=2, rows=6))
    server_list: GridConfig = field(default_factory=lambda: GridConfig(columns=2, rows=6))
    admin_menu: GridConfig = field(default_factory=lambda: GridConfig(columns=3, rows=2))


@dataclass
class AppConfig:
    interface: InterfaceConfig = field(default_factory=InterfaceConfig)
    bot: BotConfig = field(default_factory=BotConfig)
    web: WebConfig = field(default_factory=WebConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    regulation: RegulationConfig = field(default_factory=RegulationConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    schedule_chart: ScheduleChartConfig = field(default_factory=ScheduleChartConfig)
    ram_input: RamInputConfig = field(default_factory=RamInputConfig)
    list_grids: ListGridsConfig = field(default_factory=ListGridsConfig)


def register_configs() -> None:
    cs = ConfigStore.instance()
    cs.store(name="base_config", node=AppConfig)
