import logging
import os

import hydra
from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf

from dml_bot.bot.app import build_application
from dml_bot.config.schema import AppConfig, register_configs
from dml_bot.db.session import init_engine, session_scope
from dml_bot.logging_setup import setup_logging
from dml_bot.scheduling.jobs import build_scheduler
from dml_bot.services import regulation_service

register_configs()


@hydra.main(version_base=None, config_path="configs", config_name="config")
def main(cfg: DictConfig) -> None:
    load_dotenv()
    app_cfg: AppConfig = OmegaConf.to_object(cfg)

    setup_logging(app_cfg.logging)
    logger = logging.getLogger("dml_bot.main")

    init_engine(app_cfg.database.path, echo=app_cfg.database.echo)
    with session_scope() as session:
        regulation_service.ensure_seeded(session, app_cfg.regulation)

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    admin_ids = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}

    # APScheduler needs a running event loop, which only exists once PTB's run_polling
    # starts one, so the scheduler is built/started/stopped via PTB's post_init/post_shutdown
    # hooks rather than synchronously here.
    scheduler_holder: dict = {}

    async def on_startup(app) -> None:
        scheduler = build_scheduler(app.bot, app_cfg)
        scheduler.start()
        scheduler_holder["scheduler"] = scheduler

    async def on_shutdown(_app) -> None:
        scheduler = scheduler_holder.get("scheduler")
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    application = build_application(token, admin_ids, app_cfg, post_init=on_startup, post_shutdown=on_shutdown)

    logger.info("DML Resource Manager bot starting")
    application.run_polling()


if __name__ == "__main__":
    main()
