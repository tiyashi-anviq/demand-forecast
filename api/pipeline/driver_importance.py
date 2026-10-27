"""How much does each similarity driver matter for a product's sales, by segment? (weights for the New products screen)

For each segment we model weekly log sales from the same drivers the screen uses, on our own products (primary sales) and on the market's products
(retail sell-out, competitor.csv), and ask how much worse the model predicts PRODUCTS IT HAS NOT SEEN when one driver is scrambled
(permutation importance, 5-fold cross-validation grouped by product, so a product is never in both the fit and the test). That is the situation of a
new product, and it measures how much a driver explains of the sales of a segment's products over time, not just how alike two products look.
Driver  ->  column
  cat     product category (dummy)          tech   technology level           pack   pack format
  price   log selling price                 season month of year + festival week     shelf  shelf life (own only)
  ltype   launch type, or established       dist   weighted distribution      scheme own: trade scheme %, market: promotion depth x share
  timing  season of launch (launched products only)    comp   own: competitor-activity week, market: number of live products in the category
A driver that has no column for a source is left out of that source and the rest are rescaled. Importance is turned into weights per segment, and
segments with few products lean on the overall importances: w = a * segment + (1 - a) * overall, a = n / (n + N0).
Writes impact_weights.json."""
import json, warnings, numpy as np, pandas as pd, lightgbm as lgb
from sklearn.model_selection import GroupKFold
warnings.filterwarnings("ignore")
DR = ["cat", "tech", "pack", "price", "season", "shelf", "ltype", "dist", "scheme", "timing", "comp"]
SEGS = ["Batteries", "Flashlights", "Home care", "Lighting & electrical"]
N0 = 20; REPEATS = 5; FLOOR = 2
seg_of = lambda cat: "Batteries" if cat.startswith("Batteries") else "Flashlights" if cat.startswith("Flash") else "Home care" if cat.startswith("Mosq") else "Lighting & electrical"
seas = lambda m: np.select([np.isin(m, [9, 10, 11]), np.isin(m, [12, 1, 2]), np.isin(m, [3, 4, 5])], [0, 1, 2], 3)

# ---------------- own products (national, primary sales)
d = pd.read_csv("eveready_mock_data_v2.csv", low_memory=False, parse_dates=["week_beginning"])
o = d[(d.reporting_level == "National") & (d.primary_sales_units > 0)].copy()
o["seg"] = o.product_category.map(seg_of); o["y"] = np.log(o.primary_sales_units); o["pid"] = o.product_code
mo = o.week_beginning.dt.month
first = o.groupby("pid").week_beginning.transform("min")
OWN = pd.DataFrame({"pid": o.pid, "seg": o.seg, "y": o.y,
    "cat": o.product_category.astype("category").cat.codes, "tech": o.technology_level.astype("category").cat.codes, "pack": o.pack_format.astype("category").cat.codes,
    "price": np.log(o.average_selling_price_inr), "season": mo, "festival": o.festival.notna().astype(float), "shelf": o.shelf_life_weeks,
    "ltype": o.launch_type.fillna("Established").astype("category").cat.codes, "dist": o.weighted_distribution_pct,
    "scheme": o.trade_scheme_discount_pct.fillna(0), "timing": np.where(o.is_new_product == 1, seas(o.launch_date.fillna(o.week_beginning).pipe(pd.to_datetime, errors="coerce").dt.month.fillna(1).values), np.nan),
    "comp": o.competitor_activity_note.notna().astype(float)})

# ---------------- market products (national retail sell-out, all brands but ours)
c = pd.read_csv("competitor_data_v2.csv", low_memory=False, parse_dates=["week_beginning"])
c = c[(c.market == "NATIONAL") & (c.brand != "Eveready") & (c.retail_sales_units > 0)].copy()
c["seg"] = c.category.map(seg_of); c["pid"] = c.product_name
live = c.groupby(["category", "week_beginning"]).product_name.transform("nunique")
lw = c.groupby("pid").week_beginning.transform("min"); mc = c.week_beginning.dt.month
MKT = pd.DataFrame({"pid": c.pid, "seg": c.seg, "y": np.log(c.retail_sales_units),
    "cat": c.category.astype("category").cat.codes, "tech": c.technology_level.astype("category").cat.codes, "pack": c.pack_format.astype("category").cat.codes,
    "price": np.log(c.average_price_inr), "season": mc, "festival": 0.0, "shelf": np.nan,
    "ltype": c.launch_type.fillna("Established").astype("category").cat.codes, "dist": c.weighted_distribution_pct,
    "scheme": c.sold_on_promotion_pct / 100 * c.avg_promo_discount_pct, "timing": np.where(c.launch_type.notna(), seas(lw.dt.month.values), np.nan), "comp": live})

COLS = {"cat": ["cat"], "tech": ["tech"], "pack": ["pack"], "price": ["price"], "season": ["season", "festival"], "shelf": ["shelf"], "ltype": ["ltype"], "dist": ["dist"],
        "scheme": ["scheme"], "timing": ["timing"], "comp": ["comp"]}
PARAM = dict(objective="regression", num_leaves=8, learning_rate=0.08, n_estimators=160, min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.9, verbose=-1, n_jobs=1)

def importance(df, seed=0):
    """returns {driver: increase in held-out squared error (>=0)} and the held-out R2"""
    drivers = [k for k in DR if df[COLS[k][0]].notna().any() and df[COLS[k][0]].nunique() > 1]
    feats = [f for k in drivers for f in COLS[k]]
    X = df[feats].reset_index(drop=True); y = df.y.values; g = df.pid.values
    nf = min(5, len(set(g))); rs = np.random.RandomState(seed); imp = {k: 0.0 for k in drivers}; sse = 0.0; sst = 0.0
    for tr, te in GroupKFold(nf).split(X, y, g):
        m = lgb.LGBMRegressor(random_state=seed, **PARAM).fit(X.iloc[tr], y[tr])
        base = ((m.predict(X.iloc[te]) - y[te]) ** 2).mean(); sse += base * len(te); sst += ((y[te] - y[tr].mean()) ** 2).sum()
        for k in drivers:
            inc = []
            for _ in range(REPEATS):
                Xp = X.iloc[te].copy(); perm = rs.permutation(len(te))
                for f in COLS[k]: Xp[f] = Xp[f].values[perm]
                inc.append(((m.predict(Xp) - y[te]) ** 2).mean() - base)
            imp[k] += max(np.mean(inc), 0) * len(te)
    n = len(y); return {k: v / n for k, v in imp.items()}, 1 - sse / sst

def share(imp):
    t = sum(imp.values()); return {k: v / t for k, v in imp.items()} if t > 0 else {}

def whole(sh):
    """weights from importance shares: add to 100, nothing below FLOOR, whole numbers"""
    w = np.array([sh.get(k, 0.0) for k in DR]) * 100; w = np.maximum(w, FLOOR); w = w * 100 / w.sum()
    f = np.floor(w).astype(int); r = 100 - f.sum()
    for j in np.argsort(-(w - f))[:r]: f[j] += 1
    return {k: int(v) for k, v in zip(DR, f)}

res = {}
for src, df in (("own", OWN), ("market", MKT)):
    for sg in ["ALL"] + SEGS:
        x = df if sg == "ALL" else df[df.seg == sg]
        if x.pid.nunique() < 5: continue
        imp, r2 = importance(x); res[(src, sg)] = dict(share=share(imp), r2=float(r2), n=int(x.pid.nunique()))
        print(f"{src:6} {sg:22} products {res[(src, sg)]['n']:3d}  held-out R2 {r2:5.2f}  " + "  ".join(f"{k} {100 * v:4.1f}" for k, v in sorted(res[(src, sg)]['share'].items(), key=lambda t: -t[1])[:6]), flush=True)

def combine(sg):
    """own and market importances averaged, weighted by number of products; drivers present in one source only keep that source's value"""
    parts = [(res[(s, sg)]["share"], res[(s, sg)]["n"]) for s in ("own", "market") if (s, sg) in res]
    out = {}
    for k in DR:
        v = [(sh[k], n) for sh, n in parts if k in sh]
        if v: out[k] = sum(a * n for a, n in v) / sum(n for _, n in v)
    t = sum(out.values()); return {k: x / t for k, x in out.items()}
allsh = combine("ALL"); nprod = {sg: sum(res[(s, sg)]["n"] for s in ("own", "market") if (s, sg) in res) for sg in SEGS}
segsh = {}
for sg in SEGS:
    a = nprod[sg] / (nprod[sg] + N0); sh = combine(sg)
    segsh[sg] = {k: a * sh.get(k, allsh.get(k, 0)) + (1 - a) * allsh.get(k, 0) for k in DR}

# ---- stability: bootstrap over products of the overall importance (own + market), to say which weights are firm
rs = np.random.RandomState(3); boots = []
for b in range(8):
    shs = []
    for src, df in (("own", OWN), ("market", MKT)):
        ids = df.pid.unique(); pick = rs.choice(ids, len(ids)); x = pd.concat([df[df.pid == p].assign(pid=f"{p}#{i}") for i, p in enumerate(pick)]); imp, _ = importance(x, seed=b); shs.append((share(imp), len(ids)))
    out = {k: sum(sh.get(k, 0) * n for sh, n in shs if k in sh) / sum(n for sh, n in shs if k in sh) for k in DR if any(k in sh for sh, _ in shs)}
    t = sum(out.values()); boots.append({k: v / t for k, v in out.items()})
spread = {k: float(np.std([bb.get(k, 0) for bb in boots])) for k in DR}

out = dict(drivers=DR, n0=N0, floor=FLOOR, n_products=nprod,
           global_=whole(allsh), segments={sg: whole(segsh[sg]) for sg in SEGS},
           share_global={k: round(100 * allsh.get(k, 0), 1) for k in DR}, share_segments={sg: {k: round(100 * segsh[sg].get(k, 0), 1) for k in DR} for sg in SEGS},
           spread={k: round(100 * v, 1) for k, v in spread.items()},
           by_source={f"{s}|{sg}": dict(r2=round(v["r2"], 3), n=v["n"], share={k: round(100 * x, 1) for k, x in v["share"].items()}) for (s, sg), v in res.items()})
out["global"] = out.pop("global_")
json.dump(out, open("impact_weights.json", "w"), indent=1)
print("global", out["global"]); [print(sg, w) for sg, w in out["segments"].items()]; print("spread (sd of share, pts)", out["spread"])
