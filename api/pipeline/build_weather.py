import json, numpy as np, pandas as pd
import engine as en, clean
ext=en.load_ext()
d,y,price,sch,meta=en.load_panel(path="eveready_mock_data_v2_ext.csv",level="National",target="primary_sales_units")
y_raw=y; y=clean.clean_panel(y,meta)
n=len(y); S=y.shape[1]; cols=list(y.columns); w0=y.index[0]
raw=pd.read_csv("ext_ext.csv",parse_dates=["week_beginning"]).set_index("week_beginning")
H=16; PRE=8
allrows=en.build_rows(y,price,sch,meta,ext,origins=range(40,n-1),horizons=list(range(1,en.H_MAX+1)))
mp=meta.set_index("series").loc[cols]
keys={"ALL":np.arange(S)}
for c in sorted(mp.category.unique()): keys["cat:"+c]=np.where(mp.category.values==c)[0]
sk={}
for i in range(S): sk.setdefault(mp.sku.iloc[i],[]).append(i)
for k,v in sk.items(): keys["sku:"+k]=np.array(v)
out={"seasons":{}}
for lab,cut in (("2024","2024-05-27"),("2025","2025-05-26"),("2026","2026-05-25")):
    t=int(np.where(y.index==pd.Timestamp(cut))[0][0])
    M=np.full((H,S),np.nan)
    if True:
        tr=allrows[allrows["T"]<=t]
        fut=en.build_rows(y,price,sch,meta,ext,origins=[t],horizons=list(range(1,H+1)),with_target=False)
        fut["gbm"]=0.0
        for sd in (0,1): fut["gbm"]+=en.pred_gbm(en.fit_gbm(tr,sd),fut)/2
        fut["m"]=0.7*fut.gbm+0.3*fut.snaive.fillna(fut.gbm)
        M[fut.h.values-1,fut.ser.values]=fut.m.values
    wi=list(range(t-PRE+1,t+H+1)); wk=[y.index[i] if i<n else None for i in wi]
    A=y_raw.values
    nodes={}
    for k,idx in keys.items():
        act=[float(np.nansum(A[i,idx])) for i in wi]
        fc=[None if (i<=t) else float(np.nansum(M[i-t-1,idx])) for i in wi]
        nodes[k]={"a":[int(round(v)) for v in act],"f":[None if v is None else int(round(v)) for v in fc]}
    rain=[float(raw.loc[w,"rainfall_mm"]) for w in wk]; exr=[(None if pd.isna(raw.loc[w,"expected_rainfall_mm"]) else float(raw.loc[w,"expected_rainfall_mm"])) for w in wk]
    out["seasons"][lab]={"weeks":[w.strftime("%Y-%m-%d") for w in wk],"cut":t-wi[0]+1,"rain":rain,"exp":exr,"nodes":nodes}
    print(lab,"cut",cut,"weeks",wk[0].date(),wk[-1].date())
json.dump(out,open("weather.json","w"),separators=(",",":"))
print(len(json.dumps(out)))
for lab in out["seasons"]:
    s=out["seasons"][lab]
    pass
    for key in ("ALL","sku:cvt","sku:rch"):
        a=np.array(s["nodes"][key]["a"],float); f=np.array([np.nan if v is None else v for v in s["nodes"][key]["f"]])
        print(lab,key,[round(x,2) for x in (a/f-1)[s["cut"]:]])
