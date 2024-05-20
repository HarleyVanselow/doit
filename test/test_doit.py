from unittest.mock import patch, MagicMock

from mockfirestore import MockFirestore

from main import handle_hello, handle_notes, handle_gemini
from test_data import sample_payload


@patch("main.get_db_client")
def test_notes(mock_db):
    mock_firestore = MockFirestore()
    mock_db.return_value = mock_firestore
    note = "Many things happened"
    sample_payload["data"] = {
        "id": "1233616675837055047",
        "name": "notes",
        "options": [{"name": "server", "type": 3, "value": note}],
        "type": 1,
    }
    handle_notes(sample_payload)
    assert note == next(mock_firestore.collection("notes").stream(), {}).to_dict()["notes"]


@patch("main.genai.GenerativeModel")
def test_handle_gemini(MockGenerativeModel):
    # Arrange: Set up the mock object and its return values
    mock_model = MockGenerativeModel.return_value
    mock_response = MagicMock()
    mock_response.text = "Hello, human! This is a mock response!"
    mock_model.generate_content.return_value = mock_response

    # Act: Call the function under test
    result = handle_gemini(sample_payload)

    # Assert: Verify the behavior of the function
    MockGenerativeModel.assert_called_once_with('gemini-1.5-flash-latest')
    mock_model.generate_content.assert_called_once_with(
        'Hello, Gemini! Welcome to our Discord server!'
    )
    assert result == 'Hello, human! This is a mock response!'



def test_hello():
    assert "Hello! Let's doit! (TM)" == handle_hello(sample_payload)
