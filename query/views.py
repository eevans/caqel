
from django.shortcuts import render_to_response
from django.http import HttpResponse
from django.core.context_processors import csrf
from django.conf import settings

from json import dumps as to_json
from uuid import UUID

import cql
from cql.results import ResultSet
 
import threading

__local = threading.local()

def __get_cursor():
    return cql.connect(settings.CASSANDRA_HOST,
                       settings.CASSANDRA_PORT).cursor()

def __execute(query, keyspace=None):
    # Lazily assign a cursor instance to a thread-local variable
    if not hasattr(__local, "cursor") or not getattr(__local, "cursor"):
        __local.cursor = __get_cursor()
    if keyspace:
        __local.cursor.execute("USE " + keyspace)
        
    __local.cursor.execute(query)
    return __local.cursor

def __serialize(cursor):
    def marshal(value):
        if isinstance(value, UUID):
            return str(value)
        return value
        
    if isinstance(cursor.result, ResultSet):
        rows = {}
        for row in cursor.result.rows:
            rows[row.key] = []
            for col in row.columns:
                rows[row.key].append(
                    {"name": marshal(col.name), "value": marshal(col.value)})
        return to_json({"rows": rows})
    else:
        if cursor.result is None: return to_json({"void": "Success"})
        else: return to_json({"int": cursor.result})

# View methods
def index(request):
    return render_to_response("index.html", csrf(request))

def query(request):
    query_string = request.POST['post_data']
    try:
        if query_string.upper().startswith("USE"):
            __execute(query_string)
            keyspace = query_string.split()[1].strip(";")
            request.session["current_keyspace"] = keyspace
            json = to_json({"void": "Using keyspace %s" % keyspace})
        else:
            current_keyspace = request.session.get("current_keyspace", None)
            cursor = __execute(query_string, current_keyspace)
            json = __serialize(cursor)
    except cql.DatabaseError, error:
        json = to_json({"exception": str(error)})
    return HttpResponse(json, mimetype="application/json")
    
def describe_keyspaces(request):
    schema = __get_cursor().decoder.schema    # you gotta keep 'em violated
    del schema["system"]
    return HttpResponse(to_json(schema), mimetype="application/json")


