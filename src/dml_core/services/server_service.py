from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dml_core.db.models.gpu import GPU
from dml_core.db.models.server import Server
from dml_core.db.models.server_access import ServerAccess
from dml_core.db.models.watch import WatchSubscription
from dml_core.services import notification_service, reservation_service
from dml_core.utils.time_utils import utc_now


def _humanize_minutes(minutes: int) -> str:
    """Human-friendly duration for notification copy: 60 -> '1 hour', 90 -> '1 hour 30 minutes',
    30 -> '30 minutes', 120 -> '2 hours'."""
    hours, mins = divmod(max(minutes, 0), 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    if mins or not parts:
        parts.append(f"{mins} minute" + ("s" if mins != 1 else ""))
    return " ".join(parts)


class ServerAlreadyExistsError(Exception):
    pass


class GPUIndexConflictError(Exception):
    pass


def create_server(session: Session, name: str) -> Server:
    existing = session.execute(select(Server).where(Server.name == name)).scalar_one_or_none()
    if existing is not None:
        if existing.deleted_at is None:
            raise ServerAlreadyExistsError(f"A server named '{name}' already exists.")
        # The name belongs to a soft-deleted server (kept only so its GPUs' reservation history
        # still resolves). The DB has a unique constraint on `name`, so a new row can't reuse it --
        # revive the existing one instead, same as add_gpu() does for a soft-deleted GPU's index.
        existing.is_active = True
        existing.deleted_at = None
        session.flush()
        return existing
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
                f"GPU {index_on_server} already exists on server '{server.name}'."
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


def set_server_active(session: Session, server: Server, is_active: bool, now: datetime | None = None) -> Server:
    """Toggling a server off suspends (never cancels) every still-upcoming reservation on its
    GPUs; toggling it back on resumes them, rescheduled to start 1h from now. A GPU that's
    independently still deactivated (`GPU.is_active is False`) stays suspended until that GPU is
    reactivated too -- see `reservation_service.resume_suspended_reservations_for_server`."""
    now = now or utc_now()
    was_active = server.is_active
    server.is_active = is_active
    session.flush()
    if was_active and not is_active:
        reservation_service.suspend_active_reservations_for_server(session, server.id, now=now)
        notification_service.notify_server_access_users(
            session, server.id,
            f"Server '{server.name}' was deactivated. Any upcoming reservations you had on it "
            "are paused and will resume once it's reactivated.",
        )
    elif not was_active and is_active:
        resumed = reservation_service.resume_suspended_reservations_for_server(session, server.id, now=now)
        if resumed:
            delay_text = _humanize_minutes(reservation_service.reactivation_delay_minutes(session))
            notification_service.notify_server_access_users(
                session, server.id,
                f"Server '{server.name}' is active again. Your paused reservations on it have "
                f"resumed, starting {delay_text} from now with their original duration.",
            )
        else:
            notification_service.notify_server_access_users(
                session, server.id, f"Server '{server.name}' is active again."
            )
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


def set_gpu_active(session: Session, gpu: GPU, is_active: bool, now: datetime | None = None) -> GPU:
    """Toggling a GPU off suspends (never cancels) its still-upcoming reservations; toggling it
    back on resumes them, rescheduled to start 1h from now. Gated on the GPU's *effective*
    activeness (its own flag AND its server's) so this is a no-op if the server is already
    inactive -- e.g. flipping `gpu.is_active` while the server is off doesn't resume anything
    (the GPU is still blocked by the server), and toggling it back off doesn't double-suspend."""
    now = now or utc_now()
    was_effective = gpu.is_active and gpu.server.is_active
    gpu.is_active = is_active
    session.flush()
    is_effective = gpu.is_active and gpu.server.is_active
    if was_effective and not is_effective:
        reservation_service.suspend_active_reservations_for_gpu(session, gpu.id, now=now)
        notification_service.notify_server_access_users(
            session, gpu.server_id,
            f"GPU{gpu.index_on_server} on '{gpu.server.name}' was deactivated. Any upcoming "
            "reservations you had on it are paused and will resume once it's reactivated.",
        )
    elif not was_effective and is_effective:
        resumed = reservation_service.resume_suspended_reservations_for_gpu(session, gpu.id, now=now)
        if resumed:
            delay_text = _humanize_minutes(reservation_service.reactivation_delay_minutes(session))
            notification_service.notify_server_access_users(
                session, gpu.server_id,
                f"GPU{gpu.index_on_server} on '{gpu.server.name}' is active again. Your paused "
                f"reservations on it have resumed, starting {delay_text} from now with their "
                "original duration.",
            )
        else:
            notification_service.notify_server_access_users(
                session, gpu.server_id, f"GPU{gpu.index_on_server} on '{gpu.server.name}' is active again."
            )
    session.flush()
    return gpu


def delete_gpu(session: Session, gpu: GPU) -> None:
    """Retires the GPU (see _retire_gpu). Reservation history on it is preserved, never deleted."""
    _retire_gpu(session, gpu, utc_now())
    session.flush()
