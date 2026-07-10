import logging
import os

import hydra
from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf

from dml_core.config.schema import AppConfig, register_configs
from dml_core.db.session import init_engine, session_scope
from dml_core.logging_setup import setup_logging
from dml_core.services import regulation_service
from dml_web.main import run_web

register_configs()


@hydra.main(version_base=None, config_path="configs", config_name="config")
def main(cfg: DictConfig) -> None:
    load_dotenv()
    app_cfg: AppConfig = OmegaConf.to_object(cfg)

    tz_override = os.environ.get("TZ", "").strip()
    if tz_override:
        app_cfg.timezone = tz_override

    setup_logging(app_cfg.logging)

    init_engine(app_cfg.database.path, echo=app_cfg.database.echo)

    with session_scope() as session:
        regulation_service.ensure_seeded(session, app_cfg.regulation)

    logging.getLogger("main").info("DML Resource Manager starting")
    run_web(app_cfg)


if __name__ == "__main__":
    main()
