#!/usr/bin/env bash
# After chain_regen.sh: rebuild every page file for the new cut-off and copy to ../data. Resumable (re-run it).
cd "$(dirname "$0")"
[ -f done_branches ] || { echo "retrain not finished"; exit 1; }
python3 - <<'P'
import json
n=json.load(open("vintages_nat.json")); d=json.load(open("vintages_dep.json"))
json.dump({"levels":{"National":n,"Kolkata depots":d}},open("vintages.json","w"),separators=(",",":"))
P
set -e
python3 add_hist.py vintages.json
python3 build_weather.py
python3 build_ui_data.py
python3 build_challenge.py
python3 build_qc.py
python3 build_qc_lines.py
python3 build_drivers.py
python3 build_pending.py
cp ui_data.json vintages.json challenge.json weather.json qc.json drivers.json pending.json ../data/
date > done_post; echo "post-retrain build done"
