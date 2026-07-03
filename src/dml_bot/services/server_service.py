from sqlalchemy import select
from sqlalchemy.orm import Session

from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server


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
