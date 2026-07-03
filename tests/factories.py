from dml_bot.db.models import GPU, Regulation, Server, User


def make_user(session, telegram_id=1, full_name="Test User", can_use_multiple_gpus=False):
    user = User(telegram_id=telegram_id, full_name=full_name, can_use_multiple_gpus=can_use_multiple_gpus)
    session.add(user)
    session.flush()
    return user


def make_server(session, name="server-1"):
    server = Server(name=name)
    session.add(server)
    session.flush()
    return server


def make_gpu(session, server, index_on_server=0, model_name="A100", total_ram_mb=40960):
    gpu = GPU(
        server_id=server.id,
        index_on_server=index_on_server,
        model_name=model_name,
        total_ram_mb=total_ram_mb,
    )
    session.add(gpu)
    session.flush()
    return gpu


def make_regulation(session, **overrides):
    defaults = dict(
        id=1,
        max_ram_per_reservation_mb=16384,
        max_duration_hours=12,
        booking_horizon_days=90,
        min_reservation_slot_minutes=30,
        max_active_reservations_per_user=3,
    )
    defaults.update(overrides)
    regulation = Regulation(**defaults)
    session.add(regulation)
    session.flush()
    return regulation
