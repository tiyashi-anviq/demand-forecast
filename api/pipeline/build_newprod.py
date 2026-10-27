"""Data for the New products screen (similarity index and launch forecast), from the national rows of the mock data.

Writes newprod.json:
  products  one profile per product: attributes the similarity index compares, seasonal index, peak season,
            deseasonalised weekly level (mature run-rate) and, for the four launched new products, the launch facts
  ramps     for each launched new product (ours and competitors'), the launch ramp: weekly units since launch (ours) and
            the same as a share of the mature level after removing the seasonal swing
  market    from competitor.csv, per category: brands, price, share, promotion, recent launches, and how fast
            competitors' launches built distribution; also a competitive-pressure level used by the similarity index
Competitor launches (brand type New entrant / New product, 26+ weeks of data) join the pool of launch curves. They are
retail sell-out for another company, so they supply the SHAPE of a ramp and the benchmarks, never our volume.
Established products have no launch date or distribution in the data, so those drivers are left empty for them and
the screen rescales the remaining weights. Run after make_stock.py (stock is not used here); output goes to ../data.
"""
import json, re, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore", category=FutureWarning)

d = pd.read_csv("eveready_mock_data_v2.csv", low_memory=False, parse_dates=["week_beginning"])
n = d[d.reporting_level == "National"].copy().sort_values("week_beginning")
SEAS = {"Festive": [9, 10, 11], "Monsoon": [6, 7, 8], "Winter": [12, 1, 2], "Summer": [3, 4, 5]}
FLAT = 1.15          # busiest season below this multiple of the average week counts as year-round

def season_of(m):
    return next(k for k, v in SEAS.items() if m in v)

def month_index(x):
    """Average weekly units by calendar month as a multiple of the overall average (mean of the 12 values = 1)."""
    m = x.groupby(x.week_beginning.dt.month).primary_sales_units.mean().reindex(range(1, 13))
    m = m.fillna(m.mean()); return (m / m.mean()).values

def peak(idx):
    s = {k: float(np.mean([idx[m - 1] for m in v])) for k, v in SEAS.items()}
    k = max(s, key=s.get); return ("Flat" if s[k] < FLAT else k), s

prods = {}
for code, x in n.groupby("product_code"):
    x = x.sort_values("week_beginning"); f = x.iloc[0]
    new = int(f.is_new_product) == 1
    live = x[x.primary_sales_units.fillna(0) > 0]
    prods[code] = dict(code=code, name=str(f.product_name), cat=str(f.product_category), seg=str(f.business_segment),
        tech=str(f.technology_level), pack=str(f.pack_format), shelf=int(f.shelf_life_weeks),
        asp=round(float(x.average_selling_price_inr.iloc[-26:].mean()), 2),
        scheme=round(float(x.trade_scheme_discount_pct.mean()), 2),
        comp=round(float(x.competitor_activity_note.notna().mean()), 3),
        new=new, launch_type=str(f.launch_type) if new else None,
        launch=live.week_beginning.iloc[0].strftime("%Y-%m-%d") if new else None,
        dist=round(float(x.weighted_distribution_pct.iloc[-13:].mean()), 1) if new and x.weighted_distribution_pct.notna().any() else None,
        _x=x)
# seasonal index: own for established products; new products borrow the average of their category's established products
for p in prods.values():
    p["idx"] = month_index(p["_x"]) if not p["new"] else None
for p in prods.values():
    if p["new"]:
        peers = [q["idx"] for q in prods.values() if not q["new"] and q["cat"] == p["cat"]] or [q["idx"] for q in prods.values() if not q["new"]]
        a = np.mean(peers, axis=0); p["idx"] = a / a.mean(); p["idx_from"] = "category"
    p["peak"], p["season_score"] = peak(p["idx"])
# competitor.csv: market context per category (national market) and a competitive-pressure level per category
cp = pd.read_csv("competitor.csv", low_memory=False, parse_dates=["week_beginning"], date_format="%Y-%m-%d")
cp = cp[cp.market == "NATIONAL"].copy(); LAST = cp.week_beginning.max()
SEG = {p["cat"]: p["seg"] for p in prods.values()}; SEG["Mosquito repellent \u2014 liquid vaporizer"] = "Home care"
pct_rank = lambda v: list(pd.Series(v).rank(pct=True, method="average"))
cats_m = sorted(cp.category.unique()); stat = {}
for cat in cats_m:
    x = cp[cp.category == cat]; l52 = x[x.week_beginning > LAST - pd.Timedelta(weeks=52)]
    stat[cat] = dict(brands=int(x.brand.nunique()), promo=float(l52.sold_on_promotion_pct.mean()), launches=0)
# launches in last 52 weeks: products whose listed_from is within the last year
lf = cp.dropna(subset=["listed_from"]).drop_duplicates("product_name")[["category", "product_name", "listed_from", "brand_type"]]
lf["listed_from"] = pd.to_datetime(lf.listed_from)
for cat in cats_m:
    z = lf[lf.category == cat]; stat[cat]["launches"] = int((z.listed_from > LAST - pd.Timedelta(weeks=52)).sum())
pr = [pct_rank([stat[c][k] for c in cats_m]) for k in ("brands", "promo", "launches")]
score_c = [float(np.mean([pr[j][i] for j in range(3)])) for i in range(len(cats_m))]
order = sorted(range(len(cats_m)), key=lambda i: score_c[i]); level_c = {}
for r, i in enumerate(order): level_c[cats_m[i]] = "Low" if r < len(cats_m) * 0.36 else ("Medium" if r < len(cats_m) * 0.64 else "High")
for p in prods.values(): p["comp_level"] = level_c.get(p["cat"], "Medium")
# mature weekly level (deseasonalised) and launch ramps
ramps = {}
for code, p in prods.items():
    x = p.pop("_x"); idx = p["idx"]
    de = x.primary_sales_units.values / idx[x.week_beginning.dt.month.values - 1]
    if not p["new"]:
        p["level"] = round(float(np.nanmean(de[-52:]))); continue
    p["level"] = round(float(np.nanmean(de[-13:])))
    live = x[x.week_beginning >= pd.Timestamp(p["launch"])]
    u = live.primary_sales_units.values; ix = idx[live.week_beginning.dt.month.values - 1]
    r = u / (ix * p["level"]); sm = np.convolve(np.pad(r, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    p["launch_season"] = season_of(pd.Timestamp(p["launch"]).month)
    ramps[code] = dict(start=p["launch"], units=[int(v) for v in u], ratio=[round(float(min(v, 2.0)), 3) for v in sm])
# ---- competitor launches as extra launch curves, market context per category
cat_idx = {}
for cat in cats_m:                       # monthly index of the category's total retail sales (national)
    w = cp[cp.category == cat].groupby("week_beginning").retail_sales_units.sum()
    m = w.groupby(w.index.month).mean().reindex(range(1, 13)); m = m.fillna(m.mean()); cat_idx[cat] = (m / m.mean()).values
ADV = ("premium", "smart", "wi-fi", "rgb", "app-controlled", "solar")
def tech_of(nm):
    t = nm.lower(); return "Advanced" if any(k in t for k in ADV) else ("Standard" if "standard" in t else None)
def pack_of(nm):
    return "Bundle" if re.search(r"\d+-pack|twin pack|bulb set|combo", nm.lower()) else "Single"
LT = {"New brand entry": "New brand", "New product from existing brand": "New product from existing brand"}
ml, mramps = [], {}
for (cat, name), x in cp.groupby(["category", "product_name"]):
    x = x.sort_values("week_beginning"); f = x.iloc[0]
    if f.brand_type not in ("New entrant", "New product") or pd.isna(f.listed_from) or len(x) < 26: continue
    idx = cat_idx[cat]; u = x.retail_sales_units.values.astype(float); mo = x.week_beginning.dt.month.values - 1
    level = float(np.nanmean(u[-13:] / idx[mo[-13:]]))
    r = u / (idx[mo] * level); sm = np.convolve(np.pad(r, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    code = f"mk{len(ml) + 1:02d}"; pk, sc = peak(idx); lm = pd.Timestamp(f.listed_from).month
    ml.append(dict(code=code, name=name, brand=str(f.brand), cat=cat, seg=SEG.get(cat, "Other"), tech=tech_of(name), pack=pack_of(name), shelf=None,
        asp=round(float(x.average_price_inr.mean()), 2),
        scheme=None, comp_level=level_c[cat], new=True, launch_type=LT.get(f.launch_type), launch=pd.Timestamp(f.listed_from).strftime("%Y-%m-%d"),
        dist=round(float(x.weighted_distribution_pct.iloc[:13].mean()), 1), d13=round(float(x.weighted_distribution_pct.iloc[min(12, len(x) - 1)]), 1),
        u13=int(round(u[:13].mean())), u26=int(round(u[:26].mean())), unow=int(round(u[-13:].mean())), level=int(round(level)),
        idx=[round(float(v), 3) for v in idx], peak=pk, season_score={k: round(v, 2) for k, v in sc.items()},
        launch_season=season_of(lm), src="market", btype=str(f.brand_type), wks=len(x)))
    mramps[code] = dict(ratio=[round(float(min(v, 2.0)), 3) for v in sm[:104]])
for p in prods.values(): p["src"] = "own"
mkt = {}
l13 = cp[cp.week_beginning > LAST - pd.Timedelta(weeks=13)]
for cat in cats_m:
    x = l13[l13.category == cat]; g = x.groupby("brand")
    br = pd.DataFrame(dict(units=g.retail_sales_units.sum(), value=g.retail_sales_value_inr.sum(), type=g.brand_type.agg(lambda v: v.mode().iloc[0]),
        products=g.product_name.nunique(), dist=g.apply(lambda d: np.average(d.weighted_distribution_pct, weights=d.retail_sales_units.clip(lower=1))),
        promo=g.apply(lambda d: np.average(d.sold_on_promotion_pct, weights=d.retail_sales_units.clip(lower=1))))).reset_index()
    br["price"] = br.value / br.units.replace(0, np.nan); br["share"] = br.value / br.value.sum(); br = br.sort_values("share", ascending=False)
    dd = [m_ for m_ in ml if m_["cat"] == cat]
    byt = {}
    for t in ("New brand", "New product from existing brand"):
        v = [m_["d13"] for m_ in dd if m_["launch_type"] == t]; byt[t] = round(float(np.median(v)), 1) if v else None
    mkt[cat] = dict(level=level_c[cat], brands=stat[cat]["brands"], promo=round(stat[cat]["promo"], 1), launches52=stat[cat]["launches"],
        price_med=round(float(br.price.median()), 2), dist13=byt, own=any(p["cat"] == cat for p in prods.values()),
        top=[dict(brand=r.brand, type=r.type, products=int(r.products), price=round(float(r.price), 2), dist=round(float(r.dist), 1), promo=round(float(r.promo), 1),
                  units=int(round(r.units / 13)), share=round(float(r.share), 4)) for r in br.head(8).itertuples()],
        launches=[dict(code=m_["code"], name=m_["name"], brand=m_["brand"], launch=m_["launch"], type=m_["launch_type"], price=m_["asp"], d13=m_["d13"], u13=m_["u13"], u26=m_["u26"], unow=m_["unow"], wks=m_["wks"])
                  for m_ in sorted(dd, key=lambda m_: m_["launch"], reverse=True)])
for p in prods.values():
    p["idx"] = [round(float(v), 3) for v in p["idx"]]; p["season_score"] = {k: round(v, 2) for k, v in p["season_score"].items()}
out = dict(asof=n.week_beginning.max().strftime("%Y-%m-%d"), ref_dist=60.0, seasons=SEAS,
           cats=sorted(set(cats_m) | {p["cat"] for p in prods.values()}), products=list(prods.values()) + ml, ramps={**ramps, **mramps}, market=mkt)
json.dump(out, open("newprod.json", "w"), separators=(",", ":"))
print(len(out["products"]), "profiles,", len(out["ramps"]), "launch curves,", len(mkt), "market categories")
print({c: (m["level"], m["brands"], m["promo"], m["launches52"]) for c, m in mkt.items()})
print(len(open("newprod.json").read()) // 1024, "KB")
