"""Realistic synthetic stock for eveready_mock_data_v2.csv.

Rewrites only the stock columns (opening / replenishment / closing / safety / reorder point, stock value and the
production columns that mirror replenishment). Sales, budget, forecasts and every other column are left alone, so
the forecasting runs do not change; only the Forecast challenge stock check reads these columns.

Design (all weeks of cover are against the average of the next six weeks of sales):
  * normal stock sits at 3-6 weeks of cover per series; depots are scaled so Bardhaman-type depots run heavy and
    Barrackpore-type depots run lean (DEPOT_F);
  * from Sep 2025 to Aug 2026 about a quarter of series get an overstock episode (2.0-2.6x normal for 8-14 weeks) and
    a fifth get a short-stock episode (0.25-0.45x for 4-8 weeks), so the check has real cases to catch;
  * the stock chain keeps close = open + received - sales, and stock can only run down as fast as sales.
Safety stock is 1.5 weeks of forward sales; reorder point is safety plus one week.
Idempotent: depends only on sales, standard cost and the series name. Run before build_challenge.py.
"""
import sys, zlib
import numpy as np, pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "eveready_mock_data_v2.csv"
DEPOT_F = {"ALL": 1.0, "bar": 1.5, "bkp": 1.0, "bpr": 0.55, "dan": 1.2, "tar": 0.8}
EP_FROM, EP_TO = pd.Timestamp("2025-09-01"), pd.Timestamp("2026-08-31")

d = pd.read_csv(SRC, low_memory=False)
wk = pd.to_datetime(d.week_beginning)
d["_wk"] = wk
for (lvl, dep, sku), x in d.groupby(["reporting_level", "depot_code", "product_code"]):
    x = x.sort_values("_wk"); idx = x.index
    n = len(x); s = x.primary_sales_units.fillna(0).values.astype(float)
    rng = np.random.default_rng(zlib.crc32(f"{lvl}|{dep}|{sku}".encode()))
    fwd = np.empty(n)
    for t in range(n):
        nxt = s[t + 1:t + 7]
        fwd[t] = nxt.mean() if len(nxt) >= 3 else s[max(0, t - 5):t + 1].mean()
    base = rng.uniform(3.0, 6.0) * DEPOT_F.get(dep, 1.0)
    mult = np.ones(n)
    inwin = np.where((x._wk.values >= np.datetime64(EP_FROM)) & (x._wk.values <= np.datetime64(EP_TO)))[0]
    if rng.random() < 0.25:
        a = rng.choice(inwin); mult[a:a + rng.integers(8, 15)] *= rng.uniform(2.0, 2.6)
    if rng.random() < 0.20:
        a = rng.choice(inwin); mult[a:a + rng.integers(4, 9)] *= rng.uniform(0.25, 0.45)
    k = np.array([0.25, 0.5, 0.25]); mult = np.convolve(np.pad(mult, 1, mode="edge"), k, mode="valid")
    noise = np.exp(np.convolve(np.pad(rng.normal(0, 0.07, n), 1, mode="edge"), k, mode="valid"))
    tgt = base * mult * noise * fwd
    safety = 1.5 * fwd
    opening = np.zeros(n); recv = np.zeros(n); close = np.zeros(n)
    opening[0] = tgt[0]
    for i in range(n):
        if i: opening[i] = close[i - 1]
        recv[i] = max(0.0, tgt[i] - opening[i] + s[i])
        close[i] = opening[i] + recv[i] - s[i]
    d.loc[idx, "opening_stock_units"] = opening.round()
    d.loc[idx, "replenishment_received_units"] = recv.round()
    d.loc[idx, "closing_stock_units"] = (opening.round() + recv.round() - s).clip(min=0)
    d.loc[idx, "safety_stock_units"] = safety.round()
    d.loc[idx, "reorder_point_units"] = (safety + fwd).round()
    d.loc[idx, "production_required_units"] = recv.round()
    d.loc[idx, "production_allocated_units"] = np.fmin(recv.round(), d.loc[idx, "plant_capacity_units"].values)
    d.loc[idx, "replenishment_ordered_units"] = d.loc[idx, "production_allocated_units"]
m = d.depot_stock_value_inr_lakh.notna()
d.loc[m, "depot_stock_value_inr_lakh"] = (d.loc[m, "closing_stock_units"] * d.loc[m, "standard_cost_inr"] / 1e5).round(3)
d.drop(columns="_wk").to_csv(SRC, index=False)
print("stock rewritten in", SRC)
