"""FastAPI app factory + process entrypoint for the web backend. Imports only dml_core's db/
services/config layer."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dml_core.config.schema import AppConfig
from dml_core.db.session import session_scope
from dml_core.services import auth_service
from dml_web import security
from dml_web.errors import register_exception_handlers
from dml_web.scheduler import build_scheduler
from dml_web.routers import admin_regulation as admin_regulation_router
from dml_web.routers import admin_reservations as admin_reservations_router
from dml_web.routers import admin_servers as admin_servers_router
from dml_web.routers import admin_usage as admin_usage_router
from dml_web.routers import admin_users as admin_users_router
from dml_web.routers import auth as auth_router
from dml_web.routers import reservations as reservations_router
from dml_web.routers import schedule as schedule_router
from dml_web.routers import watches as watches_router

logger = logging.getLogger("dml_web.main")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    scheduler = build_scheduler(app.state.app_cfg)
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


def create_app(app_cfg: AppConfig) -> FastAPI:
    app = FastAPI(title="DML Resource Manager API", lifespan=_lifespan)
    app.state.app_cfg = app_cfg
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_cfg.web.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
    app.include_router(schedule_router.router, prefix="/api", tags=["schedule"])
    app.include_router(reservations_router.router, prefix="/api/reservations", tags=["reservations"])
    app.include_router(watches_router.router, prefix="/api/watches", tags=["watches"])
    app.include_router(admin_users_router.router, prefix="/api/admin/users", tags=["admin-users"])
    app.include_router(admin_servers_router.router, prefix="/api/admin/servers", tags=["admin-servers"])
    app.include_router(admin_servers_router.gpu_router, prefix="/api/admin/gpus", tags=["admin-servers"])
    app.include_router(admin_regulation_router.router, prefix="/api/admin/regulation", tags=["admin-regulation"])
    app.include_router(
        admin_reservations_router.router, prefix="/api/admin/reservations", tags=["admin-reservations"]
    )
    app.include_router(admin_usage_router.router, prefix="/api/admin/usage", tags=["admin-usage"])

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


def run_web(app_cfg: AppConfig) -> None:
    import uvicorn

    security.configure(
        secret=os.environ["WEB_JWT_SECRET"],
        expire_minutes=app_cfg.web.access_token_expire_minutes,
    )

    admin_username = os.environ.get("WEB_ADMIN_USERNAME", "").strip()
    admin_password = os.environ.get("WEB_ADMIN_PASSWORD", "").strip()
    with session_scope() as session:
        seeded = auth_service.ensure_admin_seeded(session, admin_username, admin_password)
    if seeded is not None:
        logger.info("Seeded bootstrap web admin %r", admin_username)

    app = create_app(app_cfg)
    uvicorn.run(app, host=app_cfg.web.host, port=app_cfg.web.port)
