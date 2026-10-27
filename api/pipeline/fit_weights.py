"""Fit the driver weights of the New products similarity index from the products we already have (newprod.json).

Idea: treat every existing product as if it were a new launch. Score all other products against it with the same 11 drivers the screen uses,
take the closest matches the way the screen does, and see how well they predict what really happened:
  level   mature weekly run-rate (the screen's volume)             30 own + 45 market products, each predicted from its own pool
  season  12-month seasonal shape (the screen's seasonal index)   same
  ramp    launch curve, share of mature level by week since listing   49 launches (4 ours, 45 market's)
The weights are chosen to minimise those prediction errors (each task scaled by the error of the old hand-set weights, so the three count equally).
Category is held at its set weight and no other driver goes below 2. Segments with few products lean on the overall weights: w_segment = a * fitted_segment + (1 - a) * overall, a = n / (n + N0).
Checked on products the fit never saw: 5-fold cross-validation, folds stratified by segment, scored against the hand-set and equal weights.
Writes predict_weights.json (merged into npd_weights.json by combine_weights.py)."""
import json, sys, numpy as np

D = json.load(open("newprod.json")); P = D["products"]; R = D["ramps"]; REF = D["ref_dist"]
DR = ["cat", "tech", "pack", "price", "season", "shelf", "ltype", "dist", "scheme", "timing", "comp"]
MANUAL = dict(cat=25, tech=3, pack=20, price=12, season=8, shelf=3, ltype=6, dist=12, scheme=2, timing=4, comp=5)
GRID = [2, 3, 5, 8, 12, 18, 26]          # no zero: a driver the data cannot speak to keeps a small say
FIXED = {"cat": 25}                      # category is not learnable here: same-category products already rank first, so it stays as set
N0 = 20; K = 3
SEASONS = ["Festive", "Winter", "Summer", "Monsoon"]; COMP = ["Low", "Medium", "High"]
SEG = {p["cat"]: p["seg"] for p in P}
nan = np.nan
def cyc(a, b):
    if a not in SEASONS or b not in SEASONS: return 9
    d = abs(SEASONS.index(a) - SEASONS.index(b)); return min(d, 4 - d)
def near(lst, a, b): return 1.0 if a == b else 0.5 if abs(lst.index(a) - lst.index(b)) == 1 else 0.0

def score(k, A, B):
    """same rules as score() in similarity.js, with the target product A standing in for the user's inputs"""
    if k == "cat": return 1.0 if B["cat"] == A["cat"] else 0.5 if B["seg"] == SEG[A["cat"]] else 0.0
    if k == "tech": return nan if not A["tech"] or not B["tech"] else float(A["tech"] == B["tech"])
    if k == "pack": return nan if not A["pack"] or not B["pack"] else float(A["pack"] == B["pack"])
    if k == "price": return float(np.clip(1 - abs(np.log(A["asp"] / B["asp"])) / np.log(4), 0, 1))
    if k == "season":
        a, b = A["peak"], B["peak"]
        return 1.0 if a == b else 0.4 if (a == "Flat" or b == "Flat") else 0.4 if cyc(a, b) == 1 else 0.0
    if k == "shelf": return nan if not A["shelf"] or not B["shelf"] else near([104, 260, 520], A["shelf"], B["shelf"])
    if k == "ltype":
        if not A["new"] or not A["launch_type"]: return nan
        if B["new"] and not B["launch_type"]: return nan
        if not B["new"]: return 0.3
        return 1.0 if B["launch_type"] == A["launch_type"] else 0.5 if A["launch_type"] == "Line extension" else 0.2
    if k == "dist": return nan if not A["dist"] or B["dist"] is None else float(np.clip(1 - abs(A["dist"] - B["dist"]) / 30, 0, 1))
    if k == "scheme": return nan if A["scheme"] is None or B["scheme"] is None else float(np.clip(1 - abs(A["scheme"] - B["scheme"]) / 2, 0, 1))
    if k == "timing":
        if not A.get("launch_season") or not B.get("launch_season"): return nan
        c = cyc(A["launch_season"], B["launch_season"]); return 1.0 if c == 0 else 0.5 if c == 1 else 0.0
    if k == "comp": return nan if not A["comp_level"] or not B["comp_level"] else near(COMP, A["comp_level"], B["comp_level"])

n = len(P); code = {p["code"]: i for i, p in enumerate(P)}
S = np.full((n, n, len(DR)), nan)
for i, A in enumerate(P):
    for j, B in enumerate(P):
        if i != j:
            for d, k in enumerate(DR): S[i, j, d] = score(k, A, B)
OBS = ~np.isnan(S); S0 = np.nan_to_num(S)

def cands(i, pool, minsame=3):
    c = [j for j in pool if j != i]
    same = [j for j in c if P[j]["cat"] == P[i]["cat"]]
    return same if len(same) >= minsame else c

own = [i for i, p in enumerate(P) if p["src"] != "market"]; mkt = [i for i, p in enumerate(P) if p["src"] == "market"]
launched = [i for i, p in enumerate(P) if p["code"] in R]
LV = np.array([p["level"] for p in P], float); IDX = np.array([p["idx"] for p in P], float)
def ratio(i, w):
    a = R[P[i]["code"]]["ratio"]; return a[min(w, len(a) - 1)]
RAMPS = {i: np.array(R[P[i]["code"]]["ratio"][:52], float) for i in launched}
RAMPX = {i: np.array([ratio(i, w) for w in range(52)]) for i in launched}   # padded to 52 weeks with the last value, as the screen does

TASKS = []   # (kind, target, candidate list)
for i in range(n):
    TASKS.append(("level", i, cands(i, own if P[i]["src"] != "market" else mkt)))
    if P[i].get("idx_from") != "category": TASKS.append(("season", i, cands(i, own if P[i]["src"] != "market" else mkt)))
for i in launched: TASKS.append(("ramp", i, cands(i, launched)))

def index_vec(w, i, cs):
    Wd = w[None, :]; num = (S0[i, cs] * Wd).sum(1); den = (OBS[i, cs] * Wd).sum(1)
    return np.where(den > 0, 100 * num / np.maximum(den, 1e-9), 0.0)

def task_loss(kind, i, cs, w):
    ix = index_vec(w, i, cs); order = np.argsort(-ix, kind="stable")
    if kind == "ramp":
        wt = np.maximum(ix, 1) ** 2;
        pred = np.minimum(1.25, (wt[:, None] * np.vstack([RAMPX[cs[o]] for o in range(len(cs))])).sum(0) / wt.sum())
        act = RAMPX[i][:min(52, len(RAMPS[i]))]; return float(np.abs(pred[:len(act)] - act).sum() / max(act.sum(), 1e-9))
    top = [o for o in order[:K] if ix[o] > 0]
    if not top: return 1.0
    s = ix[top]
    if kind == "level":
        sc = [np.clip(P[i]["dist"] / (P[cs[o]]["dist"] or REF), 0.4, 2.5) if P[i]["dist"] else 1.0 for o in top]
        lv = np.array([LV[cs[o]] * c for o, c in zip(top, sc)]); pred = (s * lv).sum() / s.sum(); return float(abs(np.log(pred / LV[i])))
    idx = (s[:, None] * np.vstack([IDX[cs[o]] for o in top])).sum(0) / s.sum(); idx = idx / idx.mean()
    return float(np.abs(np.log(idx / IDX[i])).mean())

def losses(w, tasks):
    out = {"level": [], "season": [], "ramp": []}
    for kind, i, cs in tasks: out[kind].append(task_loss(kind, i, cs, w))
    return {k: (np.mean(v) if v else np.nan) for k, v in out.items()}

wM = np.array([MANUAL[k] for k in DR], float)
def make_objective(tasks):
    base = losses(wM, tasks)
    def J(w):
        if w.sum() <= 0: return 9.0
        l = losses(w, tasks); return float(np.nanmean([l[k] / base[k] for k in l if base[k] and not np.isnan(base[k])]))
    return J, base

def fit(tasks, start=None, sweeps=4):
    J, base = make_objective(tasks); w = (start if start is not None else wM).copy(); best = J(w)
    for _ in range(sweeps):
        moved = False
        for d in np.random.RandomState(0).permutation(len(DR)):
            if DR[d] in FIXED: continue
            for g in GRID:
                if g == w[d]: continue
                w2 = w.copy(); w2[d] = g; v = J(w2)
                if v < best - 1e-5: w, best, moved = w2, v, True
        if not moved: break
    return w, best

def norm(w): return 100 * w / w.sum()
def whole(w):
    """whole-number weights that add to 100 (largest remainder), for the screen's drop-downs"""
    w = norm(np.asarray(w, float)); f = np.floor(w).astype(int); r = 100 - f.sum()
    for j in np.argsort(-(w - f))[:r]: f[j] += 1
    return [int(x) for x in f]
SEGS = sorted({p["seg"] for p in P})
seg_of_task = lambda t: P[t[1]]["seg"]

def fit_all(tasks):
    wg, _ = fit(tasks); out = {"global": wg}
    for sg in SEGS:
        tk = [t for t in tasks if seg_of_task(t) == sg]
        ntar = len({t[1] for t in tk})
        if ntar < 4: out[sg] = wg; continue
        ws, _ = fit(tk, start=wg); a = ntar / (ntar + N0); out[sg] = a * norm(ws) + (1 - a) * norm(wg)
    return out

if __name__ == "__main__":
    # ---- 5-fold cross-validation, folds stratified by segment, on target products
    rs = np.random.RandomState(1); fold = {}
    for sg in SEGS:
        ids = [i for i in range(n) if P[i]["seg"] == sg]; rs.shuffle(ids)
        for r, i in enumerate(ids): fold[i] = r % 5
    res = {m: {"level": [], "season": [], "ramp": []} for m in ("manual", "equal", "fitted_global", "fitted_segment")}
    for f in range(5):
        train = [t for t in TASKS if fold[t[1]] != f]; test = [t for t in TASKS if fold[t[1]] == f]
        W = fit_all(train); eq = np.ones(len(DR))
        for t in test:
            kind, i, cs = t; sg = P[i]["seg"]
            for m, w in (("manual", wM), ("equal", eq), ("fitted_global", W["global"]), ("fitted_segment", W[sg])):
                res[m][kind].append(task_loss(kind, i, cs, np.asarray(w, float)))
        print("fold", f, "done", flush=True)
    cv = {m: {k: round(float(np.mean(v)), 4) for k, v in r.items()} for m, r in res.items()}
    for m, r in cv.items(): print(f"{m:16}", r)
    # ---- final fit on everything
    W = fit_all(TASKS)
    full = {m: losses(np.asarray(w, float), TASKS) for m, w in (("manual", wM), ("fitted_global", W["global"]))}
    out = dict(drivers=DR, manual=MANUAL, n_tasks={k: sum(1 for t in TASKS if t[0] == k) for k in ("level", "season", "ramp")},
               n_products={sg: sum(1 for p in P if p["seg"] == sg) for sg in SEGS}, shrink_n0=N0,
               global_=dict(zip(DR, whole(W["global"]))),
               segments={sg: dict(zip(DR, whole(W[sg]))) for sg in SEGS},
               cv={m: v for m, v in cv.items()},
               cv_gain={k: round(1 - cv["fitted_global"][k] / cv["manual"][k], 3) for k in cv["manual"]},
               cv_gain_segment={k: round(1 - cv["fitted_segment"][k] / cv["manual"][k], 3) for k in cv["manual"]})
    out["global"] = out.pop("global_")
    json.dump(out, open("predict_weights.json", "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("global", "cv_gain", "cv_gain_segment")}, indent=1))
