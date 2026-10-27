import pandas as pd, numpy as np
from scipy.optimize import nnls
pd.set_option('display.width',250,'display.max_columns',40,'display.max_rows',100,'display.max_colwidth',45)
c=pd.read_csv('comp.csv',parse_dates=['week_beginning','listed_from']); c=c[c.market=='NATIONAL'].copy()
ext=pd.read_csv('ext.csv',parse_dates=['week_beginning']).set_index('week_beginning')
W0=c.week_beginning.min()
c['grp']=np.where(c.category.str.startswith('Mosquito'), c.category+'|'+c.pack_description.fillna('').str.split(' ').str[0].str.replace(':',''), c.category)
c['vel']=c.retail_sales_units/c.weighted_distribution_pct.replace(0,np.nan)
# established products = listed at window start
est=c[c.listed_from.isna() | (c.listed_from<=W0)]
# category-group median price & velocity by week among established products
med_px=est.groupby(['grp','week_beginning']).average_price_inr.median().rename('px_med')
med_vel=est.groupby(['grp','week_beginning']).vel.median().rename('vel_med')
c=c.join(med_px,on=['grp','week_beginning']).join(med_vel,on=['grp','week_beginning'])
c['vi']=c.vel/c.vel_med
def season(w):
    r=ext.loc[w] if w in ext.index else None
    fest=False
    if r is not None:
        s=str(r.festival_sell_in_period) if 'festival_sell_in_period' in r else ''
    ex=pd.read_csv('ext.csv',parse_dates=['week_beginning']).set_index('week_beginning').festival_sell_in_period
    return None
exs=pd.read_csv('ext.csv',parse_dates=['week_beginning']).set_index('week_beginning').festival_sell_in_period.fillna('')
def season(w):
    if exs.get(w,'')!='' and ('Durga' in exs.get(w,'') or 'Diwali' in exs.get(w,'')): return 'Festive'
    m=w.month
    if m in (12,1,2,11): return 'Winter'
    if m in (3,4,5): return 'Summer'
    if m in (6,7,8): return 'Monsoon'
    return 'Festive'
rows=[]
for (cat,prod),g in c[c.listed_from>W0].groupby(['category','product_name']):
    g=g.sort_values('week_beginning'); L=g.listed_from.iloc[0]; g=g[g.week_beginning>=L]
    first=g.iloc[0]
    k=g.reset_index(drop=True)
    if len(k)<26: continue
    u=k.retail_sales_units.values; vi=k.vi.values; d=k.weighted_distribution_pct.values
    rows.append(dict(category=cat,brand=first.brand,product=prod,launch=L,dist_launch=first.weighted_distribution_pct,
      price=first.average_price_inr,price_ratio=first.average_price_inr/first.px_med,pack_format=first.pack_format,
      launch_situation=first.launch_type,technology=first.technology_level,season=season(L),
      vi13=np.nanmean(vi[:13]),vi26=np.nanmean(vi[13:26]),units13=u[:13].sum(),units26=u[13:26].sum(),weeks=len(k)))
T=pd.DataFrame(rows)
T['price_tier']=pd.cut(T.price_ratio,[0,0.85,1.15,99],labels=['Value','Mid','Premium'])
T['out1']=np.log(T.vi13.clip(lower=1e-3)); T['out2']=np.log((T.vi26/T.vi13).clip(lower=1e-3))
print(len(T)); print(T[['category','product','dist_launch','price_ratio','price_tier','pack_format','launch_situation','technology','season','vi13','vi26']].round(2).to_string())
print(T.price_tier.value_counts().to_dict(), T.season.value_counts().to_dict())
T.to_pickle('launch_table.pkl')
