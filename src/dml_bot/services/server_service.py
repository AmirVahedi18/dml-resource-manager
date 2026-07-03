from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.reservation import Reservation
from dml_bot.db.models.server import Server
from dml_bot.db.models.watch import WatchSubscription


class ServerAlreadyExistsError(Exception):
    pass


class GPUIndexConflictError(Exception):
    pass


def create_server(session: Session, name: str, description: str | None = None) -> Server:
    existing = session.execute(select(Server).where(Server.name == name)).scalar_one_or_none()
    if existing is not None:
        raise ServerAlreadyExistsError(f"server '{name}' already exists")
    server = Server(name=name, description=description)
    session.add(server)
    session.flush()
    return server


def list_servers(session: Session, active_only: bool = True) -> list[Server]:
    stmt = select(Server)
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
        raise GPUIndexConflictError(
            f"GPU index {index_on_server} already exists on server '{server.name}'"
        )
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
    stmt = select(GPU).where(GPU.server_id == server.id)
    if active_only:
        stmt = stmt.where(GPU.is_active.is_(True))
    return list(session.execute(stmt).scalars().all())


def get_gpu(session: Session, gpu_id: int) -> GPU | None:
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


def _delete_gpu_dependents(session: Session, gpu_id: int) -> None:
    session.execute(delete(WatchSubscription).where(WatchSubscription.gpu_id == gpu_id))
    session.execute(delete(Reservation).where(Reservation.gpu_id == gpu_id))


def delete_server(session: Session, server: Server) -> None:
    """Permanently deletes the server, its GPUs, and all their reservations/watches. There's no
    FK cascade configured at the DB level (SQLite FK enforcement isn't enabled in this project),
    so dependent rows are deleted explicitly to avoid leaving orphaned rows behind."""
    gpus = list_gpus(session, server, active_only=False)
    for gpu in gpus:
        _delete_gpu_dependents(session, gpu.id)
        session.delete(gpu)
    session.delete(server)
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
    """Permanently deletes the GPU and all its reservations/watches (see delete_server)."""
    _delete_gpu_dependents(session, gpu.id)
    session.delete(gpu)
    session.flush()
