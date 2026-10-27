"""Adds the order-line view to qc.json (run after build_qc.py): why lines fail, OTIF by line size, and what right-sized orders would change.
Reads qc_order_lines.csv.gz (synthetic placeholder, see make_qc_lines.py). The 'avoidable' reasons are the ones tied to over-sized orders."""
import json, numpy as np, pandas as pd
L = pd.read_csv("qc_order_lines.csv.gz", parse_dates=["week_beginning"]); L["failure_reason"] = L.failure_reason.fillna("")
d = pd.read_csv("eveready_mock_data_v2_ext.csv", low_memory=False, parse_dates=["week_beginning"])
n = d[(d.reporting_level == "National") & d.quick_commerce_ordered_units.notna()][["week_beginning", "product_code", "quick_commerce_partner_sell_out_units", "quick_commerce_order_lines"]]
L = L.merge(n, on=["week_beginning", "product_code"]); L["rel"] = L.ordered_units / (L.quick_commerce_partner_sell_out_units.clip(lower=1) / L.quick_commerce_order_lines)
AVOID = {"Over-sized order: allocation cut", "Dispatch queue (busy week)"}
rs_ = L.failure_reason.str.split("; ")
L["left"] = rs_.apply(lambda a: [x for x in a if x and x not in AVOID])
L["otif_right"] = (L["left"].str.len() == 0).astype(int)
tot = len(L); fail = L[L.otif == 0]
reasons = {}
for r in ["Over-sized order: allocation cut", "Dispatch queue (busy week)", "Depot stockout", "Pick and pack short", "Transport delay", "Late order cut-off"]:
    c = int(rs_.apply(lambda a, r=r: r in a).sum()); reasons[r] = dict(lines=c, share_of_failed=round(c / len(fail), 4), avoidable=r in AVOID)
bins = [0, 0.5, 1, 2, 4, 1e9]; lab = ["under 0.5x", "0.5 to 1x", "1 to 2x", "2 to 4x", "over 4x"]
L["band"] = pd.cut(L.rel, bins, labels=lab, right=False)
by_size = [dict(band=b, lines=int((L.band == b).sum()), otif=round(float(L[L.band == b].otif.mean()), 4), in_full=round(float(L[L.band == b].in_full.mean()), 4)) for b in lab]
by = lambda col: [dict(name=str(k), lines=int(len(g)), otif=round(float(g.otif.mean()), 4)) for k, g in L.groupby(col)]
sku = {s: dict(otif=round(float(g.otif.mean()), 4), otif_right=round(float(g.otif_right.mean()), 4), lines=int(len(g))) for s, g in L.groupby("product_code")}
out = json.load(open("qc.json"))
out["lines"] = dict(synthetic=True, lines=tot, otif=round(float(L.otif.mean()), 4), on_time=round(float(L.on_time.mean()), 4), in_full=round(float(L.in_full.mean()), 4),
                    otif_right_sized=round(float(L.otif_right.mean()), 4), failed=int(len(fail)), reasons=reasons, by_size=by_size, by_partner=by("partner"), by_city=by("city"), by_sku=sku,
                    first_week=str(L.week_beginning.min().date()), last_week=str(L.week_beginning.max().date()),
                    note="Line-level data is a simulated placeholder. Weekly totals match the weekly file; which lines fail and why is assumed (see make_qc_lines.py).")
json.dump(out, open("qc.json", "w"), separators=(",", ":"))
print("OTIF", out["lines"]["otif"], "-> right-sized", out["lines"]["otif_right_sized"]); print(by_size); print({k: v["share_of_failed"] for k, v in reasons.items()})
print(out["lines"]["by_partner"], out["lines"]["by_city"])
