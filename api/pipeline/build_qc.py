import pickle, json, numpy as np, pandas as pd
d=pd.read_csv("eveready_mock_data_v2_ext.csv",low_memory=False,parse_dates=["week_beginning"])
nat=d[d.reporting_level=="National"].copy()
P=pickle.load(open("natv2_primary_sales_units.pkl","rb")); bt,fut,meta,weeks,cols=P["bt"],P["fut"],P["meta"],P["weeks"],P["cols"]
nW=len(weeks); W=(0.2,0.3,0.5)
def ens(r):
    p=[(W[0],r.snaive),(W[1],r.get("ets",np.nan)),(W[2],r.gbm)]; p=[(a,b) for a,b in p if pd.notna(b)]; tw=sum(a for a,_ in p); return sum(a*b for a,b in p)/tw if tw>0 else np.nan
skus=sorted(nat[nat.quick_commerce_ordered_units.notna()].product_code.unique())
ser_of={s:cols.index("ALL|"+s) for s in skus}
pv=lambda c: nat.pivot(index="week_beginning",columns="product_code",values=c).reindex(index=weeks)
A=pv("primary_sales_units"); OR=pv("quick_commerce_ordered_units"); DL=pv("quick_commerce_delivered_units"); SO=pv("quick_commerce_partner_sell_out_units")
ST=pv("quick_commerce_partner_stock_units"); LN=pv("quick_commerce_order_lines"); OT=pv("quick_commerce_lines_on_time"); IF=pv("quick_commerce_lines_in_full"); OF=pv("quick_commerce_lines_otif")
RT=pv("quick_commerce_returned_units"); PX=pv("average_selling_price_inr")
i0=int(np.where(OR[skus[0]].notna().values)[0][0]); print("QC starts idx",i0,weeks[i0].date())
T0=max(109,i0+8)   # first week with a demand forecast AND a full 8-week QC window
# demand forecasts (ensemble) at h=4 for backtest, h=1..13 for future
b4=bt[bt.h==4].copy(); b4["m"]=b4.apply(ens,axis=1)
D4=np.full((nW,len(cols)),np.nan); D4[b4["T"].values.astype(int),b4.ser.values.astype(int)]=b4.m.values
fu=fut[fut.h<=13].copy(); fu["m"]=fu.apply(ens,axis=1)
DF=np.full((13,len(cols)),np.nan); DF[fu.h.values.astype(int)-1,fu.ser.values.astype(int)]=fu.m.values
def share(t,s):
    a=SO[s].values[t-7:t+1]; b=A[s].values[t-7:t+1]; return np.nansum(a)/np.nansum(b)
need=np.full((nW,len(skus)),np.nan)
for j,s in enumerate(skus):
    for T in range(T0,nW):
        if not np.isnan(D4[T,ser_of[s]]): need[T,j]=share(T-4,s)*D4[T,ser_of[s]]
needF=np.full((13,len(skus)),np.nan)
for j,s in enumerate(skus):
    sh=share(nW-1,s)
    for k in range(13): needF[k,j]=sh*DF[k,ser_of[s]]
so=np.array([SO[s].values for s in skus]).T; ordr=np.array([OR[s].values for s in skus]).T
# diagnostics
m=~np.isnan(need)&~np.isnan(so)
wape=lambda a,f: np.abs(f-a).sum()/a.sum()
naive=np.full_like(so,np.nan)
for T in range(T0,nW): naive[T]=np.nanmean(so[T-7:T-3],0)   # mean of weeks T-7..T-4 (known at origin T-4)
print("WAPE SKU-week: need_fc",round(wape(so[m],need[m]),3),"naive4w",round(wape(so[m],naive[m]),3),"requested",round(wape(so[m],ordr[m]),3))
tw=np.nansum(np.where(m,so,0),1); tf=np.nansum(np.where(m,need,0),1); tn=np.nansum(np.where(m,naive,0),1); to=np.nansum(np.where(m,ordr,0),1)
ok=tw>0; print("WAPE total-week: need_fc",round(wape(tw[ok],tf[ok]),3),"naive",round(wape(tw[ok],tn[ok]),3),"requested",round(wape(tw[ok],to[ok]),3))
# counterfactual simulation over backtest window
COV=(1,2,3); out={"weeks":[w.strftime("%Y-%m-%d") for w in weeks[i0:]]+[ (weeks[-1]+pd.Timedelta(days=7*k)).strftime("%Y-%m-%d") for k in range(1,14)],"hist":nW-i0,"first_need":T0-i0,"skus":{}}
nm=meta.drop_duplicates("sku").set_index("sku")
tot={c:dict(ship=0,lost=0,sold=0) for c in COV}
for j,s in enumerate(skus):
    price=float(PX[s].iloc[-26:].mean())
    rec={}; cfs={}; lost={}; fwd={}; fst={}
    for c in COV:
        r_=np.full(nW,np.nan); st_=np.full(nW,np.nan); lo_=np.full(nW,np.nan); stock=c*need[T0,j]
        for T in range(T0,nW):
            target=need[T,j]*(1+c); r=max(0.0,target-stock); avail=stock+r; sold=min(so[T,j],avail); stock=avail-sold
            r_[T]=r; st_[T]=stock; lo_[T]=so[T,j]-sold
        rec[c]=r_; cfs[c]=st_; lost[c]=lo_
        # forward from actual stock
        stock=float(ST[s].iloc[-1]); f_=np.zeros(13); fs_=np.zeros(13)
        for k in range(13):
            target=needF[k,j]*(1+c); r=max(0.0,target-stock); avail=stock+r; sold=min(needF[k,j],avail); stock=avail-sold; f_[k]=r; fs_[k]=stock
        fwd[c]=f_; fst[c]=fs_
    rnd=lambda a:[None if np.isnan(v) else int(round(v)) for v in a]
    node={"name":str(nm.loc[s,"name"]),"cat":str(nm.loc[s,"category"]),"price":round(price,2),
      "ordered":rnd(OR[s].values[i0:]),"delivered":rnd(DL[s].values[i0:]),"sellout":rnd(SO[s].values[i0:]),"stock":rnd(ST[s].values[i0:]),"returned":rnd(RT[s].values[i0:]),
      "lines":rnd(LN[s].values[i0:]),"ontime":rnd(OT[s].values[i0:]),"infull":rnd(IF[s].values[i0:]),"otif":rnd(OF[s].values[i0:]),
      "need":rnd(np.concatenate([need[i0:,j],needF[:,j]])),
      "rec":{str(c):rnd(np.concatenate([rec[c][i0:],fwd[c]])) for c in COV},
      "cfstock":{str(c):rnd(np.concatenate([cfs[c][i0:],fst[c]])) for c in COV},
      "lost":{str(c):rnd(lost[c][i0:]) for c in COV}}
    out["skus"][s]=node
json.dump(out,open("qc.json","w"),separators=(",",":"))
print("bytes",len(json.dumps(out)))
for c in COV:
    sh=sum(np.nansum(np.array(out["skus"][s]["rec"][str(c)][:nW-i0],dtype=float)) for s in skus); dl=sum(np.nansum(np.array([v or 0 for v in out["skus"][s]["delivered"][T0-i0:]],float)) for s in skus)
    ls=sum(np.nansum(np.array([v or 0 for v in out["skus"][s]["lost"][str(c)]],float)) for s in skus); sold=sum(np.nansum(so[T0:,j]) for j in range(len(skus)))
    print("cover",c,"shipped cf",round(sh/1e6,1),"M vs delivered actual",round(dl/1e6,1),"M; lost share",round(ls/sold,3))
