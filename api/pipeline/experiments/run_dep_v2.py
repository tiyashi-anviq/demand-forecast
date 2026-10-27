import time, pickle, sys
import pandas as pd, numpy as np
import engine as en
ext = en.load_ext()
d,y,price,sch,meta = en.load_panel(path="sales_v2.csv", level="Kolkata depot", target="primary_sales_units")
t0=time.time()
allrows, bt = en.run(y,price,sch,meta,ext,use_ets=False,first_test_origin=104,retrain_every=4,eval_h=(13,))
print("backtest secs", round(time.time()-t0), flush=True)
fut,_ = en.final_forecast(allrows,y,price,sch,meta,ext,use_ets=False,seeds=(0,1))
print("final secs", round(time.time()-t0), flush=True)
pickle.dump(dict(bt=bt,fut=fut,meta=meta,weeks=y.index,cols=list(y.columns)), open("depv2_primary_sales_units.pkl","wb"))
print("DONE",flush=True)
