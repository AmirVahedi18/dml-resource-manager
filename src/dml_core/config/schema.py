"""Structured config dataclasses registered with Hydra's ConfigStore for validation."""
from dataclasses import dataclass, field

from hydra.core.config_store import ConfigStore


@dataclass
class DatabaseConfig:
    path: str = "data/dml.sqlite3"
    echo: bool = False


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
    filename: str = "app.log"
    max_bytes: int = 1_048_576
    backup_count: int = 5
    console: bool = True


@dataclass
class RegulationConfig:
    max_ram_per_reservation_gb: int = 16
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
    # How long a cancelled/consumed watch subscription lingers before cleanup deletes it.
    # Reservations are never deleted by cleanup -- they're kept forever for historical
    # availability lookback.
    cleanup_retention_days: int = 30


@dataclass
class ScheduleChartConfig:
    bucket_hours: float = 2.0


@dataclass
class AppConfig:
    # IANA timezone used to display times to users (e.g. Asia/Tehran, UTC). Overridable without
    # touching configs/ by setting TZ in .env -- see main.py.
    timezone: str = "UTC"
    web: WebConfig = field(default_factory=WebConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    regulation: RegulationConfig = field(default_factory=RegulationConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    schedule_chart: ScheduleChartConfig = field(default_factory=ScheduleChartConfig)


def register_configs() -> None:
    cs = ConfigStore.instance()
    cs.store(name="base_config", node=AppConfig)
