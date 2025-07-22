import datetime

from sqlalchemy import inspect, JSON, INTEGER, String, TIMESTAMP

from services.loggs import logger
from tests.fixtures.postgresql import engine, session


def test_event_model(session):
    from infrastructure.models.postgresql import Event

    create_date_1 = datetime.datetime(
        year=2025,
        month=1,
        day=1,
        hour=12,
        minute=0,
        second=0,
        microsecond=0,
    )

    create_date_2 = datetime.datetime(
        year=2025,
        month=2,
        day=1,
        hour=12,
        minute=0,
        second=0,
        microsecond=0,
    )

    event_data_1 = {
        "user_id": 1,
        "event_type": "login",
        "details": {
            "level": 10,
        },
        "created_at": create_date_1,
    }

    event_data_2 = {
        "user_id": 1,
        "event_type": "login",
        "details": {
            "level": 10,
        },
        "created_at": create_date_2,
    }

    test_model_1 = Event(**event_data_1)
    test_model_2 = Event(**event_data_2)

    session.add_all([test_model_1, test_model_2])
    session.commit()

    models = session.query(Event).all()
    assert len(models) == 2
    assert test_model_1.id == 1
    assert test_model_2.id == 2

    test_data_dict_1 = test_model_1.to_dict()
    del test_data_dict_1["id"]

    test_data_dict_2 = test_model_2.to_dict()
    del test_data_dict_2["id"]

    assert test_data_dict_1 == event_data_1
    assert test_data_dict_2 == event_data_2

    table_name = Event.__tablename__
    inspector = inspect(session.bind)
    table_names = inspector.get_table_names()
    assert table_name in table_names

    columns = inspector.get_columns(table_name)

    column_details = {col["name"]: col for col in columns}

    assert "id" in column_details
    assert column_details["id"]["name"] == "id"
    assert column_details["id"]["nullable"] == False
    assert isinstance(column_details["id"]["type"], INTEGER)

    assert "user_id" in column_details
    assert column_details["user_id"]["name"] == "user_id"
    assert column_details["user_id"]["nullable"] == False
    assert isinstance(column_details["user_id"]["type"], INTEGER)

    assert "event_type" in column_details
    assert column_details["event_type"]["name"] == "event_type"
    assert column_details["event_type"]["nullable"] == False
    assert isinstance(column_details["event_type"]["type"], String)

    assert "details" in column_details
    assert column_details["details"]["name"] == "details"
    assert column_details["details"]["nullable"] == False
    assert isinstance(column_details["details"]["type"], JSON)

    assert "created_at" in column_details
    assert column_details["created_at"]["name"] == "created_at"
    assert column_details["created_at"]["nullable"] == False
    assert isinstance(column_details["created_at"]["type"], TIMESTAMP)
