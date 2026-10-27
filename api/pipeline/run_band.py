import sys, time, pickle
import engine as en, clean
lvl=sys.argv[1]; ets=lvl=="National"
ext=en.load_ext()
d,y,price,sch,meta=en.load_panel(path="eveready_mock_data_v2_ext.csv",level=lvl,target="primary_sales_units")
y_raw=y; y=clean.clean_panel(y,meta)
t0=time.time()
allrows,bt=en.run(y,price,sch,meta,ext,use_ets=ets,first_test_origin=105,retrain_every=4,eval_h=(13,19,26),verbose=False)
print(lvl,"secs",round(time.time()-t0),len(bt),flush=True)
bt["y"]=y_raw.values[bt["T"].values.astype(int),bt.ser.values.astype(int)]
pickle.dump(dict(bt=bt,cols=list(y.columns),weeks=y.index),open("band_"+("nat" if ets else "dep")+".pkl","wb"))
