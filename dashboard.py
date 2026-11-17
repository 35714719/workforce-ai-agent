"""Local-only browser UI for the existing WorkforceAI prototype."""
import argparse, json, os, secrets, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from agent import Agent, Store, GeminiPlanner, demo_planner, EMPLOYEES, POLICIES, COURSES

ROOT=Path(__file__).resolve().parent
SESSION='dashboard'

def snapshot(store):
    requests=[dict(r) for r in store.db.execute('SELECT * FROM requests WHERE session=? ORDER BY rowid DESC',(SESSION,))]
    return {'employees':list(EMPLOYEES.values()),'policies':POLICIES,
            'courses':{k:{'name':v[0],'price':v[1]} for k,v in COURSES.items()},
            'requests':requests,'remembered_employee':store.recall(SESSION),
            'live_available':bool(os.getenv('GEMINI_API_KEY')),'model':os.getenv('GEMINI_MODEL') or 'code default'}

def make_server(port=8501, db=None, planner_factory=GeminiPlanner):
    db=str(db or ROOT/'dashboard.db')
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def send(self, status, data, mime='application/json; charset=utf-8'):
            if isinstance(data,dict): data=json.dumps(data).encode()
            if isinstance(data,str): data=data.encode()
            self.send_response(status); self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers(); self.wfile.write(data)
        def trusted_host(self):
            return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
        def do_GET(self):
            if not self.trusted_host(): return self.send(403,{'error':'Use the local dashboard URL.'})
            route=urlsplit(self.path).path
            if route=='/': return self.send(200,(ROOT/'web/index.html').read_text().replace('__TOKEN__',token),'text/html; charset=utf-8')
            files={'/style.css':('style.css','text/css'),'/app.js':('app.js','application/javascript')}
            if route in files:
                file,mime=files[route]; return self.send(200,(ROOT/'web'/file).read_bytes(),mime)
            if route=='/api/state':
                if self.headers.get('X-Workforce-Token')!=token: return self.send(403,{'error':'Reload the dashboard.'})
                store=Store(db)
                try: return self.send(200,snapshot(store))
                finally: store.db.close()
            return self.send(404,{'error':'Not found'})
        def do_POST(self):
            if not self.trusted_host() or self.headers.get('X-Workforce-Token')!=token: return self.send(403,{'error':'Reload the local dashboard.'})
            if self.headers.get('Origin') not in (None,f'http://127.0.0.1:{self.server.server_port}'): return self.send(403,{'error':'Invalid origin.'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=12000: raise ValueError()
                data=json.loads(self.rfile.read(size))
                if not isinstance(data,dict): raise ValueError()
            except (ValueError,UnicodeError): return self.send(400,{'error':'Invalid request.'})
            store=Store(db)
            try:
                route=urlsplit(self.path).path
                if route=='/api/ask':
                    q=data.get('question'); mode=data.get('mode')
                    if not isinstance(q,str) or not q.strip() or len(q)>2000 or mode not in ('offline','live'): return self.send(400,{'error':'Enter a question of 1–2000 characters and select a valid mode.'})
                    if mode=='live' and not os.getenv('GEMINI_API_KEY'): return self.send(400,{'error':'Set GEMINI_API_KEY in CMD and restart the dashboard.'})
                    agent=Agent(store,planner_factory() if mode=='live' else demo_planner,'gemini-live' if mode=='live' else 'offline-demo (rule-based, not AI inference)')
                    result=agent.run(q,SESSION)
                    failure=None
                    if result['status']=='error':
                        row=store.db.execute("SELECT detail FROM audit WHERE session=? AND event='failure' ORDER BY rowid DESC LIMIT 1",(SESSION,)).fetchone()
                        if row: failure=json.loads(row['detail']).get('type')
                    return self.send(200,{'result':result,'state':snapshot(store),'failure_type':failure})
                if route=='/api/decision':
                    rid=data.get('id'); approved=data.get('approved')
                    if not isinstance(rid,str) or type(approved) is not bool: return self.send(400,{'error':'Explicit human decision required.'})
                    try: result=store.decide(SESSION,rid,approved)
                    except ValueError: return self.send(409,{'error':'Request is no longer pending in this dashboard.'})
                    return self.send(200,{'result':result,'state':snapshot(store)})
                return self.send(404,{'error':'Not found'})
            finally: store.db.close()
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--port',type=int,default=8501); p.add_argument('--no-browser',action='store_true'); a=p.parse_args()
    try: server=make_server(a.port)
    except OSError: p.error('Port unavailable. Try python dashboard.py --port 8502')
    url=f'http://127.0.0.1:{server.server_port}'
    print(f'WorkforceAI dashboard: {url}\nSynthetic data only. Press Ctrl+C to stop.',flush=True)
    if not a.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=='__main__': main()
