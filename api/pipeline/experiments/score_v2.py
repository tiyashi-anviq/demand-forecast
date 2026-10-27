import pickle, numpy as np, pandas as pd
P=pickle.load(open("natv2_primary_sales_units.pkl","rb")); bt=P["bt"].copy()
d=pd.read_csv("sales_v2.csv",low_memory=False,parse_dates=["week_beginning"]); d=d[d.reporting_level=="National"]
d["series"]=d.depot_code+"|"+d.product_code
ex=d.set_index(["week_beginning","series"])[["sales_forecast_3m_ahead_units","sales_forecast_2m_ahead_units","sales_forecast_1m_ahead_units"]]
bt=bt.join(ex,on=["week","series"])
bt["exist"]=np.select([bt.h==13,bt.h==9,bt.h==4],[bt.sales_forecast_3m_ahead_units,bt.sales_forecast_2m_ahead_units,bt.sales_forecast_1m_ahead_units],np.nan)
bt=bt[bt.valid&bt.y.notna()].dropna(subset=["ets","exist"])
bt["ens"]=.2*bt.snaive+.3*bt.ets+.5*bt.gbm
A=lambda f,y:1-np.abs(f-y).sum()/y.sum()
cat=P["meta"].set_index("series").category; bt["cat_"]=bt.series.map(cat); bt["mon"]=bt.week.dt.to_period("M")
for h in (13,9,4):
    s=bt[bt.h==h]
    r={m:round(A(s[m],s.y),3) for m in ["exist","snaive","ets","gbm","ens"]}
    r["blend50"]=round(A(.5*s.ens+.5*s.exist,s.y),3)
    g=s.groupby(["cat_","mon"])[["y","exist","ens"]].sum(); g["bl"]=.5*g.ens+.5*g.exist
    gs=s.groupby(["series","mon"])[["y","exist","ens"]].sum(); gs["bl"]=.5*gs.ens+.5*gs.exist
    print(h,r,"| sku-month ex/ens/bl",[round(A(gs[c],gs.y),3) for c in ["exist","ens","bl"]],"| cat-month ex/ens/bl",[round(A(g[c],g.y),3) for c in ["exist","ens","bl"]])
