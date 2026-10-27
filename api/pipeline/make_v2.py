"""Build eveready_mock_data_v2.csv from the original mock file (original untouched).

Goals (CFO-quoted figures, all synthetic):
  * sales-team forecast accuracy ~68% at M3 (weekly SKU level), ~70% M2, ~79% M1
  * quick-commerce: partners over-order ~10x real need in episodes; fulfilment ~96%, OTIF ~85%
  * delayed monsoon: 50-60% demand swing on torch SKUs, then recovery spillover
  * depot imbalance: some depots overstocked, some short
  * less random SKU-week noise + clearer forecastable drivers (weather outlook, festivals, power cuts)
"""
import numpy as np, pandas as pd
import engine as en

rng = np.random.default_rng(42)
SRC = "sales.csv"
d = pd.read_csv(SRC, low_memory=False, parse_dates=["week_beginning"])
d["series"] = d.reporting_level.str[:3] + "|" + d.depot_code + "|" + d.product_code
d = d.sort_values(["series", "week_beginning"]).reset_index(drop=True)
ext = en.load_ext()
LAMBDA = 0.50  # share of original idiosyncratic noise kept

# ---------------------------------------------------------------- demand signal
def zs(s):
    return (s - s.mean()) / s.std()

pc = zs(ext.pcut); rn = zs(ext.rain); hot = zs(ext.temp)
cat_drv = {  # category -> (log effect per 1 sd of expected power-cut outlook, rain, temp)
    "Emergency & rechargeable LED": (0.20, 0.08, 0.0),
    "Flashlights — rechargeable": (0.18, 0.08, 0.0),
    "Flashlights — conventional": (0.12, 0.06, 0.0),
    "Batteries — carbon-zinc": (0.08, 0.06, 0.0),
    "Batteries — alkaline": (0.06, 0.04, 0.0),
    "LED bulbs": (0.0, 0.0, 0.0),
}
fest_cat = {"Decorative & festive": 0.28, "LED bulbs": 0.10, "Panels & downlighters": 0.08, "LED battens & tubelights": 0.08}
diwali = ext.sellin_diwali; durga = ext.sellin_durga

MONSOON = {  # delayed-monsoon shock multipliers by week (torch SKUs), then recovery spillover
    "2025-06-09": .38, "2025-06-16": .35, "2025-06-23": .40, "2025-06-30": .46, "2025-07-07": .56, "2025-07-14": .68,
    "2025-07-21": 1.35, "2025-07-28": 1.25, "2025-08-04": 1.12, "2025-08-11": 1.05}
MON_SKUS = {"rch", "hyb", "cvt"}

parts = []
for lvl, g in d.groupby("reporting_level"):
    L = np.log1p(g.pivot(index="week_beginning", columns="series", values="primary_sales_units"))
    med = L.rolling(9, center=True, min_periods=3).median()
    dev = L - med
    meta = g.groupby("series").agg(cat=("product_category", "first"), seg=("business_segment", "first"))
    common = pd.DataFrame(index=L.index, columns=L.columns, dtype=float)
    for cat, idx in meta.groupby("cat").groups.items():
        cols = list(idx)
        grp = cols if len(cols) >= 3 else list(meta.index[meta.seg == meta.loc[cols[0], "seg"]])
        common[cols] = np.repeat(dev[grp].mean(axis=1).values[:, None], len(cols), axis=1)
    idio = dev - common
    drv = pd.DataFrame(0.0, index=L.index, columns=L.columns)
    e = ext.reindex(L.index)
    for s in L.columns:
        cat = meta.loc[s, "cat"]
        a, b, c = cat_drv.get(cat, (0, 0, 0))
        x = a * pc.reindex(L.index) + b * rn.reindex(L.index) + c * hot.reindex(L.index)
        if cat in fest_cat:
            x = x + fest_cat[cat] * (diwali.reindex(L.index) + 0.6 * durga.reindex(L.index)).clip(upper=1)
        drv[s] = x.values
    mon = pd.DataFrame(0.0, index=L.index, columns=L.columns)
    for wk, m in MONSOON.items():
        for s in L.columns:
            if s.split("|")[-1] in MON_SKUS and pd.Timestamp(wk) in mon.index:
                mon.loc[pd.Timestamp(wk), s] = np.log(m)
                common.loc[pd.Timestamp(wk), s] = 0.0   # neutralise earlier ad-hoc dip so the designed swing is the only one
    for s_ in L.columns:
        if s_.split("|")[-1] in MON_SKUS:
            w_ = (med.index >= pd.Timestamp("2025-05-26")) & (med.index <= pd.Timestamp("2025-08-25"))
            tmp = med[s_].copy(); tmp[w_] = np.nan
            med[s_] = tmp.interpolate(limit_direction="both")
    sig_known = med + common + drv                  # what a good planner could foresee
    sig_true = sig_known + mon                      # + unforeseen monsoon shock
    Lnew = sig_true + LAMBDA * idio
    ynew = np.expm1(Lnew).clip(lower=0).round()
    parts.append((lvl, ynew, sig_known))

# ---------------------------------------------------------------- write back demand-driven columns
new_y = {}; fsig = {}
for lvl, ynew, sk in parts:
    st = ynew.stack(); new_y.update({(w, s): v for (w, s), v in st.items()})
    st2 = sk.stack(); fsig.update({(w, s): v for (w, s), v in st2.items()})
key = list(zip(d.week_beginning, d.series))
d["y_old"] = d.primary_sales_units
d["y_new"] = [new_y.get(k, np.nan) for k in key]
d["fsig"] = [np.expm1(fsig.get(k, np.nan)) for k in key]
d = d[d.y_new.notna()].copy()
f = np.where(d.y_old > 0, d.y_new / d.y_old.replace(0, np.nan), 1.0)
d["f"] = np.where(np.isfinite(f), f, 1.0)
# smoothed series-level factor for stock-like columns
d["g"] = d.groupby("series").apply(lambda x: (x.y_new.rolling(13, center=True, min_periods=4).mean() /
                                                x.y_old.rolling(13, center=True, min_periods=4).mean().replace(0, np.nan))
                                     ).reset_index(level=0, drop=True).reindex(d.index).fillna(1.0)

def rnd(s): return s.round()
d["primary_sales_units"] = d.y_new
d["primary_sales_value_inr"] = rnd(d.primary_sales_value_inr * d.f)
d["primary_sales_b2b_p1_units"] = rnd(d.primary_sales_b2b_p1_units * d.f)
d["primary_sales_b2b_p2_units"] = rnd(d.primary_sales_b2b_p2_units * d.f)
d["primary_sales_b2c_units"] = (d.primary_sales_units - d.primary_sales_b2b_p1_units - d.primary_sales_b2b_p2_units).clip(lower=0)
d["primary_sales_units"] = d.primary_sales_b2c_units + d.primary_sales_b2b_p1_units + d.primary_sales_b2b_p2_units
for c in ["unfulfilled_b2c_units", "unfulfilled_b2b_p1_units", "unfulfilled_b2b_p2_units", "open_orders_units", "secondary_sales_units", "trade_scheme_spend_inr"]:
    d[c] = rnd(d[c] * d.f)
unf = d.unfulfilled_b2c_units + d.unfulfilled_b2b_p1_units + d.unfulfilled_b2b_p2_units
d["orders_received_units"] = np.maximum(rnd(d.orders_received_units * d.f), d.primary_sales_units + unf * 0)
for c in ["distributor_stock_units", "procurement_request_units", "budget_units", "budget_value_inr"]:
    d[c] = rnd(d[c] * d.g)

# ---------------------------------------------------------------- stock chain (identity: close = open + received - sales)
DEPOT_F = {"ALL": 1.0, "bar": 1.9, "bkp": 1.0, "bpr": 0.40, "dan": 1.35, "tar": 0.75}  # overstocked / short depots
out = []
for s, x in d.groupby("series"):
    x = x.sort_values("week_beginning").copy()
    fac = DEPOT_F.get(x.depot_code.iloc[0], 1.0)
    close_t = (x.closing_stock_units * x.g * fac).clip(lower=0).values
    safety = x.safety_stock_units.values * x.g.values
    sales = x.primary_sales_units.values
    opening = np.zeros(len(x)); recv = np.zeros(len(x)); close = np.zeros(len(x))
    opening[0] = x.opening_stock_units.iloc[0] * x.g.iloc[0] * fac
    for i in range(len(x)):
        if i: opening[i] = close[i - 1]
        tgt = max(close_t[i], 0.25 * safety[i])
        recv[i] = max(0, tgt - opening[i] + sales[i])
        close[i] = opening[i] + recv[i] - sales[i]
    x["opening_stock_units"] = opening.round(); x["replenishment_received_units"] = recv.round()
    x["closing_stock_units"] = (x.opening_stock_units + x.replenishment_received_units - sales).clip(lower=0)
    x["safety_stock_units"] = safety.round(); x["reorder_point_units"] = (x.reorder_point_units * x.g).round()
    x["production_required_units"] = x.replenishment_received_units
    x["production_allocated_units"] = np.minimum(x.production_required_units, x.plant_capacity_units)
    x["replenishment_ordered_units"] = x.production_allocated_units
    ratio = (x.depot_stock_value_inr_lakh / x.closing_stock_units.replace(0, np.nan)).median()
    out.append(x)
d = pd.concat(out).sort_values(["week_beginning", "series"]).reset_index(drop=True)
old_close = pd.read_csv(SRC, low_memory=False, usecols=["reporting_level", "depot_code", "product_code", "week_beginning", "closing_stock_units", "depot_stock_value_inr_lakh"], parse_dates=["week_beginning"])
cost_per_unit_lakh = d.standard_cost_inr / 1e5
mask = d.depot_stock_value_inr_lakh.notna()
d.loc[mask, "depot_stock_value_inr_lakh"] = (d.loc[mask, "closing_stock_units"] * cost_per_unit_lakh[mask]).round(3)

# ---------------------------------------------------------------- sales-team forecasts (calibrated to CFO baseline accuracy)
def make_fc(target_acc, bias, shared, seed):
    r = np.random.default_rng(seed)
    u = r.standard_normal(len(d)); w = r.standard_normal(len(d))
    lo, hi = 0.02, 0.9
    base = np.log1p(d.fsig.values)
    for _ in range(30):
        s = (lo + hi) / 2
        fc = np.expm1(base + bias + s * (shared * u + np.sqrt(1 - shared ** 2) * w))
        acc = 1 - np.abs(fc - d.primary_sales_units).sum() / d.primary_sales_units.sum()
        lo, hi = (s, hi) if acc > target_acc else (lo, s)
    return fc, s
d["sales_forecast_3m_ahead_units"], s3 = make_fc(0.68, 0.035, 0.85, 1)
d["sales_forecast_2m_ahead_units"], s2 = make_fc(0.70, 0.050, 0.80, 2)
d["sales_forecast_1m_ahead_units"], s1 = make_fc(0.79, 0.070, 0.70, 3)
for c in ["sales_forecast_3m_ahead_units", "sales_forecast_2m_ahead_units", "sales_forecast_1m_ahead_units"]:
    d[c] = d[c].clip(lower=0).round()
r = np.random.default_rng(7)
d["consensus_forecast_1m_ahead_units"] = (d.sales_forecast_1m_ahead_units * np.exp(r.normal(0.012, 0.05, len(d)))).round()
print("forecast noise sd", round(s3, 3), round(s2, 3), round(s1, 3))

# ---------------------------------------------------------------- quick commerce (standalone channel view)
qc = d.quick_commerce_ordered_units.notna()
q = d[qc].copy()
r = np.random.default_rng(11)
sell = (q.primary_sales_units * r.uniform(0.07, 0.11, len(q))).round()          # real partner sell-out
episode = r.random(len(q)) < 0.35
mult = np.where(episode, r.uniform(7.0, 13.0, len(q)), r.uniform(1.2, 2.2, len(q)))
ordered = (sell * mult).round()
delivered = (ordered * np.clip(r.normal(0.96, 0.02, len(q)), 0.88, 1.0)).round()
lines = q.quick_commerce_order_lines.values
p_otif = np.clip(r.normal(0.85, 0.06, len(q)), 0.6, 0.98)
otif = np.round(lines * p_otif)
on_time = np.minimum(lines, otif + np.round(lines * r.uniform(0.04, 0.10, len(q))))
in_full = np.minimum(lines, otif + np.round(lines * r.uniform(0.03, 0.08, len(q))))
q["quick_commerce_partner_sell_out_units"] = sell
q["quick_commerce_ordered_units"] = ordered; q["quick_commerce_delivered_units"] = delivered
q["quick_commerce_lines_otif"] = otif; q["quick_commerce_lines_on_time"] = on_time; q["quick_commerce_lines_in_full"] = in_full
# partner stock / returns: returns excess above 4 weeks of cover
for s, x in q.groupby("series"):
    x = x.sort_values("week_beginning"); stock = 0.0; st = []; rt = []
    for dl, se in zip(x.quick_commerce_delivered_units, x.quick_commerce_partner_sell_out_units):
        stock = max(0.0, stock + dl - se)
        ret = max(0.0, 0.5 * (stock - 4 * se)); stock -= ret
        st.append(round(stock)); rt.append(round(ret))
    q.loc[x.index, "quick_commerce_partner_stock_units"] = st; q.loc[x.index, "quick_commerce_returned_units"] = rt
for c in [c for c in d.columns if c.startswith("quick_commerce")]:
    d.loc[q.index, c] = q[c]

# ---------------------------------------------------------------- housekeeping + checks
drop = ["y_old", "y_new", "fsig", "f", "g", "series"]
v2 = d.drop(columns=drop)
v2["week_beginning"] = v2.week_beginning.dt.strftime("%Y-%m-%d")
orig_cols = list(pd.read_csv(SRC, nrows=1).columns)
v2 = v2[orig_cols]
v2.to_csv("eveready_mock_data_v2.csv", index=False)

n = d[d.reporting_level == "National"]
A = lambda f, y: 1 - np.abs(f - y).sum() / y.sum()
print("WAPE-accuracy (weekly SKU) M3/M2/M1:", [round(A(n[c], n.primary_sales_units), 3) for c in
      ["sales_forecast_3m_ahead_units", "sales_forecast_2m_ahead_units", "sales_forecast_1m_ahead_units"]])
x = n[n.quick_commerce_ordered_units.notna()]
print("QC fulfil", round(x.quick_commerce_delivered_units.sum() / x.quick_commerce_ordered_units.sum(), 3),
      "OTIF", round(x.quick_commerce_lines_otif.sum() / x.quick_commerce_order_lines.sum(), 3),
      "median ordered/sell-out in episodes", round((x.quick_commerce_ordered_units / x.quick_commerce_partner_sell_out_units).quantile(0.9), 1),
      "avg", round(x.quick_commerce_ordered_units.sum() / x.quick_commerce_partner_sell_out_units.sum(), 2))
print("overall fulfilment", round(n.primary_sales_units.sum() / n.orders_received_units.sum(), 3))
