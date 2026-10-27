import engine as _en
"""Explainability data for the Forecast & accuracy cards -> drivers.json

1. facts: week-level context (festivals, sell-in period, weather, market events, competitor moves) for every week Oct 2023 - Mar 2027.
2. models: the three models' own forecasts for each display week (26 past weeks, 13 weeks ahead from the backtest, then 26 future weeks),
   summed to every node (all products, category, product). The ensemble is a fixed linear blend, so
       ensemble = w_naive * naive + w_ets * ets + w_lightgbm * lightgbm
   exactly, and a change against any reference splits into each model's pull on the forecast.
   A model missing for a series (e.g. no ETS) is filled with that series' ensemble value, so the identity above always holds.
"""
import pickle, json, os
import numpy as np, pandas as pd
from lyref import ly_ref

HIST, FC = 26, 26
WD = os.environ.get("DF_WORK", ".")
S = pd.read_csv("eveready_mock_data_v2_ext.csv", low_memory=False, parse_dates=["week_beginning"])
E = pd.read_csv("ext_ext.csv", parse_dates=["week_beginning"]).set_index("week_beginning")
WEIGHTS = {"National": (0.2, 0.3, 0.5), "Kolkata depots": (0.3, 0.0, 0.7)}   # seasonal naive, ETS, LightGBM; same hand-set weights as build_ui_data
LEVELS = {"National": (f"{WD}/natv2_primary_sales_units.pkl", "National"), "Kolkata depots": (f"{WD}/depv2_primary_sales_units.pkl", "Kolkata depot")}

# ---- week facts
wk_all = pd.date_range(pd.Timestamp("2022-09-26"), pd.read_csv("eveready_mock_data_v2_ext.csv", usecols=["week_beginning"], parse_dates=["week_beginning"]).week_beginning.max() + pd.Timedelta(weeks=FC), freq="7D")
isf = E.is_forecast_week.reindex(wk_all).fillna(0).values == 1
def wx(a, e):
    v = E[a].reindex(wk_all).values.astype(float); ev = E[e].reindex(wk_all).values.astype(float)
    return np.where(isf, ev, v)                              # measured for past weeks, planning-time expectation for coming weeks
rain, temp, power = wx("rainfall_mm", "expected_rainfall_mm"), wx("temp_max_c", "expected_temp_max_c"), wx("power_cut_hours", "expected_power_cut_hours")
_n = S[S.reporting_level == "National"]
_ev = _n.dropna(subset=["event_note"]).groupby("week_beginning").event_note.agg(lambda x: sorted({e.strip() for v in x for e in v.split(";")}))
_cp = {}
for (ww, c), v in _n.dropna(subset=["competitor_activity_note"]).groupby(["week_beginning", "product_category"]).competitor_activity_note.agg(lambda x: sorted(set(x))).items():
    _cp.setdefault(ww, {})[c] = v
_LYR, _LYL = ly_ref(wk_all, E.reset_index())
INFO = []
for i, w in enumerate(wk_all):
    r = E.loc[w] if w in E.index else None
    INFO.append(None if r is None else {
        "fest": None if pd.isna(r.festival) else str(r.festival), "sellin": None if pd.isna(r.festival_sell_in_period) else str(r.festival_sell_in_period),
        "rain": float(rain[i]), "temp": float(temp[i]), "power": float(power[i]), "fc": bool(isf[i]), "lyi": int(_LYR[i]), "lyl": _LYL[i], "ev": _ev.get(w, []), "comp": _cp.get(w, {})})

# ---- per-model forecasts
U = json.load(open(f"{WD}/ui_data.json"))
res = {"weeks": [w.strftime("%Y-%m-%d") for w in wk_all], "info": INFO, "weights": {k: list(v) for k, v in WEIGHTS.items()}, "levels": {}}
for lname, (pk, lvl) in LEVELS.items():
    P = pickle.load(open(pk, "rb")); weeks, cols, meta, bt, fut = P["weeks"], P["cols"], P["meta"], P["bt"], P["fut"]
    _en.ets_off_in_fest(bt); _en.ets_off_in_fest(fut)
    nW, nS = len(weeks), len(cols); assert nW + FC == len(wk_all)
    W3 = np.array(WEIGHTS[lname]); RAW = np.full((3, HIST + FC, nS), np.nan)

    def put(df, j):
        ok = (j >= 0) & (j < HIST + FC); ser = df.ser.values.astype(int)
        vals = np.c_[df.snaive.values, df.ets.values if "ets" in df else np.full(len(df), np.nan), df.gbm.values]
        avail = ~np.isnan(vals) & (W3 > 0); tw = (avail * W3).sum(1)
        ens = np.where(tw > 0, (np.where(avail, vals, 0) * W3).sum(1) / np.maximum(tw, 1e-9), np.nan)
        for m in range(3): RAW[m, j[ok], ser[ok]] = np.where(avail[:, m], vals[:, m], ens)[ok]
    b13 = bt[bt.h == 13]; put(b13, b13["T"].values.astype(int) - (nW - HIST))
    fu = fut[fut.h <= FC]; put(fu, HIST + fu.h.values.astype(int) - 1)

    mp = meta.set_index("series").loc[cols]
    keys = {"ALL": np.arange(nS)}
    for c in sorted(mp.category.unique()): keys["cat:" + c] = np.where(mp.category.values == c)[0]
    for sk in sorted(set(mp.sku)): keys["sku:" + sk] = np.where(mp.sku.values == sk)[0]
    nodes = {}
    for k, idx in keys.items():
        un, vn = U["levels"][lname]["nodes"][k]["u"], U["levels"][lname]["nodes"][k]["v"]
        scl = []                                              # rupees per unit, so the same cards work for the Value measure
        for jj in range(HIST + FC):
            vv = vn["actual"][jj] if jj < HIST else vn["model"][jj]; uu = un["actual"][jj] if jj < HIST else un["model"][jj]
            scl.append(round(vv / uu, 3) if (vv is not None and uu) else 1.0)
        mdl = {nm: [None if np.isnan(RAW[m][jj, idx]).all() else int(round(np.nansum(RAW[m][jj, idx]))) for jj in range(HIST + FC)] for m, nm in enumerate(("sn", "et", "gb"))}
        if W3[1] == 0: mdl["et"] = None
        mdl["sc"] = scl
        nodes[k] = {"mdl": mdl}
    res["levels"][lname] = nodes

def _clean(o):
    if isinstance(o, float): return None if o != o else o
    if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list): return [_clean(v) for v in o]
    return o
json.dump(_clean(res), open("drivers.json", "w"), separators=(",", ":"), allow_nan=False)
print("drivers.json", os.path.getsize("drivers.json"))
