from unittest.mock import patch

from mockfirestore import MockFirestore


@patch("main.get_db_client")
def test_basic(mock_db):
    # There should always be a vote
    mock_firestore = MockFirestore()
    mock_db.return_value = mock_firestore
