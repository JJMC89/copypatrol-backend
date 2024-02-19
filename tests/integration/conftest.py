from __future__ import annotations

import pytest
from sqlalchemy.orm import scoped_session, sessionmaker

from copypatrol_backend import database


@pytest.fixture(scope="session")
def engine():
    return database._create_engine(echo=True)


@pytest.fixture(scope="session")
def setup_database(engine):
    database.TableBase.metadata.drop_all(bind=engine)
    database.TableBase.metadata.create_all(bind=engine)
    yield
    database.TableBase.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine, setup_database):
    connection = engine.connect()
    transaction = connection.begin()
    session = scoped_session(
        sessionmaker(autocommit=False, autoflush=False, bind=connection)
    )
    yield session
    session.close()
    transaction.rollback()
    connection.close()
