"""Two routers in one module: `router` (servers, mounted at /api/admin/servers) and `gpu_router`
(GPUs, mounted at /api/admin/gpus) -- kept as separate path prefixes rather than nesting GPU routes
under /servers/{server_id}/gpus/{gpu_id}/... so a GPU-scoped route (rename/activate/delete by its
own id) never has to share a path shape with a server-scoped one."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.models.user import User
from dml_bot.services import server_service
from dml_web.deps import get_session, require_admin
from dml_web.schemas.admin_servers import (
    GpuAdminOut,
    GpuCreateRequest,
    GpuRenameRequest,
    ServerAdminOut,
    ServerCreateRequest,
    ServerRenameRequest,
    SetGpuActiveRequest,
    SetServerActiveRequest,
)

router = APIRouter()
gpu_router = APIRouter()


def _get_server_or_404(session: Session, server_id: int) -> Server:
    server = session.get(Server, server_id)
    if server is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")
    return server


def _get_gpu_or_404(session: Session, gpu_id: int) -> GPU:
    gpu = server_service.get_gpu(session, gpu_id)
    if gpu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "GPU not found")
    return gpu


@router.get("", response_model=list[ServerAdminOut])
def list_servers(
    session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> list[Server]:
    return server_service.list_servers(session, active_only=False)


@router.post("", response_model=ServerAdminOut, status_code=status.HTTP_201_CREATED)
def create_server(
    payload: ServerCreateRequest, session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> Server:
    return server_service.create_server(session, payload.name, payload.description)


@router.patch("/{server_id}/rename", response_model=ServerAdminOut)
def rename_server(
    server_id: int,
    payload: ServerRenameRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> Server:
    server = _get_server_or_404(session, server_id)
    return server_service.rename_server(session, server, payload.name)


@router.patch("/{server_id}/active", response_model=ServerAdminOut)
def set_server_active(
    server_id: int,
    payload: SetServerActiveRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> Server:
    server = _get_server_or_404(session, server_id)
    return server_service.set_server_active(session, server, payload.is_active)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(
    server_id: int, session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> None:
    server = _get_server_or_404(session, server_id)
    server_service.delete_server(session, server)


@router.get("/{server_id}/gpus", response_model=list[GpuAdminOut])
def list_gpus(
    server_id: int, session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> list[GPU]:
    server = _get_server_or_404(session, server_id)
    return server_service.list_gpus(session, server, active_only=False)


@router.post("/{server_id}/gpus", response_model=GpuAdminOut, status_code=status.HTTP_201_CREATED)
def add_gpu(
    server_id: int,
    payload: GpuCreateRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> GPU:
    server = _get_server_or_404(session, server_id)
    return server_service.add_gpu(session, server, payload.index_on_server, payload.model_name, payload.total_ram_mb)


@gpu_router.patch("/{gpu_id}/rename", response_model=GpuAdminOut)
def rename_gpu(
    gpu_id: int,
    payload: GpuRenameRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> GPU:
    gpu = _get_gpu_or_404(session, gpu_id)
    return server_service.rename_gpu(session, gpu, payload.model_name)


@gpu_router.patch("/{gpu_id}/active", response_model=GpuAdminOut)
def set_gpu_active(
    gpu_id: int,
    payload: SetGpuActiveRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> GPU:
    gpu = _get_gpu_or_404(session, gpu_id)
    return server_service.set_gpu_active(session, gpu, payload.is_active)


@gpu_router.delete("/{gpu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gpu(
    gpu_id: int, session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> None:
    gpu = _get_gpu_or_404(session, gpu_id)
    server_service.delete_gpu(session, gpu)
