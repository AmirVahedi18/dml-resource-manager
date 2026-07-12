from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from dml_core.db.models.user import User
from dml_core.db.models.watch import WatchSubscription
from dml_core.services import watch_service
from dml_web.deps import get_session, require_admin
from dml_web.schemas.admin_watches import AdminWatchListOut, AdminWatchOut

router = APIRouter()


def _status_of(w: WatchSubscription) -> str:
    if w.notified_at is not None:
        return "matched"
    if not w.is_active:
        return "cancelled"
    return "active"


def _to_admin_out(w: WatchSubscription) -> AdminWatchOut:
    return AdminWatchOut(
        id=w.id,
        gpu_id=w.gpu_id,
        user_id=w.user_id,
        user_full_name=w.user.full_name,
        server_name=w.gpu.server.name,
        gpu_index=w.gpu.index_on_server,
        range_start=w.range_start,
        range_end=w.range_end,
        min_ram_needed_mb=w.min_ram_needed_mb,
        description=w.description,
        auto_book=w.auto_book,
        status=_status_of(w),
    )


@router.get("", response_model=AdminWatchListOut)
def list_watches(
    user_id: int | None = None,
    gpu_id: int | None = None,
    server_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> AdminWatchListOut:
    total = watch_service.count_watches(session, user_id=user_id, gpu_id=gpu_id, server_id=server_id)
    watches = watch_service.list_watches(
        session,
        user_id=user_id,
        gpu_id=gpu_id,
        server_id=server_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return AdminWatchListOut(
        items=[_to_admin_out(w) for w in watches], total=total, page=page, page_size=page_size
    )


@router.delete("/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_watch(
    watch_id: int, session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> None:
    watch = session.get(WatchSubscription, watch_id)
    if watch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watch not found")
    watch_service.cancel_watch(session, watch)
