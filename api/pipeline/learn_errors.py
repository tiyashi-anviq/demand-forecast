"""Continuous learning from forecast errors (walk-forward test).
At every forecast origin t, the layer looks only at forecasts whose actual week was already known at t (T <= t), takes the log error log(actual / forecast)
for the same horizon, averages it with exponential decay per series, shrinks it toward the category average and toward zero, and multiplies the new forecast by
exp(correction). Scored against the unadjusted ensemble on the same rows. Writes learn_errors.json with the best setting and the gain."""
import pickle, json, sys, numpy as np, pandas as pd
W = {"nat": (0.2, 0.3, 0.5), "dep": (0.3, 0.0, 0.7)}
def load(tag):
    b = pickle.load(open(f"{tag}clean_bt.pkl", "rb"))["bt"].copy(); w = W[tag]
    e = b.ets.fillna(0) if tag == "nat" else 0 * b.gbm
    tw = w[0] * b.snaive.notna() + (w[1] * b.ets.notna() if tag == "nat" else 0) + w[2] * b.gbm.notna()
    b["f"] = (w[0] * b.snaive.fillna(0) + (w[1] * e if tag == "nat" else 0) + w[2] * b.gbm.fillna(0)) / tw
    b = b[b.valid & (b.f > 0) & (b.y > 0)].copy(); b["le"] = np.log(b.y / b.f); return b
def adjust(b, hl, shrink_cat, lam, h):
    x = b[b.h == h].sort_values(["t", "ser"]); out = pd.Series(0.0, index=x.index)
    for t in sorted(x.t.unique()):
        past = x[x["T"] <= t]; cur = x[x.t == t]
        if past.empty: continue
        wgt = 0.5 ** ((t - past["T"]) / hl); p = past.assign(wl=wgt * past["le"], w=wgt)
        s = p.groupby("ser")[["wl", "w"]].sum(); c = (s.wl / s.w).reindex(cur.ser).fillna(0).values * (s.w.reindex(cur.ser).fillna(0).values / (s.w.reindex(cur.ser).fillna(0).values + 1.0))
        cm = p.groupby("cat")[["wl", "w"]].sum(); cmv = (cm.wl / cm.w).reindex(cur.cat).fillna(0).values
        out.loc[cur.index] = lam * ((1 - shrink_cat) * c + shrink_cat * cmv)
    return x.assign(adj=out, fa=x.f * np.exp(out))
def wape(y, f): return float(np.abs(y - f).sum() / y.sum())
def score(x, s=None):
    y, f, fa = x.y.values, x.f.values, x.fa.values
    tot = lambda col: float(np.mean([abs(g.y.sum() - g[col].sum()) / g.y.sum() for _, g in x.groupby("week")]))   # all products, weekly total
    return dict(wape=wape(y, f), wape_adj=wape(y, fa), total=tot("f"), total_adj=tot("fa"))
if __name__ == "__main__":
    res = {}
    for tag in ("nat", "dep"):
        b = load(tag); res[tag] = {}
        for h in sorted(b.h.unique()):
            best = None
            for hl in (8, 16, 32):
                for sc in (0.0, 0.5):
                    for lam in (0.5, 1.0):
                        x = adjust(b, hl, sc, lam, h); x = x[x.t >= 129]    # leave the first blocks as learning-in
                        r = score(x); r.update(hl=hl, sc=sc, lam=lam)
                        if best is None or r["wape_adj"] < best["wape_adj"]: best = r
            base = best["wape"]; print(tag, h, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in best.items()}, flush=True); res[tag][int(h)] = best
    json.dump(res, open("learn_errors.json", "w"), indent=1)
