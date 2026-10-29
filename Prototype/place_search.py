"""Explicit, cached place search. Photon with a city-search fallback."""
from functools import lru_cache
from threading import Lock
import math
import os
import time
import requests

_lock=Lock()
_last_request=0.0
USER_AGENT='FloodsafeStudentPrototype/1.0 (https://github.com/Siyagour/Flood-Management)'

class SearchError(Exception):
    def __init__(self,message,status=502):
        super().__init__(message)
        self.status=status

def _get(url,params):
    try:
        response=requests.get(url,params=params,headers={'User-Agent':USER_AGENT},timeout=(3,5))
        if response.status_code==429:raise SearchError('Place search is busy. Wait a few seconds and try again.',429)
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise SearchError('Place search timed out. Check your connection and try again.',504) from exc
    except (requests.RequestException,ValueError) as exc:
        raise SearchError('Place search is unavailable. Try again, use a preset location, or pan the map manually.') from exc

def _valid(lat,lon):
    return math.isfinite(lat) and math.isfinite(lon) and -85<=lat<=85 and -180<=lon<=180

def _photon(query):
    data=_get(os.environ.get('FLOODSAFE_GEOCODER_URL','https://photon.komoot.io/api/'),{'q':query+' India','lang':'en','limit':15,'bbox':'68,6,98,38'})
    if not isinstance(data,dict) or not isinstance(data.get('features'),list):
        raise SearchError('The search service returned an invalid response. Please retry.')
    places=[]
    for item in data['features'][:15]:
        try:
            lon,lat=map(float,item['geometry']['coordinates'][:2])
            props=item.get('properties',{})
            if not isinstance(props,dict):continue
            if str(props.get('countrycode','')).upper()!='IN':continue
            name=', '.join(dict.fromkeys(str(props[k]) for k in ['name','city','state','country'] if props.get(k)))
            if name and _valid(lat,lon):places.append({'name':name,'lat':lat,'lon':lon})
        except (KeyError,TypeError,ValueError,IndexError,AttributeError):continue
    return places[:5]

def _cities(query):
    data=_get('https://geocoding-api.open-meteo.com/v1/search',{'name':query,'count':5,'language':'en','format':'json','countryCode':'IN'})
    if not isinstance(data,dict) or ('results' not in data and 'generationtime_ms' not in data):
        raise SearchError('The fallback search returned an invalid response.')
    items=data.get('results',[])
    if not isinstance(items,list):raise SearchError('The fallback search returned an invalid response.')
    places=[]
    for item in items[:5]:
        try:
            if str(item.get('country_code','')).upper()!='IN':continue
            lat=float(item['latitude']);lon=float(item['longitude'])
            name=', '.join(dict.fromkeys(str(item[k]) for k in ['name','admin1','country'] if item.get(k)))
            if name and _valid(lat,lon):places.append({'name':name,'lat':lat,'lon':lon})
        except (KeyError,TypeError,ValueError,AttributeError):continue
    return places[:5]

@lru_cache(maxsize=128)
def find_places(query):
    global _last_request
    # Verified OSM campus access point; resolve common campus abbreviations even
    # when public search services are unavailable. Not a Google Places result.
    words=query.casefold().replace('-', ' ').split()
    if ('techno' in words and 'njr' in words) or query.casefold().replace(' ','') in {'technonjr','tinjr'}:
        return [{'name':'Techno India NJR Institute of Technology — campus access, Kaladwas, Udaipur, Rajasthan, India',
                 'lat':24.5179096,'lon':73.7518783,
                 'source':'OpenStreetMap named campus access road',
                 'source_url':'https://www.openstreetmap.org/way/1205398059'}]
    with _lock:
        remaining=1.1-(time.monotonic()-_last_request)
        if remaining>0:time.sleep(remaining)
        _last_request=time.monotonic()
        try:return _photon(query)
        except SearchError as first:
            try:return _cities(query)
            except SearchError:raise first
