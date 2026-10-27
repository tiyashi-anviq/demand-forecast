"""Demand-forecasting demo API.

Serves the pre-computed forecast artefacts (written by ``pipeline/``) as JSON for the React UI.
Files are read from ``DF_DATA_DIR`` (default: ``api/data``) and reloaded automatically when they change on disk.
"""
import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

DATA_DIR = Path(os.environ.get("DF_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
FILES = {
    "forecast": "ui_data.json",
    "vintages": "vintages.json",
    "challenge": "challenge.json",
    "pending": "pending.json",
    "weather": "weather.json",
    "quick_commerce": "qc.json",
    "drivers": "drivers.json",
    "new_products": "newprod.json",
    "launch_case": "launch.json",
    "npd_weights": "npd_weights.json",
}

app = FastAPI(title="AnvIQ Demand Forecasting API", version="1.0.0",
              description="Forecast, vintages, forecast challenge, weather shocks and quick-commerce data. All data is synthetic.")
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("DF_CORS", "*").split(","), allow_methods=["GET"], allow_headers=["*"])

_cache: dict[str, tuple[float, Any]] = {}


def load(name: str) -> Any:
    path = DATA_DIR / FILES[name]
    if not path.exists():
        raise HTTPException(503, f"{path.name} not found in {DATA_DIR}. Run the pipeline or copy the data files.")
    mtime = path.stat().st_mtime
    hit = _cache.get(name)
    if hit and hit[0] == mtime:
        return hit[1]
    data = json.loads(path.read_text())
    _cache[name] = (mtime, data)
    return data


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "data_dir": str(DATA_DIR),
            "files": {k: (DATA_DIR / v).exists() for k, v in FILES.items()}}


@app.get("/api/forecast", tags=["forecast"])
def forecast(level: Optional[str] = Query(None, description="National or Kolkata depots; omit for both")):
    """Weekly actual / model / P50 / range / sales-team / last-year / budget series for every category and product node."""
    d = load("forecast")
    if level is None:
        return d
    if level not in d["levels"]:
        raise HTTPException(404, f"Unknown level '{level}'")
    return {**{k: v for k, v in d.items() if k != "levels"}, "levels": {level: d["levels"][level]}}


@app.get("/api/vintages", tags=["vintages"])
def vintages(level: Optional[str] = Query(None, description="National or Kolkata depots; omit for both")):
    """Monthly totals for the M3 / M2 / M1 model runs against actuals and the sales team."""
    d = load("vintages")
    if level is None:
        return d
    if level not in d["levels"]:
        raise HTTPException(404, f"Unknown level '{level}'")
    return {"levels": {level: d["levels"][level]}}


@app.get("/api/challenge/months", tags=["challenge"])
def challenge_months():
    return load("challenge")["months"]


@app.get("/api/challenge/rows", tags=["challenge"])
def challenge_rows(level: str = "National", month: str = "2026-09", lead: int = Query(3, ge=1, le=3)):
    """Sales-team forecast rows to challenge: [sku, name, category, depot, forecast, budget, last_year, actual, model, stock, safety, reason, weeks]."""
    rows = load("challenge")["rows"].get(f"{level}|{month}|{lead}")
    if rows is None:
        raise HTTPException(404, "No forecast run for that level, month and lead")
    return {"level": level, "month": month, "lead": lead, "rows": rows}


@app.get("/api/challenge/pending", tags=["challenge"])
def challenge_pending():
    """Sales-team forecasts submitted for the months still open (next month at M1, then M2, M3), joined to the references used to challenge them.
    rows[level]: [sku, name, category, depot, month, lead, forecast, budget, last_year, model, stock, safety, stated_reason, weeks]."""
    return load("pending")


@app.get("/api/weather", tags=["weather"])
def weather():
    """Pre-shock forecast vs actual demand and rainfall for monsoon 2024, 2025 and 2026."""
    return load("weather")


@app.get("/api/weather/{season}", tags=["weather"])
def weather_season(season: str):
    s = load("weather")["seasons"].get(season)
    if s is None:
        raise HTTPException(404, f"Unknown season '{season}'")
    return s


@app.get("/api/quick-commerce", tags=["quick commerce"])
def quick_commerce():
    """Requested / delivered / sell-out / stock / OTIF lines, forecast need and recommended shipments per quick-commerce SKU."""
    return load("quick_commerce")


@app.get("/api/new-products", tags=["new products"])
def new_products():
    """Product profiles, seasonal indices and launch ramps behind the similarity index and launch forecast."""
    return load("new_products")


@app.get("/api/new-products/launch-case", tags=["new products"])
def launch_case():
    """Worked launch case (liquid mosquito vaporizer): launch ramps, rate of sale, season, leave-one-launch-out back-test and the parameters for a new scenario."""
    return load("launch_case")


@app.get("/api/new-products/weights", tags=["new products"])
def npd_weights():
    """Similarity-index driver weights fitted to the existing products, per segment, with cross-validated error against the hand-set weights."""
    return load("npd_weights")


@app.get("/api/drivers")
def drivers(level: Optional[str] = None):
    """Per-week driver breakdown (change vs same week last year) for the 'why this week' panel."""
    d = load("drivers")
    if level is None: return d
    return {"weeks": d["weeks"], "info": d["info"], "weights": d["weights"].get(level), "nodes": d["levels"].get(level, {})}
