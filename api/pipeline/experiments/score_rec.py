import pickle, numpy as np, pandas as pd
P=pickle.load(open("natv2_primary_sales_units.pkl","rb")); bt=P["bt"]; rec=pickle.load(open("rec_bt.pkl","rb"))
m=bt.merge(rec,on=["ser","t","h"],how="inner")
m=m[m.y.notna()&m.valid]
d=pd.read_csv("sales_v2.csv",low_memory=False,parse_dates=["week_beginning"]); d=d[d.reporting_level=="National"]
d["series"]=d.depot_code+"|"+d.product_code
col={4:"sales_forecast_1m_ahead_units",9:"sales_forecast_2m_ahead_units",13:"sales_forecast_3m_ahead_units"}
w=lambda a,f:1-np.abs(f-a).sum()/a.sum()
rows=[]
for h,lab in [(4,"M1 (4wk)"),(9,"M2 (9wk)"),(13,"M3 (13wk)")]:
    x=m[m.h==h].copy()
    sf=d[["series","week_beginning",col[h]]].rename(columns={col[h]:"sales"})
    x["week_beginning"]=x.week
    x=x.merge(sf,left_on=["series","week_beginning"],right_on=["series","week_beginning"],how="left")
    x["ens"]=0.5*x.gbm+0.3*x.ets.fillna(x.gbm)+0.2*x.snaive
    x["ens_rec"]=0.5*x.rec+0.3*x.ets.fillna(x.rec)+0.2*x.snaive
    r={"horizon":lab,"n":len(x)}
    for k in ["gbm","rec","snaive","ens","ens_rec","sales"]:
        z=x[x[k].notna()]; r[k+"_skuwk"]=round(w(z.y,z[k]),4)
    # total per week
    g=x.groupby("week")[["y","gbm","rec","ens","ens_rec","sales"]].sum(min_count=1)
    for k in ["gbm","rec","ens","ens_rec","sales"]: r[k+"_totwk"]=round(w(g.y,g[k]),4)
    # 4-week-month proxy: category-free total over 4-week blocks
    g["blk"]=np.arange(len(g))//4; b=g.groupby("blk").sum()
    for k in ["gbm","rec","ens","ens_rec","sales"]: r[k+"_tot4w"]=round(w(b.y,b[k]),4)
    rows.append(r)
R=pd.DataFrame(rows).set_index("horizon").T
pd.set_option("display.width",200); print(R)
