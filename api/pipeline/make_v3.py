"""Build eveready_mock_data_v3.csv and competitor_data_v2.csv from the v2 files (v2 untouched).

Demand side is left exactly as in v2 (primary_sales_units, forecasts, budget do not change), so the models and
UI built on v2 are unaffected. v3 adds the supply-side and workflow cases the CFO workbook asks for:
  1. Capacity squeeze with P1/P2/B2C shortfall rules          (Supply 4)
  2. Inter-depot transfers with lane cost and transit time   (Supply 2)
  3. 26 forward weeks of pending forecasts / requests         (Demand 2, Supply 1: flag at submission)
  4. Eveready products in the competitor (Nielsen-style) file (Demand 3: share and positioning)
"""
import numpy as np, pandas as pd

rng = np.random.default_rng(7)
d = pd.read_csv("sales_v2.csv", low_memory=False, parse_dates=["week_beginning"])
ext = pd.read_csv("ext.csv", parse_dates=["week_beginning"])
d["series"] = d.reporting_level.str[:3] + "|" + d.depot_code + "|" + d.product_code
d = d.sort_values(["series", "week_beginning"]).reset_index(drop=True)
assert d.primary_sales_units.notna().all()
PRIMARY0 = d.primary_sales_units.copy()
UNF = ["unfulfilled_b2c_units", "unfulfilled_b2b_p1_units", "unfulfilled_b2b_p2_units"]
nat = d.reporting_level == "National"

# ======================================================================= 1. capacity squeeze
# Shortfall order when capacity is short: P2 is deferred first, then B2C, and P1 last (P1 is protected).
d["capacity_constraint_flag"] = 0
d["production_shortfall_units"] = 0.0
wk = lambda s: pd.Timestamp(s)
sellin = d.loc[d.festival_sell_in_period.notna(), "week_beginning"].drop_duplicates()
sellin = set(w for w in sellin if w.year in (2024, 2025))
B2B_HEAVY = ["wir", "dl15", "pn12", "bt20", "bt40", "ham", "tap"]
TORCH = ["rch", "hyb", "cvt"]
OUTAGE = [wk("2026-03-09"), wk("2026-03-16")]
RECOVERY = [wk("2025-07-21"), wk("2025-07-28"), wk("2025-08-04")]
frac = {}                                  # (product, week) -> share of that week's primary sales that went unserved
for w in sellin:
    ramp = 0.10 + 0.22 * np.exp(-((w - wk(f"{w.year}-10-14")).days / 16.0) ** 2)    # peaks around the Diwali sell-in
    for p in B2B_HEAVY:
        frac[(p, w)] = float(np.clip(ramp * rng.uniform(0.8, 1.2), 0.05, 0.4))
for w, f0 in zip(OUTAGE, (0.80, 0.55)):    # plant line outage
    for p in B2B_HEAVY:
        frac[(p, w)] = float(np.clip(f0 * rng.uniform(0.9, 1.05), 0.3, 0.9))
for w, f0 in zip(RECOVERY, (0.28, 0.22, 0.14)):   # torch demand rebound after the delayed monsoon
    for p in TORCH:
        frac[(p, w)] = f0 * rng.uniform(0.9, 1.1)
key = list(zip(d.product_code, d.week_beginning))
f = pd.Series([frac.get(k, 0.0) for k in key], index=d.index)
hit = f > 0
U = (d.primary_sales_units * f).round()
cls = {"p2": d.primary_sales_b2b_p2_units, "b2c": d.primary_sales_b2c_units, "p1": d.primary_sales_b2b_p1_units}
rem = U.copy(); out = {}
for c in ("p2", "b2c", "p1"):                       # lowest priority absorbs the shortfall first
    take = np.minimum(rem, cls[c]); out[c] = take; rem = rem - take
d.loc[hit, "unfulfilled_b2c_units"] = (d.unfulfilled_b2c_units + out["b2c"])[hit]
d.loc[hit, "unfulfilled_b2b_p1_units"] = (d.unfulfilled_b2b_p1_units + out["p1"])[hit]
d.loc[hit, "unfulfilled_b2b_p2_units"] = (d.unfulfilled_b2b_p2_units + out["p2"])[hit]
d.loc[hit, "orders_received_units"] = (d.orders_received_units + U)[hit]
alloc0 = d.production_allocated_units.copy()
d.loc[hit, "production_required_units"] = (alloc0 + U)[hit]       # what was asked for; allocated stays what was made
d.loc[hit & nat, "plant_capacity_units"] = np.ceil(alloc0 * 1.02)[hit & nat]
d.loc[hit, "capacity_constraint_flag"] = 1
d["production_shortfall_units"] = (d.production_required_units - d.production_allocated_units).clip(lower=0)
d.loc[~nat, "plant_capacity_units"] = np.nan                       # plant capacity is a national figure

# ======================================================================= 2. inter-depot transfers
KM = {("tar", "bar"): 25, ("tar", "dan"): 35, ("tar", "bkp"): 30, ("tar", "bpr"): 40, ("bar", "dan"): 45,
      ("bar", "bkp"): 18, ("bar", "bpr"): 55, ("dan", "bkp"): 50, ("dan", "bpr"): 45, ("bkp", "bpr"): 60}
km = lambda a, b: KM.get((a, b), KM.get((b, a)))
for c in ("inter_depot_transfer_in_units", "inter_depot_transfer_out_units", "inter_depot_transfer_cost_inr"):
    d[c] = np.where(nat, np.nan, 0.0)
d["inter_depot_transfer_counterparty"] = pd.Series(dtype="object")
d["inter_depot_transfer_transit_days"] = np.nan
dep = d[~nat]
vol = dep.groupby("product_code").primary_sales_units.sum().sort_values(ascending=False)
prods = [p for p in vol.index[:14]]
weeks = sorted(d.week_beginning.unique())
idx = {(s, w): i for i, (s, w) in enumerate(zip(d.series, d.week_beginning))}
byser = {s: g.index.to_numpy() for s, g in d[~nat].groupby("series")}      # sorted by week already
def cover(i):  # weeks of cover
    return d.at[i, "closing_stock_units"] / max(d.at[i, "primary_sales_units"], 1.0)
events = []
for p in prods:
    for w in weeks[26::5]:                                         # a review every 5 weeks after the first half year
        w = pd.Timestamp(w)
        rows = {dc: idx.get((f"Kol|{dc}|{p}", w)) for dc in ("tar", "bar", "dan", "bkp", "bpr")}
        if any(v is None for v in rows.values()): continue
        cov = {dc: cover(i) for dc, i in rows.items()}
        a = max(cov, key=cov.get); b = min(cov, key=cov.get)
        if cov[a] < 2.0 or cov[b] > 1.2 or cov[a] - cov[b] < 1.2: continue
        ia, ib = rows[a], rows[b]
        T = float(np.floor(min(0.35 * d.at[ia, "closing_stock_units"], 1.6 * d.at[ib, "primary_sales_units"])))
        if T < 50: continue
        events.append((p, w, a, b, T))
wpos = {pd.Timestamp(w): j for j, w in enumerate(weeks)}
def at_week(sname, w):   # row label of a series at a week, or None
    return idx.get((sname, w))
REP = ["replenishment_received_units", "replenishment_ordered_units", "production_allocated_units", "production_required_units"]
for p, w, a, b, T in events:
    wk4 = pd.Timestamp(weeks[wpos[w] + 4]) if wpos[w] + 4 < len(weeks) else None
    if wk4 is None: continue
    sa, sb = f"Kol|{a}|{p}", f"Kol|{b}|{p}"
    ia, ib, ia4, ib4 = idx[(sa, w)], idx[(sb, w)], idx[(sa, wk4)], idx[(sb, wk4)]
    if d.at[ib4, "replenishment_received_units"] < T: continue              # destination can only give back what it was due to receive
    if min(d.at[idx[(sa, pd.Timestamp(weeks[wpos[w] + st])) ], "closing_stock_units"] - 0.8 * d.at[idx[(sa, pd.Timestamp(weeks[wpos[w] + st]))], "safety_stock_units"] for st in range(4)) < T: continue
    for sname, sign in ((sa, -1), (sb, 1)):
        for step in range(5):                                                # stock is shifted for 4 weeks, then replenishment squares it up
            i = idx[(sname, pd.Timestamp(weeks[wpos[w] + step]))]
            if step < 4:
                old = d.at[i, "closing_stock_units"]; new = old + sign * T
                d.at[i, "closing_stock_units"] = new
                if old > 0: d.at[i, "depot_stock_value_inr_lakh"] = d.at[i, "depot_stock_value_inr_lakh"] * new / old
            if step >= 1: d.at[i, "opening_stock_units"] = d.at[i, "opening_stock_units"] + sign * T
            if step == 4:
                for c in REP: d.at[i, c] = d.at[i, c] - sign * T
    cost = 2500 + T * (0.9 + 0.02 * km(a, b)); days = 1 if km(a, b) <= 40 else 2
    d.at[ia, "inter_depot_transfer_out_units"] = T; d.at[ib, "inter_depot_transfer_in_units"] = T
    d.at[ia, "inter_depot_transfer_counterparty"] = b; d.at[ib, "inter_depot_transfer_counterparty"] = a
    d.at[ia, "inter_depot_transfer_cost_inr"] = round(cost / 2); d.at[ib, "inter_depot_transfer_cost_inr"] = round(cost / 2)
    d.at[ia, "inter_depot_transfer_transit_days"] = days; d.at[ib, "inter_depot_transfer_transit_days"] = days
print("transfer events:", int((d.inter_depot_transfer_out_units > 0).sum()))

# ======================================================================= 3. forward weeks, pending submissions
LAST = d.week_beginning.max()
fw = pd.date_range(LAST + pd.Timedelta(days=7), periods=26, freq="7D")
assert fw[-1] == ext.week_beginning.max(), (fw[-1], ext.week_beginning.max())
mth = lambda w: (w + pd.Timedelta(days=3)).strftime("%Y-%m")       # Thursday rule
m0 = mth(LAST + pd.Timedelta(days=7))                              # first forward month = M1 target month
mlist = sorted(set(mth(w) for w in fw))
horizon = {m: 1 + i for i, m in enumerate(mlist[:3])}              # M1, M2, M3 target months (Oct, Nov, Dec)
STAT = ["supplier_moq_units", "case_pack_units", "supplier_lead_time_days", "standard_cost_inr", "shelf_life_weeks",
        "service_level_target", "supplier_price_break_quantity_units", "supplier_price_break_discount_pct"]
IDC = ["reporting_level", "region", "depot_code", "depot_name", "business_segment", "product_category", "product_code",
       "product_name", "is_new_product", "launch_date", "planned_launch_date", "pack_format", "technology_level", "launch_type"]
OVR = ["Festival sell-in", "Distributor feedback", "Scheme loading", "NPD launch plan", "Competitor activity", "Weather"]
sig = {3: 0.38, 2: 0.34, 1: 0.24}
newrows = []
exw = ext.set_index("week_beginning")
for s, g in d.groupby("series"):
    g = g.set_index("week_beginning"); last = g.iloc[-1]
    a = g.primary_sales_units; b = g.budget_units
    ga = float(np.clip(a.iloc[-52:].sum() / max(a.iloc[-104:-52].sum(), 1), 0.85, 1.25)) if len(a) >= 104 else 1.0
    gb = float(np.clip(b.iloc[-52:].sum() / max(b.iloc[-104:-52].sum(), 1), 0.85, 1.25)) if len(b) >= 104 else 1.0
    for w in fw:
        ly = w - pd.Timedelta(days=364)
        if ly not in a.index: continue
        base = a.loc[ly] * ga; r = {c: last[c] for c in IDC + STAT}
        r.update(week_beginning=w, series=s, is_forecast_week=1, festival=exw.at[w, "festival"], festival_sell_in_period=exw.at[w, "festival_sell_in_period"],
                 average_selling_price_inr=last.average_selling_price_inr, budget_units=round(b.loc[ly] * gb) if ly in b.index else np.nan)
        r["budget_value_inr"] = round(r["budget_units"] * last.average_selling_price_inr) if pd.notna(r["budget_units"]) else np.nan
        m = mth(w); k = horizon.get(m)                              # horizons available now: this month's week has M1, M2, M3
        reason = None; scale = 1.0
        if k is not None and rng.random() < 0.13:                    # a submission well out of line with budget and last year
            scale = rng.choice([rng.uniform(1.5, 2.2), rng.uniform(0.4, 0.6)]); reason = rng.choice(OVR)
        for h in (3, 2, 1):
            if k is not None and h >= k:                            # an M3 forecast exists for the M1, M2 and M3 months, and so on
                r[f"sales_forecast_{h}m_ahead_units"] = round(base * scale * np.exp(rng.normal(0, sig[h]) - sig[h] ** 2 / 2))
        if k == 1: r["consensus_forecast_1m_ahead_units"] = round(r["sales_forecast_1m_ahead_units"] * rng.uniform(0.96, 1.04))
        if reason: r["forecast_override_reason"] = reason
        if k is not None:
            fc = r.get("sales_forecast_1m_ahead_units") or r.get("sales_forecast_2m_ahead_units") or r.get("sales_forecast_3m_ahead_units")
            buf = rng.uniform(1.12, 1.38) if rng.random() > 0.1 else rng.uniform(1.7, 2.1)    # a few buffers far above the norm
            r["procurement_request_units"] = round(fc * buf)
        newrows.append(r)
fwd = pd.DataFrame(newrows)
# --- a pre-launch product with no sales history: an Eveready smart LED bulb planned for 16 Nov 2026 (new-product case)
NPD5_LAUNCH = pd.Timestamp("2026-11-16")
tpl = fwd[fwd.product_code == "lb9"].copy()
tpl["series"] = tpl.series.str.replace("lb9", "npd05")
for c, v in dict(product_code="npd05", product_name="Eveready Smart Wi-Fi LED Bulb 9W", is_new_product=1, planned_launch_date=NPD5_LAUNCH.strftime("%Y-%m-%d"),
                 launch_type="New product from existing brand", pack_format="Single", technology_level="Advanced").items():
    tpl[c] = v
tpl["launch_date"] = np.nan
live = tpl.week_beginning >= NPD5_LAUNCH
ramp = np.clip((tpl.week_beginning - NPD5_LAUNCH).dt.days / 7 / 10, 0, 1) * 0.5 + 0.5          # budget and forecast ramp over the first weeks
tpl["budget_units"] = np.where(live, (tpl.budget_units * 0.22 * ramp).round(), np.where(tpl.budget_units.notna(), 0, np.nan))
mult = rng.uniform(1.4, 1.9, len(tpl))                                     # the sales team is optimistic against budget
for c in ["sales_forecast_3m_ahead_units", "sales_forecast_2m_ahead_units", "sales_forecast_1m_ahead_units", "consensus_forecast_1m_ahead_units"]:
    tpl[c] = np.where(live & tpl[c].notna(), (tpl.budget_units * mult).round(), np.where(tpl[c].notna(), 0, np.nan))
fcn = tpl.sales_forecast_1m_ahead_units.fillna(tpl.sales_forecast_2m_ahead_units).fillna(tpl.sales_forecast_3m_ahead_units)
tpl["procurement_request_units"] = np.where(tpl.procurement_request_units.notna(), (fcn * 1.25).round(), np.nan)
tpl["budget_value_inr"] = tpl.budget_units * tpl.average_selling_price_inr
tpl["forecast_override_reason"] = np.where(tpl.sales_forecast_3m_ahead_units.notna() & live, "NPD launch plan", None)
fwd = pd.concat([fwd, tpl], ignore_index=True)
d["is_forecast_week"] = 0
d = pd.concat([d, fwd], ignore_index=True).sort_values(["series", "week_beginning"]).reset_index(drop=True)
print("forward rows:", len(fwd))

# ======================================================================= 4. Eveready in the competitor file
comp = pd.read_csv("competitor.csv", parse_dates=["week_beginning"])
h = d[d.is_forecast_week == 0]
dist_base = {"Batteries — carbon-zinc": 82, "Batteries — alkaline": 64, "Decorative & festive": 46, "Electrical accessories": 38,
             "Emergency & rechargeable LED": 52, "Flashlights — conventional": 58, "Flashlights — rechargeable": 50,
             "LED battens & tubelights": 48, "LED bulbs": 44, "Panels & downlighters": 36}
leader = {"Batteries — carbon-zinc", "Batteries — alkaline"}
rows = []
for mk, sel in (("NATIONAL", h.reporting_level == "National"), ("KOLKATA", h.reporting_level != "National")):
    g = h[sel].groupby(["week_beginning", "product_code"]).agg(
        cat=("product_category", "first"), name=("product_name", "first"), units=("secondary_sales_units", "sum"),
        price=("average_selling_price_inr", "mean"), sch=("trade_scheme_discount_pct", "mean"), pf=("pack_format", "first"),
        tl=("technology_level", "first"), ld=("launch_date", "first"), ltype=("launch_type", "first"), new=("is_new_product", "first")).reset_index()
    g = g[g.units > 0]
    for k0, x in g.groupby("product_code"):
        n = len(x); drift = np.linspace(0, 3, n) + rng.normal(0, 0.6, n)
        wd = np.clip(dist_base[x.cat.iloc[0]] + (8 if mk == "KOLKATA" else 0) + drift, 5, 97)
        if x.new.iloc[0] == 1: wd = np.clip(wd * np.linspace(0.3, 1, n) ** 0.5, 5, 97)   # a new product builds its distribution
        price = (x.price * 1.18).round(2).to_numpy()
        rows.append(pd.DataFrame({"week_beginning": x.week_beginning, "market": mk, "category": x.cat, "brand": "Eveready",
            "product_name": x.name, "brand_type": "Leader" if x.cat.iloc[0] in leader else "Challenger",
            "listed_from": x.ld.where(x.new == 1), "average_price_inr": price, "weighted_distribution_pct": wd.round(1),
            "numeric_distribution_pct": (wd * 0.66).round(1), "sold_on_promotion_pct": (x.sch * 4).clip(0, 35).round(1),
            "avg_promo_discount_pct": (x.sch * 1.5).clip(0, 12).round(1), "retail_sales_units": x.units.round(),
            "retail_sales_value_inr": (x.units * price).round(), "pack_format": x.pf, "technology_level": x.tl,
            "launch_type": x.ltype.where(x.new == 1)}))
ev = pd.concat(rows, ignore_index=True)
comp2 = pd.concat([comp, ev], ignore_index=True)[comp.columns.tolist()].sort_values(["week_beginning", "market", "category", "brand", "product_name"])
comp2.to_csv("competitor_data_v2.csv", index=False)
print("competitor rows:", len(comp), "->", len(comp2))

# ======================================================================= write
d["week_beginning"] = d.week_beginning.dt.strftime("%Y-%m-%d")
d = d.drop(columns=["series"])
assert (d.loc[d.is_forecast_week == 0, "primary_sales_units"].to_numpy() == PRIMARY0.to_numpy()).all()
d.to_csv("eveready_mock_data_v3.csv", index=False)
print("v3 rows:", len(d), "cols:", d.shape[1])
