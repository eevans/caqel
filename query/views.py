
from django.shortcuts import render_to_response
from django.http import HttpResponse
from django.core.context_processors import csrf
from django.conf import settings

from json import dumps as to_json
from uuid import UUID
from cql.connection import Connection
from cql.results import RowsProxy
from cql.errors import CQLException
 
import threading

__local = threading.local()

def __get_connection():
    return Connection(settings.CASSANDRA_HOST, settings.CASSANDRA_PORT)

def __execute(query, *args):
    # Lazily assign a connection instance to a thread-local variable
    if not hasattr(__local, "conn") or not getattr(__local, "conn"):
        __local.conn = __get_connection()
    return __local.conn.execute(query, *args)

def __serialize(results):
    def marshal(value):
        if isinstance(value, UUID):
            return str(value)
        return value
        
    if isinstance(results, RowsProxy):
        rows = {}
        for result in results:
            rows[result.key] = []
            for col in result:
                rows[result.key].append(
                    {"name": marshal(col.name), "value": marshal(col.value)})
        return to_json({"rows": rows})
    else:
        if results is None: return to_json({"void": "Success"})
        else: return to_json({"int": results})

# View methods
def index(request):
    return render_to_response("index.html", csrf(request))

def query(request):
    query_string = request.POST['post_data']
    try:
        results = __execute(query_string)
        
        # If return was void (None), and the statement is a USE, then
        # tailor the display message a bit.
        if results is None and query_string.upper().startswith("USE"):
            keyspace = query_string.split()[1].strip(";")
            json = to_json({"void": "Using keyspace %s" % keyspace})
        else:
            json = __serialize(results)
    except CQLException, error:
        json = to_json({"exception": str(error)})
    return HttpResponse(json, mimetype="application/json")
    
def describe_keyspaces(request):
    schema = __get_connection().decoder.schema    # you gotta keep 'em violated
    return HttpResponse(to_json(schema), mimetype="application/json")


