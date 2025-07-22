import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from infrastructure.models.postgresql import ABCModel
from infrastructure.models.postgresql.abc import ABCAdminModel


class TestModel(ABCModel):
    __tablename__ = "test_model"


class TestAdminModel(ABCAdminModel):
    __tablename__ = "test_admin_model"


@pytest.fixture(scope="function")
def engine():
    env_path: Path = Path(__file__).parent.parent.parent / "docker" / ".env"
    load_dotenv(env_path)
    port = os.getenv("POSTGRES_PORT")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    db = os.getenv("POSTGRES_TEST_NAME")
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=user,
        password=password,
        host="localhost",
        port=port,
        database=db,
    )
    test_engine = create_engine(url)
    ABCModel.metadata.create_all(test_engine)
    yield test_engine
    ABCModel.metadata.drop_all(test_engine)


@pytest.fixture(scope="function")
def session(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
