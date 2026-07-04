import asyncio
import logging
import os
import signal

import hydra
from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf
from telegram import MenuButtonDefault

from dml_bot.bot_reply.app import build_reply_application
from dml_bot.config.schema import AppConfig, register_configs
from dml_bot.db.session import init_engine, session_scope
from dml_bot.logging_setup import setup_logging
from dml_bot.scheduling.jobs import build_scheduler
from dml_bot.services import regulation_service

register_configs()


async def _wait_for_stop_signal() -> None:
    """Blocks until SIGINT/SIGTERM, since polling-only mode has no other server owning the wait."""
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()


async def _run(application, app_cfg: AppConfig) -> None:
    scheduler = build_scheduler(application.bot, app_cfg)

    await application.initialize()
    await application.bot.set_chat_menu_button(menu_button=MenuButtonDefault())

    await application.start()
    await application.updater.start_polling()
    scheduler.start()
    try:
        await _wait_for_stop_signal()
    finally:
        scheduler.shutdown(wait=False)
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


@hydra.main(version_base=None, config_path="configs", config_name="config")
def main(cfg: DictConfig) -> None:
    load_dotenv()
    app_cfg: AppConfig = OmegaConf.to_object(cfg)

    tz_override = os.environ.get("TZ", "").strip()
    if tz_override:
        app_cfg.bot.timezone = tz_override

    setup_logging(app_cfg.logging)
    logger = logging.getLogger("dml_bot.main")

    init_engine(app_cfg.database.path, echo=app_cfg.database.echo)
    with session_scope() as session:
        regulation_service.ensure_seeded(session, app_cfg.regulation)

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    admin_ids = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}

    application = build_reply_application(token, admin_ids, app_cfg)

    logger.info("DML Resource Manager starting")
    asyncio.run(_run(application, app_cfg))


if __name__ == "__main__":
    main()
