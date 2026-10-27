import pickle,numpy as np,pandas as pd
W=(0.2,0.3,0.5)
def ens(b):
    p=W[0]*b.snaive+W[1]*b.ets.fillna(b.snaive)*(b.ets.notna())+W[2]*b.gbm
    p=np.where(b.ets.notna(),W[0]*b.snaive+W[1]*b.ets+W[2]*b.gbm,(0.3*b.snaive+0.7*b.gbm)); return p
o=pickle.load(open("natv2_primary_sales_units.pkl","rb"))["bt"]; n=pickle.load(open("natclean_primary_sales_units.pkl","rb"))["bt"]
meta=pickle.load(open("natclean_primary_sales_units.pkl","rb"))["meta"].set_index("series")
def prep(b):
    b=b.copy(); b["m"]=ens(b); b["sku"]=b.series.map(meta.sku); b["wk"]=b.week; return b
o,n=prep(o),prep(n)
wape=lambda b:np.abs(b.m-b.y).sum()/b.y.sum()
for h in (4,9,13):
    a,c=o[o.h==h],n[n.h==h]
    print("h",h,"SKU-week WAPE old",round(wape(a),4),"new",round(wape(c),4))
    for nm,msk in (("torch",lambda b:b.sku.isin(["rch","hyb","cvt"])),("non-torch",lambda b:~b.sku.isin(["rch","hyb","cvt"]))):
        print("   ",nm,round(wape(a[msk(a)]),4),round(wape(c[msk(c)]),4))
    # 2026 torch May-Aug targets
    for nm,lo,hi in (("2026 Jun-Aug torch","2026-06-01","2026-08-31"),("2025 shock wks torch","2025-06-09","2025-08-11")):
        f=lambda b:b[(b.week>=lo)&(b.week<=hi)&b.sku.isin(["rch","hyb","cvt"])]
        if len(f(a)): print("   ",nm,"WAPE",round(wape(f(a)),3),round(wape(f(c)),3),"bias old",round(f(a).m.sum()/f(a).y.sum()-1,3),"new",round(f(c).m.sum()/f(c).y.sum()-1,3))
