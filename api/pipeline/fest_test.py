"""Hold-one-season-out test of ways to forecast the Durga Puja weeks. Forecast origin is 4 weeks before the first Puja week (a); targets are weeks a-3 .. a+6.
Everything is compared as a ratio to L, the mean weekly sales over weeks a-12..a-5 (known at the origin).
  flat      ratio 1 (no festival effect)
  blend     the current ensemble (seasonal naive / damped ETS / LightGBM) from the backtest
  blend_noETS   the same with ETS removed and the weights rescaled
  overlay   mean ratio of the other seasons at the same week offset (category ratios shrunk halfway toward the all-product ratio)
  hybrid    average of blend_noETS and overlay
Held-out seasons are the ones the backtest covers (2024, 2025). Overlay uses the other seasons that have 8 weeks of lead-in (2023, 2024, 2025)."""
import pickle, json, numpy as np, pandas as pd
S = pd.read_csv("eveready_mock_data_v2_ext.csv", usecols=["week_beginning", "reporting_level", "product_code", "product_category", "primary_sales_units"], parse_dates=["week_beginning"])
N = S[S.reporting_level == "National"]
cat_of = N.drop_duplicates("product_code").set_index("product_code").product_category.to_dict()
P = pickle.load(open("natv2_primary_sales_units.pkl", "rb")); bt = P["bt"].copy(); weeks = pd.DatetimeIndex(P["weeks"])
bt = bt[bt.series.str.startswith("ALL|")].copy(); bt["sku"] = bt.series.str.split("|").str[1]; bt["cat"] = bt.sku.map(cat_of)
W = (0.2, 0.3, 0.5)
bt["blend"] = (W[0] * bt.snaive + W[1] * bt.ets + W[2] * bt.gbm) / sum(W[i] for i, c in enumerate([bt.snaive, bt.ets, bt.gbm]) if True)
bt["noets"] = (W[0] * bt.snaive + W[2] * bt.gbm) / (W[0] + W[2])
wk = N.groupby(["week_beginning", "product_category"]).primary_sales_units.sum().unstack()
wk["ALL"] = wk.sum(axis=1)
anchors = {2022: "2022-09-26", 2023: "2023-10-16", 2024: "2024-10-07", 2025: "2025-09-29"}
K = list(range(-3, 7)); CATS = ["ALL"] + [c for c in wk.columns if c != "ALL"]
def Lval(y, c):
    a = pd.Timestamp(anchors[y]); idx = weeks.get_loc(a)
    return wk[c].reindex(weeks[idx - 12: idx - 4]).mean()
def act(y, c):
    a = pd.Timestamp(anchors[y]); idx = weeks.get_loc(a); return np.array([wk[c].get(weeks[idx + k], np.nan) for k in K])
RAT = {(y, c): act(y, c) / Lval(y, c) for y in (2023, 2024, 2025) for c in CATS}
def fc(y, c, col):
    a = pd.Timestamp(anchors[y]); idx = weeks.get_loc(a); out = []
    for k in K:
        T = idx + k; r = bt[(bt["T"] == T) & (bt.t <= idx - 4)]
        if c != "ALL": r = r[r.cat == c]
        if not len(r): out.append(np.nan); continue
        r = r[r.t == r.t.max()]; out.append(r[col].sum())
    return np.array(out) / Lval(y, c)
def overlay(y, c, lam=0.5):
    tr = [z for z in (2023, 2024, 2025) if z != y]
    a = np.mean([RAT[(z, "ALL")] for z in tr], 0)
    if c == "ALL": return a
    return lam * np.mean([RAT[(z, c)] for z in tr], 0) + (1 - lam) * a
res = {}
for y in (2024, 2025):
    for c in CATS:
        a = RAT[(y, c)]; m = {"flat": np.ones(len(K)), "blend": fc(y, c, "blend"), "blend_noETS": fc(y, c, "noets"), "overlay": overlay(y, c)}
        m["hybrid"] = (m["blend_noETS"] + m["overlay"]) / 2
        for n_, p in m.items():
            e = np.abs(p - a); res.setdefault(n_, []).append(dict(y=y, c=c, mae=float(np.nanmean(e)), mae12=float(np.nanmean(e[[K.index(1), K.index(2)]])), bias12=float(np.nanmean((p - a)[[K.index(1), K.index(2)]]))))
    print(y, "ALL actual ratios", np.round(RAT[(y, "ALL")], 2), "\n    blend", np.round(fc(y, "ALL", "blend"), 2), "\n    noETS", np.round(fc(y, "ALL", "noets"), 2), "\n    overlay", np.round(overlay(y, "ALL"), 2))
tab = []
for n_, r in res.items():
    d = pd.DataFrame(r); tab.append(dict(method=n_, all_mae=round(d[d.c == "ALL"].mae.mean(), 3), all_mae_wk12=round(d[d.c == "ALL"].mae12.mean(), 3), all_bias_wk12=round(d[d.c == "ALL"].bias12.mean(), 3),
                                          cat_mae=round(d[d.c != "ALL"].mae.mean(), 3), cat_mae_wk12=round(d[d.c != "ALL"].mae12.mean(), 3)))
T = pd.DataFrame(tab); print(T.to_string(index=False)); json.dump(tab, open("fest_test.json", "w"), indent=1)
