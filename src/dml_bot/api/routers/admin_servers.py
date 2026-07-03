from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from dml_bot.api.deps import get_db_session, require_admin
from dml_bot.api.templating import templates
from dml_bot.db.models.server import Server
from dml_bot.services import server_service

router = APIRouter(prefix="/api/admin/servers")


def _render_overview(request: Request, session: Session):
    servers = server_service.list_servers(session, active_only=False)
    overview = [
        {"server": s, "gpus": server_service.list_gpus(session, s, active_only=False)} for s in servers
    ]
    return templates.TemplateResponse(request, "partials/admin_servers_overview.html", {"overview": overview})


@router.get("")
async def overview(request: Request, session: Session = Depends(get_db_session), _admin=Depends(require_admin)):
    return _render_overview(request, session)


@router.get("/new")
async def new_server_form(request: Request, _admin=Depends(require_admin)):
    return templates.TemplateResponse(request, "partials/admin_servers_new_server.html", {})


@router.post("/new")
async def create_server(
    request: Request,
    name: str = Form(...),
    session: Session = Depends(get_db_session),
    _admin=Depends(require_admin),
):
    try:
        server_service.create_server(session, name)
    except server_service.ServerAlreadyExistsError as exc:
        return templates.TemplateResponse(request, "partials/admin_servers_new_server.html", {"error": str(exc)})
    return _render_overview(request, session)


@router.get("/new-gpu")
async def new_gpu_choose_server(
    request: Request, session: Session = Depends(get_db_session), _admin=Depends(require_admin)
):
    servers = server_service.list_servers(session)
    return templates.TemplateResponse(
        request, "partials/admin_servers_new_gpu_server.html", {"servers": servers}
    )


@router.get("/new-gpu/{server_id}")
async def new_gpu_form(
    server_id: int, request: Request, session: Session = Depends(get_db_session), _admin=Depends(require_admin)
):
    server = session.get(Server, server_id)
    return templates.TemplateResponse(request, "partials/admin_servers_new_gpu_form.html", {"server": server})


@router.post("/new-gpu/{server_id}")
async def create_gpu(
    server_id: int,
    request: Request,
    index_on_server: int = Form(...),
    model_name: str = Form(...),
    total_ram_mb: int = Form(...),
    session: Session = Depends(get_db_session),
    _admin=Depends(require_admin),
):
    server = session.get(Server, server_id)
    try:
        server_service.add_gpu(session, server, index_on_server, model_name, total_ram_mb)
    except server_service.GPUIndexConflictError as exc:
        return templates.TemplateResponse(
            request, "partials/admin_servers_new_gpu_form.html", {"server": server, "error": str(exc)}
        )
    return _render_overview(request, session)
