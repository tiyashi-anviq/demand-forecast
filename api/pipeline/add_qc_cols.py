"""Folds the simulated quick-commerce order lines into the main weekly data file as extra columns on the National rows,
so the order-line view lives in the same CSV as everything else (the line-level rows themselves cannot sit in a weekly file).
Adds, per product-week: lines that failed by each reason (a line can have two), lines by size band against real need (lines and lines OTIF),
and the lines that would have arrived OTIF if the over-sized-order reasons were removed. Re-runnable: it drops and rebuilds these columns.
Run after make_qc_lines.py and only when nothing else is reading the CSV (it backs the file up to <name>.bak first)."""
import sys, shutil, numpy as np, pandas as pd
F = sys.argv[1] if len(sys.argv) > 1 else "eveready_mock_data_v2_ext.csv"
shutil.copyfile(F, F + ".bak")
d = pd.read_csv(F, low_memory=False); d["week_beginning"] = pd.to_datetime(d.week_beginning)
d = d[[c for c in d.columns if not c.startswith("qc_line_")]]
L = pd.read_csv("qc_order_lines.csv.gz", parse_dates=["week_beginning"]); L["failure_reason"] = L.failure_reason.fillna("")
n = d[(d.reporting_level == "National") & d.quick_commerce_ordered_units.notna()][["week_beginning", "product_code", "quick_commerce_partner_sell_out_units", "quick_commerce_order_lines"]]
L = L.merge(n, on=["week_beginning", "product_code"]); L["rel"] = L.ordered_units / (L.quick_commerce_partner_sell_out_units.clip(lower=1) / L.quick_commerce_order_lines)
AVOID = {"Over-sized order: allocation cut", "Dispatch queue (busy week)"}
R = {"Over-sized order: allocation cut": "oversized_cut", "Dispatch queue (busy week)": "dispatch_queue", "Depot stockout": "stockout", "Pick and pack short": "pickpack", "Transport delay": "transport", "Late order cut-off": "cutoff"}
parts = L.failure_reason.str.split("; ")
g = pd.DataFrame({"week_beginning": L.week_beginning, "product_code": L.product_code})
for r, k in R.items(): g[f"qc_line_fail_{k}"] = parts.apply(lambda a, r=r: int(r in a))
g["qc_line_otif_if_rightsized"] = parts.apply(lambda a: int(all((not x) or x in AVOID for x in a)))
bins = [0, 0.5, 1, 2, 4, 1e9]; names = ["lt05", "05_1", "1_2", "2_4", "gt4"]
band = pd.cut(L.rel, bins, labels=names, right=False)
for b in names:
    g[f"qc_line_n_{b}"] = (band == b).astype(int); g[f"qc_line_otif_{b}"] = ((band == b) & (L.otif == 1)).astype(int)
agg = g.groupby(["week_beginning", "product_code"]).sum().reset_index(); agg["reporting_level"] = "National"
out = d.merge(agg, on=["week_beginning", "product_code", "reporting_level"], how="left")
out["week_beginning"] = out.week_beginning.dt.strftime("%Y-%m-%d") if d.week_beginning.dt.hour.eq(0).all() else out.week_beginning
out.to_csv(F, index=False)
cols = [c for c in out.columns if c.startswith("qc_line_")]
print("added", len(cols), "columns to", F, "; lines covered", int(out.qc_line_n_lt05.fillna(0).sum() + out.qc_line_n_05_1.fillna(0).sum() + out.qc_line_n_1_2.fillna(0).sum() + out.qc_line_n_2_4.fillna(0).sum() + out.qc_line_n_gt4.fillna(0).sum()), "of", len(L))
