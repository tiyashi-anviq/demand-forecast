"""Adds monthly actuals back to Oct 2023 to vintages.json (for month-on-month and year-on-year cards).
Weeks that straddle two months are pro-rated by days (4/7 to one month, 3/7 to the other), as everywhere else."""
import json, sys
import numpy as np, pandas as pd
path = sys.argv[1] if len(sys.argv) > 1 else "vintages.json"
S = pd.read_csv("eveready_mock_data_v2_ext.csv", low_memory=False, parse_dates=["week_beginning"],
                usecols=["week_beginning", "reporting_level", "product_code", "product_category", "primary_sales_units", "primary_sales_value_inr"])
# pro-rata: split each Monday-Sunday week across the months its days fall in
_wk = sorted(S.week_beginning.unique())
_sh = pd.DataFrame([(w, m, (pd.date_range(w, periods=7).strftime("%Y-%m") == m).mean())
                    for w in _wk for m in sorted(set(pd.date_range(w, periods=7).strftime("%Y-%m")))], columns=["week_beginning", "m", "share"])
S = S.merge(_sh, on="week_beginning")
for c in ("primary_sales_units", "primary_sales_value_inr"): S[c] = S[c] * S.share
_first, _last = pd.Timestamp(_wk[0]), pd.Timestamp(_wk[-1]) + pd.Timedelta(days=6)
_ok = {m for m in S.m.unique() if pd.Timestamp(m + "-01") >= _first and (pd.Timestamp(m + "-01") + pd.offsets.MonthEnd(0)) <= _last}
S = S[S.m.isin(_ok)]
V = json.load(open(path))
for lname, lvl in (("National", "National"), ("Kolkata depots", "Kolkata depot")):
    d = S[S.reporting_level == lvl]
    d = d.assign(w=d.week_beginning)
    months = sorted(d.m.unique())
    wk = d.drop_duplicates(["m", "w"]).groupby("m").share.sum()   # days/7 per month
    out = {"months": [{"m": m, "weeks": round(float(wk[m]), 1)} for m in months], "nodes": {}}
    def agg(x):
        g = x.groupby("m")[["primary_sales_units", "primary_sales_value_inr"]].sum().reindex(months).fillna(0)
        return {"u": [int(round(v)) for v in g.primary_sales_units], "v": [int(round(v)) for v in g.primary_sales_value_inr]}
    out["nodes"]["ALL"] = agg(d)
    for c, x in d.groupby("product_category"): out["nodes"]["cat:" + c] = agg(x)
    for p, x in d.groupby("product_code"): out["nodes"]["sku:" + p] = agg(x)
    V["levels"][lname]["hist"] = out
    chk = V["levels"][lname]["nodes"]["ALL"]["u"]["actual"][0]; mine = out["nodes"]["ALL"]["u"][months.index("2025-12")]
    print(lname, len(months), months[0], months[-1], "check Dec25", chk, mine, "ok" if chk == mine else "MISMATCH")
json.dump(V, open(path, "w"), separators=(",", ":"))
