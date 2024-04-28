from datetime import datetime
import os
import random
import re
import flask
import functions_framework
from google.cloud import firestore
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from requests import request
import requests

DISCORD_PUBLIC_KEY = "9416d2be504b253e228d3149e29825294715d261c348d9c7e2618276bb1419c8"
NO_COMMAND_MESSAGE = lambda m: f"No handling for command {m} yet"
NOMINATIONS_COLLECTION = "nominations"
VOTES_COLLECTION = "votes"
MOVIE_COLLECTION = "movies"


class Movie:
    def __init__(self, data):
        if "Title" in data:
            self.title = data.get("Title")
            self.year = data.get("Year")
            self.rated = data.get("Rated")
            self.released = data.get("Released")
            self.runtime = data.get("Runtime")
            self.genre = data.get("Genre")
            self.director = data.get("Director")
            self.writer = data.get("Writer")
            self.actors = data.get("Actors")
            self.plot = data.get("Plot")
            self.language = data.get("Language")
            self.country = data.get("Country")
            self.awards = data.get("Awards")
            self.poster = data.get("Poster")
            self.ratings = data.get("Ratings")
            self.metascore = data.get("Metascore")
            self.imdb_rating = data.get("imdbRating")
            self.imdb_votes = data.get("imdbVotes")
            self.imdb_id = data.get("imdbID")
            self.type = data.get("Type")
            self.dvd = data.get("DVD")
            self.box_office = data.get("BoxOffice")
            self.production = data.get("Production")
            self.website = data.get("Website")
            self.response = data.get("Response")
            self.first_nominated_by = data.get("user")
        else:
            self.__dict__.update(data)

    def info(self):
        return f"""**{self.title}**
{self.plot}
IMDB rating: {self.imdb_rating}
Metacritic: {self.metascore}
{self.poster}
"""


class Nomination:
    votes = []

    @staticmethod
    def from_dict(data):
        nomination = Nomination()
        nomination.__dict__.update(data)
        return nomination

    def __init__(self, nominator="", movie_id="", title=""):
        self.nominator = nominator
        self.movie_id = movie_id
        self.title = title
        self.won = False

    def get_movie(self, db):
        return get_movie(db, self.movie_id)

    def vote(self, vote_context):
        self.votes += vote_context


class Vote:
    status_created = "CREATED"
    status_running = "RUNNING"
    status_completed = "COMPLETED"

    def __init__(self, data=None):
        if data:
            self.__dict__.update(data)
            self.nominations = [
                Nomination.from_dict(n) for n in data.get("nominations", [])
            ]
        else:
            self.status = Vote.status_created
            self.created_at = datetime.now()
            self.nominations = []

    def to_dict(self):
        raw = self.__dict__.copy()
        raw["nominations"] = [n.__dict__ for n in raw["nominations"]]
        return raw


def create_vote(db):
    vote = get_vote(db, Vote.status_created)
    if not vote:
        vote = db.collection(VOTES_COLLECTION).document()
        vote.set(Vote().to_dict())
    return vote


def get_vote(db, status):
    query = db.collection(VOTES_COLLECTION).where("status", "==", status).stream()
    found_vote = next(query, None)
    return (
        found_vote
        if found_vote == None
        else Vote(found_vote.to_dict() | {"id": found_vote.id})
    )


def create_nomination(db, movie, nomination_context):
    vote = get_vote(db, Vote.status_created)
    if not vote:
        return "A vote is already in progress, no longer accepting nominations"
    nomination = Nomination(
        movie_id=movie.imdb_id, title=movie.title, nominator=nomination_context["user"]
    )
    db.collection(VOTES_COLLECTION).document(vote.id).update(
        {"nominations": firestore.ArrayUnion([nomination.__dict__])}
    )


def end_vote(db, vote: Vote):
    top_score = max([len(n.votes) for n in vote.nominations])
    winner = random.choice([n for n in vote.nominations if len(n.votes) == top_score])
    winner.won = True
    vote.status = Vote.status_completed
    db.collection(VOTES_COLLECTION).document(vote.id).set(vote.to_dict())
    return vote


def handle_vote(data):
    action = data["data"]["options"][0]["name"]
    if action in vote_commands:
        return vote_commands[action](data)
    else:
        return NO_COMMAND_MESSAGE(action)


def handle_vote_start(data):
    db = get_db_client()
    active_vote = get_vote(db, Vote.status_running)
    if active_vote:
        return "The vote has already started!"
    else:
        active_vote = get_vote(db, Vote.status_created)
        db.collection(VOTES_COLLECTION).document(active_vote.id).update(
            {"status": Vote.status_running}
        )
    nominations_list = "\n".join(
        [f"({i+1}) {nom.title}" for i, nom in enumerate(active_vote.nominations)]
    )
    return f"Voting has opened!\n{nominations_list}"


def handle_vote_end(data):
    db = get_db_client()
    active_vote = get_vote(db, Vote.status_running)
    if not active_vote:
        return "There is no active vote!"
    finished_vote = end_vote(db, active_vote)
    # Start taking nominations for the next vote
    create_vote(db)
    result_message = (
        "\n".join(
            [f"{nom.title}: {len(nom.votes)}" for nom in finished_vote.nominations]
        )
        + "\n"
    )
    winner = next(filter(lambda n: n.won, finished_vote.nominations))
    winner_message = f"The winner is: {winner.title}\n"
    winner_details = winner.get_movie(db).info()
    return (
        "Voting has ended! The results:\n"
        + result_message
        + winner_message
        + winner_details
    )


def handle_vote_voters(data):
    db = get_db_client()
    current_vote = get_vote(db, Vote.status_running)
    if not current_vote:
        return "No active vote"
    else:
        current_voters = "\n".join(sorted([vote["user"] for nomination in current_vote.nominations for vote in nomination.votes]))
        return f"Current voters:\n{current_voters}"


def get_db_client():
    return firestore.Client(project="promising-silo-421623")


def search_movie(query):
    base_url = f"http://www.omdbapi.com?apikey={os.environ['OMDB_API_KEY']}&"
    base_url += "&".join([f"{k}={v}" for k, v in query.items()])
    return requests.get(base_url).json()


def get_movie(db, movie_id):
    movie_record = db.collection(MOVIE_COLLECTION).document(movie_id).get()
    return None if not movie_record.exists else Movie(movie_record.to_dict())


def get_or_create_movie(db, search_result, nomination_context):
    movie_id = search_result["imdbID"]
    movie = get_movie(db, movie_id)
    if movie:
        return movie
    else:
        search_result["user"] = nomination_context["user"]
        new_movie = Movie(search_result)
        new_doc = db.collection(MOVIE_COLLECTION).document(movie_id)
        new_doc.set(new_movie.__dict__)
        return new_movie


def get_username(data):
    return data["member"]["user"]["username"]


def handle_vote_cast(data):
    voter = get_username(data)
    db = get_db_client()
    vote = get_vote(db, Vote.status_running)
    if not vote:
        return "Can't cast ballot - no vote currently running"
    ballot_text = data["data"]["options"][0]["value"]
    if ballot_text.startswith("random"):
        ballot_text = ballot_text.replace("random ", "")
        choice = int(random.choice(ballot_text.split(" ")))
    else:
        choice = int(ballot_text)
    # If a user has already voted, remove it and place their new one
    for nomination in vote.nominations:
        nomination.votes = [v for v in nomination.votes if v["user"] != voter]
    vote.nominations[choice - 1].votes.append({"user": voter})
    db.collection(VOTES_COLLECTION).document(vote.id).set(vote.to_dict())
    return "Ballot cast!"


def handle_nominate(data):
    nomination_context = {"user": get_username(data)}
    db = get_db_client()
    nom = data["data"]["options"][0]
    if nom["name"] == "id":
        query = {"i": nom["value"]}
    elif match := re.match(r"([\s\S]+) \((\d+)\)$", nom["value"]):
        query = {"t": match.group(1), "y": match.group(2)}
    else:
        query = {"t": nom["value"]}
    search_result = search_movie(query)
    if search_result["Response"] == "False":
        return "No movie found!"
    movie = get_or_create_movie(db, search_result, nomination_context)
    create_nomination(db, movie, nomination_context)

    return "Registered nomination!"


def handle_info(data):
    pass


commands = {
    "vote": handle_vote,
    "nominate": handle_nominate,
    "info": handle_info,
}
vote_commands = {
    "start": handle_vote_start,
    "end": handle_vote_end,
    "voters": handle_vote_voters,
    "cast": handle_vote_cast,
}


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
