from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dml_bot.db.models.user import User
from dml_bot.db.models.watch import WatchSubscription
from dml_bot.services import server_service, watch_service
from dml_web import access
from dml_web.deps import get_current_user, get_session
from dml_web.schemas.watches import WatchCreate, WatchOut

router = APIRouter()


@router.get("", response_model=list[WatchOut])
def list_my_watches(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> list[WatchSubscription]:
    return watch_service.list_watches_for_user(session, user.id)


@router.post("", response_model=WatchOut, status_code=status.HTTP_201_CREATED)
def create_watch(
    payload: WatchCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> WatchSubscription:
    gpu = server_service.get_gpu(session, payload.gpu_id)
    if gpu is None:
        raise HTTPException(404, "GPU not found")
    access.ensure_gpu_access(session, user, gpu)

    # Web offers auto-book watches only -- there's no notification channel to fall back to a
    # plain "just notify" for (see the web-interface plan's "Watches" decision).
    return watch_service.create_watch(
        session, user, gpu, payload.range_start, payload.range_end, payload.min_ram_needed_mb, auto_book=True
    )


@router.delete("/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_watch(
    watch_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> None:
    watch = session.get(WatchSubscription, watch_id)
    if watch is None or watch.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watch not found")
    watch_service.cancel_watch(session, watch)
