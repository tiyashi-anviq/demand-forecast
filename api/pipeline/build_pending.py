"""Pending sales-forecast submissions for the forecast-challenge queue (Expectation: challenge at the point of submission).

The queue is what the sales team has submitted for the three months still open at the planning date:
    next month at M1, the month after at M2, the one after that at M3
(from the 26 forward weeks added to eveready_mock_data_v3.csv by make_v3.py).
Each submission is joined to the references the planner needs when it arrives: budget, last year's actual, the model's
current view (national only), and stock on hand at the planning date.
Writes ../data/pending.json:
  {asof, months:[{m,label,lead,weeks}], reasons:[...], rows:{level:[[sku,name,category,depot,month,lead,forecast,budget,
    last_year,model,stock,safety,reason,weeks], ...]}}
"""
import json, pickle
import numpy as np, pandas as pd

v3 = pd.read_csv("eveready_mock_data_v3.csv", low_memory=False, parse_dates=["week_beginning"])
cur = pd.read_csv("eveready_mock_data_v2_ext.csv", low_memory=False, parse_dates=["week_beginning"])
cuts, runs, cols = pickle.load(open("vint_runs.pkl", "rb"))
t, M = runs["latest"]                                   # model as of the last actual week; M[i-t-1] is week i
w0 = pd.Timestamp("2022-09-26")
widx = lambda w: int((w - w0).days // 7)

ASOF = cur.week_beginning.max()
assert widx(ASOF) == t, (ASOF, t)
fw = v3[(v3.is_forecast_week == 1) & (v3.week_beginning > ASOF)].copy()   # weeks after the last actual (the Oct weeks that are now actuals drop out)
mth = lambda w: (w + pd.Timedelta(days=3)).strftime("%Y-%m")        # Thursday rule, as make_v3
months = sorted(fw.week_beginning.map(mth).unique())
if months and months[0] == mth(ASOF): months = months[1:]           # the month the last actual week belongs to is not pending: only its tail week is left
months = months[:3]
lead = {m: i + 1 for i, m in enumerate(months)}
wk_of = {m: sorted(w for w in fw.week_beginning.unique() if mth(pd.Timestamp(w)) == m) for m in months}
# Submissions for the shifted horizons: after the cut-off moves, the next month is M1 and needs a 1m forecast, the month after a 2m forecast, and so on.
# make_v3 generated them for the old cut-off; the missing ones are filled from the same row's other horizons (or last year's actual) with the same noise level (SIMULATED).
_rng = np.random.default_rng(26); _lead = {m: i + 1 for i, m in enumerate(months)}
_cols = {3: "sales_forecast_3m_ahead_units", 2: "sales_forecast_2m_ahead_units", 1: "sales_forecast_1m_ahead_units"}
_ly = {}
for _lv in ("National", "Kolkata depot"):
    _x = cur[cur.reporting_level == _lv].copy(); _x["series"] = _x.depot_code + "|" + _x.product_code
    _ly[_lv] = _x.pivot(index="week_beginning", columns="series", values="primary_sales_units")
for _i in fw.index:
    _k = _lead.get(mth(fw.at[_i, "week_beginning"]))
    if _k is None: continue
    for _h in (3, 2, 1):
        if _h < _k or pd.notna(fw.at[_i, _cols[_h]]): continue
        _have = [fw.at[_i, c] for c in _cols.values() if pd.notna(fw.at[_i, c])]
        if _have: _base = float(np.mean(_have))
        else:
            _s = fw.at[_i, "depot_code"] + "|" + fw.at[_i, "product_code"]; _w = fw.at[_i, "week_beginning"] - pd.Timedelta(days=364); _A = _ly[fw.at[_i, "reporting_level"]]
            _base = float(_A.at[_w, _s]) if (_s in _A.columns and _w in _A.index and pd.notna(_A.at[_w, _s])) else np.nan
        if np.isfinite(_base): fw.at[_i, _cols[_h]] = round(_base * np.exp(_rng.normal(0, 0.12)))
out = {"asof": ASOF.strftime("%Y-%m-%d"),
       "months": [{"m": m, "label": pd.Timestamp(m + "-01").strftime("%b %y"), "lead": lead[m], "weeks": len(wk_of[m])} for m in months],
       "reasons": ["Festival sell-in", "Distributor feedback", "Scheme loading", "NPD launch plan", "Competitor activity", "Weather", "Supply constraint"],
       "rows": {}}

for lvl, lab in (("National", "National"), ("Kolkata depot", "Kolkata depots")):
    x = cur[cur.reporting_level == lvl].copy(); x["series"] = x.depot_code + "|" + x.product_code
    A = x.pivot(index="week_beginning", columns="series", values="primary_sales_units")
    ST = x.pivot(index="week_beginning", columns="series", values="closing_stock_units")
    SS = x.pivot(index="week_beginning", columns="series", values="safety_stock_units")
    g = fw[fw.reporting_level == lvl].copy(); g["series"] = g.depot_code + "|" + g.product_code
    meta = g.drop_duplicates("series").set_index("series")
    rows = []
    for s in sorted(g.series.unique()):
        dep, sku = s.split("|")
        gs = g[g.series == s].set_index("week_beginning")
        for m in months:
            ws = [pd.Timestamp(w) for w in wk_of[m] if pd.Timestamp(w) in gs.index]
            col = f"sales_forecast_{lead[m]}m_ahead_units"
            f = gs.loc[ws, col]
            if f.isna().all(): continue
            b = gs.loc[ws, "budget_units"].sum()
            ly = float(sum(A.at[w - pd.Timedelta(days=364), s] for w in ws if s in A.columns and (w - pd.Timedelta(days=364)) in A.index and pd.notna(A.at[w - pd.Timedelta(days=364), s])))
            mv = None
            if lvl == "National" and s in cols:
                c = cols.index(s); mv = float(sum(M[widx(w) - t - 1][c] for w in ws))
            rs = gs.loc[ws, "forecast_override_reason"].dropna()
            reason = rs.mode().iloc[0] if len(rs) else ""
            st = ST.at[ASOF, s] if s in ST.columns else np.nan; ss = SS.at[ASOF, s] if s in SS.columns else np.nan
            rows.append([sku, str(meta.at[s, "product_name"]), str(meta.at[s, "product_category"]), dep, m, lead[m], int(round(f.sum())), int(round(b)),
                         int(round(ly)), None if mv is None else int(round(mv)), None if np.isnan(st) else int(round(st)), None if np.isnan(ss) else int(round(ss)), reason, len(ws)])
    out["rows"][lab] = rows

json.dump(out, open("pending.json", "w"), separators=(",", ":"))
print(out["months"], {k: len(v) for k, v in out["rows"].items()})
print(out["rows"]["National"][:3])
