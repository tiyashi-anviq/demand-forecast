#!/usr/bin/env bash
# Rebuilds every data file the API serves, from the three source CSVs in this folder
# (sales_v2.csv, ext.csv, competitor.csv). Needs: pip install pandas numpy lightgbm statsmodels
# Slow stages are the backtests (a few minutes each on 2 cores). Run from this folder: bash run_all.sh
set -e
cd "$(dirname "$0")"
# 1. Forecast runs on history with the 2025 delayed-monsoon shock neutralised (see clean.py)
python3 run_clean.py National
python3 run_clean.py "Kolkata depot"
cp natclean_primary_sales_units.pkl natv2_primary_sales_units.pkl
cp depclean_primary_sales_units.pkl depv2_primary_sales_units.pkl
# 2. Back-test residuals at 13 / 19 / 26 weeks ahead (for the 80% range)
python3 run_band.py National
python3 run_band.py "Kolkata depot"
# 3. Month-end forecast vintages (M3 / M2 / M1) and the weather-shock runs
python3 build_vintages.py
python3 add_hist.py vintages.json
python3 build_weather.py
# 4. Page data
python3 build_ui_data.py
python3 make_stock.py        # realistic synthetic stock (cover 3-6 weeks, some over/under-stocked episodes)
python3 build_challenge.py
python3 build_qc.py
python3 make_qc_lines.py   # simulated order lines; replace qc_order_lines.csv.gz with Eveready's line file when available
python3 build_qc_lines.py  # adds the order-line view to qc.json (must run after build_qc.py)
python3 build_newprod.py
python3 build_drivers.py
# 5. Publish to the API's data folder
cp ui_data.json vintages.json challenge.json weather.json qc.json drivers.json newprod.json ../data/
echo "Done. Data written to ../data"
