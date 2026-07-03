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


@dataclass
class SchedulerConfig:
    poll_interval_seconds: int = 60
    reminder_minutes_before: int = 15
    cleanup_retention_days: int = 30


@dataclass
class WebappConfig:
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass
class AppConfig:
    interface: str = "webapp"  # "webapp" (Mini App only) or "legacy" (classic chat menu only)
    bot: BotConfig = field(default_factory=BotConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    regulation: RegulationConfig = field(default_factory=RegulationConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    webapp: WebappConfig = field(default_factory=WebappConfig)


def register_configs() -> None:
    cs = ConfigStore.instance()
    cs.store(name="base_config", node=AppConfig)
