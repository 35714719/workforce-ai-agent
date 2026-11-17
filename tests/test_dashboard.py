import json, os, re, tempfile, threading, unittest, urllib.request, urllib.error
from unittest.mock import patch
from pathlib import Path
from dashboard import make_server
from agent import demo_planner

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=make_server(0,Path(self.temp.name)/'test.db',lambda:demo_planner)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        html=urllib.request.urlopen(self.base).read().decode()
        self.token=re.search(r'name="workforce-token" content="([^"]+)"',html)[1]
    def tearDown(self):
        self.server.shutdown();self.thread.join();self.server.server_close();self.temp.cleanup()
    def call(self,path,data=None,token=True):
        headers={'X-Workforce-Token':self.token} if token else {}
        if data is not None: headers['Content-Type']='application/json'
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req) as r: return r.status,json.load(r)
        except urllib.error.HTTPError as e: return e.code,json.load(e)
    def ask(self,q,mode='offline'): return self.call('/api/ask',{'question':q,'mode':mode})
    def test_state_and_static(self):
        code,state=self.call('/api/state');self.assertEqual(code,200);self.assertEqual(len(state['employees']),2);self.assertNotIn('key',state)
        for name in ['/style.css','/app.js']:
            with urllib.request.urlopen(self.base+name) as r:self.assertGreater(len(r.read()),100)
    def test_token_required(self): self.assertEqual(self.call('/api/state',token=False)[0],403)
    def test_recommendation_and_memory(self):
        _,out=self.ask('Recommend training for E001');self.assertEqual(out['result']['status'],'complete');self.assertEqual(out['state']['remembered_employee'],'E001');self.assertIn('Python fundamentals',out['result']['answer'])
    def test_policy_with_memory(self):
        self.ask('Recommend training for E001');_,out=self.ask('What is the training approval policy? (Selected employee: E001)');self.assertEqual([t['tool'] for t in out['result']['tool_trace']],['search_policy'])
    def test_approve_and_prevent_repeat(self):
        _,out=self.ask('Propose Python training for E001');rid=out['result']['pending_requests'][0]
        self.assertEqual(self.call('/api/decision',{'id':rid,'approved':'yes'})[0],400)
        _,decision=self.call('/api/decision',{'id':rid,'approved':True});self.assertEqual(decision['result']['status'],'approved');self.assertEqual(self.call('/api/decision',{'id':rid,'approved':False})[0],409)
    def test_reject(self):
        _,out=self.ask('Propose SQL training for E002');rid=out['result']['pending_requests'][0];_,d=self.call('/api/decision',{'id':rid,'approved':False});self.assertEqual(d['result']['status'],'rejected')
    def test_mock_live_path(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'test-only'}):
            _,out=self.ask('Recommend training for E001','live');self.assertEqual(out['result']['mode'],'gemini-live');self.assertEqual(out['result']['status'],'complete');self.assertNotIn('test-only',json.dumps(out))
    def test_missing_key(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':''}): self.assertEqual(self.ask('Recommend training for E001','live')[0],400)
    def test_bad_input(self): self.assertEqual(self.call('/api/ask',{'question':'','mode':'offline'})[0],400)
