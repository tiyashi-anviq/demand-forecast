"""Second-stage 'learn from mistakes' layer for the NATIONAL forecast (see learn_stack.py for the walk-forward test).
fit(bt, t): trains on backtest rows whose actual week T <= t. Target log(actual / ensemble forecast), L1 loss, weight = forecast (= WAPE loss).
multiplier(fut, model, own): factor (damped to 70%) to multiply the ensemble forecast of rows `fut` (columns as engine.build_rows + gbm, snaive, ets, m).
Pooled own-error feature: decayed weighted median of actual/forecast over the series' own past rows (any horizon) known at the origin."""
import numpy as np, pandas as pd, lightgbm as lgb
W = (0.2, 0.3, 0.5)
FE = ["h", "cat", "woy", "month", "fest", "fest_major", "wk_durga", "wk_diwali", "sellin_durga", "sellin_diwali", "cv13", "growth", "l1", "m4", "ly_m", "lbase"]
X = FE + ["lf", "d_g", "d_s", "d_e", "oe"]
DAMP = 0.7; HL = 12
def wmed(v, w):
    o = np.argsort(v); v, w = v[o], w[o]; cw = np.cumsum(w); return float(v[np.searchsorted(cw, 0.5 * cw[-1])])
def ens(b):
    ok = lambda c: b[c].notna()
    tw = W[0] * ok("snaive") + W[1] * ok("ets") + W[2] * ok("gbm")
    return (W[0] * b.snaive.fillna(0) + W[1] * b.ets.fillna(0) + W[2] * b.gbm.fillna(0)) / tw
def feats(b, f):
    b = b.copy(); b["f"] = f; b["lf"] = np.log(b.f)
    b["d_g"] = np.log(b.gbm.clip(lower=1) / b.f); b["d_s"] = np.log(b.snaive.clip(lower=1) / b.f); b["d_e"] = np.log(b.ets.clip(lower=1) / b.f) if "ets" in b else 0.0
    return b
def own_at(past, t):
    """series -> decayed weighted median of actual/forecast, over rows of `past` whose actual week is <= t"""
    p = past[past["T"] <= t]; out = {}
    for s, g in p.groupby("ser"):
        if len(g) >= 2: out[s] = float(np.log(wmed(g.r.values, (0.5 ** ((t - g["T"]) / HL) * g.f).values)))
    return out
def train_frame(bt):
    b = bt[bt.valid & bt.y.notna() & (bt.y > 0)].copy(); b["f"] = ens(b); b = b[b.f > 0].copy(); b = feats(b, b.f.values); b["r"] = b.y / b.f
    oe = np.zeros(len(b)); pos = {i: k for k, i in enumerate(b.index)}
    for s, g in b.groupby("ser"):
        for t in g.t.unique():
            o = own_at(g, t); k = [pos[i] for i in g.index[g.t == t]]; oe[k] = o.get(s, 0.0)
    b["oe"] = oe; return b
def fit(tf, t):
    tr = tf[tf["T"] <= t]
    if len(tr) < 400: return None
    m = lgb.LGBMRegressor(objective="l1", n_estimators=120, learning_rate=0.05, num_leaves=8, min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
    m.fit(tr[X], np.log(tr.r.clip(0.05, 20)), sample_weight=tr.f); return m, own_at(tf, t)
def multiplier(fut, fit_out):
    if fit_out is None: return np.ones(len(fut))
    m, own = fit_out; f = fut.m.values; b = feats(fut, f); b["oe"] = [own.get(s, 0.0) for s in b.ser]
    return np.exp(DAMP * m.predict(b[X]))
