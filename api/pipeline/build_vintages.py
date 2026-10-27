import json, time, sys, os, pickle, numpy as np, pandas as pd
import engine as en, clean
LVL=sys.argv[1] if len(sys.argv)>1 else "National"; NAT=LVL=="National"; TAG="nat" if NAT else "dep"
W=(0.2,0.3,0.5) if NAT else (0.3,0.0,0.7)  # snaive, ets, gbm
ext=en.load_ext()
d,y,price,sch,meta=en.load_panel(path="eveready_mock_data_v2_ext.csv",level=LVL,target="primary_sales_units")
y=clean.clean_panel(y,meta)
n=len(y); S=y.shape[1]; cols=list(y.columns); w0=y.index[0]
wk=lambda i: w0+pd.Timedelta(days=7*i)
mon=lambda i: (wk(i)+pd.Timedelta(days=3)).strftime("%Y-%m")
REAGG=os.environ.get("REAGG")=="1"   # REAGG=1: reuse the saved runs and only redo the monthly roll-up
allrows=None if REAGG else en.build_rows(y,price,sch,meta,ext,origins=range(40,n-1),horizons=list(range(1,en.H_MAX+1)))
# cutoffs: last week fully ended on/before each month end
def cutoff_for(month_end):
    ok=[i for i in range(n) if wk(i)+pd.Timedelta(days=6)<=month_end]; return ok[-1]
mends=pd.date_range("2025-09-30","2026-09-30",freq="ME")
cuts={m.strftime("%Y-%m"):cutoff_for(m) for m in mends}
cuts["latest"]=n-1
runs={}; raws={}; t0=time.time()
STACK=NAT and os.environ.get('STACK','1')=='1'   # learn-from-mistakes layer (stacker.py), national only
FESTFX=NAT and os.environ.get('FESTFX','1')=='1'   # festival-by-category mix (fest_effects.py): national only (no gain on the monthly depot vintages, tested)
if FESTFX: os.environ['FE_LEVEL']=LVL; import fest_effects
if STACK:
    import stacker; TF=stacker.train_frame(pickle.load(open('natclean_bt.pkl','rb'))['bt'])
for lab,t in ([] if REAGG else cuts.items()):
    cfile=f"ck_vint_{TAG}_{lab}.pkl"
    if os.path.exists(cfile):                 # finished before a restart: reuse
        z=pickle.load(open(cfile,"rb")); runs[lab]=z[:2]; raws[lab]=z[2] if len(z)>2 else z[1]; print(lab,"resumed",flush=True); continue
    tr=allrows[allrows["T"]<=t]
    fut=en.build_rows(y,price,sch,meta,ext,origins=[t],horizons=list(range(1,en.H_MAX+1)),with_target=False)
    fut["gbm"]=0.0
    for sd in (0,1):
        fut["gbm"]+=en.pred_gbm(en.fit_gbm(tr,sd),fut)/2
    if NAT:
        E=en.ets_forecast_cached(y.values,t)
        fut["ets"]=[E[s,h-1] for s,h in zip(fut.ser,fut.h)]
        en.ets_off_in_fest(fut)
    else:
        fut["ets"]=np.nan
    def ens(r):
        p=[(W[0],r.snaive),(W[1],r.ets),(W[2],r.gbm)]; p=[(a,b) for a,b in p if pd.notna(b)]; tw=sum(a for a,_ in p); return sum(a*b for a,b in p)/tw
    fut["m"]=fut.apply(ens,axis=1)
    M0=np.full((en.H_MAX,S),np.nan); M0[fut.h.values-1,fut.ser.values]=fut.m.values
    if STACK:
        _mult=stacker.multiplier(fut,stacker.fit(TF,t))
        if FESTFX: _m2,_isf=fest_effects.apply(fut,t); _mult[_isf]=1.0   # festival weeks: no error-learning nudge; festival-by-category mix instead
        fut["m"]=fut.m.values*_mult
        if FESTFX: fut.loc[_isf,"m"]=_m2[_isf]
    elif FESTFX:
        _m2,_isf=fest_effects.apply(fut,t); fut.loc[_isf,"m"]=_m2[_isf]
    M=np.full((en.H_MAX,S),np.nan); M[fut.h.values-1,fut.ser.values]=fut.m.values
    runs[lab]=(t,M); raws[lab]=M0; pickle.dump((t,M,M0),open(cfile+'.tmp','wb')); os.replace(cfile+'.tmp',cfile); print(lab,wk(t).date(),round(time.time()-t0),flush=True)
PK="vint_runs.pkl" if NAT else "vint_runs_dep.pkl"
if REAGG: cuts,runs,cols=pickle.load(open(PK,"rb"))
else:
    pickle.dump((cuts,runs,cols),open(PK,"wb"))
    if NAT: pickle.dump((cuts,raws,cols),open("vint_runs_raw.pkl","wb"))
# actuals, sales-team, price, keys
dd=pd.read_csv("eveready_mock_data_v2_ext.csv",low_memory=False,parse_dates=["week_beginning"]); dd=dd[dd.reporting_level==LVL].copy(); dd["series"]=dd.depot_code+"|"+dd.product_code
pv=lambda c: dd.pivot(index="week_beginning",columns="series",values=c).reindex(index=y.index,columns=cols)
A=pv("primary_sales_units").values; PX=pv("average_selling_price_inr"); price_s=PX.iloc[-26:].mean().fillna(PX.mean()).values
SF={3:pv("sales_forecast_3m_ahead_units").values,2:pv("sales_forecast_2m_ahead_units").values,1:pv("sales_forecast_1m_ahead_units").values}
mp=meta.set_index("series").loc[cols]
keys={"ALL":np.arange(S)}
for c in sorted(mp.category.unique()): keys["cat:"+c]=np.where(mp.category.values==c)[0]
sk={}
for i in range(S): sk.setdefault(mp.sku.iloc[i],[]).append(i)
for k,v in sk.items(): keys["sku:"+k]=np.array(v)
months=sorted({mon(i) for i in range(104-0,n+en.H_MAX)})
months=[m for m in months if "2025-12"<=m<="2027-03"]
def share(i,m):   # pro-rata: fraction of week i's 7 days (Mon-Sun) that fall in month m
    return float((pd.date_range(wk(i),periods=7).strftime("%Y-%m")==m).mean())
mi={m:[i for i in range(n+en.H_MAX) if share(i,m)>0] for m in months}
mw={m:np.array([share(i,m) for i in mi[m]]) for m in months}
def mlabel(m): return pd.Timestamp(m+"-01").strftime("%b %y")
def madd(k):  # month index offset
    return 0
def cutlab(m,k):  # cutoff label = month-end k months before target month m
    return (pd.Timestamp(m+"-01")-pd.DateOffset(months=k)).strftime("%Y-%m")
out={"months":[],"nodes":{}}
meta_m=[]
for m in months:
    idxs=mi[m]; allact=all(i<n for i in idxs)
    meta_m.append({"m":m,"label":mlabel(m),"weeks":round(float(mw[m].sum()),1),"actualWeeks":round(float(mw[m][[i<n for i in idxs]].sum()),1),"complete":allact,
                   "ok":{str(k):(cutlab(m,k) in cuts and all(1<=i-runs[cutlab(m,k)][0]<=en.H_MAX for i in idxs)) for k in (3,2,1)},
                   "latest":all(i<=runs["latest"][0] or i-runs["latest"][0]<=en.H_MAX for i in idxs) and not all(i<=runs["latest"][0] for i in idxs)})
out["months"]=meta_m
def unit_total(idx,vals,mult):
    x=vals[:,idx]*(price_s[idx] if mult else 1); return None if np.isnan(x).all() else float(np.nansum(x))
for key,idx in keys.items():
    node={"u":{},"v":{}}
    for mult,u in ((False,"u"),(True,"v")):
        r={"actual":[],"m3":[],"m2":[],"m1":[],"s3":[],"s2":[],"s1":[],"latest":[]}
        for mm in meta_m:
            m=mm["m"]; wi=mi[m]
            # actual (only fully actual months; else None)
            if mm["complete"]:
                a=A[wi][:,idx]*(price_s[idx] if mult else 1) if False else None
            av=None
            if mm["complete"]:
                x=A[wi][:,idx]*(price_s[idx] if mult else 1)*mw[m][:,None]; av=float(np.nansum(x))
            r["actual"].append(av)
            for k in (3,2,1):
                if mm["ok"][str(k)]:
                    t,M=runs[cutlab(m,k)]; x=np.stack([M[i-t-1] for i in wi])[:,idx]*(price_s[idx] if mult else 1)*mw[m][:,None]; r["m%d"%k].append(float(np.nansum(x)))
                else: r["m%d"%k].append(None)
                if mm["complete"]:
                    x=SF[k][wi][:,idx]*(price_s[idx] if mult else 1)*mw[m][:,None]; r["s%d"%k].append(float(np.nansum(x)))
                else: r["s%d"%k].append(None)
            if mm["latest"]:
                t,M=runs["latest"]; x=np.stack([M[i-t-1] if i>t else A[i] for i in wi])[:,idx]*(price_s[idx] if mult else 1)*mw[m][:,None]
                r["latest"].append(float(np.nansum(x)) if not np.isnan(x).all() else None)
            else: r["latest"].append(None)
        node[u]={kk:[None if v is None else int(round(v)) for v in vv] for kk,vv in r.items()}
    out["nodes"][key]=node
json.dump(out,open(f"vintages_{TAG}.json","w"),separators=(",",":"))
print("bytes",len(json.dumps(out)))
for mm in meta_m: print(mm["m"],mm["complete"],mm["ok"],mm["latest"])
a=out["nodes"]["ALL"]["u"]
for i,mm in enumerate(meta_m): print(mm["m"],[a[k][i] and round(a[k][i]/1e7,2) for k in ("actual","m3","m2","m1","s3","s2","s1","latest")])
