"""Synthetic order-line data for quick commerce (placeholder until Eveready's real order-line file is available).

The weekly file has, per product, the number of order lines, how many were on time, in full and OTIF, and the units ordered and delivered.
This script breaks each product-week into individual order lines that add back to those weekly numbers exactly:
  line_id, week_beginning, product_code, partner, city, order_date, requested_delivery_date, actual_delivery_date,
  ordered_units, delivered_units, in_full, on_time, otif, failure_reason, depot_stock_units
Assumptions that are SIMULATED, not observed (they are what a real file would replace):
  * line size is lognormal around the week's average; how many lines fall short is fixed by the weekly data, but WHICH lines fall short
    is drawn in proportion to (line size / the line's share of real partner need) ** 1.5, so over-sized lines miss in full more often
  * short lines of 2.5x or more of their share of real need are labelled 'Over-sized order: allocation cut' 75% of the time
  * late lines are labelled 'Dispatch queue (busy week)' when units ordered are over 3x real need that week, otherwise transport delay / late cut-off
  * partner and city are drawn at random (4 partners, 6 cities); they carry no effect
Because the weekly totals are kept, nothing existing on the Quick commerce page changes. Writes qc_order_lines.csv.gz."""
import numpy as np, pandas as pd
rs = np.random.RandomState(11)
d = pd.read_csv("eveready_mock_data_v2_ext.csv", low_memory=False, parse_dates=["week_beginning"])
n = d[(d.reporting_level == "National") & d.quick_commerce_ordered_units.notna()].sort_values(["week_beginning", "product_code"])
PARTNERS = ["Partner 1", "Partner 2", "Partner 3", "Partner 4"]; PW = [0.38, 0.30, 0.20, 0.12]
CITIES = ["Delhi NCR", "Mumbai", "Bengaluru", "Hyderabad", "Kolkata", "Chennai"]; CW = [0.24, 0.22, 0.20, 0.12, 0.12, 0.10]
stock_col = "closing_stock_units" if "closing_stock_units" in n.columns else None
rows = []; fixed = 0
for _, r in n.iterrows():
    L = int(r.quick_commerce_order_lines)
    if L <= 0: continue
    O = float(r.quick_commerce_ordered_units); D = float(r.quick_commerce_delivered_units); SO = max(float(r.quick_commerce_partner_sell_out_units), 1.0)
    OT, IF, OF = int(r.quick_commerce_lines_on_time), int(r.quick_commerce_lines_in_full), int(r.quick_commerce_lines_otif)
    OT, IF = min(OT, L), min(IF, L)
    k = OF + L - OT - IF                                    # lines that are both late and short
    lo, hi = max(0, (L - OT) + (L - IF) - L), min(L - OT, L - IF)
    if not lo <= k <= hi: k = min(max(k, lo), hi); fixed += 1
    w = rs.lognormal(0, 0.9, L); q = np.maximum(1, np.round(O * w / w.sum())).astype(int); q[np.argmax(q)] += int(round(O)) - q.sum()
    q = np.maximum(q, 1)
    rel = q / (SO / L)                                      # line size against its share of real need
    nS, nL = L - IF, L - OT
    p = rel ** 1.5; p = p / p.sum()
    S = np.zeros(L, bool)
    if nS: S[rs.choice(L, nS, replace=False, p=p)] = True
    Lt = np.zeros(L, bool); sidx = np.where(S)[0]; oidx = np.where(~S)[0]
    kk = min(k, len(sidx), nL)
    if kk: Lt[rs.choice(sidx, kk, replace=False)] = True
    rest = nL - kk
    if rest > 0 and len(oidx): Lt[rs.choice(oidx, min(rest, len(oidx)), replace=False)] = True
    dl = q.astype(float).copy()
    if S.any():
        short = q[S] * rs.uniform(0.1, 0.7, S.sum()); target = max(O - D, 0.0)
        if short.sum() > 0 and target > 0: short = np.minimum(short * target / short.sum(), q[S] * 0.95)
        dl[S] = q[S] - short
    dl = np.round(dl).astype(int)
    busy = O / SO > 3
    reason = np.full(L, "", dtype=object)
    for i in range(L):
        if S[i]:
            if rel[i] >= 2.5: reason[i] = "Over-sized order: allocation cut" if rs.rand() < 0.75 else "Depot stockout"
            else: reason[i] = "Depot stockout" if rs.rand() < 0.5 else "Pick and pack short"
        if Lt[i]:
            lr = "Dispatch queue (busy week)" if (busy and rs.rand() < 0.6) else ("Transport delay" if rs.rand() < 0.6 else "Late order cut-off")
            reason[i] = (reason[i] + "; " + lr) if reason[i] else lr
    od = rs.randint(0, 5, L); late = rs.randint(1, 4, L) * Lt
    wk = r.week_beginning
    pr = rs.choice(PARTNERS, L, p=PW); ct = rs.choice(CITIES, L, p=CW)
    stk = r.closing_stock_units if stock_col and pd.notna(r.closing_stock_units) else np.nan
    for i in range(L):
        o = wk + pd.Timedelta(days=int(od[i])); rq = o + pd.Timedelta(days=1); ac = rq + pd.Timedelta(days=int(late[i]))
        rows.append((f"QC{wk:%y%m%d}-{r.product_code}-{i + 1:03d}", wk.date(), r.product_code, pr[i], ct[i], o.date(), rq.date(), ac.date(), int(q[i]), int(dl[i]),
                     int(not S[i]), int(not Lt[i]), int((not S[i]) and (not Lt[i])), reason[i], stk))
out = pd.DataFrame(rows, columns=["line_id", "week_beginning", "product_code", "partner", "city", "order_date", "requested_delivery_date", "actual_delivery_date",
                                  "ordered_units", "delivered_units", "in_full", "on_time", "otif", "failure_reason", "depot_stock_units"])
out.to_csv("qc_order_lines.csv.gz", index=False)
# reconcile with the weekly file
g = out.groupby(["week_beginning", "product_code"]).agg(lines=("line_id", "size"), ot=("on_time", "sum"), inf=("in_full", "sum"), of=("otif", "sum"), o=("ordered_units", "sum"), dl=("delivered_units", "sum")).reset_index()
g["week_beginning"] = pd.to_datetime(g.week_beginning)
m = n.merge(g, on=["week_beginning", "product_code"])
print("lines", len(out), "sku-weeks", len(m), "infeasible weekly splits adjusted", fixed)
for a, b in [("quick_commerce_order_lines", "lines"), ("quick_commerce_lines_on_time", "ot"), ("quick_commerce_lines_in_full", "inf"), ("quick_commerce_lines_otif", "of"), ("quick_commerce_ordered_units", "o"), ("quick_commerce_delivered_units", "dl")]:
    print(f"{a:34} weekly file {m[a].sum():>12,.0f}   lines {m[b].sum():>12,.0f}   max abs diff {np.abs(m[a] - m[b]).max():.0f}")
print("OTIF", round(out.otif.mean(), 4), "on time", round(out.on_time.mean(), 4), "in full", round(out.in_full.mean(), 4))
print(out[out.failure_reason != ""].failure_reason.str.split("; ").explode().value_counts())
