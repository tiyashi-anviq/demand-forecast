import pandas as pd, numpy as np, itertools, json
from scipy.optimize import nnls
T=pd.read_pickle('launch_table.pkl').reset_index(drop=True)
F=['dist_launch','price_tier','pack_format','launch_situation','technology','season']
tier={'Value':0,'Mid':1,'Premium':2}; seas=['Winter','Summer','Monsoon','Festive']
ld=np.log(T.dist_launch); rng=ld.max()-ld.min()
def fdist(a,b):
    return np.array([abs(np.log(a.dist_launch)-np.log(b.dist_launch))/rng,
      abs(tier[a.price_tier]-tier[b.price_tier])/2,
      float(a.pack_format!=b.pack_format), float(a.launch_situation!=b.launch_situation), float(a.technology!=b.technology),
      min((seas.index(a.season)-seas.index(b.season))%4,(seas.index(b.season)-seas.index(a.season))%4)/2])
n=len(T); D=np.zeros((n,n,6))
for i in range(n):
    for j in range(n):
        if i!=j: D[i,j]=fdist(T.loc[i],T.loc[j])
z=lambda x:(x-x.mean())/x.std()
Y1=z(T.out1).values; Y2=z(T.out2).values
def fit(excl=None):
    idx=[i for i in range(n) if i!=excl]; X=[];y=[]
    for i,j in itertools.combinations(idx,2):
        X.append(D[i,j]); y.append(abs(Y1[i]-Y1[j])+abs(Y2[i]-Y2[j]))
    w,_=nnls(np.array(X),np.array(y)); return w/w.sum() if w.sum()>0 else np.ones(6)/6
w=fit(); print('learned weights',dict(zip(F,w.round(3))))
eq=np.ones(6)/6
def loo(wfun):
    err1=[];err2=[]
    for i in range(n):
        w_=wfun(i); dist=np.array([D[i,j]@w_ if j!=i else 9 for j in range(n)]); top=np.argsort(dist)[:3]
        err1.append(abs(T.out1[i]-T.out1[top].mean())); err2.append(abs(T.out2[i]-T.out2[top].mean()))
    return np.mean(err1),np.mean(err2)
base=(np.mean([abs(T.out1[i]-T.out1.drop(i).mean()) for i in range(n)]),np.mean([abs(T.out2[i]-T.out2.drop(i).mean()) for i in range(n)]))
print('LOO MAE (log velocity idx, log ramp) | global-mean',np.round(base,3),'| equal weights',np.round(loo(lambda i:eq),3),'| learned (refit w/o i)',np.round(loo(lambda i:fit(i)),3))
# alternative: out1 only
def fit1(excl=None):
    idx=[i for i in range(n) if i!=excl]; X=[];y=[]
    for i,j in itertools.combinations(idx,2): X.append(D[i,j]); y.append(abs(Y1[i]-Y1[j]))
    w,_=nnls(np.array(X),np.array(y)); return w/w.sum()
print('out1-only weights',dict(zip(F,fit1().round(3))))
# stability: weights from bootstrap
bs=[]
rs=np.random.default_rng(0)
for b in range(40):
    s=rs.choice(n,n,replace=True); X=[];y=[]
    for i,j in itertools.combinations(range(n),2):
        pass
    sel=sorted(set(s)); X=[];y=[]
    for i,j in itertools.combinations(sel,2): X.append(D[i,j]); y.append(abs(Y1[i]-Y1[j])+abs(Y2[i]-Y2[j]))
    ww,_=nnls(np.array(X),np.array(y)); bs.append(ww/ww.sum())
print('bootstrap weight sd',dict(zip(F,np.array(bs).std(0).round(3))))
np.save('D.npy',D); json.dump(dict(zip(F,w.tolist())),open('weights.json','w'))
# Ultima queries
def q(dist,price_ratio,pack,tech,season='Festive',sit='New product from existing brand',w_=w):
    a=pd.Series(dict(dist_launch=dist,price_tier='Premium' if price_ratio>1.15 else 'Value' if price_ratio<0.85 else 'Mid',pack_format=pack,launch_situation=sit,technology=tech,season=season))
    dd=np.array([fdist(a,T.loc[j])@w_ for j in range(n)]); top=np.argsort(dd)[:3]
    return a.price_tier,[(T['product'][j][:55],T.category[j][:18],round(1-dd[j],3)) for j in top]
print('PLUG-IN combo', q(6,105/100,'Bundle','Standard'))
print('PORTABLE combo', q(6,299/100,'Bundle','Advanced'))
print('PLUG-IN equal-w', q(6,1.05,'Bundle','Standard',w_=eq))
print('PORTABLE equal-w', q(6,2.99,'Bundle','Advanced',w_=eq))
