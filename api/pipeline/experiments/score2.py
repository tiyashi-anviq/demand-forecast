import pickle, numpy as np, pandas as pd
P=pickle.load(open("nat_primary_sales_units.pkl","rb")); bt=P["bt"].copy()
d=pd.read_csv("sales.csv",low_memory=False,parse_dates=["week_beginning"]); d=d[d.reporting_level=="National"]
d["series"]=d.depot_code+"|"+d.product_code
ex=d.set_index(["week_beginning","series"])[["sales_forecast_3m_ahead_units","sales_forecast_2m_ahead_units","sales_forecast_1m_ahead_units","budget_units"]]
bt=bt.join(ex,on=["week","series"])
bt["exist"]=np.select([bt.h==13,bt.h==9,bt.h==4],[bt.sales_forecast_3m_ahead_units,bt.sales_forecast_2m_ahead_units,bt.sales_forecast_1m_ahead_units],np.nan)
bt=bt[bt.valid&bt.y.notna()].dropna(subset=["ets","exist"])
bt["ens"]=.2*bt.snaive+.3*bt.ets+.5*bt.gbm
A=lambda f,y:1-np.abs(f-y).sum()/y.sum()
for h in (13,9,4):
    s=bt[bt.h==h]
    print(h,"exist",round(A(s.exist,s.y),3),"ens",round(A(s.ens,s.y),3),
      {w:round(A(w*s.exist+(1-w)*s.ens,s.y),3) for w in (.3,.5,.7)})
    # monthly sku accuracy
    s=s.assign(m=s.week.dt.to_period("M")); g=s.groupby(["series","m"])[["y","exist","ens"]].sum()
    print("   monthly sku-level exist",round(A(g.exist,g.y),3),"ens",round(A(g.ens,g.y),3),"blend.5",round(A(.5*g.exist+.5*g.ens,g.y),3))
    # by sku-type
    s2=s.assign(e1=(s.exist-s.y).abs(),e2=(s.ens-s.y).abs()).groupby("series")[["e1","e2","y"]].sum()
    s2["a_ex"]=1-s2.e1/s2.y; s2["a_ens"]=1-s2.e2/s2.y
    if h==13: print(s2[["a_ex","a_ens","y"]].round(2).sort_values("y",ascending=False).to_string())
# noise check: how well does a centred 5-wk moving average of actual explain the actual (noise floor)
d2=d.pivot(index="week_beginning",columns="series",values="primary_sales_units")
ma=d2.rolling(5,center=True).mean(); m=(d2-ma).abs().sum().sum()/d2.sum().sum()
print("oracle-smooth WAPE",round(m,3))
# is existing forecast ~ actual * noise? ratio dispersion
r=(d.sales_forecast_1m_ahead_units/d.primary_sales_units.replace(0,np.nan))
print(r.describe())
