from unittest.mock import patch
from main import (
    create_vote,
    get_db_client,
    handle_info,
    handle_nominate,
    handle_stats,
    handle_view_nominations,
    handle_vote_cast,
    handle_vote_end,
    handle_vote_start,
    handle_vote_voters,
)
from mockfirestore import MockFirestore
from test_data import *

server_stats_data = {
    "id": "1233616675837055047",
    "name": "stats",
    "options": [{"name": "server", "type": 1}],
    "type": 1,
}
vote_start_data = {
    "id": "1233616675837055047",
    "name": "vote",
    "options": [{"name": "start", "type": 1}],
    "type": 1,
}
vote_end_data = {
    "id": "1233616675837055047",
    "name": "vote",
    "options": [{"name": "end", "type": 1}],
    "type": 1,
}
vote_voters_data = {
    "id": "1233616675837055047",
    "name": "vote",
    "options": [{"name": "voters", "type": 1}],
    "type": 1,
}
view_info_data = {
    "id": "1233616675837055047",
    "name": "info",
    "options": [{"name": "movie", "type": 3, "value": "Spider-man"}],
    "type": 3,
}
vote_nominees_data = {
    "id": "1233616675837055047",
    "name": "vote",
    "options": [{"name": "nominations", "type": 1}],
    "type": 1,
}
nominate_data_1 = {
    "id": "1233616675837055047",
    "name": "nominate",
    "options": [{"name": "title", "type": 3, "value": "Spider-man"}],
    "type": 1,
}
nominate_data_2 = {
    "id": "1233616675837055047",
    "name": "nominate",
    "options": [{"name": "title", "type": 3, "value": "Spider-man 2"}],
    "type": 1,
}
nominate_data_3 = {
    "id": "1233616675837055047",
    "name": "nominate",
    "options": [{"name": "title", "type": 3, "value": "Spider-man 3"}],
    "type": 1,
}
vote_data_random = {
    "id": "1233616675837055047",
    "name": "vote",
    "options": [
        {
            "name": "cast",
            "type": 1,
            "options": [{"name": "ballot", "type": 1, "value": "random"}],
        }
    ],
    "type": 1,
}
vote_data_1 = {
    "id": "1233616675837055047",
    "name": "vote",
    "options": [
        {
            "name": "cast",
            "type": 1,
            "options": [{"name": "ballot", "type": 1, "value": "1"}],
        }
    ],
    "type": 1,
}
vote_data_2 = {
    "id": "1233616675837055047",
    "name": "vote",
    "options": [
        {
            "name": "cast",
            "type": 1,
            "options": [{"name": "ballot", "type": 1, "value": "random 2 2 2"}],
        }
    ],
    "type": 1,
}


def fake_omdb(query):
    if query["t"] == "Spider-man 2":
        return spiderman2
    elif query["t"] == "Spider-man 3":
        return spiderman3
    elif query["t"] == "Spider-man":
        return spiderman1


@patch("main.search_movie")
@patch("main.get_db_client")
def test_flow(mock_db, mock_omdb):
    # There should always be a vote
    mock_firestore = MockFirestore()
    mock_db.return_value = mock_firestore
    mock_omdb.side_effect = fake_omdb
    create_vote(mock_firestore)
    # Nominate 2 movies
    nominations()
    # View nominations
    view_nominations()
    # Start vote
    vote_start()
    # Four votes, with movie #2 winning
    voting()
    # View voters
    view_voters()
    # Vote ends
    end_vote()
    # Should be able to start nominating again
    nominations()
    # Get server stats so far
    stats()


@patch("main.search_movie")
@patch("main.get_db_client")
def test_random_nomination(mock_db, mock_omdb):
    # There should always be a vote
    mock_firestore = MockFirestore()
    mock_db.return_value = mock_firestore
    mock_omdb.side_effect = fake_omdb
    create_vote(mock_firestore)
    # Nominate 2 movies
    nominations()
    vote_start()
    # User 1 votes for option 1
    sample_payload["member"] = member_1
    sample_payload["data"] = vote_data_random
    assert "Ballot cast!" == handle_vote_cast(sample_payload)


@patch("main.search_movie")
def test_info(mock_omdb):
    # There should always be a vote
    mock_omdb.side_effect = fake_omdb
    sample_payload["data"] = view_info_data
    assert handle_info(sample_payload).startswith("**" + spiderman1["Title"] + "**")


# def test_real_flow():
#     # There should always be a vote
#     db = get_db_client()
#     create_vote(db)
#     # Nominate 2 movies
#     nominations()
#     # Start vote
#     vote_start()
#     # Four votes, with movie #2 winning
#     voting()
#     # View voters
#     view_voters()
#     # Vote ends
#     end_vote()
#     # Should be able to start nominating again
#     nominations()
def end_vote():
    sample_payload["data"] = vote_end_data
    vote_end_message = handle_vote_end(sample_payload)
    assert vote_end_message.startswith(
        "Voting has ended! The results:\nSpider-Man 2: 1\nSpider-Man 3: 3\nThe winner is: Spider-Man 3"
    )

def stats():
    sample_payload["data"] = server_stats_data
    stats = handle_stats(sample_payload)
    assert "**Server Stats**\n2 movies have been nominated, and we have watched 2 movies with an average metacritic score of 59.0\n" == stats

def view_nominations():
    sample_payload["data"] = vote_nominees_data
    voters = handle_view_nominations(sample_payload)
    assert voters == "Current nominations:\n(1) Spider-Man 2\n(2) Spider-Man 3"


def view_voters():
    sample_payload["data"] = vote_voters_data
    voters = handle_vote_voters(sample_payload)
    assert voters == "Current voters:\nlanzauq\nmysteryjudge\nquaznal\ntiemaker"


def voting():
    # User 1 votes for option 1
    sample_payload["member"] = member_1
    sample_payload["data"] = vote_data_1
    assert "Ballot cast!" == handle_vote_cast(sample_payload)
    # User 2 votes for option 2
    sample_payload["member"] = member_2
    sample_payload["data"] = vote_data_2
    assert "Ballot cast!" == handle_vote_cast(sample_payload)
    # User 3 votes for option 2
    sample_payload["member"] = member_3
    sample_payload["data"] = vote_data_2
    assert "Ballot cast!" == handle_vote_cast(sample_payload)
    # User 4 votes for option 1, then switches to option 2
    sample_payload["member"] = member_4
    sample_payload["data"] = vote_data_1
    assert "Ballot cast!" == handle_vote_cast(sample_payload)
    sample_payload["data"] = vote_data_2
    assert "Ballot cast!" == handle_vote_cast(sample_payload)


def vote_start():
    sample_payload["data"] = vote_start_data
    result = handle_vote_start(sample_payload)
    assert (
        result
        == """Voting has opened!
(1) Spider-Man 2
(2) Spider-Man 3"""
    )


def nominations():
    # Member 1 nominates data 1
    sample_payload["data"] = nominate_data_1
    sample_payload["member"] = member_1
    result = handle_nominate(sample_payload)
    assert result == "Registered nomination!"
    # Member 2 nominates data 2
    sample_payload["data"] = nominate_data_2
    sample_payload["member"] = member_2
    result = handle_nominate(sample_payload)
    assert result == "Registered nomination!"
    # Member 1 changes their mind and nominates 3
    sample_payload["data"] = nominate_data_3
    sample_payload["member"] = member_1
    result = handle_nominate(sample_payload)
    assert result == "Registered nomination!"


# def test_nominate():
# 	# db = get_db_client()
# 	# create_vote(db)
# 	result = handle_nominate(sample_payload)
# 	assert result == "Registered nomination!"
