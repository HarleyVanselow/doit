import os
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
GEMINI_MODEL_TYPE = 'gemini-1.5-flash-latest'

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
    note_doc.set({
        "notes": notes,
        "user": user,
        "session_date": datetime.now(),
        "private": private
    })


# Helper functions
def get_username(data):
    return data["member"]["user"]["username"]


def no_command_message(x): return f"No {x} command registered!"


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


def handle_notes(data):
    db = get_db_client()
    write_session_notes(db, data["data"]["options"][0]["value"], get_username(data))
    return "Session notes logged!"


def handle_dragonbot(data):
    """
    Function to query database, build prompt, and ask Gemini a question.

    Args:
        data:

    Returns: Response from Gemini
    """
    # Fetch all session notes from db
    db = get_db_client()
    notes = get_notes(db)

    # Build prompt

    # Ask Gemini
    model = genai.GenerativeModel(GEMINI_MODEL_TYPE)


def handle_gemini(data):
    # Instantiate Gemini model
    model = genai.GenerativeModel(GEMINI_MODEL_TYPE)

    # Get prompt from Discord
    prompt = data["data"]["options"][0]["value"]
    return model.generate_content(prompt).text


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
    "notes": handle_notes
}
