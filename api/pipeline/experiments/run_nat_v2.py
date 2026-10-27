import time, pickle, sys
import pandas as pd, numpy as np
import engine as en
target = sys.argv[1] if len(sys.argv)>1 else "primary_sales_units"
ext = en.load_ext()
d,y,price,sch,meta = en.load_panel(path="sales_v2.csv", level="National", target=target)
t0=time.time()
allrows, bt = en.run(y,price,sch,meta,ext,use_ets=True,first_test_origin=104,retrain_every=4)
print("backtest secs", round(time.time()-t0))
fut,_ = en.final_forecast(allrows,y,price,sch,meta,ext,use_ets=True)
print("final secs", round(time.time()-t0))
pickle.dump(dict(bt=bt,fut=fut,meta=meta,weeks=y.index,cols=list(y.columns)), open(f"natv2_{target}.pkl","wb"))
