import engine as _en
import pickle, json, os, sys
import numpy as np, pandas as pd
from lyref import ly_ref
_EXT = pd.read_csv('ext_ext.csv', parse_dates=['week_beginning'])

S = pd.read_csv("eveready_mock_data_v2_ext.csv", low_memory=False, parse_dates=["week_beginning"])
HIST, FC = 26, 26
LEVELS = {"National": ("natv2_primary_sales_units.pkl", "National", (0.2, 0.3, 0.5)),
          "Kolkata depots": ("depv2_primary_sales_units.pkl", "Kolkata depot", (0.3, 0.0, 0.7))}

def ens(row, w):
    sn, et, gb = row.snaive, row.get("ets", np.nan), row.gbm
    parts = [(w[0], sn), (w[1], et), (w[2], gb)]
    parts = [(a, b) for a, b in parts if a > 0 and pd.notna(b)]
    if not parts: return np.nan
    tw = sum(a for a, _ in parts); return sum(a * b for a, b in parts) / tw

out = {"levels": {}}
for lname, (pk, lvl, w) in LEVELS.items():
    if not os.path.exists(pk):
        print("missing", pk); continue
    P = pickle.load(open(pk, "rb")); bt, fut, meta, weeks, cols = P["bt"], P["fut"], P["meta"], P["weeks"], P["cols"]
    _en.ets_off_in_fest(bt); _en.ets_off_in_fest(fut)   # ETS has no festival awareness: leave it out of the Puja / Diwali weeks
    d = S[S.reporting_level == lvl].copy(); d["series"] = d.depot_code + "|" + d.product_code
    pv = lambda c: d.pivot(index="week_beginning", columns="series", values=c).reindex(index=weeks, columns=cols)
    A, SF, BU, VAL, PX = pv("primary_sales_units"), pv("sales_forecast_3m_ahead_units"), pv("budget_units"), pv("primary_sales_value_inr"), pv("average_selling_price_inr")
    nW = len(weeks); future_weeks = pd.date_range(weeks[-1] + pd.Timedelta(days=7), periods=FC, freq="7D")
    allw = list(weeks[-HIST:]) + list(future_weeks); N = HIST + FC; nS = len(cols)
    price = PX.iloc[-26:].mean().fillna(PX.mean()).values
    # model arrays (units): history from backtest h=13, future from final forecast
    bt13 = bt[bt.h == 13].copy(); bt13["m"] = [ens(r, w) for r in bt13.itertuples(index=False)] if False else bt13.apply(lambda r: ens(r, w), axis=1)
    M_all = np.full((nW, nS), np.nan); M_all[bt13["T"].values.astype(int), bt13.ser.values.astype(int)] = bt13.m.values
    bp = {"National": "band_nat.pkl", "Kolkata depots": "band_dep.pkl"}[lname]
    bnd = {13: M_all}
    if os.path.exists(bp):
        bb = _en.ets_off_in_fest(pickle.load(open(bp, "rb"))["bt"])
        for h_ in (13, 19, 26):
            s_ = bb[bb.h == h_].copy(); s_["m"] = s_.apply(lambda r: ens(r, w), axis=1)
            Mh = np.full((nW, nS), np.nan); Mh[s_["T"].values.astype(int), s_.ser.values.astype(int)] = s_.m.values; bnd[h_] = Mh
    hk = [13 if k <= 16 else (19 if k <= 22 else 26) for k in range(1, FC + 1)]
    fu = fut[fut.h <= FC].copy(); fu["m"] = fu.apply(lambda r: ens(r, w), axis=1)
    _fx = lname == "National" and os.environ.get("FESTFX", "1") == "1"   # festival-by-category mix in festival weeks (fest_effects.py): national only
    if _fx:
        import importlib; os.environ["FE_LEVEL"] = lvl; import fest_effects; importlib.reload(fest_effects)
    _mult = np.ones(len(fu))
    if lname == "National" and os.environ.get("STACK", "1") == "1":   # learn-from-mistakes layer on the forward forecast (stacker.py)
        import stacker; _tf = stacker.train_frame(pickle.load(open("natclean_bt.pkl", "rb"))["bt"])
        _mult = stacker.multiplier(fu, stacker.fit(_tf, nW - 1))
    if _fx:
        _m2, _isf = fest_effects.apply(fu, nW - 1); _mult[_isf] = 1.0
        fu["m"] = fu.m.values * _mult; fu.loc[_isf, "m"] = _m2[_isf]
    else: fu["m"] = fu.m.values * _mult
    Mf = np.full((FC, nS), np.nan); Mf[fu.h.values.astype(int) - 1, fu.ser.values.astype(int)] = fu.m.values
    pickle.dump({"Mf": Mf, "cols": list(cols)}, open("mf_" + lname.split()[0].lower() + ".pkl", "wb"))   # per-series final forecast, used by build_drivers
    # M3 / M2 / M1 weekly runs: each week comes from the month-end run made 3 / 2 / 1 months before that week's month
    vr = {"National": "vint_runs.pkl", "Kolkata depots": "vint_runs_dep.pkl"}[lname]
    vcuts, vruns, vcols = pickle.load(open(vr, "rb")); assert list(vcols) == list(cols)
    w0_ = weeks[0]
    def runs_arr(k):
        R_ = np.full((N, nS), np.nan)
        for j in range(N):
            T = nW - HIST + j; wk_ = w0_ + pd.Timedelta(days=7 * T); m_ = (wk_ + pd.Timedelta(days=3)).strftime("%Y-%m")
            lab_ = (pd.Timestamp(m_ + "-01") - pd.DateOffset(months=k)).strftime("%Y-%m")
            if lab_ in vcuts:
                t_, M_ = vruns[lab_]; h_ = T - t_
                if 1 <= h_ <= M_.shape[0]: R_[j] = M_[h_ - 1]
        return R_
    RUNS = {k: runs_arr(k) for k in (3, 2, 1)}
    # arrays over the display window
    act = np.vstack([A.values[-HIST:], np.full((FC, nS), np.nan)])
    mod = np.vstack([M_all[-HIST:], Mf])
    sal = np.vstack([SF.values[-HIST:], np.full((FC, nS), np.nan)])
    ly = np.vstack([A.values[nW - HIST - 52: nW - 52], A.values[nW - 52: nW - 52 + FC]])
    # festival-aware last year: a festival week is compared with the same festival last year (dated calendar), other weeks 52 weeks back
    _wk = list(weeks) + list(future_weeks); _ref, _ = ly_ref(pd.DatetimeIndex(_wk), _EXT)
    _gi = list(range(nW - HIST, nW)) + list(range(nW, nW + FC))
    lyf = np.vstack([A.values[_ref[g]] if 0 <= _ref[g] < nW else np.full(nS, np.nan) for g in _gi])
    # budget: history actual; future derived from last year's budget scaled by trailing budget trend
    B = BU.values
    trend = np.clip(np.nansum(B[-26:], 0) / np.maximum(np.nansum(A.values[-26:], 0), 1), 0.9, 1.2)
    bud_f = A.values[nW - 52: nW - 52 + FC] * trend   # derived: last year's actual x current budget-to-actual ratio
    bud = np.vstack([B[-HIST:], bud_f])
    # value arrays
    valact = np.vstack([VAL.values[-HIST:], np.full((FC, nS), np.nan)])
    mp = meta.set_index("series").loc[cols]
    keys = {"ALL": np.arange(nS)}
    for c in sorted(mp.category.unique()): keys["cat:" + c] = np.where(mp.category.values == c)[0]
    for i, s in enumerate(cols): keys["sku:" + mp.sku.iloc[i] + ("" if lvl == "National" else "")] = keys.get("sku:" + mp.sku.iloc[i], np.array([], int))
    skus = {}
    for i, s in enumerate(cols): skus.setdefault(mp.sku.iloc[i], []).append(i)
    for k, v in skus.items(): keys["sku:" + k] = np.array(v)
    nodes = {}
    for k, idx in keys.items():
        if len(idx) == 0: continue
        def agg(a, mult=None):
            x = a[:, idx] * (price[idx] if mult else 1)
            return np.where(np.isnan(x).all(1), np.nan, np.nansum(x, 1))
        node = {"u": {}, "v": {}}
        for nm, arr in (("actual", act), ("model", mod), ("sales", sal), ("budget", bud), ("ly", ly), ("lyf", lyf), ("m3", RUNS[3]), ("m2", RUNS[2]), ("m1", RUNS[1])):
            node["u"][nm] = agg(arr)
            node["v"][nm] = agg(arr, True)
        node["v"]["actual"] = np.where(np.isnan(valact[:, idx]).all(1), np.nan, np.nansum(valact[:, idx], 1))
        # 80% range from backtest ratios at this node (all available weeks)
        am = A.values[:, idx]; mm = M_all[:, idx]
        def qs(h_):
            M_ = bnd.get(h_, M_all)[:, idx]; ok_ = ~np.isnan(M_).all(1)
            if ok_.sum() < 6: M_ = M_all[:, idx]; ok_ = ~np.isnan(M_).all(1)
            ra_ = np.nansum(am[ok_], 1) / np.maximum(np.nansum(M_[ok_], 1), 1)
            l_ = np.log(np.clip(ra_, 1e-3, None)); return np.quantile(l_, .10), np.quantile(l_, .90), np.quantile(l_, .50)
        QS = {h_: qs(h_) for h_ in (13, 19, 26)}
        q10, q90, q50 = QS[13]; q10L, q90L, q50L = QS[26]
        m10 = np.full(N, np.nan); m90 = m10.copy(); m50 = m10.copy()
        for j, h_ in enumerate(hk): m10[HIST + j], m90[HIST + j], m50[HIST + j] = QS[h_]
        for u in ("u", "v"):
            mf = node[u]["model"].copy(); mf[:HIST] = np.nan
            node[u]["lo"] = mf * np.exp(m10); node[u]["hi"] = mf * np.exp(m90); node[u]["p50"] = mf * np.exp(m50)
        label = "All products" if k == "ALL" else (k[4:] if k.startswith("cat:") else mp.name[mp.sku == k[4:]].iloc[0])
        node["label"] = label
        # accuracy of the weekly M3 / M2 / M1 lines over the visible history (units)
        ah = node["u"]["actual"][:HIST]; accR = []
        for k_ in ("m3", "m2", "m1"):
            fh = node["u"][k_][:HIST]; ok_ = ~(np.isnan(ah) | np.isnan(fh))
            accR.append(round(float(1 - np.abs(fh[ok_] - ah[ok_]).sum() / ah[ok_].sum()), 4) if ok_.sum() >= 10 else None)
        node["accR"] = accR + [HIST]
        for u in ("u", "v"):
            node[u] = {kk: [None if (v is None or (isinstance(v, float) and np.isnan(v))) else int(round(v)) for v in vv.tolist()] for kk, vv in node[u].items()}
        okm = ~np.isnan(mm).all(1)
        a_ = np.nansum(am[okm], 1); f_ = np.nansum(mm[okm], 1)
        node["acc"] = [round(float(1 - np.abs(f_ - a_).sum() / a_.sum()), 4), round(float(np.clip(f_ - a_, 0, None).sum() / a_.sum()), 4),
                       round(float(np.clip(a_ - f_, 0, None).sum() / a_.sum()), 4), int(okm.sum())]
        node["band"] = [round(float(np.exp(q10)), 3), round(float(np.exp(q90)), 3), round(float(np.exp(q50)), 3)]
        node["bandL"] = [round(float(np.exp(q10L)), 3), round(float(np.exp(q90L)), 3), round(float(np.exp(q50L)), 3)]
        nodes[k] = node
    prod = [{"code": c, "name": mp.name[mp.sku == c].iloc[0], "cat": mp.category[mp.sku == c].iloc[0]} for c in sorted(skus)]
    out["levels"][lname] = {"nodes": nodes, "products": prod, "cats": sorted(mp.category.unique().tolist())}
    out["weeks"] = [w_.strftime("%Y-%m-%d") for w_ in allw]
    out["histN"], out["fcN"] = HIST, FC
    print(lname, "nodes", len(nodes), "ALL 13wk model", sum(nodes["ALL"]["u"]["model"][HIST:]) / 1e7, "Cr; budget", sum(nodes["ALL"]["u"]["budget"][HIST:]) / 1e7, "ly", sum(nodes["ALL"]["u"]["ly"][HIST:]) / 1e7)
    print("  band", nodes["ALL"]["band"], "peak", max(nodes["ALL"]["u"]["model"][HIST:]) / 1e7)
json.dump(out, open("ui_data.json", "w"), separators=(",", ":"))
print("bytes", os.path.getsize("ui_data.json"))
