import argparse, json, os
from agent import Agent, Store, GeminiPlanner, demo_planner

p=argparse.ArgumentParser(description='WorkforceAI - synthetic workforce training agent')
p.add_argument('--db',default='workforce.db'); p.add_argument('--session',default='demo')
p.add_argument('--live',action='store_true',help='Call Gemini with synthetic data only')
p.add_argument('--ask',help='One question; omit for interactive session')
p.add_argument('--approve',metavar='REQUEST_ID'); p.add_argument('--reject',metavar='REQUEST_ID')
a=p.parse_args(); store=Store(a.db)
if a.approve and a.reject: p.error('Choose one decision.')
if a.approve or a.reject:
    try: print(json.dumps(store.decide(a.session,a.approve or a.reject,bool(a.approve)),indent=2))
    except ValueError as e: p.error(str(e))
    raise SystemExit
if a.live and not os.getenv('GEMINI_API_KEY'): p.error('Set GEMINI_API_KEY before enabling --live.')
agent=Agent(store,GeminiPlanner() if a.live else demo_planner,'gemini-live' if a.live else 'offline-demo (rule-based, not AI inference)')
def ask(q): print(json.dumps(agent.run(q,a.session),indent=2))
if a.ask: ask(a.ask)
else:
    print('WorkforceAI | synthetic data only | type exit to quit')
    while True:
        try: q=input('\nYou: ').strip()
        except (EOFError,KeyboardInterrupt): break
        if q.lower() in ('exit','quit'): break
        ask(q)
