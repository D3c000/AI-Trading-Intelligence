import json, math, datetime as dt
from pathlib import Path
import yfinance as yf

FILE=Path('state.json')
SYMBOLS=['NVDA','TSLA','AAPL','AMD','SNDK','MSFT','BTC-USD','ETH-USD','SOL-USD','XRP-USD','DOGE-USD','AVAX-USD']
COST=.005 # illustrative 0.5% each side, not a broker quote

def analyze(symbol):
    h=yf.Ticker(symbol).history(period='3mo',interval='1h',auto_adjust=False)
    c=h.Close.dropna()
    if len(c)<50: raise ValueError('Insufficient history')
    stamp=c.index[-1].to_pydatetime().astimezone(dt.timezone.utc)
    now=dt.datetime.now(dt.timezone.utc)
    p=float(c.iloc[-1]); fast=float(c.tail(10).mean()); slow=float(c.tail(40).mean())
    momentum=float(c.iloc[-1]/c.iloc[-12]-1); vol=float(c.pct_change().tail(40).std())
    if not all(math.isfinite(x) for x in [p,fast,slow,momentum,vol]) or p<=0: raise ValueError('Invalid quote')
    fresh=0 <= (now-stamp).total_seconds() <= 7200
    # Stock quotes must also be from the current regular NY session.
    if not symbol.endswith('-USD'):
        from zoneinfo import ZoneInfo
        ny=now.astimezone(ZoneInfo('America/New_York'))
        fresh=fresh and ny.weekday()<5 and (9,30)<=(ny.hour,ny.minute)<(16,0) and stamp.astimezone(ny.tzinfo).date()==ny.date()
    agents={
       'Technical':{'vote':1 if p>fast>slow else -1 if p<fast<slow else 0,'detail':f'10/40 bar averages: {fast:.2f}/{slow:.2f}'},
       'Momentum':{'vote':1 if momentum>.015 else -1 if momentum<-.015 else 0,'detail':f'11-bar return {momentum:.2%}'},
       'Quant':{'vote':1 if momentum>max(.02,2*vol) else -1 if momentum< -max(.02,2*vol) else 0,'detail':'Momentum relative to recent volatility; heuristic, not a calibrated probability'},
       'Risk':{'vote':0,'detail':f'Hourly volatility {vol:.2%}','pass':vol<.035},
       'Execution':{'vote':0,'detail':'Recent indicative bar; assumed 0.5% fee/slippage each side','pass':fresh},
       'News':{'vote':0,'detail':'No verified news feed configured; abstains'} }
    score=sum(a['vote'] for a in agents.values()); eligible=agents['Risk']['pass'] and fresh
    return {'symbol':symbol,'price':p,'timestamp':stamp.isoformat(),'agents':agents,'score':score,'fresh':fresh,'eligible':eligible,'decision':'BUY CANDIDATE' if eligible and score==3 else 'SELL CANDIDATE' if fresh and score<=-2 else 'HOLD'}

def run():
    now=dt.datetime.now(dt.timezone.utc); day=now.date().isoformat()
    s=json.loads(FILE.read_text()) if FILE.exists() else {'cash':50.,'positions':{},'trades':[],'history':[],'day':day,'day_start':50.,'halted':False,'daily_halt':False,'marks':{}}
    rows=[]; errors={}
    for sym in SYMBOLS:
        try: rows.append(analyze(sym))
        except Exception as e: errors[sym]=str(e)[:180]
    lookup={r['symbol']:r for r in rows}
    for r in rows:
        if r['fresh']: s['marks'][r['symbol']]=r['price']
    def equity(): return s['cash']+sum(v['qty']*s['marks'].get(k,v['price'])*(1-COST) for k,v in s['positions'].items())
    if s['day']!=day: s.update(day=day,day_start=equity(),daily_halt=False)
    if equity()<=45: s['halted']=True
    if equity()<=s['day_start']-1: s['daily_halt']=True
    for sym,v in list(s['positions'].items()):
        r=lookup.get(sym)
        if not r or not r['fresh'] or r['timestamp']<=v['bar']: continue
        p=r['price']
        if p<=v['price']*.97 or p>=v['price']*1.06 or r['score']<=-2 or s['halted'] or s['daily_halt']:
            proceeds=v['qty']*p*(1-COST); s['cash']+=proceeds; del s['positions'][sym]
            s['trades'].append({'time':now.isoformat(),'symbol':sym,'side':'SELL','price':p,'amount':proceeds,'pnl':proceeds-v['cost']})
    if equity()<=45: s['halted']=True
    if equity()<=s['day_start']-1: s['daily_halt']=True
    if not s['halted'] and not s['daily_halt'] and all(k in lookup and lookup[k]['fresh'] for k in s['positions']):
        for r in sorted(rows,key=lambda a:a['score'],reverse=True):
            sym=r['symbol']; p=r['price']
            if r['decision']!='BUY CANDIDATE' or sym in s['positions'] or len(s['positions'])>=2 or s['cash']<40: continue
            if any(t['symbol']==sym and t['time'][:10]==day for t in s['trades']): continue
            s['cash']-=10; s['positions'][sym]={'qty':10*(1-COST)/p,'price':p,'cost':10,'bar':r['timestamp']}
            s['trades'].append({'time':now.isoformat(),'symbol':sym,'side':'BUY','price':p,'amount':10,'pnl':None})
    s['equity']=equity(); s['history'].append({'time':now.isoformat(),'equity':s['equity']}); s['history']=s['history'][-2000:]; s['updated']=now.isoformat(); s['signals']=rows; s['errors']=errors
    FILE.write_text(json.dumps(s,indent=2,allow_nan=False))
if __name__=='__main__': run()
