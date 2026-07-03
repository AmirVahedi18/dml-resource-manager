import asyncio
import logging
import os
import signal

import hydra
import uvicorn
from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf
from telegram import MenuButtonDefault, MenuButtonWebApp, WebAppInfo

from dml_bot.api.app import build_api_app
from dml_bot.bot.app import build_application
from dml_bot.bot_reply.app import build_reply_application
from dml_bot.config.schema import AppConfig, register_configs
from dml_bot.db.session import init_engine, session_scope
from dml_bot.logging_setup import setup_logging
from dml_bot.scheduling.jobs import build_scheduler
from dml_bot.services import regulation_service

register_configs()


async def _wait_for_stop_signal() -> None:
    """Blocks until SIGINT/SIGTERM, mirroring what uvicorn.Server.serve() does on its own --
    needed here because in "legacy" mode there's no uvicorn server to own that wait."""
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()


async def _run(application, api_app, app_cfg: AppConfig, webapp_public_url: str) -> None:
    """Runs the Telegram bot's polling loop and -- only when `interface: webapp` -- the Mini App's
    web server, concurrently on one event loop. `Application.run_polling()` is a blocking
    convenience call that owns the loop itself, so it can't be combined with also serving HTTP --
    this drives the same initialize/start/poll lifecycle manually instead."""
    logger = logging.getLogger("dml_bot.main")
    scheduler = build_scheduler(application.bot, app_cfg)

    await application.initialize()

    if app_cfg.interface == "webapp":
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Open App", web_app=WebAppInfo(url=webapp_public_url))
        )
    else:
        await application.bot.set_chat_menu_button(menu_button=MenuButtonDefault())

    await application.start()
    await application.updater.start_polling()
    scheduler.start()
    try:
        if app_cfg.interface == "webapp":
            server = uvicorn.Server(
                uvicorn.Config(api_app, host=app_cfg.webapp.host, port=app_cfg.webapp.port, log_level="info")
            )
            await server.serve()
        else:
            logger.info("Running in %r interface mode -- Mini App web server not started", app_cfg.interface)
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

    if app_cfg.interface not in {"webapp", "legacy", "reply_keyboard"}:
        raise ValueError(
            "configs/config.yaml: interface must be 'webapp', 'legacy', or 'reply_keyboard', "
            f"got {app_cfg.interface!r}"
        )

    setup_logging(app_cfg.logging)
    logger = logging.getLogger("dml_bot.main")

    init_engine(app_cfg.database.path, echo=app_cfg.database.echo)
    with session_scope() as session:
        regulation_service.ensure_seeded(session, app_cfg.regulation)

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    admin_ids = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}
    webapp_public_url = os.environ.get("WEBAPP_PUBLIC_URL", "").strip()

    if app_cfg.interface == "webapp" and not webapp_public_url:
        raise RuntimeError(
            "interface is set to 'webapp' in configs/config.yaml but WEBAPP_PUBLIC_URL is not "
            "set in .env -- the Mini App needs a public HTTPS URL to register its menu button."
        )

    if app_cfg.interface == "reply_keyboard":
        application = build_reply_application(token, admin_ids, app_cfg)
    else:
        application = build_application(token, admin_ids, app_cfg)
    api_app = build_api_app(app_cfg, token, admin_ids) if app_cfg.interface == "webapp" else None

    logger.info("DML Resource Manager starting in %r interface mode", app_cfg.interface)
    asyncio.run(_run(application, api_app, app_cfg, webapp_public_url))


if __name__ == "__main__":
    main()
