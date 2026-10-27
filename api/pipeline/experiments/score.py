import pickle, numpy as np, pandas as pd, sys
target=sys.argv[1] if len(sys.argv)>1 else "primary_sales_units"
P=pickle.load(open(f"nat_{target}.pkl","rb")); bt=P["bt"].copy()
d=pd.read_csv("sales.csv",low_memory=False,parse_dates=["week_beginning"]); d=d[d.reporting_level=="National"]
d["series"]=d.depot_code+"|"+d.product_code
ex=d.set_index(["week_beginning","series"])[["sales_forecast_3m_ahead_units","sales_forecast_2m_ahead_units","sales_forecast_1m_ahead_units","consensus_forecast_1m_ahead_units"]]
bt["wk"]=bt.week
bt=bt.join(ex,on=["wk","series"])
bt["exist"]=np.select([bt.h==13,bt.h==9,bt.h==4],[bt.sales_forecast_3m_ahead_units,bt.sales_forecast_2m_ahead_units,bt.sales_forecast_1m_ahead_units],np.nan)
bt=bt[bt.valid & bt.y.notna()]
def acc(f,y):
    e=f-y; return 1-np.abs(e).sum()/y.sum(), np.clip(e,0,None).sum()/y.sum(), np.clip(-e,0,None).sum()/y.sum(), f.sum()/y.sum()
for h in (13,9,4):
    s=bt[bt.h==h].dropna(subset=["ets","gbm","snaive","exist"])
    print(f"h={h} n={len(s)} weeks {s.wk.min().date()}..{s.wk.max().date()}")
    for m in ["exist","snaive","ets","gbm"]:
        print("  ",m,[round(x,3) for x in acc(s[m].values,s.y.values)])
    for w in [(0,.5,.5),(.2,.3,.5),(.1,.2,.7),(0,0,1)]:
        f=w[0]*s.snaive+w[1]*s.ets+w[2]*s.gbm
        print("   ens",w,[round(x,3) for x in acc(f.values,s.y.values)])
