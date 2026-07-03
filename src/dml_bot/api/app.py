from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dml_bot.api.routers import (
    admin_regulation,
    admin_reservations,
    admin_servers,
    admin_usage,
    admin_users,
    home,
    reserve,
    reservations,
    schedule,
    watches,
)
from dml_bot.api.templating import STATIC_DIR
from dml_bot.config.schema import AppConfig


def build_api_app(config: AppConfig, bot_token: str, admin_ids: set[int]) -> FastAPI:
    app = FastAPI(title="DML Resource Manager Mini App")
    app.state.config = config
    app.state.bot_token = bot_token
    app.state.admin_ids = admin_ids

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(home.router)
    app.include_router(schedule.router)
    app.include_router(reserve.router)
    app.include_router(reservations.router)
    app.include_router(watches.router)

    app.include_router(admin_users.router)
    app.include_router(admin_servers.router)
    app.include_router(admin_regulation.router)
    app.include_router(admin_usage.router)
    app.include_router(admin_reservations.router)

    return app
