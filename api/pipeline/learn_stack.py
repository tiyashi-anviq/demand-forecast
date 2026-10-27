"""Second-stage model that learns from the first model's mistakes (walk-forward).
Target: actual / forecast.  Loss: L1 on the ratio with weight = forecast, which is exactly the WAPE loss (sum |actual - c*forecast|).
Features known at the forecast origin: horizon, category, week of year, festival flags (Puja / Diwali week counters), the ensemble's own components
(how far GBM, ETS and seasonal naive disagree), recent level and volatility, and the series' own past errors (decayed weighted median of actual/forecast for answers
already known at the origin). At origin t it is fit only on rows whose actual week T <= t. Scored against the plain ensemble on the same rows."""
import json, numpy as np, pandas as pd, lightgbm as lgb
from learn_errors_wape import load, wmed, wape
FE = ["h", "cat", "woy", "month", "fest", "fest_major", "wk_durga", "wk_diwali", "sellin_durga", "sellin_diwali", "cv13", "growth", "l1", "m4", "ly_m", "lbase"]
def prep(b, tag):
    b = b.copy(); b["lf"] = np.log(b.f)
    b["d_g"] = np.log(b.gbm.clip(lower=1) / b.f); b["d_s"] = np.log(b.snaive.clip(lower=1) / b.f)
    b["d_e"] = np.log(b.ets.clip(lower=1) / b.f) if tag == "nat" else 0.0
    b["r"] = b.y / b.f; return b
def own_err(b, hl=12):
    """for every row: decayed weighted median of r over the same series' rows with T <= t (known at the origin)."""
    out = np.zeros(len(b)); idx = {i: k for k, i in enumerate(b.index)}
    for ser, g in b.groupby("ser"):
        g = g.sort_values("t")
        for i, row in g.iterrows():
            p = g[g["T"] <= row.t]
            out[idx[i]] = np.log(wmed(p.r.values, (0.5 ** ((row.t - p["T"]) / hl) * p.f).values)) if len(p) >= 2 else 0.0
    return out
def run(tag, h, first=129):
    b = prep(load(tag), tag); b = b[b.h == h].sort_values(["t", "ser"]).reset_index(drop=True)
    b["oe"] = own_err(b); X = FE + ["lf", "d_g", "d_s", "d_e", "oe"]
    pred = pd.Series(1.0, index=b.index)
    for t in sorted(b.t.unique()):
        if t < first: continue
        tr = b[b["T"] <= t]; te = b[b.t == t]
        if len(tr) < 400: continue
        m = lgb.LGBMRegressor(objective="l1", n_estimators=120, learning_rate=0.05, num_leaves=8, min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1)
        m.fit(tr[X], np.log(tr.r.clip(0.05, 20)), sample_weight=tr.f)   # median of log ratio = median of ratio; weight = forecast
        pred.loc[te.index] = np.exp(0.7 * m.predict(te[X]))                 # 0.7: damp the correction
    x = b[b.t >= first].copy(); x["fa"] = x.f * pred.loc[x.index]
    tot = lambda col: float(np.mean([abs(g.y.sum() - g[col].sum()) / g.y.sum() for _, g in x.groupby("week")]))
    under = lambda col: float(np.maximum(x.y - x[col], 0).sum() / x.y.sum()); over = lambda col: float(np.maximum(x[col] - x.y, 0).sum() / x.y.sum())
    return dict(wape=wape(x.y.values, x.f.values), wape_adj=wape(x.y.values, x.fa.values), total=tot("f"), total_adj=tot("fa"),
                under=under("f"), under_adj=under("fa"), over=over("f"), over_adj=over("fa"), n=len(x))
if __name__ == "__main__":
    res = {}
    for tag in ("nat", "dep"):
        res[tag] = {}
        for h in (4, 9, 13) if tag == "nat" else (13,):
            r = run(tag, h); res[tag][h] = r; print(tag, h, {k: round(v, 4) for k, v in r.items()}, flush=True)
    json.dump(res, open("learn_stack.json", "w"), indent=1)
