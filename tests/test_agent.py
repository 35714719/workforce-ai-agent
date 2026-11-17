import unittest
from agent import Store, Agent, retrieve, GeminiPlanner

class AgentTests(unittest.TestCase):
    def setUp(self): self.s=Store(':memory:'); self.a=Agent(self.s)
    def tearDown(self): self.s.db.close()
    def test_retrieval(self): self.assertIn('POL-01',[p['id'] for p in retrieve('training approval budget')])
    def test_unknown_policy(self): self.assertEqual(retrieve('zebra pineapple'),[])
    def test_gaps_and_memory(self):
        self.a.run('What skills does E001 need?','a')
        r=self.a.run('Recommend training','a'); self.assertIn('Python fundamentals',r['answer']); self.assertIn('POL-01',r['policy_sources'])
        self.assertIn('Which',self.a.run('Recommend training','b')['answer'])
    def test_request_and_decision(self):
        q='Propose Python training for E001'; r=self.a.run(q,'a'); rid=r['pending_requests'][0]
        self.assertEqual(self.a.run(q,'a')['pending_requests'],[rid])
        with self.assertRaises(ValueError): self.s.decide('b',rid,True)
        self.assertEqual(self.s.decide('a',rid,True)['status'],'approved')
        with self.assertRaises(ValueError): self.s.decide('a',rid,False)
    def test_rejection(self):
        rid=self.a.run('Draft SQL training for E002')['pending_requests'][0]; self.assertEqual(self.s.decide('demo',rid,False)['status'],'rejected')
    def test_unknown_employee(self): self.assertEqual(self.a.run('Skills of E999')['status'],'needs_input')
    def test_block_employment(self): self.assertEqual(self.a.run('Fire E001')['status'],'blocked')
    def test_unallowlisted_tool(self):
        a=Agent(self.s,lambda *x:{'tool':'approve','args':{}}); self.assertEqual(a.run('Hello')['status'],'error')
    def test_proposal_without_evidence(self):
        a=Agent(self.s,lambda *x:{'tool':'propose_training','args':{'employee':'E001','skill':'python'}})
        self.assertEqual(a.run('Propose Python training for E001')['status'],'error'); self.assertEqual(self.s.db.execute('SELECT count(*) FROM requests').fetchone()[0],0)
    def test_invalid_course(self): self.assertEqual(self.a.run('Propose SQL training for E001')['status'],'error')
    def test_model_cannot_change_employee(self):
        a=Agent(self.s,lambda *x:{'tool':'skills_gap','args':{'employee':'E002'}}); self.assertEqual(a.run('Skills E001')['status'],'error')
    def test_scripted_model_loop(self):
        steps=iter([{'tool':'search_policy','args':{'query':'training approval'}},{'tool':'skills_gap','args':{'employee':'E001'}},{'tool':'finish','args':{'answer':'Python and ticketing; see POL-01.'}}])
        a=Agent(self.s,lambda *x:next(steps),'mock-model'); r=a.run('Skills E001'); self.assertEqual(r['status'],'complete'); self.assertEqual(len(r['tool_trace']),2)
    def test_negative_proposal(self):
        r=self.a.run("Do not propose Python training for E001"); self.assertEqual(r["pending_requests"],[])
    def test_no_implicit_proposal(self):
        steps=iter([{'tool':'skills_gap','args':{'employee':'E001'}},{'tool':'search_policy','args':{'query':'training approval budget'}},{'tool':'propose_training','args':{'employee':'E001','skill':'python'}}])
        self.assertEqual(Agent(self.s,lambda *a:next(steps)).run('Tell me about Python for E001')['status'],'error')

if __name__=='__main__': unittest.main()
