"""Rebuilds the Sep 2022 - Sep 2023 history (synthetic) from LEARNED effects instead of copying the following year.

 in : eveready_mock_data_v2.csv (2023-10-02 .. 2026-09-28, the user's file, untouched)   ext.csv
 out: eveready_mock_data_v2_ext.csv (2022-09-26 .. 2026-09-28)                            ext_ext.csv

Method
  1. Weather for the new year: typical Kolkata weekly climate from the three real years, with the 2023 monsoon arriving on its real
     date (Kolkata about 23 Jun 2023, week of 19 Jun; Kerala onset was 8 Jun) and Cyclone Sitrang on its real date (24 Oct 2022, Diwali week).
  2. Demand: per category, the common log-deviation of its products is explained by annual season, each festival on its real week
     (Durga Puja stretch, Diwali, Christmas, Holi, Eid, Poila Baisakh, Rath Yatra, ...) and weather (see regen_model.py). Categories with no
     stable pattern out of sample (leave-one-year-out) keep only a trend. Each series then gets its own level and trend, and its own
     residual noise, bootstrapped in 3-week blocks (cyclone weeks excluded) with the same weeks used for every series so cross-series co-movement is kept.
  3. Every other column is taken from a template row of the same series (festival weeks from the same festival, other weeks 52 weeks later)
     and scaled by new sales over template sales; prices drift backwards; ledgers (distributor and depot stock) are rebuilt backwards from the
     first real week so the identities hold. New-product series are not created. Free-text notes and influencer fields are left empty.
"""
import numpy as np, pandas as pd
import regen_model as rm

rng = np.random.default_rng(2022)
d = pd.read_csv("eveready_mock_data_v2.csv", low_memory=False, parse_dates=["week_beginning"])
e = pd.read_csv("ext.csv", parse_dates=["week_beginning"])
COLS = list(d.columns)
W0 = pd.Timestamp("2023-10-02")
NEW = pd.date_range("2022-09-26", "2023-09-25", freq="7D")             # 53 weeks
RW = pd.DatetimeIndex(sorted(d.week_beginning.unique()))
ex = e.set_index("week_beginning")
exr = ex[ex.is_forecast_week == 0]

# ------------------------------------------------------------------ calendar of the new year (real dates)
CAL = {"2022-09-26": "Durga Puja (Shashthi–Saptami)", "2022-10-03": "Durga Puja (Ashtami–Dashami); Kojagari Lakshmi Puja",
       "2022-10-24": "Kali Puja / Diwali; Bhai Phonta", "2022-10-31": "Jagaddhatri Puja (Chandannagar)", "2022-12-19": "Christmas / Park Street festival",
       "2023-01-09": "Gangasagar Mela", "2023-01-23": "Saraswati Puja", "2023-01-30": "Kolkata International Book Fair", "2023-03-06": "Dol Jatra / Holi",
       "2023-04-10": "Chaitra Sale (Choitro Sankranti); Poila Baisakh (Bengali New Year, Halkhata)", "2023-04-17": "Eid ul-Fitr",
       "2023-06-12": "Jamai Sasthi", "2023-06-19": "Rath Yatra", "2023-09-11": "Vishwakarma Puja", "2023-09-18": "Ganesh Chaturthi"}
cal = {pd.Timestamp(k): v for k, v in CAL.items()}
SELL = {pd.Timestamp("2022-09-26"): "Durga Puja sell-in", pd.Timestamp("2022-10-10"): "Kali Puja / Diwali sell-in",
        pd.Timestamp("2022-10-17"): "Kali Puja / Diwali sell-in", pd.Timestamp("2022-10-24"): "Kali Puja / Diwali sell-in"}
ONSET = pd.Timestamp("2023-06-19")        # week containing Kolkata's 2023 monsoon onset (about 23 Jun; delayed, east India stalled until about 22 Jun)
SITRANG = pd.Timestamp("2022-10-24")      # Cyclone Sitrang landfall 24 Oct 2022, Diwali / Kali Puja week

# ------------------------------------------------------------------ 1. weather for the new year
def woy(w): return int(min(((w + pd.Timedelta(days=3)).dayofyear - 1) // 7, 51))
def clim(col, how="mean"):
    g = exr.groupby([woy(w) for w in exr.index])[col]
    s = (g.mean() if how == "mean" else g.median()).reindex(range(52)).interpolate(limit_direction="both")
    v = np.r_[s.values[-1], s.values, s.values[0]]
    return pd.Series(np.convolve(v, [0.25, 0.5, 0.25], mode="valid"), index=range(52))
cl = {c: clim(c, "median" if c == "rainfall_mm" else "mean") for c in ("rainfall_mm", "temp_max_c", "power_cut_hours", "dengue_index")}
# monsoon rain by week since onset (weeks 1..): mean of the three real seasons
onsets = {2024: "2024-05-20", 2025: "2025-06-30", 2026: "2026-05-25"}
prof = {}
for y, o in onsets.items():
    o = pd.Timestamp(o)
    for w, v in exr.loc[o:o + pd.Timedelta(weeks=20), "rainfall_mm"].items(): prof.setdefault((w - o).days // 7, []).append(v)
mon = pd.Series({k: np.mean(v) for k, v in prof.items() if k >= 1}).sort_index()
mon = pd.Series(np.convolve(np.r_[mon.values[0], mon.values, mon.values[-1]], [0.25, 0.5, 0.25], mode="valid"), index=mon.index)
rows = []
for w in NEW:
    k = (w - ONSET).days // 7; j = woy(w)
    if w >= ONSET and k <= 18:
        rain = 70.0 if k == 0 else float(mon.get(k, mon.iloc[-1]))
    else: rain = float(cl["rainfall_mm"][j])
    rain = max(rain * np.exp(rng.normal(0, 0.30)), 0.1)
    temp = cl["temp_max_c"][j] + rng.normal(0, 0.8); pcut = cl["power_cut_hours"][j] + rng.normal(0, 0.3); cyc = np.nan
    if pd.Timestamp("2023-06-05") <= w < ONSET: temp += 2.0; pcut += 1.5; rain *= 0.6          # monsoon stalled: heat stress in the east
    if w == SITRANG: rain, pcut, cyc = 125.0, 9.5, "Cyclone Sitrang (landfall 24-Oct-2022)"
    rows.append(dict(week_beginning=w, rainfall_mm=round(rain, 1), temp_max_c=round(min(temp, 40.4), 1), power_cut_hours=round(max(pcut, 2.0), 1),
                     heatwave_flag=float(temp >= 39.4), cyclone_event=cyc, dengue_index=round(max(cl["dengue_index"][j] * np.exp(rng.normal(0, 0.1)), 0), 3)))
nw = pd.DataFrame(rows).set_index("week_beginning")

# ------------------------------------------------------------------ 2. demand model
fest_real = ex.festival.to_dict(); fest_new = {w: cal.get(w) for w in NEW}
Xr, names = rm.design(RW, fest_real, exr); Xr = np.nan_to_num(Xr)
Xn, _ = rm.design(NEW, fest_new, nw); Xn = np.nan_to_num(Xn)
noT = [i for i, n in enumerate(names) if n != "trend"]
base = d[d.is_new_product == 0].copy(); base["series"] = base.reporting_level.str[:3] + "|" + base.depot_code + "|" + base.product_code
Y = np.log1p(base.pivot(index="week_beginning", columns="series", values="primary_sales_units").reindex(RW))
cat = base.drop_duplicates("series").set_index("series").product_category
shock = np.array([w.strftime("%Y-%m-%d") in rm.MON_SHOCK for w in RW])
valid = pd.DataFrame(True, index=RW, columns=Y.columns)
for s in Y.columns:
    if s.split("|")[2] in rm.MON_SKUS: valid.loc[shock, s] = False                 # the 2025 delayed-monsoon shock is not seasonality
fold = np.where(RW < "2024-10-01", 0, np.where(RW < "2025-10-01", 1, 2))
nat = [c for c in Y.columns if c.startswith("Nat")]
Yd = Y[nat] - Y[nat].where(valid[nat]).mean()
Yd = Yd.where(valid[nat])
C = Yd.T.groupby(cat[nat]).mean().T
ALPHA, MIN_R2 = 3.0, 0.05
pen = rm.penalty(names, ALPHA)
beta, use = {}, {}
print("category: out-of-sample shape R2 (leave-one-year-out) -> used")
for k in C.columns:
    y = C[k].values.astype(float); er, vr = [], []
    for f in range(3):
        tr = (fold != f) & ~np.isnan(y); te = (fold == f) & ~np.isnan(y)
        b = rm.ridge(Xr[tr], y[tr], np.ones(tr.sum()), pen); p = rm.predict(b, Xr[te])
        er.append(np.mean(((y[te] - y[te].mean()) - (p - p.mean())) ** 2)); vr.append(np.var(y[te]))
    r2 = 1 - np.mean(er) / np.mean(vr); use[k] = r2 >= MIN_R2
    ok = ~np.isnan(y); beta[k] = rm.ridge(Xr[ok], y[ok], np.ones(ok.sum()), pen)
    print(f"  {k[:40]:40s} {r2:6.2f} -> {'season, festivals, weather' if use[k] else 'trend only'}")

def cat_eff(k, X):                                             # effect of everything except the trend, zero when the category is trend-only
    return (X[:, noT] @ beta[k][1:][noT]) if use[k] else np.zeros(len(X))
cen = {k: cat_eff(k, Xr).mean() for k in C.columns}
tr_r = Xr[:, names.index("trend")]; tr_n = Xn[:, names.index("trend")]
LOGCAP = np.log(1.2)
cyc_w = [i for i, w in enumerate(RW) if isinstance(exr.cyclone_event.get(w), str)]
bad = np.zeros(len(RW), bool)
for i in cyc_w: bad[max(i - 1, 0): i + 2] = True                      # cyclone weeks and their neighbours are real events, not noise to replay at random
starts = [i for i in range(len(RW) - 3) if not bad[i: i + 3].any()]
tau = np.concatenate([np.arange(s, s + 3) for s in rng.choice(starts, size=int(np.ceil(len(NEW) / 3)))])[: len(NEW)]   # 3-week blocks, shared by all series
fit_real, fit_new, ynew = {}, {}, {}
for s in Y.columns:
    k = cat[s]; ok = valid[s].values & ~np.isnan(Y[s].values)
    er = cat_eff(k, Xr) - cen[k]; en = cat_eff(k, Xn) - cen[k]
    A = np.column_stack([np.ones(ok.sum()), tr_r[ok]]); a, b = np.linalg.lstsq(A, Y[s].values[ok] - er[ok], rcond=None)[0]
    u = np.where(ok, Y[s].values - er - a - b * tr_r, 0.0)
    fit_real[s] = a + b * tr_r + er
    fit_new[s] = a + np.clip(0.6 * b * tr_n, -LOGCAP, LOGCAP) + en
    ynew[s] = np.maximum(fit_new[s] + u[tau], 0.0)
fit_real = pd.DataFrame(fit_real, index=RW); fit_new = pd.DataFrame(fit_new, index=NEW); ynew = pd.DataFrame(ynew, index=NEW)

# ------------------------------------------------------------------ 3. rows: template week per new week
def keys(s): return rm.keys(s)
real_fest = {w: keys(fest_real.get(w)) for w in RW}
DUR_N, DIW_N = [pd.Timestamp("2022-09-26")], [pd.Timestamp("2022-10-24")]
DUR_T, DIW_T = pd.Timestamp("2023-10-16"), pd.Timestamp("2023-11-06")
def tmpl(w):
    od = (w - DUR_N[0]).days // 7
    if -6 <= od <= 8:
        ow = (w - DIW_N[0]).days // 7
        return (DUR_T + pd.Timedelta(weeks=od)) if abs(od) <= abs(ow) else (DIW_T + pd.Timedelta(weeks=ow))
    for kk in keys(cal.get(w)):
        for j in range(40, 65):
            t = w + pd.Timedelta(weeks=j)
            if kk in real_fest.get(t, []): return t
    return max(w + pd.Timedelta(weeks=52), W0)
mp = pd.DataFrame({"week_beginning": NEW, "tw": [tmpl(w) for w in NEW]})
assert mp.tw.min() >= W0 and mp.tw.max() <= RW.max()
mp["u"] = np.arange(len(NEW)) / (len(NEW) - 1)
x = mp.merge(base.drop(columns=["series"]).rename(columns={"week_beginning": "tw"}), on="tw", how="inner")
x["series"] = x.reporting_level.str[:3] + "|" + x.depot_code + "|" + x.product_code
orig = x.copy()
yn = np.array([np.expm1(ynew.at[w, s]) for w, s in zip(x.week_beginning, x.series)])
yht = np.array([np.expm1(fit_real.at[t, s]) for t, s in zip(x.tw, x.series)])
yhn = np.array([np.expm1(fit_new.at[w, s]) for w, s in zip(x.week_beginning, x.series)])
yt = orig.primary_sales_units.values
den = np.where(yt >= 0.3 * yht, yt, yht)
x["f"] = np.clip(yn / np.maximum(den, 1.0), 0.15, 6.0)
x["fb"] = np.clip(yhn / np.maximum(yht, 1.0), 0.4, 2.5)

UNIT_F = ["sales_forecast_3m_ahead_units", "sales_forecast_2m_ahead_units", "sales_forecast_1m_ahead_units", "consensus_forecast_1m_ahead_units",
          "procurement_request_units", "orders_received_units", "open_orders_units", "secondary_sales_units",
          "primary_sales_b2b_p1_units", "primary_sales_b2b_p2_units", "unfulfilled_b2c_units", "unfulfilled_b2b_p1_units", "unfulfilled_b2b_p2_units",
          "production_required_units", "production_allocated_units", "replenishment_ordered_units", "replenishment_received_units",
          "safety_stock_units", "reorder_point_units", "purchase_order_units", "transfer_out_units", "transfer_in_units", "lost_sales_units",
          "quick_commerce_ordered_units", "quick_commerce_delivered_units", "quick_commerce_order_lines", "quick_commerce_lines_on_time",
          "quick_commerce_lines_in_full", "quick_commerce_lines_otif", "quick_commerce_partner_sell_out_units", "quick_commerce_partner_stock_units",
          "quick_commerce_returned_units"]
for c in UNIT_F: x[c] = (orig[c] * x.f).round()
x["primary_sales_units"] = np.round(yn)
x["budget_units"] = (orig.budget_units * x.fb).round()
x["primary_sales_b2c_units"] = x.primary_sales_units - x.primary_sales_b2b_p1_units - x.primary_sales_b2b_p2_units
neg = x.primary_sales_b2c_units < 0
x.loc[neg, "primary_sales_b2b_p1_units"] = (x.loc[neg, "primary_sales_units"] * 0.2).round()
x.loc[neg, "primary_sales_b2b_p2_units"] = (x.loc[neg, "primary_sales_units"] * 0.2).round()
x["primary_sales_b2c_units"] = x.primary_sales_units - x.primary_sales_b2b_p1_units - x.primary_sales_b2b_p2_units
# prices drift backwards: the series' own first-week ASP over its ASP one year later
asp = base.pivot_table(index="week_beginning", columns=["depot_code", "product_code"], values="average_selling_price_inr")
pf = (asp.loc[W0] / asp.loc[W0 + pd.Timedelta(weeks=52)]).clip(1.0, 1.12)
x["pf"] = [pf.get((a, b), 1.05) for a, b in zip(x.depot_code, x.product_code)]
x["average_selling_price_inr"] = (orig.average_selling_price_inr * x.pf).round(2)
for c in ("standard_cost_inr", "purchase_unit_cost_paid_inr", "supplier_price_break_unit_cost_inr"): x[c] = (orig[c] * x.pf).round(1)
x["primary_sales_value_inr"] = (x.primary_sales_units * x.average_selling_price_inr * (1 - x.trade_scheme_discount_pct / 100)).round()
x["trade_scheme_spend_inr"] = (x.primary_sales_units * x.average_selling_price_inr * x.trade_scheme_discount_pct / 100).round()
x["budget_value_inr"] = (x.budget_units * x.average_selling_price_inr).round()
x["lost_sales_value_inr"] = (x.lost_sales_units * x.average_selling_price_inr).round()
x["transfer_freight_cost_inr"] = (orig.transfer_freight_cost_inr * x.f).round()
x["depot_stock_value_inr_lakh"] = (orig.depot_stock_value_inr_lakh * x.f * x.pf).round(2)
x["plant_capacity_units"] = (orig.plant_capacity_units * 0.93).round()
for c in [c for c in COLS if c.startswith("quick_commerce")]: x[c] = np.nan             # no quick commerce before 2025
x["festival"] = x.week_beginning.map(cal)
x["festival_sell_in_period"] = x.week_beginning.map(SELL)
for c in ("event_note", "competitor_activity_note", "forecast_override_reason"): x[c] = np.nan
x["influencer_campaign_active"] = 0.0; x["influencer_spend_inr_lakh"] = 0.0; x["influencer_reach_thousands"] = 0.0; x["influencer_test_control_group"] = "No campaign"
x["launch_date"] = np.nan; x["planned_launch_date"] = np.nan

# ------------------------------------------------------------------ ledgers rebuilt backwards from the first real week (identities hold exactly)
first = d[d.week_beginning == W0].set_index(["depot_code", "product_code"])
x = x.sort_values(["depot_code", "product_code", "week_beginning"]).reset_index(drop=True)
for (dc, pc), grp in x.groupby(["depot_code", "product_code"], sort=False):
    idx = grp.index[::-1]; r0 = first.loc[(dc, pc)]
    S = r0.distributor_stock_units - r0.primary_sales_units + r0.secondary_sales_units
    C_ = r0.opening_stock_units
    for i in idx:
        P, Sec = x.at[i, "primary_sales_units"], x.at[i, "secondary_sales_units"]
        lb = 0.3 * max(S, 1); Sp = max(S - P + Sec, lb)
        x.at[i, "distributor_stock_units"] = S; x.at[i, "secondary_sales_units"] = max(Sp - S + P, 0); S = Sp
        R = x.at[i, "replenishment_received_units"]; Op = max(C_ - R + P, 0.3 * max(C_, 1)); R = C_ - Op + P
        x.at[i, "closing_stock_units"], x.at[i, "opening_stock_units"] = C_, Op
        x.at[i, "replenishment_received_units"] = max(R, 0); x.at[i, "replenishment_ordered_units"] = max(R, 0); C_ = Op
for c in ("secondary_sales_units", "distributor_stock_units", "opening_stock_units", "closing_stock_units", "replenishment_received_units", "replenishment_ordered_units"):
    x[c] = x[c].round()

new = x[COLS].copy()
out = pd.concat([new, d], ignore_index=True).sort_values(["week_beginning", "reporting_level", "depot_code", "product_code"], kind="stable").reset_index(drop=True)
out.to_csv("eveready_mock_data_v2_ext.csv", index=False)

# ------------------------------------------------------------------ external factors for the new weeks
rows = []
for w in NEW:
    t = max(w + pd.Timedelta(weeks=52), W0); r = ex.loc[t].copy(); u = (w - NEW[0]).days / ((NEW[-1] - NEW[0]).days)
    for c in ("temp_max_c", "rainfall_mm", "power_cut_hours", "heatwave_flag", "cyclone_event", "dengue_index"): r[c] = nw.at[w, c]
    for c in ("zinc_price_inr_per_kg", "rural_income_index", "led_price_index"):
        j = ex.loc[W0, c] / ex.loc[W0 + pd.Timedelta(weeks=52), c]; r[c] = round(r[c] * j ** u * np.exp(rng.normal(0, 0.006)), 3)
    r["is_forecast_week"] = 0
    for c in e.columns:
        if c.startswith("expected_"): r[c] = np.nan
    r["outage_pressure_index"] = np.nan
    r["festival"] = cal.get(w, np.nan); r["festival_sell_in_period"] = SELL.get(w, np.nan); r["week_beginning"] = w; rows.append(r)
ne = pd.DataFrame(rows)[list(e.columns)]
pd.concat([ne, e], ignore_index=True).sort_values("week_beginning").to_csv("ext_ext.csv", index=False)
print("new rows", len(new), "total", len(out), "series", new.groupby(["depot_code", "product_code"]).ngroups)
