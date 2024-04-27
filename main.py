import os
import flask
import functions_framework

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

DISCORD_PUBLIC_KEY = "9416d2be504b253e228d3149e29825294715d261c348d9c7e2618276bb1419c8"


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
    if not 'IS_LOCAL' in os.environ:
        verify_request(request)
    request_json = request.get_json(silent=True)
    request_args = request.args
    if request.path == "/":
        return {"type": 1}
    return {
        "type":4,
        "data": request_json
    }
