"""Central logging configuration: rotating file handler under logs/ plus optional console output."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dml_core.config.schema import LoggingConfig

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(cfg: LoggingConfig) -> None:
    log_dir = Path(cfg.dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("dml_core")
    root.setLevel(cfg.level)
    root.handlers.clear()

    file_handler = RotatingFileHandler(
        log_dir / cfg.filename,
        maxBytes=cfg.max_bytes,
        backupCount=cfg.backup_count,
    )
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(file_handler)

    if cfg.console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(console_handler)
