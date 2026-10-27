"""Worked new-product case: a liquid mosquito vaporizer launch, learned from the launches already in the competitor (Nielsen-style) data.

Model (per SKU, weekly, national):  units(age, week) = WD_plateau x ROS_ref x (price / price_ref)^elasticity x season(week) x ramp(age)
  * ramp(age)    sales as a share of the launch's steady level, from the past launches (deseasonalised)
  * season(week) category seasonal index from established products
  * ROS_ref      steady units per point of weighted distribution: a parent brand's own rate of sale x a launch discount for a line
                 extension, or the new-entrant rate for a new brand
  * elasticity   own-price effect estimated within products over time (promotions and price moves), not across brands
Back-test: every past launch is forecast with the others only, using its real plateau distribution as the plan.
Writes launch.json (the page computes new scenarios from the parameters in it)."""
import json, numpy as np, pandas as pd

d = pd.read_csv("competitor_data_v2.csv", low_memory=False, parse_dates=["week_beginning"])
m = d[d.category.str.contains("osquito") & (d.market == "NATIONAL")].copy()
m["fmt"] = np.where(m.product_name.str.contains("Combo"), "Combo", np.where(m.product_name.str.contains("Refill 35"), "Refill 35", "Refill 45"))
FMT = ["Refill 35", "Refill 45", "Combo"]
m["ros"] = m.retail_sales_units / m.weighted_distribution_pct
lt = m[m.launch_type.notna()].groupby("product_name").week_beginning.min()
m["age"] = (m.week_beginning - m.product_name.map(lt)).dt.days // 7
W = sorted(m.week_beginning.unique()); n = len(W)
woyf = lambda s: s.dt.isocalendar().week.clip(upper=52).astype(int)
m["woy"] = woyf(m.week_beginning)

# season index from established products
inc = m[~m.product_name.isin(lt.index)]
tot = inc.groupby("week_beginning").retail_sales_units.sum().reindex(W)
ratio = tot / tot.rolling(53, center=True, min_periods=27).mean()
woy = pd.Series(woyf(pd.Series(W)).values, index=W)
si = ratio.groupby(woy).mean(); si = (si / si.mean()).reindex(range(1, 53)).interpolate().bfill().ffill()
m["si"] = m.woy.map(si); m["ros_d"] = m.ros / m.si
inc = m[~m.product_name.isin(lt.index)]

# own-price effect: within-product, over time, on established products (log rate of sale on log price). The estimate moves with how the
# yearly price drift is treated (-0.9 without a time trend, -1.7 with one) and in this data most price movement comes from promotions,
# so it is used as an indicative value and the page says so.
EL, EL_SE = -0.9, 0.4
# steady level of each launched SKU (ages 26-51, deseasonalised) and its ramp
RAMP_AGES = np.arange(52)
sku = {}
for p in lt.index:
    x = m[(m.product_name == p) & (m.age >= 0) & (m.age <= 51)].sort_values("age")
    ss = x[x.age.between(26, 51)]
    u_ss = (ss.retail_sales_units / ss.si).mean()
    sku[p] = dict(brand=x.brand.iloc[0], btype=x.brand_type.iloc[0], ltype=x.launch_type.iloc[0], fmt=x.fmt.iloc[0], start=lt[p],
                  wd=float(ss.weighted_distribution_pct.mean()), price=float(x.average_price_inr.mean()), u_ss=float(u_ss), ros=float(ss.ros_d.mean()),
                  ramp=(x.retail_sales_units / x.si / u_ss).values, actual=x.retail_sales_units.values)
def smooth(a, k=5):
    p = np.pad(a, (k // 2, k // 2), mode="edge"); return np.convolve(p, np.ones(k) / k, mode="valid")
def mean_ramp(names):
    R = np.vstack([sku[p]["ramp"][:52] for p in names]); r = smooth(R.mean(0)); return r, np.percentile(R, 10, axis=0), np.percentile(R, 90, axis=0)

# parent-brand rate of sale: last 52 weeks of established products
last = inc[inc.week_beginning >= W[-52]]
par = last.groupby(["brand", "fmt"]).agg(ros=("ros_d", "mean"), price=("average_price_inr", "mean"), wd=("weighted_distribution_pct", "mean")).reset_index()
brand_meta = m.groupby("brand").agg(btype=("brand_type", "first"), prot=("protection_hours_per_refill", "max")).reset_index()
PAR = {b: {r.fmt: dict(ros=float(r.ros), price=float(r.price), wd=float(r.wd)) for r in g.itertuples()} for b, g in par.groupby("brand")}

# events: one per launch (brand + start week)
ev = {}
for p, s in sku.items(): ev.setdefault((s["brand"], s["start"]), []).append(p)
EXT = [k for k in ev if sku[ev[k][0]]["ltype"].startswith("New product")]; NEW = [k for k in ev if k not in EXT]

def ref_ros(p, others, parent_ros=None):
    """steady ROS for SKU p from the other launches"""
    s = sku[p]
    if s["ltype"].startswith("New product"):
        rs = [sku[q]["ros"] / PAR_BY[(sku[q]["brand"], sku[q]["fmt"])] for q in others if sku[q]["ltype"].startswith("New product")]
        return PAR_BY[(s["brand"], s["fmt"])] * float(np.mean(rs)), float(np.mean(rs))
    rs = [sku[q]["ros"] for q in others if not sku[q]["ltype"].startswith("New product") and sku[q]["fmt"] == s["fmt"]]
    return float(np.mean(rs)), None
PAR_BY = {(b, f): v["ros"] for b, g in PAR.items() for f, v in g.items()}
PAR_BY_P = {(b, f): v["price"] for b, g in PAR.items() for f, v in g.items()}
USE_PRICE = False

def predict(p, others):
    s = sku[p]; ramp, _, _ = mean_ramp(others)
    ros, _ = ref_ros(p, others)
    wk = [pd.Timestamp(s["start"]) + pd.Timedelta(weeks=int(a)) for a in range(52)]
    sidx = np.array([si[int(w.isocalendar().week) if int(w.isocalendar().week) <= 52 else 52] for w in wk])
    pref = PAR_BY_P[(s["brand"], s["fmt"])] if s["ltype"].startswith("New product") else float(np.mean([sku[q]["price"] for q in others if not sku[q]["ltype"].startswith("New product") and sku[q]["fmt"] == s["fmt"]]))
    return s["wd"] * ros * sidx * ramp * (s["price"] / pref) ** (EL if USE_PRICE else 0)

rows = []
for k, names in ev.items():
    others = [q for q in sku if q not in names]
    act = sum(sku[p]["actual"][:52] for p in names); pr = sum(predict(p, others) for p in names)
    # naive benchmark: the average launched SKU of the same format x its own plateau distribution relative to the others' (no brand or season knowledge)
    nv = 0
    for p in names:
        same = [q for q in others if sku[q]["fmt"] == sku[p]["fmt"]]
        nv = nv + np.mean([sku[q]["actual"][:52] / sku[q]["wd"] for q in same], axis=0) * sku[p]["wd"]
    r13 = pr[:13].sum() / act[:13].sum(); r52 = pr.sum() / act.sum(); n52 = nv.sum() / act.sum()
    wmape = np.abs(pr - act).sum() / act.sum(); nwm = np.abs(nv - act).sum() / act.sum()
    s0 = sku[names[0]]
    rows.append(dict(name=(s0["brand"] + (" " + names[0].split(" Liquid")[0].replace(s0["brand"], "").strip() if s0["ltype"].startswith("New product") else "")).strip(), brand=s0["brand"], btype=s0["btype"], ltype=s0["ltype"],
                     start=str(pd.Timestamp(s0["start"]).date()), skus=[sku[p]["fmt"] for p in names], wd=round(float(np.mean([sku[p]["wd"] for p in names])), 1),
                     price=[round(sku[p]["price"], 1) for p in names], actual=[round(float(x)) for x in act], pred=[round(float(x)) for x in pr],
                     u13=round(float(act[:13].sum())), u52=round(float(act.sum())), p13=round(float(pr[:13].sum())), p52=round(float(pr.sum())),
                     r13=round(float(r13), 3), r52=round(float(r52), 3), wmape=round(float(wmape), 3), naive_r52=round(float(n52), 3), naive_wmape=round(float(nwm), 3)))
    print(f"{rows[-1]['name']:24} u52 {act.sum():10.0f} pred/actual 13w {r13:.2f}  52w {r52:.2f}  weekly WMAPE {wmape:.2f}  | naive 52w {n52:.2f} WMAPE {nwm:.2f}")
r52 = np.array([r["r52"] for r in rows]); print("pred/actual 52w:", r52.round(2), " mean abs err", np.abs(r52 - 1).mean().round(3), " weekly WMAPE mean", np.mean([r["wmape"] for r in rows]).round(3), " naive", np.mean([r["naive_wmape"] for r in rows]).round(3))

# full-sample parameters for new scenarios
ramp_all, lo, hi = mean_ramp(list(sku))
ext_ratio = float(np.mean([sku[q]["ros"] / PAR_BY[(sku[q]["brand"], sku[q]["fmt"])] for q in sku if sku[q]["ltype"].startswith("New product")]))
new_ros = {f: float(np.mean([sku[q]["ros"] for q in sku if not sku[q]["ltype"].startswith("New product") and sku[q]["fmt"] == f])) for f in FMT}
new_price = {f: float(np.mean([sku[q]["price"] for q in sku if not sku[q]["ltype"].startswith("New product") and sku[q]["fmt"] == f])) for f in FMT}
new_wd = float(np.mean([sku[q]["wd"] for q in sku if not sku[q]["ltype"].startswith("New product")]))
catu = float(inc.groupby("week_beginning").retail_sales_units.sum().iloc[-52:].mean())
catv = float(m[m.week_beginning >= W[-52]].groupby("week_beginning").retail_sales_value_inr.sum().mean())
# positioning (last 52 weeks, refill 45 as the like-for-like pack)
sh = last.groupby("brand").retail_sales_units.sum(); sh = sh / sh.sum()
pos = []
for b_, g in PAR.items():
    bm = brand_meta.set_index("brand").loc[b_]
    r45 = g.get("Refill 45") or g["Refill 35"]
    pos.append(dict(brand=b_, btype=bm.btype, price=round(r45["price"], 1), prot=float(bm.prot), wd=round(r45["wd"], 1), share=round(float(sh.get(b_, 0)), 3), ros=round(r45["ros"])))
out = dict(category="Mosquito repellent — liquid vaporizer", asof=str(pd.Timestamp(W[-1]).date()), weeks=n,
           season=[round(float(si[i]), 3) for i in range(1, 53)], ramp=[round(float(x), 3) for x in ramp_all], ramp_lo=[round(float(x), 3) for x in smooth(lo)], ramp_hi=[round(float(x), 3) for x in smooth(hi)],
           elasticity=dict(b=round(EL, 2), se=round(EL_SE, 2)), ext_ratio=round(ext_ratio, 3), new_ros={k: round(v) for k, v in new_ros.items()}, new_price={k: round(v, 1) for k, v in new_price.items()}, new_wd=round(new_wd, 1),
           parents={b_: {f: dict(ros=round(v["ros"]), price=round(v["price"], 1)) for f, v in g.items()} for b_, g in PAR.items()},
           cat_units=round(catu), cat_value=round(catv), unit_value=round(catv / (m[m.week_beginning >= W[-52]].groupby("week_beginning").retail_sales_units.sum().mean()), 1),
           positioning=pos, launches=rows, backtest=dict(mean_abs_err52=round(float(np.abs(r52 - 1).mean()), 3), ratio_lo=round(float(r52.min()), 2), ratio_hi=round(float(r52.max()), 2),
                     wmape=round(float(np.mean([r["wmape"] for r in rows])), 3), naive_wmape=round(float(np.mean([r["naive_wmape"] for r in rows])), 3)))
json.dump(out, open("launch.json", "w"), separators=(",", ":"))
print("ext_ratio", round(ext_ratio, 2), "new_ros", out["new_ros"], "new_wd", out["new_wd"], "cat_units", out["cat_units"], "unit_value", out["unit_value"])
