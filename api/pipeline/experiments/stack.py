import pickle, numpy as np, pandas as pd, engine as en, lightgbm as lgb
ext=en.load_ext(); d,y,price,sch,meta=en.load_panel()
P=pickle.load(open("nat_primary_sales_units.pkl","rb")); bt=P["bt"]
dd=d.copy(); ex=dd.set_index(["week_beginning","series"])[["sales_forecast_3m_ahead_units","sales_forecast_2m_ahead_units","sales_forecast_1m_ahead_units","budget_units"]]
rows=en.build_rows(y,price,sch,meta,ext,origins=range(40,len(y)-1),horizons=[4,9,13])
rows["series"]=y.columns[rows.ser]; rows=rows.join(ex,on=["week","series"])
rows["exist"]=np.select([rows.h==13,rows.h==9,rows.h==4],[rows.sales_forecast_3m_ahead_units,rows.sales_forecast_2m_ahead_units,rows.sales_forecast_1m_ahead_units],np.nan)
rows["lex"]=np.log1p(rows.exist)-rows.lbase; rows["lbud"]=np.log1p(rows.budget_units)-rows.lbase
rows["lsn"]=np.log1p(rows.snaive)-rows.lbase
F=en.FEATS+["lex","lbud","lsn"]
out=[]
for t0 in range(104,len(y)-1,4):
    tr=rows[(rows["T"]<=t0)&rows.valid&rows.y.notna()]
    m=lgb.LGBMRegressor(n_estimators=300,learning_rate=0.04,num_leaves=16,min_child_samples=40,subsample=.8,subsample_freq=1,colsample_bytree=.8,reg_lambda=3,verbose=-1,n_jobs=2,objective="huber",alpha=.6)
    m.fit(tr[F],np.log1p(tr.y)-tr.lbase,categorical_feature=["cat","dep","sku"])
    te=rows[(rows.t>=t0)&(rows.t<t0+4)&rows.valid&rows.y.notna()].copy()
    te["stk"]=np.clip(np.expm1(m.predict(te[F])+te.lbase),0,None); out.append(te)
s=pd.concat(out)
s=s.drop(columns=["snaive"]).merge(bt[["series","t","h","snaive","ets","gbm"]],on=["series","t","h"],how="left")
s["ens"]=.2*s.snaive+.3*s.ets+.5*s.gbm
A=lambda f,y:1-np.abs(f-y).sum()/y.sum()
for h in (13,9,4):
    q=s[s.h==h].dropna(subset=["ens","exist"])
    r=[round(A(q[c],q.y),3) for c in ["exist","ens","stk"]]
    r.append(round(A(.5*q.stk+.5*q.exist,q.y),3)); r.append(round(A((q.stk+q.exist+q.ens)/3,q.y),3))
    e=q.stk-q.y
    print(h,"exist/ens/stk/stk+exist/avg3",r,"over",round(e.clip(lower=0).sum()/q.y.sum(),3),"under",round((-e).clip(lower=0).sum()/q.y.sum(),3))
s.to_pickle("stack_bt.pkl")
