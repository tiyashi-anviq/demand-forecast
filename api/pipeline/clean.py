import os
import numpy as np, pandas as pd
SHOCK_SKUS={"rch","hyb","cvt"}
WIN=("2025-06-09","2025-08-11")   # "Delayed monsoon" event weeks + recovery spill-over
def clean_panel(y, meta):
    """Replace shock-window weeks of affected SKUs with last-year level x recent growth (computed on pre-shock weeks)."""
    yc=y.copy(); idx=y.index
    if os.environ.get("CLEAN","0")!="1": return yc   # the monsoon shock below exists only in our own earlier build; off for the real v2 data
    w0=idx.get_loc(pd.Timestamp(WIN[0])); w1=idx.get_loc(pd.Timestamp(WIN[1]))
    sku=meta.set_index("series").sku
    log=[]
    for c in y.columns:
        if sku[c] not in SHOCK_SKUS: continue
        v=y[c].values.astype(float)
        g=np.nansum(v[w0-8:w0])/max(np.nansum(v[w0-60:w0-52]),1)
        for t in range(w0,w1+1):
            yc.iloc[t,yc.columns.get_loc(c)]=round(v[t-52]*g)
    return yc
