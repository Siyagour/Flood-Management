import unittest
import networkx as nx
from shapely.geometry import Polygon, LineString, mapping
from planner import make_grid,plan_on_graph

class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.g=nx.MultiDiGraph()
        for n,(x,y) in enumerate([(73.71,24.58),(73.711,24.58),(73.712,24.58),(73.711,24.581)]):
            self.g.add_node(n,x=x,y=y)
        for u,v,length in [(0,1,100),(1,2,100),(0,3,180),(3,2,180)]:
            for a,b in [(u,v),(v,u)]:
                self.g.add_edge(a,b,length=length,geometry=LineString([(self.g.nodes[a]['x'],self.g.nodes[a]['y']),(self.g.nodes[b]['x'],self.g.nodes[b]['y'])]))
        self.grid={'features':[{'properties':{'id':'A','lat':24.58,'lon':73.71,'people':120}}]}
        self.shelters=[{'id':'S1','lat':24.58,'lon':73.712,'capacity':100},{'id':'S2','lat':24.581,'lon':73.711,'capacity':10}]
    def test_capacity_conservation(self):
        p=plan_on_graph(self.g,self.grid,self.shelters,[])
        self.assertEqual(p['summary']['assigned'],110)
        self.assertEqual(p['summary']['unassigned'],10)
        for s in p['shelters']: self.assertLessEqual(s['assigned'],s['capacity'])
    def test_closed_edge_uses_detour(self):
        flood={'geometry':mapping(Polygon([(73.7114,24.5799),(73.7116,24.5799),(73.7116,24.5801),(73.7114,24.5801)])),'depth':40}
        p=plan_on_graph(self.g,self.grid,self.shelters[:1],[flood])
        self.assertIn([24.581,73.711],p['routes'][0]['coordinates'])
        self.assertGreater(p['summary']['closed_links'],0)
    def test_flooded_shelter_excluded(self):
        flood={'geometry':mapping(Polygon([(73.7119,24.5799),(73.7121,24.5799),(73.7121,24.5801),(73.7119,24.5801)])),'depth':40}
        p=plan_on_graph(self.g,self.grid,self.shelters,[flood])
        self.assertEqual(p['shelters'][0]['status'],'Flooded')
        self.assertTrue(all(r['shelter']!='S1' for r in p['routes']))
    def test_tiny_boundary_grid(self):
        geo=mapping(Polygon([(73.71,24.58),(73.7101,24.58),(73.7101,24.5801),(73.71,24.5801)]))
        grid=make_grid(geo,7,3000)
        self.assertGreater(len(grid['features']),0)
    def test_curved_edge_retains_shape(self):
        coords=[(73.71,24.58),(73.7105,24.58001),(73.711,24.58)]
        self.g[0][1][0]['geometry']=LineString(coords)
        p=plan_on_graph(self.g,self.grid,self.shelters[:1],[])
        self.assertIn([24.58001,73.7105],p['routes'][0]['coordinates'])
    def test_unreachable_origin_stays_unassigned(self):
        self.g.remove_edges_from(list(self.g.edges(0,keys=True)))
        p=plan_on_graph(self.g,self.grid,self.shelters,[])
        self.assertEqual(p['summary']['assigned'],0)
        self.assertEqual(p['summary']['unassigned'],120)
if __name__=='__main__':unittest.main()
