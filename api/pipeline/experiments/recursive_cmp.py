import pickle, time, numpy as np, pandas as pd
import engine as en
ext = en.load_ext()
d,y,price,sch,meta = en.load_panel(path="sales_v2.csv", level="National", target="primary_sales_units")
n=len(y); S=y.shape[1]
print("weeks",n,y.index[0].date(),y.index[-1].date(),"series",S)
tr_rows = en.build_rows(y,price,sch,meta,ext,origins=range(40,n-1),horizons=[1])
def step_pred(mdl, Y, P, SC, wk_index, t):
    yy=pd.DataFrame(Y,index=wk_index,columns=y.columns); pp=pd.DataFrame(P,index=wk_index,columns=y.columns); ss=pd.DataFrame(SC,index=wk_index,columns=y.columns)
    r=en.build_rows(yy,pp,ss,meta,ext,origins=[t],horizons=[1],with_target=False)
    return r, en.pred_gbm(mdl,r)
H=13; out=[]
t0=time.time()
for blk in range(104,n-1,4):
    mdl=en.fit_gbm(tr_rows[tr_rows["T"]<=blk],0)
    for t in range(blk,min(blk+4,n-1)):
        if t+4>n-1: continue
        Y=y.values[:t+1].copy(); P=price.values[:t+1].copy(); SC=sch.values[:t+1].copy()
        idx=list(y.index[:t+1])
        for k in range(1,H+1):
            if t+k>n-1: break
            idx.append(y.index[t+k])
            Y=np.vstack([Y,np.full((1,S),np.nan)]); P=np.vstack([P,P[-1:]]); SC=np.vstack([SC,SC[-1:]])
            # features at origin t+k-1 (last row of history = previous prediction)
            r,p=step_pred(mdl,Y[:-1],P[:-1],SC[:-1],pd.DatetimeIndex(idx[:-1]),t+k-1)
            # rows are by series order
            p=np.where(r.valid.values,p,np.nan)
            # fill invalid with last value
            p=np.where(np.isnan(p),np.nan_to_num(Y[-2]),p)
            Y[-1]=p
            if k in (4,9,13):
                out.append(pd.DataFrame({"ser":np.arange(S),"t":t,"h":k,"rec":p}))
    print("block",y.index[blk].date(),round(time.time()-t0),flush=True)
rec=pd.concat(out,ignore_index=True)
pickle.dump(rec,open("rec_bt.pkl","wb"))
