"""Appends SYNTHETIC actuals for the weeks of 5, 12 and 19 Oct 2026 (the data now runs to 25 Oct) to eveready_mock_data_v2_ext.csv and ext_ext.csv.

Nothing here is observed. The weeks are simulated from the file's own history so that the whole pipeline can be exercised on the new cut-off:
  * Durga Puja hike: for each series, sales in the weeks around the Puja are the pre-festival level (mean of weeks a-12..a-5, a = week of
    Mahalaya / first Puja week, 12 Oct 2026) times the ratio seen in the same weeks of 2023, 2024 and 2025 (median of the three years,
    blended 50/50 with the median of the same category), with 7% random noise.   Offsets: 5 Oct = a-1, 12 Oct = a, 19 Oct = a+1.
  * Every other column is rebuilt from that sales number with the file's own identities: closing = opening + received - sales,
    distributor stock = previous + primary - secondary, order lines and OTIF shares from the last 8 weeks (a little worse in the hike weeks).
  * Budget, the sales team's M3/M2/M1 forecasts, override reasons and procurement requests are the ones already submitted for those weeks
    (eveready_mock_data_v3.csv forward weeks), so what the sales team said stays what it said.
  * Weather: the expected values plus noise.
Re-runnable only on the original file: it refuses if 2026-10-05 is already there. Originals are copied to bk_pre_oct/ first.
Run order afterwards: make_qc_lines.py, add_qc_cols.py (rebuilds the qc_line_* columns), then fill_v3_forward.py is NOT needed (build_pending handles it)."""
import os, shutil, numpy as np, pandas as pd
rng = np.random.default_rng(2610)
F, E, V3 = "eveready_mock_data_v2_ext.csv", "ext_ext.csv", "eveready_mock_data_v3.csv"
NEW = [pd.Timestamp(x) for x in ("2026-10-05", "2026-10-12", "2026-10-19")]
OFF = {NEW[0]: -1, NEW[1]: 0, NEW[2]: 1}
ANCH = {2023: "2023-10-16", 2024: "2024-10-07", 2025: "2025-09-29"}; A26 = pd.Timestamp("2026-10-12")
d = pd.read_csv(F, low_memory=False, parse_dates=["week_beginning"])
assert NEW[0] not in set(d.week_beginning), "already appended"
os.makedirs("bk_pre_oct", exist_ok=True)
for f in (F, E): shutil.copyfile(f, "bk_pre_oct/" + f)
v3 = pd.read_csv(V3, low_memory=False, parse_dates=["week_beginning"])
ext = pd.read_csv(E, parse_dates=["week_beginning"])
d["key"] = d.reporting_level.str[:3] + "|" + d.depot_code + "|" + d.product_code
v3["key"] = v3.reporting_level.str[:3] + "|" + v3.depot_code + "|" + v3.product_code
G = {k: g.sort_values("week_beginning").reset_index(drop=True) for k, g in d.groupby("key")}
last_w = d.week_beginning.max(); assert last_w == pd.Timestamp("2026-09-28")
keys = [k for k, g in G.items() if g.week_beginning.iloc[-1] == last_w]

# ---------------------------------------------------------------- Puja ratios
def prof(g):
    s = g.set_index("week_beginning").primary_sales_units; out = {}
    for y, a in ANCH.items():
        a = pd.Timestamp(a); L = s.loc[a - pd.Timedelta(weeks=12): a - pd.Timedelta(weeks=5)].mean()
        if not np.isfinite(L) or L <= 0 or a - pd.Timedelta(weeks=12) < s.index[0]: continue
        for o in (-1, 0, 1):
            w = a + pd.Timedelta(weeks=o)
            if w in s.index: out.setdefault(o, []).append(s[w] / L)
    return out
P = {k: prof(G[k]) for k in keys}
cat = {k: G[k].product_category.iloc[0] for k in keys}
catmed = {}
for k in keys:
    for o, v in P[k].items(): catmed.setdefault((k[:3], cat[k], o), []).extend(v)
catmed = {c: float(np.median(v)) for c, v in catmed.items()}
def ratio(k, o):
    own = P[k].get(o)
    c = catmed.get((k[:3], cat[k], o))
    if own and len(own) >= 2 and c: return float(np.exp(0.5 * np.log(np.median(own)) + 0.5 * np.log(c)))
    if own and len(own) >= 2: return float(np.median(own))
    return c if c else 1.0

# ---------------------------------------------------------------- weeks
wx = ext.set_index("week_beginning")
rows = []
v3i = v3[v3.week_beginning.isin(NEW)].set_index(["key", "week_beginning"])
for k in keys:
    g = G[k]; s = g.primary_sales_units
    L = s.loc[(g.week_beginning >= A26 - pd.Timedelta(weeks=12)) & (g.week_beginning <= A26 - pd.Timedelta(weeks=5))].mean()
    prev = g.iloc[-1].copy(); hist = g.tail(8); h4 = g.tail(4)
    s4 = float(h4.primary_sales_units.mean()); frac = lambda c: float((hist[c] / hist.primary_sales_units.clip(lower=1)).mean())
    share = {c: float((h4[c] / h4.primary_sales_units.clip(lower=1)).mean()) for c in ("primary_sales_b2b_p1_units", "primary_sales_b2b_p2_units")}
    nat = k.startswith("Nat"); qc = pd.notna(prev.quick_commerce_ordered_units)
    for w in NEW:
        r = ratio(k, OFF[w]); S = float(max(round(L * r * np.exp(rng.normal(0, 0.07))), 1)); surge = S / s4
        x = prev.copy(); x["week_beginning"] = w
        v = v3i.loc[(k, w)] if (k, w) in v3i.index else None
        for c in ("budget_units", "budget_value_inr", "sales_forecast_3m_ahead_units", "sales_forecast_2m_ahead_units", "sales_forecast_1m_ahead_units",
                  "consensus_forecast_1m_ahead_units", "forecast_override_reason", "procurement_request_units"):
            x[c] = v[c] if v is not None else np.nan
        x["festival"] = wx.at[w, "festival"]; x["festival_sell_in_period"] = wx.at[w, "festival_sell_in_period"]
        x["competitor_activity_note"] = np.nan; x["event_note"] = np.nan
        x["primary_sales_units"] = S; x["primary_sales_value_inr"] = round(S * prev.average_selling_price_inr)
        p1 = round(S * share["primary_sales_b2b_p1_units"]); p2 = round(S * share["primary_sales_b2b_p2_units"])
        x["primary_sales_b2b_p1_units"] = p1; x["primary_sales_b2b_p2_units"] = p2; x["primary_sales_b2c_units"] = S - p1 - p2
        for c in ("unfulfilled_b2c_units", "unfulfilled_b2b_p1_units", "unfulfilled_b2b_p2_units", "lost_sales_units", "lost_sales_value_inr",
                  "transfer_out_units", "transfer_in_units", "transfer_freight_cost_inr"): x[c] = 0.0
        x["lost_sales_driver"] = np.nan; x["transfer_counterparty_depot"] = np.nan
        x["orders_received_units"] = S; x["open_orders_units"] = round(S * frac("open_orders_units"))
        sec = float(h4.secondary_sales_units.mean()) * surge ** 0.85 * np.exp(rng.normal(0, 0.05)); x["secondary_sales_units"] = round(sec)
        x["distributor_stock_units"] = max(prev.distributor_stock_units + S - round(sec), 0)
        rec = round(S * float(np.clip(frac("replenishment_received_units"), 0.85, 1.25)))
        opening = prev.closing_stock_units
        if opening + rec - S < 0.4 * prev.safety_stock_units: rec = round(0.4 * prev.safety_stock_units - opening + S)
        x["opening_stock_units"] = opening; x["replenishment_received_units"] = rec; x["replenishment_ordered_units"] = rec
        x["production_required_units"] = rec; x["production_allocated_units"] = rec; x["closing_stock_units"] = opening + rec - S
        sf = 0.5 + 0.5 * S / max(prev.primary_sales_units, 1); x["safety_stock_units"] = round(prev.safety_stock_units * sf)
        x["reorder_point_units"] = round(prev.reorder_point_units * sf)
        if pd.notna(prev.depot_stock_value_inr_lakh): x["depot_stock_value_inr_lakh"] = round(prev.depot_stock_value_inr_lakh * x["closing_stock_units"] / max(prev.closing_stock_units, 1), 2)
        x["trade_scheme_spend_inr"] = round(prev.trade_scheme_spend_inr * x["primary_sales_value_inr"] / max(prev.primary_sales_value_inr, 1))
        if nat:
            x["purchase_order_units"] = x["procurement_request_units"] if pd.notna(x["procurement_request_units"]) else round(rec * 1.0)
            x["plant_capacity_units"] = prev.plant_capacity_units
        if qc:
            so = float(h4.quick_commerce_partner_sell_out_units.mean()) * surge ** 0.9 * np.exp(rng.normal(0, 0.08))
            fr = lambda c, b: float((hist[c] / hist[b].clip(lower=1)).mean())
            O = so * fr("quick_commerce_ordered_units", "quick_commerce_partner_sell_out_units") * np.exp(rng.normal(0, 0.06))
            Lc = max(round(float(h4.quick_commerce_order_lines.mean()) * surge ** 0.8 * np.exp(rng.normal(0, 0.05))), 1)
            hit = 0.03 if surge > 1.15 else 0.0                           # a busy week costs a little service
            D = O * float(np.clip(fr("quick_commerce_delivered_units", "quick_commerce_ordered_units") - hit / 2, 0.5, 1.0))
            ot = round(Lc * float(np.clip(fr("quick_commerce_lines_on_time", "quick_commerce_order_lines") - hit + rng.normal(0, 0.02), 0.2, 1)))
            inf = round(Lc * float(np.clip(fr("quick_commerce_lines_in_full", "quick_commerce_order_lines") - hit / 2 + rng.normal(0, 0.02), 0.2, 1)))
            of = round(Lc * float(np.clip(fr("quick_commerce_lines_otif", "quick_commerce_order_lines") - hit + rng.normal(0, 0.02), 0, 1)))
            of = int(min(max(of, max(0, ot + inf - Lc)), min(ot, inf)))
            x["quick_commerce_partner_sell_out_units"] = max(round(so), 1); x["quick_commerce_ordered_units"] = max(round(O), 1)
            x["quick_commerce_delivered_units"] = round(min(D, round(O))); x["quick_commerce_order_lines"] = Lc
            x["quick_commerce_lines_on_time"] = ot; x["quick_commerce_lines_in_full"] = inf; x["quick_commerce_lines_otif"] = of
            x["quick_commerce_partner_stock_units"] = round(float(h4.quick_commerce_partner_stock_units.mean()) * surge ** 0.5)
            x["quick_commerce_returned_units"] = round(float(h4.quick_commerce_returned_units.mean()) * np.exp(rng.normal(0, 0.15)))
            x["quick_commerce_weeks_since_listing"] = prev.quick_commerce_weeks_since_listing + 1
        for c in [c for c in d.columns if c.startswith("qc_line_")]: x[c] = np.nan
        rows.append(x); prev = x; h4 = pd.concat([h4.iloc[1:], x.to_frame().T]).infer_objects(); hist = pd.concat([hist.iloc[1:], x.to_frame().T]).infer_objects()
        s4 = float(h4.primary_sales_units.astype(float).mean())
new = pd.DataFrame(rows)[d.columns].drop(columns="key")
out = pd.concat([d.drop(columns="key"), new], ignore_index=True)
out["week_beginning"] = pd.to_datetime(out.week_beginning)
out = out.sort_values(["week_beginning", "reporting_level", "depot_code", "product_code"], kind="stable").reset_index(drop=True)
out["week_beginning"] = out.week_beginning.dt.strftime("%Y-%m-%d")
out.to_csv(F, index=False)

# ---------------------------------------------------------------- weather and the other drivers: these weeks are now actuals
for w in NEW:
    i = ext.index[ext.week_beginning == w][0]
    ext.at[i, "is_forecast_week"] = 0
    ext.at[i, "temp_max_c"] = round(ext.at[i, "expected_temp_max_c"] + rng.normal(0, 0.8), 1)
    ext.at[i, "rainfall_mm"] = round(max(ext.at[i, "expected_rainfall_mm"] * np.exp(rng.normal(0, 0.30)), 0.1), 1)
    ext.at[i, "power_cut_hours"] = round(max(ext.at[i, "expected_power_cut_hours"] + rng.normal(0, 0.3), 2.0), 1)
    ext.at[i, "heatwave_flag"] = float(ext.at[i, "temp_max_c"] >= 39.4); ext.at[i, "outage_pressure_index"] = 0.0
    ext.at[i, "dengue_index"] = round(ext.at[i, "expected_dengue_index"] * np.exp(rng.normal(0, 0.1)), 3)
    ext.at[i, "zinc_price_inr_per_kg"] = round(ext.at[i, "expected_zinc_price_inr_per_kg"] * np.exp(rng.normal(0, 0.01)), 3)
    ext.at[i, "rural_income_index"] = ext.at[i, "expected_rural_income_index"]; ext.at[i, "led_price_index"] = ext.at[i, "expected_led_price_index"]
ext.to_csv(E, index=False)
g = new[new.reporting_level == "National"].groupby("week_beginning").primary_sales_units.sum()
b = d[(d.reporting_level == "National") & (d.week_beginning >= "2026-08-24")].groupby("week_beginning").primary_sales_units.sum()
print("rows added", len(new)); print("National units (lakh)"); print(pd.concat([b, g]).div(1e5).round(1).to_string())
