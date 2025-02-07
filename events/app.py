"""Main flask app for events service.

Add, edit, and fetch events list.
"""

# Copyright 2019 The Knative Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import datetime
import json
import pymongo
from bson import json_util, ObjectId

from flask import Flask, request
from werkzeug.exceptions import BadRequestKeyError
from eventclass import Event

app = Flask(__name__)  # pylint: disable=invalid-name


@app.route('/v1/', methods=['GET'])
def get_all_events():
    """Return a list of all events currently in the DB."""
    try:
        events = app.config['COLLECTION'].find({})
        events_dict = build_events_dict(events)
        # handle MongoDB objects (e.g. ObjectID) that aren't JSON serializable
        return json.loads(json_util.dumps(events_dict))
    except DBNotConnectedError:
        return 'Events database was undefined.', 500


@app.route('/v1/search', methods=['GET'])
def search_event():
    """Search for the event with the given name in the DB.

    Uses MongoDB text search, which ignores capitalization and stop words, and
    searches on word stems.
    """
    try:
        event_name = request.args['name']
        # create a text index on name to enable searching
        app.config['COLLECTION'].create_index([('name', 'text')])
        events = text_search_event_name(app.config['COLLECTION'], event_name)
        events_dict = build_events_dict(events)
        # handles MongoDB objects (e.g. ObjectID) that aren't JSON serializable
        return json.loads(json_util.dumps(events_dict))
    except BadRequestKeyError:      # missing event attributes
        return 'Event name was entered incorrectly.', 400
    except DBNotConnectedError:
        return 'Events database was undefined.', 500


@app.route('/v1/add', methods=['POST'])
def add_event():
    """Adds the posted event into the database."""
    try:
        info = {
            'name': request.form['event_name'],
            'description': request.form['description'],
            'author': request.form['author_id'],
            'event_time': request.form['event_time']
        }
        current_time = datetime.datetime.utcnow().isoformat(sep=' ',
                                                            timespec='seconds')
        info = build_event_info(info, current_time)
        event = Event(**info)
        app.config['COLLECTION'].insert_one(event.dict)
        return 'Event added.', 201
    except BadRequestKeyError:      # missing event attributes
        return 'Event info was entered incorrectly.', 400
    except DBNotConnectedError:
        return 'Events database was undefined.', 500


@app.route('/v1/edit/<event_id>', methods=['PUT'])
def edit_event(event_id):
    """Edit the event with the given id."""


@app.route('/v1/<event_id>', methods=['PUT'])
def get_one_event(event_id):
    """Retrieve one event by event_id."""
    try:
        events = app.config['COLLECTION'].find({'_id': ObjectId(event_id)})
        events = [Event(**ev).dict for ev in events]
        events_dict = build_events_dict(events)
        # handle MongoDB objects (e.g. ObjectID) that aren't JSON serializable
        return json.loads(json_util.dumps(events_dict))
    except DBNotConnectedError:
        return 'Events database was undefined.', 500


def build_event_info(info, time):
    """Adds created_at time to event info dict."""
    return {**info, 'created_at': time}


def build_events_dict(events_cursor):
    """Builds a dict in the correct format for returning through a GET request.

    Takes in a mongoDB cursor from querying the DB.
    """
    events_list = [Event(**ev).dict for ev in events_cursor]
    num_events = len(events_list)
    return {'events': events_list, 'num_events': num_events}


def text_search_event_name(coll, name):
    return coll.find({'$text': {'$search': name}})


class DBNotConnectedError(ConnectionError):
    """Raised when not able to connect to the db."""


def connect_to_mongodb():   # pragma: no cover
    # TODO(cmei4444): restructure to be consistent with other services
    """Connects to MongoDB Atlas database.

    Returns events collection if connection is successful, and None otherwise.
    """
    class Thrower():  # pylint: disable=too-few-public-methods
        """Used to raise an exception on failed db connect."""

        def __getattribute__(self, _):
            raise DBNotConnectedError(
                'Not able to find MONGODB_URI environment variable')

    mongodb_uri = os.environ.get('MONGODB_URI')
    if mongodb_uri is None:
        return Thrower()  # not able to find db config var
    return pymongo.MongoClient(mongodb_uri).eventsDB.all_events


app.config['COLLECTION'] = connect_to_mongodb()  # None if can't connect


if __name__ == '__main__':  # pragma: no cover
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
