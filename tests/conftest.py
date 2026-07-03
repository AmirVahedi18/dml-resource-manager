import pytest
from sqlalchemy.orm import sessionmaker

from dml_bot.db.session import dispose_engine, init_engine


@pytest.fixture()
def db_session():
    engine = init_engine(":memory:")
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    yield session
    session.close()
    dispose_engine()
