from datetime import datetime, timedelta, timezone

import pytest

from dml_core.db.models.reservation import ReservationStatus
from dml_core.services import notification_service, reservation_service, server_access_service
from dml_core.services import server_service as ss
from tests.factories import make_regulation, make_user

NOW = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
START = NOW + timedelta(hours=8)
END = START + timedelta(hours=2)


def test_create_server_and_add_gpu(db_session):
    server = ss.create_server(db_session, "lab-server-1")
    gpu = ss.add_gpu(db_session, server, 0, "RTX 4090", 24576)
    assert gpu.server_id == server.id
    assert ss.get_gpu(db_session, gpu.id).model_name == "RTX 4090"


def test_create_duplicate_server_raises(db_session):
    ss.create_server(db_session, "lab-server-1")
    with pytest.raises(ss.ServerAlreadyExistsError):
        ss.create_server(db_session, "lab-server-1")


def test_create_server_reuses_name_of_deleted_server(db_session):
    old_server = ss.create_server(db_session, "lab-server-1")
    ss.delete_server(db_session, old_server)

    new_server = ss.create_server(db_session, "lab-server-1")

    assert new_server.id == old_server.id
    assert new_server.is_active is True
    assert new_server.deleted_at is None
    listed = ss.list_servers(db_session)
    assert [s.id for s in listed] == [new_server.id]


def test_duplicate_gpu_index_raises(db_session):
    server = ss.create_server(db_session, "lab-server-1")
    ss.add_gpu(db_session, server, 0, "RTX 4090", 24576)
    with pytest.raises(ss.GPUIndexConflictError):
        ss.add_gpu(db_session, server, 0, "RTX 3090", 24576)


def test_add_gpu_reuses_index_of_deleted_gpu(db_session):
    server = ss.create_server(db_session, "lab-server-1")
    old_gpu = ss.add_gpu(db_session, server, 1, "RTX 3090", 24576)
    ss.delete_gpu(db_session, old_gpu)

    new_gpu = ss.add_gpu(db_session, server, 1, "GTX 1080 Ti", 12288)

    assert new_gpu.id == old_gpu.id
    assert new_gpu.model_name == "GTX 1080 Ti"
    assert new_gpu.total_ram_mb == 12288
    assert new_gpu.is_active is True
    assert new_gpu.deleted_at is None
    listed = ss.list_gpus(db_session, server)
    assert [g.id for g in listed] == [new_gpu.id]


def test_list_gpus_excludes_inactive_by_default(db_session):
    server = ss.create_server(db_session, "lab-server-1")
    active_gpu = ss.add_gpu(db_session, server, 0, "RTX 4090", 24576)
    inactive_gpu = ss.add_gpu(db_session, server, 1, "RTX 3090", 24576)
    inactive_gpu.is_active = False

    listed = ss.list_gpus(db_session, server)
    assert [g.id for g in listed] == [active_gpu.id]


def test_list_servers_excludes_inactive_by_default(db_session):
    active = ss.create_server(db_session, "server-active")
    inactive = ss.create_server(db_session, "server-inactive")
    inactive.is_active = False

    listed = ss.list_servers(db_session)
    assert [s.id for s in listed] == [active.id]


def test_set_gpu_active_off_suspends_reservations_and_notifies_users_with_access(db_session):
    server = ss.create_server(db_session, "server-1")
    gpu = ss.add_gpu(db_session, server, 0, "A100", 20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session)
    server_access_service.set_access(db_session, user.id, {server.id})
    reservation = reservation_service.create_reservation(db_session, user, gpu, START, END, 4096, regulation, now=NOW)

    ss.set_gpu_active(db_session, gpu, False, now=NOW)

    assert reservation.status == ReservationStatus.SUSPENDED
    notifications = notification_service.list_undismissed(db_session, user.id)
    assert len(notifications) == 1
    assert "deactivated" in notifications[0].message


def test_set_gpu_active_on_resumes_reservations_and_notifies(db_session):
    server = ss.create_server(db_session, "server-1")
    gpu = ss.add_gpu(db_session, server, 0, "A100", 20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session)
    server_access_service.set_access(db_session, user.id, {server.id})
    reservation = reservation_service.create_reservation(db_session, user, gpu, START, END, 4096, regulation, now=NOW)
    ss.set_gpu_active(db_session, gpu, False, now=NOW)

    reactivated_at = NOW + timedelta(hours=3)
    ss.set_gpu_active(db_session, gpu, True, now=reactivated_at)

    assert reservation.status == ReservationStatus.ACTIVE
    assert reservation.start_time == (reactivated_at + timedelta(hours=1)).replace(tzinfo=None)
    notifications = notification_service.list_undismissed(db_session, user.id)
    assert len(notifications) == 2  # deactivation + reactivation
    assert "active again" in notifications[-1].message


def test_set_gpu_active_is_noop_while_server_already_inactive(db_session):
    server = ss.create_server(db_session, "server-1")
    gpu = ss.add_gpu(db_session, server, 0, "A100", 20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session)
    server_access_service.set_access(db_session, user.id, {server.id})
    reservation = reservation_service.create_reservation(db_session, user, gpu, START, END, 4096, regulation, now=NOW)

    ss.set_server_active(db_session, server, False, now=NOW)
    assert reservation.status == ReservationStatus.SUSPENDED
    notification_service.list_undismissed(db_session, user.id)[0]  # deactivation notice

    # Toggling the GPU's own flag while the server is still off shouldn't touch the reservation
    # or fire another notification -- the GPU is still effectively inactive either way.
    ss.set_gpu_active(db_session, gpu, False, now=NOW + timedelta(hours=1))
    assert reservation.status == ReservationStatus.SUSPENDED
    assert len(notification_service.list_undismissed(db_session, user.id)) == 1


def test_set_server_active_off_suspends_all_gpus_and_notifies_once(db_session):
    server = ss.create_server(db_session, "server-1")
    gpu1 = ss.add_gpu(db_session, server, 0, "A100", 20000)
    gpu2 = ss.add_gpu(db_session, server, 1, "A100", 20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session, max_concurrent_gpus=2)
    server_access_service.set_access(db_session, user.id, {server.id})
    r1 = reservation_service.create_reservation(db_session, user, gpu1, START, END, 4096, regulation, now=NOW)
    r2 = reservation_service.create_reservation(db_session, user, gpu2, START, END, 4096, regulation, now=NOW)

    ss.set_server_active(db_session, server, False, now=NOW)

    assert r1.status == ReservationStatus.SUSPENDED
    assert r2.status == ReservationStatus.SUSPENDED
    assert len(notification_service.list_undismissed(db_session, user.id)) == 1


def test_notifications_only_go_to_users_with_access(db_session):
    server = ss.create_server(db_session, "server-1")
    ss.add_gpu(db_session, server, 0, "A100", 20000)
    with_access = make_user(db_session, full_name="Has Access")
    without_access = make_user(db_session, full_name="No Access")
    server_access_service.set_access(db_session, with_access.id, {server.id})

    ss.set_server_active(db_session, server, False, now=NOW)

    assert len(notification_service.list_undismissed(db_session, with_access.id)) == 1
    assert notification_service.list_undismissed(db_session, without_access.id) == []
