"""Scenario planning on mapped OSM roads; user supplied demand and shelters."""
import math
from functools import lru_cache
import h3
import networkx as nx
import osmnx as ox
from shapely.geometry import shape, mapping, Polygon, Point, LineString
from shapely.ops import transform
from pyproj import Transformer


def checked_polygon(geo):
    p = shape(geo)
    if p.geom_type != 'Polygon' or not p.is_valid or p.is_empty:
        raise ValueError('Draw a valid area without crossed edges.')
    # Small local scenarios keep road retrieval and animation responsive.
    metric = transform(Transformer.from_crs(4326, 6933, always_xy=True).transform, p)
    if metric.area > 25_000_000:
        raise ValueError('Select an area under 25 km². Start with a neighbourhood in Udaipur.')
    return p


def make_grid(geo, resolution, density):
    p = checked_polygon(geo)
    resolution = int(resolution)
    if not 7 <= resolution <= 11 or not 0 <= float(density) <= 50000:
        raise ValueError('Choose resolution 7–11 and density 0–50,000.')
    hp = h3.LatLngPoly([(y,x) for x,y in p.exterior.coords], *[[(y,x) for x,y in r.coords] for r in p.interiors])
    cells = sorted(h3.polygon_to_cells_experimental(hp, resolution, contain='overlap'))
    if len(cells) > 250:
        raise ValueError('That makes more than 250 hexagons. Reduce the resolution or select a smaller area.')
    features = []
    project = Transformer.from_crs(4326, 6933, always_xy=True).transform
    for cell in cells:
        clipped = Polygon([(lon,lat) for lat,lon in h3.cell_to_boundary(cell)]).intersection(p)
        if clipped.is_empty or clipped.area < 1e-12:
            continue
        point = clipped.representative_point()
        area = transform(project, clipped).area / 1e6
        features.append({'type':'Feature','geometry':mapping(clipped),'properties':{
            'id':cell,'people':round(area*float(density)), 'area_km2':area,
            'lat':point.y, 'lon':point.x}})
    return {'type':'FeatureCollection','features':features}


@lru_cache(maxsize=6)
def load_roads(boundary_wkt):
    from shapely import wkt
    p = wkt.loads(boundary_wkt)
    ox.settings.use_cache = True
    ox.settings.requests_timeout = 45
    ox.settings.overpass_rate_limit = False
    # A buffer permits routes to leave the selected population area to reach shelters.
    center = p.centroid
    epsg = 32600 + int((center.x+180)//6)+1 if center.y>=0 else 32700+int((center.x+180)//6)+1
    forward = Transformer.from_crs(4326, epsg, always_xy=True).transform
    back = Transformer.from_crs(epsg, 4326, always_xy=True).transform
    area = transform(back, transform(forward,p).buffer(1200))
    from pathlib import Path
    from datetime import datetime, timezone
    import hashlib, json
    from road_data import fetch_graph
    data_dir=Path(__file__).parent/'data'
    # Real, attributed OSM snapshot lets the starting Udaipur area work without
    # repeatedly querying a busy public service. Never fabricate road geometry.
    meta_path=data_dir/'udaipur.json'
    if meta_path.exists():
        meta=json.loads(meta_path.read_text())
        west,south,east,north=meta['bounds']
        a,b,c,d=area.bounds
        if west<=a and south<=b and east>=c and north>=d:
            graph=ox.load_graphml(data_dir/'udaipur.graphml')
            graph.graph['road_source']='OpenStreetMap Udaipur snapshot · '+meta['captured_date']
            return graph
    cache_dir=Path(__file__).parent/'.road_cache'
    cache_dir.mkdir(exist_ok=True)
    cache_path=cache_dir/(hashlib.sha256(boundary_wkt.encode()).hexdigest()[:20]+'.graphml')
    if cache_path.exists():
        return ox.load_graphml(cache_path)
    try:
        graph=fetch_graph(area.bounds)
    except Exception as first_error:
        try:
            # Larger extracts can exceed the map API size limit. Fall back to Overpass.
            ox.settings.http_user_agent='FloodsafeStudentPrototype/1.0 (github.com/Siyagour/Flood-Management)'
            graph=ox.graph_from_polygon(area,network_type='drive',retain_all=True,truncate_by_edge=True)
        except Exception as exc:
            raise RuntimeError('Road download failed. The public map services may be busy. Try a smaller area or use the starting Udaipur area, which includes a real road snapshot. '+str(exc)[:120]) from first_error
    if graph.number_of_edges()==0:
        raise ValueError('No drivable roads found. Select a neighbourhood with mapped roads.')
    graph.graph['road_source']='OpenStreetMap download · '+datetime.now(timezone.utc).date().isoformat()
    ox.save_graphml(graph,cache_path)
    return graph


def distance_m(a,b):
    lat1,lon1=a; lat2,lon2=b
    return math.hypot((lat1-lat2)*111320,(lon1-lon2)*111320*math.cos(math.radians((lat1+lat2)/2)))


def edge_coords(graph,u,v,data):
    geom=data.get('geometry')
    coords=list(geom.coords) if geom is not None else [(graph.nodes[u]['x'],graph.nodes[u]['y']),(graph.nodes[v]['x'],graph.nodes[v]['y'])]
    start=Point(graph.nodes[u]['x'],graph.nodes[u]['y'])
    if start.distance(Point(coords[-1])) < start.distance(Point(coords[0])):
        coords.reverse()
    return [[y,x] for x,y in coords]


def plan_on_graph(graph, grid, shelters, floods, threshold=25, speed=15, interval=30):
    """Shortest road paths + greedy shelter capacities, with explicit unresolved demand."""
    graph=graph.copy()
    threshold=float(threshold); speed=float(speed); interval=float(interval)
    if threshold<=0 or speed<=0 or interval<0:
        raise ValueError('Closure depth and speed must be positive; departure interval cannot be negative.')
    zones=[(checked_polygon(f['geometry']),max(0,float(f['depth']))) for f in floods]
    roads=[]
    for u,v,k,data in list(graph.edges(keys=True,data=True)):
        coords=edge_coords(graph,u,v,data)
        geom=LineString([(lon,lat) for lat,lon in coords])
        depth=max([d for zone,d in zones if geom.intersects(zone)]+[0])
        closed=depth>=threshold
        roads.append({'coordinates':coords,'closed':closed,'wet':depth>0})
        if closed:
            graph.remove_edge(u,v,k)
        else:
            data['minutes']=max(float(data.get('length',1)),1)/(speed*1000/60)*(1+depth/threshold)
            data['coords']=coords
    def snap(lat,lon):
        # Snap on the original node set so disconnected origins remain disconnected.
        node=min(graph.nodes,key=lambda n:distance_m((lat,lon),(graph.nodes[n]['y'],graph.nodes[n]['x'])))
        meters=distance_m((lat,lon),(graph.nodes[node]['y'],graph.nodes[node]['x']))
        return node,meters
    shelter_rows=[]
    for i,s in enumerate(shelters):
        lat=float(s['lat']); lon=float(s['lon']); cap=max(0,int(s['capacity']))
        node,meters=snap(lat,lon)
        flooded=any(d>=threshold and zone.covers(Point(lon,lat)) for zone,d in zones)
        status='Flooded' if flooded else 'Too far from road' if meters>300 else 'Open'
        shelter_rows.append(dict(id=s['id'],name=s.get('name',f'Shelter {i+1}'),lat=lat,lon=lon,
            road_lat=graph.nodes[node]['y'],road_lon=graph.nodes[node]['x'],node=node,
            capacity=cap,assigned=0,status=status,access_m=round(meters)))
    routes=[]; rows=[]
    for feature in sorted(grid['features'],key=lambda f:(-int(f['properties']['people']),f['properties']['id'])):
        c=feature['properties']; people=max(0,int(c['people'])); remain=people
        node,meters=snap(float(c['lat']),float(c['lon']))
        options=[]
        if meters<=300:
            for s in shelter_rows:
                if s['status']!='Open' or s['assigned']>=s['capacity']: continue
                try:
                    cost,path=nx.single_source_dijkstra(graph,node,s['node'],weight='minutes')
                    options.append((cost,s['id'],s,path))
                except (nx.NetworkXNoPath,nx.NodeNotFound): pass
        for cost,_,s,path in sorted(options,key=lambda x:(x[0],x[1])):
            amount=min(remain,s['capacity']-s['assigned'])
            if amount<=0: continue
            coords=[]; length=0
            for u,v in zip(path,path[1:]):
                data=min(graph[u][v].values(),key=lambda d:d['minutes'])
                coords.extend(data['coords'] if not coords else data['coords'][1:])
                length+=float(data.get('length',0))
            if not coords: coords=[[graph.nodes[node]['y'],graph.nodes[node]['x']]]
            departure=len(routes)*interval/60
            routes.append({'origin':c['id'],'shelter':s['id'],'people':amount,'coordinates':coords,
                'departure_min':departure,'arrival_min':departure+cost,'travel_min':cost,'distance_km':length/1000,
                'access_m':round(meters),'origin_point':[c['lat'],c['lon']]})
            s['assigned']+=amount; remain-=amount
            if remain==0: break
        reason='' if remain==0 else ('Origin more than 300 m from mapped road' if meters>300 else 'No reachable open shelter with remaining capacity')
        rows.append({'hexagon':c['id'],'people':people,'assigned':people-remain,'unassigned':remain,'reason':reason})
    return {'routes':routes,'shelters':shelter_rows,'roads':roads,'hexagons':rows,'road_source':graph.graph.get('road_source','OpenStreetMap'),
        'summary':{'demand':sum(r['people'] for r in rows),'assigned':sum(r['assigned'] for r in rows),
                   'unassigned':sum(r['unassigned'] for r in rows),'closed_links':sum(r['closed'] for r in roads)}}
