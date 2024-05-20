from unittest.mock import patch, MagicMock

from mockfirestore import MockFirestore

from main import handle_hello, handle_notes, handle_gemini, get_notes, get_current_conversation, add_to_conversation, \
    end_conversation
from main import GEMINI_MODEL_TYPE
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
    assert note == get_notes(mock_firestore)[0]["notes"]


@patch("main.genai.GenerativeModel")
def test_handle_gemini(MockGenerativeModel):
    # Arrange: Set up the mock object and its return values
    mock_model = MockGenerativeModel.return_value
    mock_response = MagicMock()
    mock_response.text = 'Hello, human! This is a mock response!'
    mock_model.generate_content.return_value = mock_response

    # Act: Call the function under test
    sample_prompt = "Hello, Gemini! Welcome to our Discord server!"
    sample_payload["data"] = {
        "id": "1233616675837055047",
        "name": "gemini",
        "options": [{
            "name": "prompt",
            "type": 3,
            "value": sample_prompt
        }],
        "type": 1,
    }
    result = handle_gemini(sample_payload)

    # Assert: Verify the behavior of the function
    MockGenerativeModel.assert_called_once_with(GEMINI_MODEL_TYPE)
    mock_model.generate_content.assert_called_once_with(
        sample_prompt
    )
    assert result == 'I said: \n' + sample_prompt + '\n' + \
        'Gemini said: \n' + 'Hello, human! This is a mock response!'


def test_hello():
    assert "Hello! Let's doit! (TM)" == handle_hello(sample_payload)

@patch("main.get_db_client")
def test_conversation(mock_db):
    mock_firestore = MockFirestore()
    mock_db.return_value = mock_firestore
    assert get_current_conversation(mock_firestore) is None
    message_1 = "Why is the sky blue?"
    message_2 = "Air or whatever idk"
    add_to_conversation(mock_firestore, {"user": "Harley", "message": message_1})
    assert message_1 == get_current_conversation(mock_firestore)["messages"][0]["message"]
    add_to_conversation(mock_firestore, {"user": "Gemini", "message": message_2})
    assert message_2 == get_current_conversation(mock_firestore)["messages"][1]["message"]
    end_conversation(mock_firestore)
    assert get_current_conversation(mock_firestore) is None

