"""Festival-by-category effects on top of recent sales (walk-forward test).
Forecast for a festival week T from origin t (h = T - t):   baseline(series, t) x exp(effect[festival, category, h])
  baseline  = median of the last 8 non-festival weeks up to t of the cleaned series  (recent sales)
  effect    = mean log( actual at the festival week / baseline at the origin h weeks earlier ) over earlier occurrences with T' <= t, all products of the category,
              shrunk toward the same festival's average over all categories (k = 1 occurrence)
Weeks with several festivals use the average of their effects. Compared with the current blend on the same rows, by festival / other weeks."""
import os, pickle, json, numpy as np, pandas as pd, engine as en, clean
LEVEL = os.environ.get("FE_LEVEL", "National"); TAG = "nat" if LEVEL == "National" else "dep"
d, y, price, sch, meta = en.load_panel(path="eveready_mock_data_v2_ext.csv", level=LEVEL, target="primary_sales_units")
yc = clean.clean_panel(y, meta); Y = yc.values.astype(float); n, S = Y.shape; w0 = yc.index[0]
cat = meta.set_index("series").loc[list(yc.columns)].category.values; cats = sorted(set(cat))
E = pd.read_csv("ext_ext.csv", parse_dates=["week_beginning"]).set_index("week_beginning").festival
FW = {}                                    # week index -> list of festival keys
for w, f in E.dropna().items():
    i = (w - w0).days // 7
    if 0 <= i < n + 30: FW[i] = [p.split(" (")[0] for p in f.split("; ")]
def baseline(t):                           # per series, at origin t
    idx = [i for i in range(t, -1, -1) if i not in FW][:8]
    return np.nanmedian(Y[idx], axis=0)
BL = {}
def B(t):
    if t not in BL: BL[t] = baseline(t)
    return BL[t]
def effects(t, h, K=1.0):
    """effect[(festival, category)] using festival weeks T' <= t and baselines at T'-h"""
    L = {}
    for Tp, fs in FW.items():
        if Tp > t or Tp - h < 20: continue
        r = np.log(np.maximum(Y[Tp], 1) / np.maximum(B(Tp - h), 1))
        for f in fs:
            for c in cats:
                m = cat == c
                if m.any(): L.setdefault((f, c), []).append(np.nanmean(r[m]))
    allf = {}
    for (f, c), v in L.items(): allf.setdefault(f, []).extend(v)
    out = {}
    for (f, c), v in L.items():
        mu = np.mean(allf[f]); k = len(v); out[(f, c)] = (k * np.mean(v) + K * mu) / (k + K)
    return out
def forecast(t, h):
    T = t + h; fs = FW.get(T)
    if not fs: return None
    ef = effects(t, h); b = B(t); out = np.full(S, np.nan)
    for j in range(S):
        v = [ef[(f, cat[j])] for f in fs if (f, cat[j]) in ef]
        if v: out[j] = b[j] * np.exp(np.mean(v))
    return out
MIX = 0.5
def apply(fut, t, mix=MIX):
    """fut: rows of one forecast origin t with columns h, ser, m (blend forecast). Festival weeks: m = (1-mix) * m + mix * festival-effect forecast. Returns (new m, is-festival-week mask)."""
    m = fut.m.values.astype(float).copy(); isf = np.zeros(len(fut), bool)
    for h in sorted(fut.h.unique()):
        h = int(h)
        if (t + h) not in FW: continue
        ff = forecast(t, h); rows = (fut.h.values == h); isf |= rows
        if ff is None: continue
        v = ff[fut.ser.values[rows].astype(int)]; ok = np.isfinite(v)
        idx = np.where(rows)[0][ok]; m[idx] = (1 - mix) * m[idx] + mix * v[ok]
    return m, isf
if __name__ == "__main__":
    bt = pickle.load(open(TAG + "clean_bt.pkl", "rb"))["bt"]; bt = bt[bt.valid & (bt.y > 0)].copy()
    Wt = (0.2, 0.3, 0.5) if TAG == "nat" else (0.3, 0.0, 0.7)
    tw = Wt[0] * bt.snaive.notna() + Wt[1] * (bt.ets.notna() if "ets" in bt else False) + Wt[2] * bt.gbm.notna()
    bt["f"] = (Wt[0] * bt.snaive.fillna(0) + Wt[1] * (bt.ets.fillna(0) if "ets" in bt else 0) + Wt[2] * bt.gbm.fillna(0)) / tw
    bt["T"] = bt["T"].astype(int); res = []
    for (t, h), g in bt[bt["T"].isin(list(FW.keys()))].groupby(["t", "h"]):
        fc = forecast(int(t), int(h))
        if fc is None: continue
        x = g.copy(); x["ff"] = fc[x.ser.values.astype(int)]; res.append(x)
    X = pd.concat(res).dropna(subset=["ff"]); w = lambda g, c: float(np.abs(g.y - g[c]).sum() / g.y.sum())
    X["mix"] = 0.5 * X.f + 0.5 * X.ff
    out = {}
    for h in [int(v) for v in sorted(X.h.unique())]:
        g = X[X.h == h]; out[h] = dict(n=len(g), blend=round(w(g, "f"), 4), fest_effect=round(w(g, "ff"), 4), mix50=round(w(g, "mix"), 4)); print(h, out[h])
    json.dump(out, open("fest_effects_" + TAG + ".json", "w"), indent=1)
