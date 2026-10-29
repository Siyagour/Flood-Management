"""Run: python Prototype/app.py, then open http://127.0.0.1:8502."""
from flask import Flask, jsonify, request
from planner import checked_polygon, make_grid, load_roads, plan_on_graph

app=Flask(__name__,static_folder='static',static_url_path='/static')
app.config['MAX_CONTENT_LENGTH']=3*1024*1024

@app.get('/')
def index(): return app.send_static_file('index.html')

@app.get('/api/search')
def search():
    from place_search import find_places, SearchError
    query=' '.join(request.args.get('q','').split())
    if not 2<=len(query)<=200:
        return jsonify(error='Enter a place name between 2 and 200 characters.'),400
    try:
        return jsonify(places=find_places(query.casefold()))
    except SearchError as exc:
        return jsonify(error=str(exc)),exc.status

@app.post('/api/grid')
def grid():
    d=request.get_json()
    return jsonify(make_grid(d['boundary'],d.get('resolution',9),d.get('density',3000)))

@app.post('/api/plan')
def plan():
    d=request.get_json()
    if not d.get('shelters'): raise ValueError('Place at least one shelter on the map.')
    if len(d['shelters'])>20 or len(d.get('floods',[]))>30: raise ValueError('Use at most 20 shelters and 30 flood zones.')
    if not d.get('grid',{}).get('features'): raise ValueError('Create the area hexagons first.')
    if len(d['grid']['features'])>250: raise ValueError('Use at most 250 hexagons.')
    p=checked_polygon(d['boundary'])
    graph=load_roads(p.wkt)
    return jsonify(plan_on_graph(graph,d['grid'],d['shelters'],d.get('floods',[]),d.get('threshold',25),d.get('speed',15),d.get('interval',30)))

@app.errorhandler(Exception)
def error(e):
    app.logger.exception('Scenario request failed')
    return jsonify(error=str(e)),400
