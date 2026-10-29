"""Download bounded OSM extracts and retain drivable ways only."""
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import requests
import osmnx as ox

USER_AGENT='FloodsafeStudentPrototype/1.0 (https://github.com/Siyagour/Flood-Management)'
EXCLUDED={'footway','path','steps','cycleway','pedestrian','construction','proposed','bridleway','corridor','elevator','platform','raceway','abandoned','bus_guideway'}

def graph_from_osm_bytes(content):
    root=ET.fromstring(content)
    kept=[]; refs=set()
    for way in root.findall('way'):
        tags={t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}
        if not tags.get('highway') or tags['highway'] in EXCLUDED: continue
        if tags.get('area')=='yes':continue
        access=tags.get('motorcar',tags.get('motor_vehicle',tags.get('vehicle',tags.get('access','yes'))))
        if access in {'no','private','agricultural','forestry'}:continue
        kept.append(way)
        refs.update(n.attrib['ref'] for n in way.findall('nd'))
    cleaned=ET.Element('osm',{'version':'0.6','generator':'Floodsafe OSM road filter'})
    for node in root.findall('node'):
        if node.attrib['id'] in refs:cleaned.append(node)
    for way in kept:cleaned.append(way)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'roads.osm'
        ET.ElementTree(cleaned).write(path,encoding='utf-8',xml_declaration=True)
        graph=ox.graph_from_xml(path,bidirectional=False,simplify=True,retain_all=True)
    if not graph.number_of_edges():raise ValueError('No drivable OpenStreetMap roads found in this area.')
    return graph

def fetch_graph(bounds):
    west,south,east,north=bounds
    response=requests.get('https://api.openstreetmap.org/api/0.6/map',
        params={'bbox':f'{west:.7f},{south:.7f},{east:.7f},{north:.7f}'},
        headers={'User-Agent':USER_AGENT},timeout=(10,40))
    response.raise_for_status()
    return graph_from_osm_bytes(response.content)
