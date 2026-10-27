# demo-df: AnvIQ Demand Forecasting (demo)

Demand forecasting and supply-planning proof of concept for Eveready, built on synthetic mock data.

```
demo-df/
  api/        FastAPI service that serves the forecast data
    app/main.py        endpoints
    data/              the JSON files the UI reads
    pipeline/          forecasting pipeline that produces data/ (engine, backtests, vintages, weather, quick commerce, challenge queue)
  ui/         React + Vite front end (Forecast & accuracy, Forecast challenge (pending submissions and past months), Weather & shocks, Quick commerce, New products)
  data/       source data files the mock data was built from
    our_build/         the 91-column file, its completeness report and the extended Sep 2022 to Oct 2026 version (same as api/pipeline/eveready_mock_data_v2_ext.csv)
  docs/       PDFs: how the UI works, with and without the glossary
  archive/    kept for reference, not used by the app
    stock_rebuild_backup/   files as they were before the stock rebuild
```

## Run it

API (port 8000):

```bash
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000     # docs at http://localhost:8000/docs
```

UI (port 5173, proxies /api to the API):

```bash
cd ui
npm install
npm run dev
```

Open http://localhost:5173. For a production build use `npm run build` (output in `ui/dist`); `npm run preview` serves it with the same API proxy. Point the UI at another API with `VITE_API_TARGET=http://host:8000`.

## API

| Endpoint | Returns |
|---|---|
| `GET /api/health` | status and which data files are present |
| `GET /api/forecast?level=` | weekly actual, model, P50, 80% range, sales-team, last-year and budget series per node |
| `GET /api/vintages` | monthly M3 / M2 / M1 model runs against actuals and the sales team |
| `GET /api/challenge/months` | target months available for the forecast challenge |
| `GET /api/challenge/rows?level=&month=&lead=` | sales-team forecasts with budget, last year, model, stock and actual |
| `GET /api/challenge/pending` | forecasts submitted for the three open months (M1, M2, M3) with the references used to check them |
| `GET /api/weather`, `/api/weather/{season}` | pre-shock forecast against actual demand and rainfall, monsoon 2024 to 2026 |
| `GET /api/new-products` | product profiles, seasonal indices, launch ramps (ours and competitors') and per-category market context behind the similarity index |
| `GET /api/quick-commerce` | requested, delivered, sell-out, stock, OTIF lines, forecast need and recommended shipments |

The API reads `api/data` (override with `DF_DATA_DIR`) and reloads a file when it changes.

## Rebuilding the data

```bash
cd api/pipeline
pip install pandas numpy lightgbm statsmodels
bash run_all.sh        # backtests take several minutes; writes the JSON files into ../data
```

Source data: `sales_v2.csv`, `ext.csv` (external factors) and `competitor.csv` (retail sell-out for competitor products, also used by the New products screen). `make_v2.py` and `cf.py` generated the mock data; `experiments/` holds the model comparisons run along the way (recursive vs direct, ensemble weights, stacking).

Quick commerce order lines: `make_qc_lines.py` breaks the weekly quick-commerce totals into simulated order lines (`qc_order_lines.csv.gz`, with dates, failure reasons and depot stock) and `build_qc_lines.py` adds the why-lines-fail view to `qc.json`. They are placeholders until Eveready's real order-line file is supplied.

## Notes

- Forecasts are direct multi-horizon (seasonal-naive with trend + damped ETS + LightGBM, weights 0.2 / 0.3 / 0.5 nationally, 0.3 / 0.7 for depots). The weights were set by hand while looking at the test window, so reported accuracy is optimistic.
- `clean.py` replaces the 2025 delayed-monsoon weeks for torch products with a normal-monsoon level before training, so the model does not learn the shock as seasonality.
- The monthly runs view for depots is included; forecast challenge, weather and quick commerce are National only; Kolkata depots show an empty state there.
- The forecast challenge checks stock separately from budget, last year and the model: stock at the forecast's cut-off divided by the forecast weekly rate, flagged above a maximum or below a minimum number of weeks. `make_stock.py` writes the synthetic stock (3-6 weeks of cover, with some overstocked and short-stocked episodes) before `build_challenge.py` runs.
- New products: the user describes a planned launch; every product is scored 0 to 100 on eleven weighted drivers (`ui/src/lib/similarity.js`). The closest of our products set volume and seasonality; launch curves come from our four launched products plus competitor launches in `competitor.csv` (shape only, never volume); competitive pressure and market context also come from `competitor.csv`. `build_newprod.py` writes `newprod.json`.
- All figures come from synthetic data.
