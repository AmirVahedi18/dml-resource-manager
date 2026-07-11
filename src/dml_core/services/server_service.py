from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dml_core.db.models.gpu import GPU
from dml_core.db.models.server import Server
from dml_core.db.models.server_access import ServerAccess
from dml_core.db.models.watch import WatchSubscription
from dml_core.services import reservation_service
from dml_core.utils.time_utils import utc_now


class ServerAlreadyExistsError(Exception):
    pass


class GPUIndexConflictError(Exception):
    pass


def create_server(session: Session, name: str) -> Server:
    existing = session.execute(select(Server).where(Server.name == name)).scalar_one_or_none()
    if existing is not None:
        raise ServerAlreadyExistsError(f"server '{name}' already exists")
    server = Server(name=name)
    session.add(server)
    session.flush()
    return server


def list_servers(session: Session, active_only: bool = True) -> list[Server]:
    stmt = select(Server).where(Server.deleted_at.is_(None))
    if active_only:
        stmt = stmt.where(Server.is_active.is_(True))
    return list(session.execute(stmt).scalars().all())


def add_gpu(
    session: Session, server: Server, index_on_server: int, model_name: str, total_ram_mb: int
) -> GPU:
    existing = session.execute(
        select(GPU).where(GPU.server_id == server.id, GPU.index_on_server == index_on_server)
    ).scalar_one_or_none()
    if existing is not None:
        if existing.deleted_at is None:
            raise GPUIndexConflictError(
                f"GPU index {index_on_server} already exists on server '{server.name}'"
            )
        # The index belongs to a soft-deleted GPU (kept only so old reservations still resolve
        # `reservation.gpu`). The DB has a unique constraint on (server_id, index_on_server), so a
        # new row can't reuse this index -- revive the existing one instead.
        existing.model_name = model_name
        existing.total_ram_mb = total_ram_mb
        existing.is_active = True
        existing.deleted_at = None
        session.flush()
        return existing
    gpu = GPU(
        server_id=server.id,
        index_on_server=index_on_server,
        model_name=model_name,
        total_ram_mb=total_ram_mb,
    )
    session.add(gpu)
    session.flush()
    return gpu


def list_gpus(session: Session, server: Server, active_only: bool = True) -> list[GPU]:
    stmt = select(GPU).where(GPU.server_id == server.id, GPU.deleted_at.is_(None))
    if active_only:
        stmt = stmt.where(GPU.is_active.is_(True))
    return list(session.execute(stmt).scalars().all())


def get_gpu(session: Session, gpu_id: int) -> GPU | None:
    """Looked up by id only (deleted GPUs included) so historical usage reports can still resolve
    reservations that reference a since-removed GPU. Booking/picker flows never reach a deleted
    GPU's id in the first place since list_gpus() already excludes them."""
    return session.get(GPU, gpu_id)


def rename_server(session: Session, server: Server, name: str) -> Server:
    existing = session.execute(select(Server).where(Server.name == name, Server.id != server.id)).scalar_one_or_none()
    if existing is not None:
        raise ServerAlreadyExistsError(f"server '{name}' already exists")
    server.name = name
    session.flush()
    return server


def set_server_active(session: Session, server: Server, is_active: bool) -> Server:
    server.is_active = is_active
    session.flush()
    return server


def _retire_gpu(session: Session, gpu: GPU, now: datetime) -> None:
    """Soft-removes a GPU: cancels (never deletes) its still-active reservations, drops its watch
    subscriptions (not history, just live notification requests), and marks it deleted. The row
    itself is kept so past reservations still resolve `reservation.gpu` instead of a dangling FK
    -- reservation history is never physically removed."""
    reservation_service.cancel_all_for_gpu(session, gpu.id, now=now)
    session.execute(delete(WatchSubscription).where(WatchSubscription.gpu_id == gpu.id))
    gpu.is_active = False
    gpu.deleted_at = now


def delete_server(session: Session, server: Server) -> None:
    """Retires the server and all its GPUs (see _retire_gpu) and drops any student server-access
    grants pointing at it. Reservation history on those GPUs is preserved, never deleted."""
    now = utc_now()
    for gpu in list_gpus(session, server, active_only=False):
        _retire_gpu(session, gpu, now)
    session.execute(delete(ServerAccess).where(ServerAccess.server_id == server.id))
    server.is_active = False
    server.deleted_at = now
    session.flush()


def rename_gpu(session: Session, gpu: GPU, model_name: str) -> GPU:
    gpu.model_name = model_name
    session.flush()
    return gpu


def set_gpu_active(session: Session, gpu: GPU, is_active: bool) -> GPU:
    gpu.is_active = is_active
    session.flush()
    return gpu


def delete_gpu(session: Session, gpu: GPU) -> None:
    """Retires the GPU (see _retire_gpu). Reservation history on it is preserved, never deleted."""
    _retire_gpu(session, gpu, utc_now())
    session.flush()
