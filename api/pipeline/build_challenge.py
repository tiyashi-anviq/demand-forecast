import pickle, json, numpy as np, pandas as pd
cuts,runs,cols=pickle.load(open("vint_runs.pkl","rb"))
d=pd.read_csv("eveready_mock_data_v2_ext.csv",low_memory=False,parse_dates=["week_beginning"])
w0=pd.Timestamp("2022-09-26"); weeks=pd.date_range(w0,d.week_beginning.max(),freq="7D"); n=len(weeks)
share=lambda i,m: float((pd.date_range(w0+pd.Timedelta(days=7*i),periods=7).strftime("%Y-%m")==m).mean())   # pro-rata share of week i in month m
months=[f"2026-{m:02d}" for m in range(1,10)]
mi={m:[i for i in range(n) if share(i,m)>0] for m in months}
mw={m:np.array([share(i,m) for i in mi[m]]) for m in months}
def cutlab(m,k): return (pd.Timestamp(m+"-01")-pd.DateOffset(months=k)).strftime("%Y-%m")
out={"months":[{"m":m,"label":pd.Timestamp(m+"-01").strftime("%b %y")} for m in months],"rows":{}}
for lvl,lab in (("National","National"),("Kolkata depot","Kolkata depots")):
    x=d[d.reporting_level==lvl].copy(); x["series"]=x.depot_code+"|"+x.product_code
    ser=sorted(x.series.unique())
    pv=lambda c: x.pivot(index="week_beginning",columns="series",values=c).reindex(index=weeks,columns=ser)
    A=pv("primary_sales_units").values; B=pv("budget_units").values; ST=pv("closing_stock_units").values; SS=pv("safety_stock_units").values
    F={k:pv(f"sales_forecast_{k}m_ahead_units").values for k in (3,2,1)}
    meta=x.drop_duplicates("series").set_index("series").loc[ser]
    R=x.pivot(index="week_beginning",columns="series",values="forecast_override_reason").reindex(index=weeks,columns=ser)
    for m in months:
        wi=mi[m]
        for k in (3,2,1):
            cl=cutlab(m,k); t,M=runs[cl]
            rows=[]
            for j,s in enumerate(ser):
                if np.isnan(F[k][wi,j]).all(): continue
                f=np.nansum(F[k][wi,j]*mw[m])
                b=np.nansum(B[wi,j]*mw[m]); ly=np.nansum(A[[i-52 for i in wi],j]*mw[m]); a=np.nansum(A[wi,j]*mw[m])
                mv=None
                if lvl=="National" and s in cols:
                    c=cols.index(s); mv=float(np.nansum([M[i-t-1][c]*w_ for i,w_ in zip(wi,mw[m])]))
                st=ST[t,j]; ss=SS[t,j]
                rs=R.iloc[wi,j].dropna(); reason=rs.mode().iloc[0] if len(rs) else ""
                dep,sku=s.split("|")
                rows.append([sku,str(meta.loc[s,"product_name"]),str(meta.loc[s,"product_category"]),dep,int(round(f)),int(round(b)),int(round(ly)),int(round(a)),None if mv is None else int(round(mv)),None if np.isnan(st) else int(round(st)),None if np.isnan(ss) else int(round(ss)),reason,round(float(mw[m].sum()),1)])
            out["rows"][f"{lab}|{m}|{k}"]=rows
json.dump(out,open("challenge.json","w"),separators=(",",":"))
print(len(json.dumps(out)))
print(out["rows"]["National|2026-09|1"][:3])
print({k:len(v) for k,v in list(out["rows"].items())[:2]}, len(out["rows"]["Kolkata depots|2026-09|1"]))
