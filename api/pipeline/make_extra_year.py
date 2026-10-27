"""Builds ONE extra year of history BEFORE the user's 91-column v2 file (synthetic) -> new files, original untouched.

 in : eveready_mock_data_v2.csv  (2023-10-02 .. 2026-09-28)      ext.csv
 out: eveready_mock_data_v2_ext.csv (2022-09-26 .. 2026-09-28)    ext_ext.csv

Method: each new week borrows the row of the same series from the matching week of Oct 2023 - Sep 2024
(52 weeks later; inside the Durga Puja / Diwali stretch, the week at the same distance from the festival, using 2024's festival).
Volumes are scaled by a category trend (damped inverse of the observed year-on-year change, bent to join the real data without a jump)
and a random shock; prices follow their own downward drift backwards; ledgers (distributor stock, depot opening/closing stock)
are rebuilt backwards from the first real week so the identities hold exactly. New-product series are not created.
"""
import numpy as np, pandas as pd

rng = np.random.default_rng(2022)
d = pd.read_csv("eveready_mock_data_v2.csv", low_memory=False, parse_dates=["week_beginning"])
e = pd.read_csv("ext.csv", parse_dates=["week_beginning"])
COLS = list(d.columns)
W0 = pd.Timestamp("2023-10-02")
NEW = pd.date_range("2022-09-26", "2023-09-25", freq="7D")             # 53 weeks
DUR_N, DIW_N = [pd.Timestamp("2022-09-26"), pd.Timestamp("2023-10-16")], [pd.Timestamp("2022-10-24"), pd.Timestamp("2023-11-06")]
DUR_T, DIW_T = pd.Timestamp("2024-10-07"), pd.Timestamp("2024-10-28")

def tmpl(w):
    best = None
    for dn, wn in zip(DUR_N, DIW_N):
        od = (w - dn).days // 7
        if -6 <= od <= 8:
            ow = (w - wn).days // 7
            best = (DUR_T + pd.Timedelta(weeks=od)) if abs(od) <= abs(ow) else (DIW_T + pd.Timedelta(weeks=ow))
    return best if best is not None else w + pd.Timedelta(weeks=52)
mp = pd.DataFrame({"week_beginning": NEW, "tw": [tmpl(w) for w in NEW]})
assert mp.tw.min() >= W0 and mp.tw.max() <= pd.Timestamp("2025-09-29")
mp["u"] = np.arange(len(NEW)) / (len(NEW) - 1)                           # 0 at start .. 1 at the join

# ---- rows: every non-new-product series, borrowed from the template week
base = d[d.is_new_product == 0]
x = mp.merge(base.rename(columns={"week_beginning": "tw"}), on="tw", how="inner")
x = x.rename(columns={"week_beginning": "week_beginning"})
x["series"] = x.depot_code + "|" + x.product_code

# ---- category trend: damped inverse of the observed year-on-year change
nat = d[d.reporting_level == "National"].copy()
nat["y"] = np.where(nat.week_beginning < "2024-10-01", 1, np.where(nat.week_beginning < "2025-10-01", 2, 3))
g = nat.groupby(["product_category", "y"]).primary_sales_units.sum().unstack()
G = (1 / (g[2] / g[1]) ** 0.7).clip(0.85, 1.2).to_dict()
x["G"] = x.product_category.map(G)
# common weekly shock per category + independent shock per row
cw = {k: rng.normal(0, 0.03, len(NEW)) for k in G}
x["wi"] = x.week_beginning.map({w: i for i, w in enumerate(NEW)})
x["eps"] = np.exp(rng.normal(0, 0.05, len(x)) + np.array([cw[c][i] for c, i in zip(x.product_category, x.wi)]))

# price drift backwards: the series' own first-week ASP over its ASP one year later
asp = base.pivot_table(index="week_beginning", columns=["depot_code", "product_code"], values="average_selling_price_inr")
pf = (asp.loc[W0] / asp.loc[W0 + pd.Timedelta(weeks=52)]).clip(1.0, 1.12)
x["pf"] = [pf.get((a, b), 1.05) for a, b in zip(x.depot_code, x.product_code)]

# ---- continuity: bend each category so the last new weeks join the first real weeks
def level(df, col, w_lo, w_hi):
    s = df[(df.week_beginning >= w_lo) & (df.week_beginning <= w_hi) & (df.reporting_level == "National")]
    return s.groupby("product_category")[col].sum()
x["f0"] = x.G * x.eps
tail = x[(x.week_beginning >= NEW[-6]) & (x.reporting_level == "National")].assign(v=lambda t: t.primary_sales_units * t.f0).groupby("product_category").v.sum() / 6
head = d[(d.week_beginning < W0 + pd.Timedelta(weeks=6)) & (d.reporting_level == "National")].groupby("product_category").primary_sales_units.sum() / 6
q = (head / tail).clip(0.7, 1.4)
x["m"] = [q[c] ** u for c, u in zip(x.product_category, x.u)]
x["f"] = x.G * x.m * x.eps                  # actual-flow factor
x["fb"] = x.G * x.m                         # budget factor (no shock)

UNIT_F = ["sales_forecast_3m_ahead_units", "sales_forecast_2m_ahead_units", "sales_forecast_1m_ahead_units", "consensus_forecast_1m_ahead_units",
          "procurement_request_units", "orders_received_units", "open_orders_units", "primary_sales_units", "secondary_sales_units",
          "primary_sales_b2b_p1_units", "primary_sales_b2b_p2_units", "unfulfilled_b2c_units", "unfulfilled_b2b_p1_units", "unfulfilled_b2b_p2_units",
          "production_required_units", "production_allocated_units", "replenishment_ordered_units", "replenishment_received_units",
          "safety_stock_units", "reorder_point_units", "purchase_order_units", "transfer_out_units", "transfer_in_units", "lost_sales_units",
          "quick_commerce_ordered_units", "quick_commerce_delivered_units", "quick_commerce_order_lines", "quick_commerce_lines_on_time",
          "quick_commerce_lines_in_full", "quick_commerce_lines_otif", "quick_commerce_partner_sell_out_units", "quick_commerce_partner_stock_units",
          "quick_commerce_returned_units"]
orig = x.copy()
for c in UNIT_F: x[c] = (orig[c] * x.f).round()
x["budget_units"] = (orig.budget_units * x.fb).round()
x["primary_sales_b2c_units"] = x.primary_sales_units - x.primary_sales_b2b_p1_units - x.primary_sales_b2b_p2_units
neg = x.primary_sales_b2c_units < 0                                   # keep the channel split adding up
x.loc[neg, "primary_sales_b2b_p1_units"] = (x.loc[neg, "primary_sales_units"] * 0.2).round()
x.loc[neg, "primary_sales_b2b_p2_units"] = (x.loc[neg, "primary_sales_units"] * 0.2).round()
x["primary_sales_b2c_units"] = x.primary_sales_units - x.primary_sales_b2b_p1_units - x.primary_sales_b2b_p2_units
# prices and values
x["average_selling_price_inr"] = (orig.average_selling_price_inr * x.pf).round(2)
for c in ("standard_cost_inr", "purchase_unit_cost_paid_inr", "supplier_price_break_unit_cost_inr"): x[c] = (orig[c] * x.pf).round(1)
x["primary_sales_value_inr"] = (x.primary_sales_units * x.average_selling_price_inr * (1 - x.trade_scheme_discount_pct / 100)).round()
x["trade_scheme_spend_inr"] = (x.primary_sales_units * x.average_selling_price_inr * x.trade_scheme_discount_pct / 100).round()
x["budget_value_inr"] = (x.budget_units * x.average_selling_price_inr).round()
x["lost_sales_value_inr"] = (x.lost_sales_units * x.average_selling_price_inr).round()
x["transfer_freight_cost_inr"] = (orig.transfer_freight_cost_inr * x.f).round()
x["depot_stock_value_inr_lakh"] = (orig.depot_stock_value_inr_lakh * x.f * x.pf).round(2)
# plant capacity: same pattern, slightly lower (capacity grows year on year in the real data)
x["plant_capacity_units"] = (orig.plant_capacity_units * 0.93).round()
# before QC listings and weeks-since-listing do not exist
for c in [c for c in COLS if c.startswith("quick_commerce")]: x[c] = np.nan
# festival labels from the real calendar for the new year; sell-in label follows the aligned template week
CAL = {"2022-09-26": "Durga Puja (Shashthi–Saptami)", "2022-10-03": "Durga Puja (Ashtami–Dashami); Kojagari Lakshmi Puja",
       "2022-10-24": "Kali Puja / Diwali; Bhai Phonta", "2022-10-31": "Jagaddhatri Puja (Chandannagar)", "2022-12-19": "Christmas / Park Street festival",
       "2023-01-09": "Gangasagar Mela", "2023-01-23": "Saraswati Puja", "2023-01-30": "Kolkata International Book Fair", "2023-03-06": "Dol Jatra / Holi",
       "2023-04-10": "Chaitra Sale (Choitro Sankranti); Poila Baisakh (Bengali New Year, Halkhata)", "2023-04-17": "Eid ul-Fitr",
       "2023-06-12": "Jamai Sasthi", "2023-06-19": "Rath Yatra", "2023-09-11": "Vishwakarma Puja", "2023-09-18": "Ganesh Chaturthi"}
cal = {pd.Timestamp(k): v for k, v in CAL.items()}
x["festival"] = x.week_beginning.map(cal)
x["launch_date"] = np.nan; x["planned_launch_date"] = np.nan

# ---- ledgers rebuilt backwards from the first real week (identities hold exactly)
first = d[d.week_beginning == W0].set_index(["depot_code", "product_code"])
x = x.sort_values(["depot_code", "product_code", "week_beginning"]).reset_index(drop=True)
for (dc, pc), grp in x.groupby(["depot_code", "product_code"], sort=False):
    idx = grp.index[::-1]
    r0 = first.loc[(dc, pc)]
    S = r0.distributor_stock_units - r0.primary_sales_units + r0.secondary_sales_units          # stock at end of last new week
    C = r0.opening_stock_units                                                                  # closing stock of last new week
    for i in idx:
        P, Sec = x.at[i, "primary_sales_units"], x.at[i, "secondary_sales_units"]
        lb = 0.3 * max(S, 1)
        Sp = max(S - P + Sec, lb)
        x.at[i, "distributor_stock_units"] = S
        x.at[i, "secondary_sales_units"] = max(Sp - S + P, 0)
        S = Sp
        R = x.at[i, "replenishment_received_units"]
        Op = max(C - R + P, 0.3 * max(C, 1))
        R = C - Op + P
        x.at[i, "closing_stock_units"], x.at[i, "opening_stock_units"] = C, Op
        x.at[i, "replenishment_received_units"] = max(R, 0)
        x.at[i, "replenishment_ordered_units"] = max(R, 0)
        C = Op
x["secondary_sales_units"] = x.secondary_sales_units.round(); x["distributor_stock_units"] = x.distributor_stock_units.round()
x["opening_stock_units"] = x.opening_stock_units.round(); x["closing_stock_units"] = x.closing_stock_units.round()
x["replenishment_received_units"] = x.replenishment_received_units.round(); x["replenishment_ordered_units"] = x.replenishment_ordered_units.round()

new = x[COLS].copy()
out = pd.concat([new, d], ignore_index=True).sort_values(["week_beginning", "reporting_level", "depot_code", "product_code"], kind="stable").reset_index(drop=True)
out.to_csv("eveready_mock_data_v2_ext.csv", index=False)

# ---- external factors for the new weeks
ex = e.set_index("week_beginning")
rows = []
for w in NEW:
    t = max(w + pd.Timedelta(weeks=52), W0); r = ex.loc[t].copy(); u = (w - NEW[0]).days / ((NEW[-1] - NEW[0]).days)
    r["temp_max_c"] = round(r.temp_max_c + rng.normal(0, 0.8), 1)
    r["rainfall_mm"] = round(max(r.rainfall_mm * np.exp(rng.normal(0, 0.3)), 0), 1)
    r["power_cut_hours"] = round(max(r.power_cut_hours + rng.normal(0, 0.3), 0), 1)
    r["dengue_index"] = round(max(r.dengue_index * np.exp(rng.normal(0, 0.1)), 0), 3)
    for c in ("zinc_price_inr_per_kg", "rural_income_index", "led_price_index"):
        j = ex.loc[W0, c] / ex.loc[W0 + pd.Timedelta(weeks=52), c]; r[c] = round(r[c] * j ** u * np.exp(rng.normal(0, 0.006)), 3)
    r["is_forecast_week"] = 0
    for c in e.columns:
        if c.startswith("expected_"): r[c] = np.nan
    r["festival"] = cal.get(w, np.nan)
    sell = x[x.week_beginning == w].festival_sell_in_period.dropna()
    r["festival_sell_in_period"] = d[d.week_beginning == tmpl(w)].festival_sell_in_period.dropna().iloc[0] if len(d[(d.week_beginning == tmpl(w))].festival_sell_in_period.dropna()) else np.nan
    r["week_beginning"] = w; rows.append(r)
ne = pd.DataFrame(rows)[list(e.columns)]
pd.concat([ne, e], ignore_index=True).sort_values("week_beginning").to_csv("ext_ext.csv", index=False)
print("new rows", len(new), "total", len(out), "series", new.groupby(["depot_code", "product_code"]).ngroups)
