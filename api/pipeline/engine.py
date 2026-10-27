"""Ensemble demand forecasting engine (direct multi-horizon).
Models: seasonal-naive-with-trend, damped ETS (national only), LightGBM global.
Rolling-origin backtest; all features known at forecast origin (no leakage).
"""
import os, warnings
import numpy as np
import pandas as pd
import lightgbm as lgb

warnings.filterwarnings("ignore")
H_MAX = 26
ETSOFF = os.environ.get("ETSOFF", "0") == "1"   # 1 = blank ETS inside the festive stretch. Off by default: tested hold-one-season-out and on the full rebuild it changed the 2026 Puja-week forecast by under 2% and accuracy by under 0.3 points (see fest_test.py)
FEST = os.environ.get("FEST", "1") == "1"   # festival-timing features + festival-aligned seasonal naive
FEST_LO, FEST_HI = -6, 8                   # weeks around the Durga Puja week that count as the festive stretch
EVAL_H = {"M1": 4, "M2": 9, "M3": 13}


# ----------------------------------------------------------------- data
def load_ext(path="ext_ext.csv"):
    e = pd.read_csv(path, parse_dates=["week_beginning"])
    e = e.sort_values("week_beginning").reset_index(drop=True)
    # "known at planning time" drivers: expected_* if present else actual (history before expectations existed)
    pairs = {"temp": ("expected_temp_max_c", "temp_max_c"), "rain": ("expected_rainfall_mm", "rainfall_mm"),
             "pcut": ("expected_power_cut_hours", "power_cut_hours"), "dengue": ("expected_dengue_index", "dengue_index"),
             "zinc": ("expected_zinc_price_inr_per_kg", "zinc_price_inr_per_kg"),
             "rural": ("expected_rural_income_index", "rural_income_index"), "led": ("expected_led_price_index", "led_price_index")}
    out = pd.DataFrame({"week": e.week_beginning})
    for k, (ex, ac) in pairs.items():
        out[k] = e[ex].where(e[ex].notna(), e[ac])
    # climatology fill for any remaining gaps (same week-of-year mean)
    woy = out.week.dt.isocalendar().week.astype(int)
    for k in pairs:
        clim = out.groupby(woy)[k].transform("mean")
        out[k] = out[k].fillna(clim)
        out[k] = out[k].ffill().bfill()
    out["fest"] = e["festival"].notna().astype(int)
    fs = e["festival_sell_in_period"].fillna("")
    out["sellin_durga"] = fs.str.contains("Durga").astype(int)
    out["sellin_diwali"] = fs.str.contains("Diwali").astype(int)
    out["fest_major"] = e["festival"].fillna("").str.contains("Durga Puja|Diwali|Holi|Eid|Poila|Chaitra").astype(int)
    out["is_forecast"] = e["is_forecast_week"].astype(int)
    fz = e["festival"].fillna("")
    d_fl = fz.str.contains(r"Durga Puja \(").values; w_fl = fz.str.contains("Kali Puja / Diwali").values
    out["durga_a"] = (d_fl & ~np.r_[False, d_fl[:-1]]).astype(int)      # first week of the Durga Puja festival run
    out["diwali_a"] = (w_fl & ~np.r_[False, w_fl[:-1]]).astype(int)     # first week of the Kali Puja / Diwali run
    return out.set_index("week")


def load_panel(path="sales.csv", level="National", target="primary_sales_units"):
    d = pd.read_csv(path, low_memory=False, parse_dates=["week_beginning"])
    d = d[d.reporting_level == level].copy()
    d["true_demand_units"] = d.primary_sales_units + d.unfulfilled_b2c_units + d.unfulfilled_b2b_p1_units + d.unfulfilled_b2b_p2_units
    d["series"] = d.depot_code + "|" + d.product_code
    meta = d.groupby("series").agg(sku=("product_code", "first"), depot=("depot_code", "first"), name=("product_name", "first"),
                                  category=("product_category", "first"), segment=("business_segment", "first"),
                                  is_new=("is_new_product", "max")).reset_index()
    y = d.pivot(index="week_beginning", columns="series", values=target).sort_index()
    price = d.pivot(index="week_beginning", columns="series", values="average_selling_price_inr").sort_index()
    sch = d.pivot(index="week_beginning", columns="series", values="trade_scheme_discount_pct").sort_index()
    return d, y, price, sch, meta


# ----------------------------------------------------------------- features
def build_rows(y, price, sch, meta, ext, origins, horizons, with_target=True):
    """One row per (series, origin index, horizon)."""
    weeks = y.index
    Y = y.values  # (T, S)
    P = price.values
    SC = sch.values
    S = Y.shape[1]
    ext_w = ext.reindex(pd.date_range(weeks[0], periods=len(weeks) + H_MAX + 60, freq="7D"))
    ext_w = ext_w.ffill()
    cat_codes = {c: i for i, c in enumerate(sorted(meta.category.unique()))}
    depot_codes = {c: i for i, c in enumerate(sorted(meta.depot.unique()))}
    sku_codes = {c: i for i, c in enumerate(sorted(meta.sku.unique()))}
    mcat = meta.set_index("series").loc[y.columns]
    cat_v = mcat.category.map(cat_codes).values
    dep_v = mcat.depot.map(depot_codes).values
    sku_v = mcat.sku.map(sku_codes).values
    anch_d = np.where(ext_w.durga_a.values == 1)[0]
    def _offs(anch):                                   # signed weeks from the nearest anchor; 12 = not near a festival
        i = np.arange(len(ext_w)); o = np.full(len(ext_w), 12.0)
        for k in range(len(anch)):
            d_ = i - anch[k]; m = (np.abs(d_) <= 10) & (np.abs(d_) < np.abs(np.where(o == 12, 99, o)))
            o[m] = d_[m]
        return o
    off_d, off_w = _offs(anch_d), _offs(np.where(ext_w.diwali_a.values == 1)[0])
    rows = []
    for t in origins:
        hist = Y[: t + 1]
        valid = ~np.isnan(hist[-1])
        n_obs = (~np.isnan(hist)).sum(0)
        m4 = np.nanmean(hist[-4:], 0)
        m13 = np.nanmean(hist[-13:], 0)
        m26 = np.nanmean(hist[-26:], 0)
        m52 = np.nanmean(hist[-52:], 0)
        sd13 = np.nanstd(hist[-13:], 0)
        l1 = hist[-1]
        l2 = hist[-2] if t >= 1 else np.full(S, np.nan)
        # growth vs last year over trailing 13 wks
        if t >= 64:
            ly13 = np.nanmean(Y[t - 51 - 12: t - 51 + 1], 0)
        else:
            ly13 = np.full(S, np.nan)
        growth = np.log1p(m13) - np.log1p(ly13)
        base = np.maximum(m13, 1.0)
        for h in horizons:
            T = t + h
            if with_target and T >= len(weeks):
                continue
            wk = ext_w.index[T]
            ly = Y[T - 52] if T - 52 >= 0 else np.full(S, np.nan)
            ly_m = np.nanmean(Y[max(T - 53, 0): T - 50], 0) if T - 52 >= 1 else ly
            ly_m = np.where(T - 52 <= t, ly_m, np.nan)  # only data known at origin
            ly = np.where(T - 52 <= t, ly, np.nan)
            ly2 = Y[T - 104] if T - 104 >= 0 else np.full(S, np.nan)
            e = ext_w.iloc[T]
            e_prev = ext_w.iloc[T - 52] if T - 52 >= 0 else e
            df = pd.DataFrame({
                "ser": np.arange(S), "t": t, "h": h, "T": T, "week": wk,
                "lbase": np.log1p(base), "l1": np.log1p(l1) - np.log1p(base), "l2": np.log1p(l2) - np.log1p(base),
                "m4": np.log1p(m4) - np.log1p(base), "m26": np.log1p(m26) - np.log1p(base), "m52": np.log1p(m52) - np.log1p(base),
                "cv13": sd13 / base, "growth": growth,
                "ly": np.log1p(ly) - np.log1p(base), "ly_m": np.log1p(ly_m) - np.log1p(base), "ly2": np.log1p(ly2) - np.log1p(base),
                "woy": wk.isocalendar().week, "month": wk.month, "n_obs": n_obs,
                "cat": cat_v, "dep": dep_v, "sku": sku_v,
                "price": np.log(np.where(np.isnan(P[t]), 1, P[t])), "sch": np.nan_to_num(SC[t]),
                "temp": e.temp, "rain": e.rain, "pcut": e.pcut, "dengue": e.dengue, "zinc": e.zinc, "rural": e.rural, "led": e.led,
                "d_temp": e.temp - e_prev.temp, "d_rain": e.rain - e_prev.rain,
                "fest": e.fest, "sellin_durga": e.sellin_durga, "sellin_diwali": e.sellin_diwali, "fest_major": e.fest_major,
                "fest_ly": e_prev.fest_major,
                "wk_durga": off_d[T], "wk_diwali": off_w[T],
            })
            df["base"] = base
            df["snaive"] = seasonal_naive(Y, t, T, m13, ly13, anch_d if FEST else None)
            df["valid"] = valid & (n_obs >= 20)
            if with_target and T < len(weeks):
                df["y"] = Y[T]
            rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    return out


def seasonal_naive(Y, t, T, m13, ly13, anchors=None):
    S = Y.shape[1]
    lag = T - 52
    if anchors is not None:                              # inside the festive stretch, use last year's week at the same distance from Durga Puja
        a = [x for x in anchors if FEST_LO <= T - x <= FEST_HI]
        if a:
            a = a[0]; prev = [x for x in anchors if x < a]
            if prev and 1 <= prev[-1] + (T - a) <= t: lag = prev[-1] + (T - a)
    if lag < 0 or lag > t:
        return m13
    ly = np.nanmean(Y[max(lag - 1, 0): lag + 2], 0)
    ratio = np.where((ly13 > 0) & ~np.isnan(ly13), m13 / np.maximum(ly13, 1), 1.0)
    ratio = np.clip(ratio, 0.6, 1.6)
    out = ly * ratio
    return np.where(np.isnan(out), m13, out)


FEATS = ["h", "lbase", "l1", "l2", "m4", "m26", "m52", "cv13", "growth", "ly", "ly_m", "ly2", "woy", "month", "cat", "dep", "sku",
         "price", "sch", "temp", "rain", "pcut", "dengue", "zinc", "rural", "led", "d_temp", "d_rain", "fest", "sellin_durga",
         "sellin_diwali", "fest_major", "fest_ly"]
if FEST: FEATS = FEATS + ["wk_durga", "wk_diwali"]


_o = os.environ.get("GBMOBJ", "huber1.5")
_OBJ = {"objective": "regression"} if _o == "l2" else {"objective": "huber", "alpha": float(_o.replace("huber", ""))}


def fit_gbm(tr, seed=0):
    tr = tr[tr.valid & tr.y.notna()]
    tgt = np.log1p(tr.y.values) - tr.lbase.values
    mdl = lgb.LGBMRegressor(n_estimators=350, learning_rate=0.04, num_leaves=24, min_child_samples=40, subsample=0.8, subsample_freq=1,
                            colsample_bytree=0.8, reg_lambda=2.0, random_state=seed, verbose=-1, n_jobs=2,
                            **_OBJ)
    mdl.fit(tr[FEATS], tgt, categorical_feature=["cat", "dep", "sku"])
    return mdl


def pred_gbm(mdl, df):
    p = np.expm1(mdl.predict(df[FEATS]) + df.lbase.values)
    return np.clip(p, 0, None)


# ETS (national only) ------------------------------------------------------
def ets_off_in_fest(df):
    """ETS has no festival awareness: blank it inside the Durga Puja / Diwali stretch so the blend leans on the festival-aware models."""
    if ETSOFF and FEST and "ets" in df and "wk_durga" in df:
        df.loc[df.wk_durga.between(FEST_LO, FEST_HI), "ets"] = np.nan
    return df


def ets_forecast(Y, t, horizons):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    S = Y.shape[1]
    out = np.full((S, max(horizons)), np.nan)
    for s in range(S):
        ser = Y[: t + 1, s]
        ser = ser[~np.isnan(ser)]
        if len(ser) < 104:
            continue
        try:
            m = ExponentialSmoothing(np.log1p(ser), trend="add", damped_trend=True, seasonal="add", seasonal_periods=52,
                                     initialization_method="estimated").fit(optimized=True)
            out[s] = np.expm1(m.forecast(max(horizons)))
        except Exception:
            pass
    return out


# ----------------------------------------------------------------- backtest + final forecast
def run(y, price, sch, meta, ext, use_ets=True, first_test_origin=104, retrain_every=4, eval_h=(4, 9, 13), seed=0, verbose=True):
    weeks = y.index
    n = len(weeks)
    horizons = list(range(1, H_MAX + 1))
    # full training feature table, all origins with at least 52 wks of history
    allrows = build_rows(y, price, sch, meta, ext, origins=range(40, n - 1), horizons=horizons)
    # test predictions for horizons of interest (all horizons for later bias calibration is costly; use full set)
    preds = []
    ck = os.environ.get("CKPT")              # optional: save each backtest block so a killed run can resume
    for t0 in range(first_test_origin, n - 1, retrain_every):
        cf = f"{ck}_{t0}.pkl" if ck else None
        if cf and os.path.exists(cf):
            preds.append(pd.read_pickle(cf)); continue
        tr = allrows[(allrows["T"] <= t0)]
        mdl = fit_gbm(tr, seed)
        te = allrows[(allrows.t >= t0) & (allrows.t < t0 + retrain_every) & allrows.h.isin(eval_h)].copy()
        if te.empty:
            continue
        te["gbm"] = pred_gbm(mdl, te)
        if use_ets:
            ev = {}
            for t in sorted(te.t.unique()):
                full = ets_forecast_cached(y.values, t)
                ev[t] = full
            te["ets"] = [ev[t][s, h - 1] for t, s, h in zip(te.t, te.ser, te.h)]
            ets_off_in_fest(te)
        preds.append(te)
        if cf: te.to_pickle(cf + ".tmp"); os.replace(cf + ".tmp", cf)
        if verbose:
            print("  backtest block", weeks[t0].date(), flush=True)
    bt = pd.concat(preds, ignore_index=True)
    bt["series"] = y.columns[bt.ser]
    return allrows, bt


_ets_cache = {}


def ets_forecast_cached(Y, t):
    key = (Y.shape, t, float(np.nansum(Y[: t + 1])))
    if key not in _ets_cache:
        _ets_cache[key] = ets_forecast(Y, t, [H_MAX])
    return _ets_cache[key]


def final_forecast(allrows, y, price, sch, meta, ext, use_ets=True, seeds=(0, 1, 2)):
    n = len(y)
    t = n - 1
    horizons = list(range(1, H_MAX + 1))
    fut = build_rows(y, price, sch, meta, ext, origins=[t], horizons=horizons, with_target=False)
    fut["gbm"] = 0.0
    for sd in seeds:
        mdl = fit_gbm(allrows[allrows["T"] <= t], sd)
        fut["gbm"] += pred_gbm(mdl, fut) / len(seeds)
    if use_ets:
        E = ets_forecast_cached(y.values, t)
        fut["ets"] = [E[s, h - 1] for s, h in zip(fut.ser, fut.h)]
        ets_off_in_fest(fut)
    fut["series"] = y.columns[fut.ser]
    return fut, mdl
