
from django.shortcuts import render_to_response
from django.http import HttpResponse
from django.core.context_processors import csrf
from django.conf import settings

import logging
logger = logging.getLogger(__name__)

try:
    from json import dumps as to_json
except ImportError:
    from simplejson import dumps as to_json

from uuid import UUID

import cql, threading

__local = threading.local()

def __get_cursor():
    if not hasattr(__local, "conn") or not getattr(__local, "conn"):
        __local.conn = cql.connect(settings.CASSANDRA_HOST,
                                   settings.CASSANDRA_PORT)
    return __local.conn.cursor()

def __execute(query, keyspace=None):
    # Lazily assign a cursor instance to a thread-local variable
    cursor = __get_cursor()
    if keyspace:
        cursor.execute("USE " + keyspace)
        
    cursor.execute(query)
    return cursor

def __serialize(cursor):
    def marshal(value):
        if isinstance(value, (UUID,long)):
            return str(value)
        return value

    if not hasattr(cursor, "result"):
        return to_json({"void": "Success"})

    rows = {}
    for x in range(cursor.rowcount):
        r = cursor.fetchone()
        rows[r[0]] = []
        for (j, column_value) in enumerate(r[1:]):
            column_name = cursor.description[j+1][0]
            rows[r[0]].append({"name": marshal(column_name),
                    "value": marshal(column_value)})

    return to_json({"rows": rows})

# View methods
def index(request):
    return render_to_response("index.html", csrf(request))

def query(request):
    query_string = request.POST['post_data']
    try:
        if query_string.upper().startswith("USE"):
            __execute(query_string)
            keyspace = query_string.split()[1].strip(";")

            # Giving people access to the system keyspace would be Bad
            if keyspace == "system":
                raise cql.DatabaseError("No. Not as stupid as I look.");

            request.session["current_keyspace"] = keyspace
            json = to_json({"void": "Using keyspace %s" % keyspace})
        elif query_string.split()[1].upper().startswith("COUNT"):
            current_keyspace = request.session.get("current_keyspace", None)
            cursor = __execute(query_string, current_keyspace)
            r = cursor.fetchone()
            json = to_json({"int": r[0]})
        else:
            current_keyspace = request.session.get("current_keyspace", None)
            cursor = __execute(query_string, current_keyspace)
            json = __serialize(cursor)
    except cql.DatabaseError, error:
        json = to_json({"exception": str(error)})
    return HttpResponse(json, mimetype="application/json")
    
def describe_keyspaces(request):
    cursor = __get_cursor()
    # ...because it's amazing how much random shit broke between 1.0.3 and 1.0.5
    if hasattr(cursor, "_connection"): client =  cursor._connection.client
    else: client = cursor.parent_connection.client
    
    schema = {}
    for ksdef in client.describe_keyspaces():
        if ksdef.name == "system":
            continue
        schema[ksdef.name] = {}
        for cfdef in ksdef.cf_defs:
            schema[ksdef.name][cfdef.name] = None
    
    return HttpResponse(to_json(schema), mimetype="application/json")


