import pytest

from dml_core.services import server_service as ss


def test_create_server_and_add_gpu(db_session):
    server = ss.create_server(db_session, "lab-server-1")
    gpu = ss.add_gpu(db_session, server, 0, "RTX 4090", 24576)
    assert gpu.server_id == server.id
    assert ss.get_gpu(db_session, gpu.id).model_name == "RTX 4090"


def test_create_duplicate_server_raises(db_session):
    ss.create_server(db_session, "lab-server-1")
    with pytest.raises(ss.ServerAlreadyExistsError):
        ss.create_server(db_session, "lab-server-1")


def test_duplicate_gpu_index_raises(db_session):
    server = ss.create_server(db_session, "lab-server-1")
    ss.add_gpu(db_session, server, 0, "RTX 4090", 24576)
    with pytest.raises(ss.GPUIndexConflictError):
        ss.add_gpu(db_session, server, 0, "RTX 3090", 24576)


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
