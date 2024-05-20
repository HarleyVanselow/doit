import os
import time
from datetime import datetime

import flask
import functions_framework
import google.generativeai as genai
from google.cloud import firestore
from google.cloud.firestore_v1 import Client
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

# Constants & Config
GCP_PROJECT_ID = "promising-silo-421623"
DISCORD_PUBLIC_KEY = "9416d2be504b253e228d3149e29825294715d261c348d9c7e2618276bb1419c8"

NOTES_COLLECTION = "notes"
CONVERSATION_COLLECTION = "conversation"
GEMINI_MODEL_TYPE = "gemini-1.5-flash-latest"

# Configure Gemini key
genai.configure(api_key=os.getenv("GEMINI_API_KEY", None))


# DB interactions
def get_db_client() -> Client:
    return firestore.Client(project=GCP_PROJECT_ID)


def get_notes(db, user=None, private=False):
    query = db.collection(NOTES_COLLECTION).where("private", "==", private)
    if user:
        query = query.where("user", "==", user)
    return [doc.to_dict() for doc in query.stream()]


def write_session_notes(db, notes, user, private=False):
    note_doc = db.collection(NOTES_COLLECTION).document()
    note_doc.set(
        {
            "notes": notes,
            "user": user,
            "session_date": int(time.time()),
            "private": private,
        }
    )


def log_conversation_message(db, user, message):
    add_to_conversation(db, {"message": message, "user": user})


def get_current_conversation(db, to_dict=True):
    doc = next(
        db.collection(CONVERSATION_COLLECTION).where("active", "==", True).stream(),
        None,
    )
    if doc and to_dict:
        return doc.to_dict()
    return doc


def add_to_conversation(db, message):
    active_conversation = get_current_conversation(db, False)
    if active_conversation:
        active_conversation_dict = active_conversation.to_dict()
        # If the conversation is more than a day old
        if (int(time.time()) - int(active_conversation_dict["started_at"])) > (60 * 60 * 24):
            end_conversation(db)
            start_new_conversation(db, message)
        else:
            db.collection(CONVERSATION_COLLECTION).document(active_conversation.id).update(
                {"messages": active_conversation_dict["messages"] + [message]}
            )
    else:
        start_new_conversation(db, message)


def start_new_conversation(db, message):
    new_conversation = db.collection(CONVERSATION_COLLECTION).document()
    new_conversation.set(
        {
            "messages": [message],
            "started_at": int(time.time()),
            "active": True,
        }
    )


def end_conversation(db):
    conversation = get_current_conversation(db, False)
    db.collection(CONVERSATION_COLLECTION).document(conversation.id).update(
        {"active": False}
    )


# Helper functions
def get_username(data):
    return data["member"]["user"]["username"]


def no_command_message(x):
    return f"No {x} command registered!"


def get_all_notes_and_sort_by_date(db):
    # Fetch all session notes from db
    notes = get_notes(db)
    # Sort notes by date from least to most recent
    notes.sort(key=lambda x: x["session_date"])
    return notes


# Discord request verification
def verify_request(request: flask.Request):
    # Your public key can be found on your application in the Developer Portal
    verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))

    signature = request.headers["X-Signature-Ed25519"]
    timestamp = request.headers["X-Signature-Timestamp"]
    body = request.data.decode("utf-8")

    try:
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
    except BadSignatureError:
        flask.abort(401, "invalid request signature")


def handle_hello(data):
    return "Hello! Let's doit! (TM)"


def handle_all_notes(data):
    # Fetch all session notes from db and display them
    db = get_db_client()
    notes = get_all_notes_and_sort_by_date(db)
    result = "Here are all the session notes:\n"
    for idx, note in enumerate(notes):
        session_date = datetime.fromtimestamp(
            note["session_date"]
        ).strftime("%Y-%m-%d %H:%M")
        result = (
            result
            + f"Week {idx + 1}, date {session_date}: \n"
            + note["notes"]
            + "\n"
        )
    return result


def handle_notes(data):
    db = get_db_client()
    write_session_notes(db, data["data"]["options"][0]["value"], get_username(data))
    return "Session notes logged!"


def handle_dragonbot(data):
    """
    Function to query database, build prompt, and ask Gemini a question.

    Returns: Question from user and response from Gemini
    """
    # Initialize db client
    db = get_db_client()

    # Check if the conversation is ongoing
    convo_history = get_current_conversation(db)

    # Get question from user
    question = data["data"]["options"][0]["value"]

    if convo_history is not None:
        # Have existing conversation history
        prompt = []
        for idx, message in enumerate(convo_history["messages"]):
            if message["user"] == 'Gemini':
                role = "model"
            else:
                role = "user"
            prompt.append({
                "role": role,
                "parts": [message["message"]]
            })
        # Add new question to prompt
        prompt.append({
            "role": "user",
            "parts": [question]
        })
    else:
        # This is a new conversation, so we prompt and input
        # the session notes from scratch
        # Fetch all session notes from db
        notes = get_all_notes_and_sort_by_date(db)

        # Build prompt from the beginning
        prompt_intro = "We are playing a Dungeons and Dragons 5e campaign, \
            and here are the weekly session notes from our adventures. \
            Please read them carefully.\n"
        prompt_end = (
            f"Please answer our question: {question} \n"
            + "Refer to the session notes, and please don't invent things that did not happen!"
            + "If the question cannot be answered from the session notes,"
            + "please say that you do not know the answer."
        )

        prompt = prompt_intro
        for idx, note in enumerate(notes):
            session_date = datetime.fromtimestamp(
                note["session_date"]
            ).strftime("%Y-%m-%d %H:%M")
            prompt = (
                prompt + f"Week {idx + 1}, date {session_date}: \n" + note["notes"] + "\n"
            )
        prompt = prompt + prompt_end

        # Log the prompt to db
        log_conversation_message(db, get_username(data), prompt)

    # Ask Gemini
    print(f"Formatted prompt, asking Gemini: {prompt}")
    model = genai.GenerativeModel(GEMINI_MODEL_TYPE)
    response = model.generate_content(prompt).text
    print("Gemini response returned")

    # Log Gemini's response to db
    log_conversation_message(db, "Gemini", response)

    return format_call_response(
        get_username(data), question, "Dragonbot", response)


def handle_bye_dragonbot(data):
    db = get_db_client()
    end_conversation(db)
    prompt = "Bye dragonbot! Thanks for you help!"
    model = genai.GenerativeModel(GEMINI_MODEL_TYPE)
    response = model.generate_content(prompt).text
    return format_call_response(
        get_username(data), prompt, "Dragonbot", response
    )


def handle_gemini(data):
    # Instantiate Gemini model
    model = genai.GenerativeModel(GEMINI_MODEL_TYPE)

    # Get prompt from Discord
    prompt = data["data"]["options"][0]["value"]
    print(f"Formatted prompt, asking Gemini: {prompt}")

    # Ask Gemini
    response = model.generate_content(prompt).text
    return format_call_response(
        get_username(data), prompt, "Gemini", response)


def format_call_response(caller, call, responder, response):
    result = f"**{caller}**:\n> " + call + "\n"
    result += f"**{responder}**:\n>>> " + response
    return result


# App entrypoint
@functions_framework.http
def hello_http(request: flask.Request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    if not "IS_LOCAL" in os.environ:
        verify_request(request)
    request_json = request.get_json(silent=True)
    if request_json["type"] == 1:
        return {"type": 1}
    print(f"Received {request_json}")
    command = request_json["data"]["name"]
    if command in commands:
        content = commands[command](request_json)
    else:
        content = no_command_message(command)
    return {
        "type": 4,
        "data": {
            "tts": False,
            "content": content,
        },
    }


# App command handler router
commands = {
    "hello": handle_hello,
    "gemini": handle_gemini,
    "notes": handle_notes,
    "dragonbot": handle_dragonbot,
    "get_all_notes": handle_all_notes,
    "bye_dragonbot": handle_bye_dragonbot
}
