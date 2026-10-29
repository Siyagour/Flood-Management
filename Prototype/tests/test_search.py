import unittest
from unittest.mock import Mock,patch
import requests
import place_search
from app import app

class SearchTests(unittest.TestCase):
    def setUp(self):
        place_search.find_places.cache_clear()
        place_search._last_request=0
        self.client=app.test_client()
    def response(self,data,status=200):
        result=Mock(status_code=status)
        result.json.return_value=data
        return result
    def test_blank_and_long_query(self):
        for query in ['',' ','x','x'*201]:
            self.assertEqual(self.client.get('/api/search',query_string={'q':query}).status_code,400)
    @patch('place_search.requests.get')
    def test_valid_result_and_cache(self,get):
        get.return_value=self.response({'features':[{'geometry':{'coordinates':[73.71,24.58]},'properties':{'name':'Udaipur','state':'Rajasthan','country':'India','country_code':'IN','countrycode':'IN'}}]})
        for query in ['Udaipur','udaipur']:
            result=self.client.get('/api/search',query_string={'q':query})
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json['places'][0]['lat'],24.58)
        self.assertEqual(get.call_count,1)
    @patch('place_search.requests.get',side_effect=requests.Timeout())
    def test_timeout(self,get):
        r=self.client.get('/api/search?q=udaipur')
        self.assertEqual(r.status_code,504)
        self.assertIn('timed out',r.json['error'])
    @patch('place_search.requests.get')
    def test_rate_limit(self,get):
        get.return_value=self.response({},429)
        self.assertEqual(self.client.get('/api/search?q=udaipur').status_code,429)
    @patch('place_search.requests.get')
    def test_malformed_response(self,get):
        get.return_value=self.response({'unexpected':True})
        self.assertEqual(self.client.get('/api/search?q=udaipur').status_code,502)
    @patch('place_search.requests.get')
    def test_no_results(self,get):
        get.return_value=self.response({'features':[]})
        self.assertEqual(self.client.get('/api/search?q=nowhere').json,{'places':[]})
    @patch('place_search.requests.get')
    def test_bad_coordinates_discarded(self,get):
        get.return_value=self.response({'features':[{'geometry':{'coordinates':[73,'NaN']},'properties':{'name':'Bad'}}]})
        self.assertEqual(self.client.get('/api/search?q=nowhere').json,{'places':[]})

    @patch('place_search.requests.get')
    def test_city_fallback(self,get):
        get.side_effect=[requests.Timeout(),self.response({'results':[{'name':'Udaipur','admin1':'Rajasthan','country':'India','country_code':'IN','countrycode':'IN','latitude':24.58,'longitude':73.71}]})]
        result=self.client.get('/api/search?q=udaipur')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json['places'][0]['name'],'Udaipur, Rajasthan, India')

    @patch('place_search.requests.get')
    def test_campus_alias_offline(self,get):
        result=self.client.get('/api/search?q=techno+NJR')
        self.assertEqual(result.status_code,200)
        self.assertIn('Techno India NJR',result.json['places'][0]['name'])
        self.assertAlmostEqual(result.json['places'][0]['lat'],24.5179096)
        get.assert_not_called()
    @patch('place_search.requests.get')
    def test_photon_excludes_international_results(self,get):
        get.return_value=self.response({'features':[
            {'geometry':{'coordinates':[73.71,24.58]},'properties':{'name':'Udaipur','countrycode':'IN'}},
            {'geometry':{'coordinates':[-0.1,51.5]},'properties':{'name':'London','countrycode':'GB'}},
            {'geometry':{'coordinates':[73.71,24.58]},'properties':{'name':'Unknown country'}}]})
        result=self.client.get('/api/search?q=udaipur')
        self.assertEqual(len(result.json['places']),1)
        self.assertIn('India',get.call_args.kwargs['params']['q'])
    @patch('place_search.requests.get')
    def test_city_fallback_excludes_international_results(self,get):
        get.side_effect=[requests.Timeout(),self.response({'results':[
            {'name':'Udaipur','country_code':'IN','latitude':24.58,'longitude':73.71},
            {'name':'London','country_code':'GB','latitude':51.5,'longitude':-.1}]})]
        result=self.client.get('/api/search?q=udaipur')
        self.assertEqual(len(result.json['places']),1)
        self.assertEqual(get.call_args.kwargs['params']['countryCode'],'IN')
