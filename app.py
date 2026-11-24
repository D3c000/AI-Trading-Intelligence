import streamlit as st
import json
from pathlib import Path
import pandas as pd
st.set_page_config(page_title='AI Trading Intelligence',page_icon='📈')
st.title('AI Trading Intelligence')
st.caption('Seven-agent research simulator | USD | No real orders')
f=Path('state.json')
if not f.exists(): st.info('Run the Trading Simulator GitHub Action first.'); st.stop()
s=json.loads(f.read_text())
st.caption('Last scan (UTC): '+s['updated'])
a,b,c=st.columns(3); a.metric('Equity',f"${s['equity']:.2f}",f"${s['equity']-50:+.2f}"); b.metric('Cash',f"${s['cash']:.2f}"); c.metric('Positions',len(s['positions']))
if s['halted'] or s['daily_halt']: st.warning('Risk shutdown active; new positions disabled.')
st.caption('Indicative prices, simulated costs, and potentially stale marks. Not actual broker fills.')
page=st.radio('View',['Overview','Agent reports','Trade history'],horizontal=True)
if page=='Overview':
    st.line_chart(pd.DataFrame(s['history']).set_index('time')['equity'])
    st.subheader('Open positions'); st.dataframe(pd.DataFrame.from_dict(s['positions'],orient='index'))
elif page=='Agent reports':
    for r in s['signals']:
        with st.expander(r['symbol']+' — '+r['decision']):
            st.write('Master score:',r['score'],'| Fresh:',r['fresh'])
            for name,a in r['agents'].items(): st.write(name+': '+a['detail'], 'Vote:',a['vote'])
    if s['errors']: st.write('Unavailable data',s['errors'])
else: st.dataframe(pd.DataFrame(s['trades']))
