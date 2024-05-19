from unittest.mock import patch

from mockfirestore import MockFirestore

from main import handle_hello, handle_notes
from test.test_data import sample_payload


@patch("main.get_db_client")
def test_notes(mock_db):
    mock_firestore = MockFirestore()
    mock_db.return_value = mock_firestore
    note = "Many things happened"
    sample_payload["data"] = {
        "id": "1233616675837055047",
        "name": "notes",
        "value": note,
        "type": 3,
    }
    handle_notes(sample_payload)
    assert note == next(mock_firestore.collection("notes").stream(), {}).to_dict()["notes"]


def test_hello():
    assert "Hello! Let's doit! (TM)" == handle_hello(sample_payload)
