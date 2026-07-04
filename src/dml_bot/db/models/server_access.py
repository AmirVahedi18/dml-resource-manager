from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from dml_bot.db.base import Base


class ServerAccess(Base):
    """Grants a student access to reserve/watch/view a specific server's GPUs. Admins bypass this
    check entirely (see dml_bot.bot_reply.gpu_picker.accessible_server_ids_for) -- there are no
    rows here for admins, since admin access to every server is implicit, not granted."""

    __tablename__ = "server_access"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), primary_key=True)
