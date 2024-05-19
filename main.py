from functools import reduce
import os
import flask
import functions_framework
from google.cloud import firestore
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from requests import request
import google.generativeai as genai


# Constants & Config
GCP_PROJECT_ID = "promising-silo-421623"
DISCORD_PUBLIC_KEY = "9416d2be504b253e228d3149e29825294715d261c348d9c7e2618276bb1419c8"
NO_COMMAND_MESSAGE = lambda x: f"No {x} command registered!"


# Configure Gemini key
genai.configure(api_key=os.environ["GEMINI_API_KEY"])


# DB interactions
def get_db_client():
    return firestore.Client(project=GCP_PROJECT_ID)


# Helper functions
def get_username(data):
    return data["member"]["user"]["username"]


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


def handle_gemini():
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = 'Hello, Gemini! Welcome to our Discord server!'
    print(model.generate_content(prompt).text)


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
    print(f"Recieved {request_json}")
    command = request_json["data"]["name"]
    if command in commands:
        content = commands[command](request_json)
    else:
        content = NO_COMMAND_MESSAGE(command)
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
    "gemini": handle_gemini
}
