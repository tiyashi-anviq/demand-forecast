import sys,time,pickle,numpy as np
import engine as en, clean
lvl=sys.argv[1]; nat=lvl=="National"
ext=en.load_ext()
d,y,price,sch,meta=en.load_panel(path="eveready_mock_data_v2_ext.csv",level=lvl,target="primary_sales_units")
yc=clean.clean_panel(y,meta)
print(lvl,"cells changed",int((yc.values!=y.values).sum()),flush=True)
t0=time.time()
eh=(4,9,13) if nat else (13,)
allrows,bt=en.run(yc,price,sch,meta,ext,use_ets=nat,first_test_origin=105,retrain_every=4,eval_h=eh,verbose=False)
bt["y"]=y.values[bt["T"].values.astype(int),bt.ser.values.astype(int)]   # score against raw actuals
print("bt",round(time.time()-t0),flush=True)
pickle.dump(dict(bt=bt,meta=meta,weeks=y.index,cols=list(y.columns)),open(("nat" if nat else "dep")+"clean_bt.pkl","wb"))
fut,_=en.final_forecast(allrows,yc,price,sch,meta,ext,use_ets=nat,seeds=(0,1,2) if nat else (0,1))
pickle.dump(dict(bt=bt,fut=fut,meta=meta,weeks=y.index,cols=list(y.columns)),open(("nat" if nat else "dep")+"clean_primary_sales_units.pkl","wb"))
print("DONE",round(time.time()-t0),flush=True)
