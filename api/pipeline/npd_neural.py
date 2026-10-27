"""Neural cold-start model for the New products screen (alternative to the similar-product index).

A small PyTorch network turns a product's attributes (the screen's drivers) into an embedding and predicts three things from it:
  level   log of mature weekly run-rate          (all 30 own + 45 market products)
  season  12-month seasonal index (log, mean 0)   (products with their own seasonal index)
  ramp    launch curve, share of mature level, weeks 0..51   (launched products)
Heads share the encoder, so the drivers' weights are learned jointly. An ensemble of seeds gives a spread (a range), and the
result is scored with the same 5-fold cross-validation (folds stratified by segment, a product never in both fit and test) and
the same error measures as fit_weights.py, so it can be set next to the manual, equal, predict-fit and impact weights:
  level  mean |log(pred / actual)|     season  mean |log(idx / actual)|     ramp  sum|pred - act| / sum(act)
Run after the retrain has finished (needs torch: pip install torch --index-url https://download.pytorch.org/whl/cpu).
Writes npd_neural.json."""
import json, sys, numpy as np, torch, torch.nn as nn
torch.set_num_threads(2)
D = json.load(open("newprod.json")); P = D["products"]; R = D["ramps"]; REF = D["ref_dist"]
SEGS = sorted({p["seg"] for p in P}); CATS = sorted({p["cat"] for p in P})
TECH = sorted({p["tech"] for p in P if p["tech"]}); PACK = sorted({p["pack"] for p in P if p["pack"]})
PEAK = ["Festive", "Winter", "Summer", "Monsoon", "Flat"]; LT = sorted({p["launch_type"] for p in P if p["launch_type"]}); COMP = ["Low", "Medium", "High"]
SEAS = ["Festive", "Winter", "Summer", "Monsoon"]

def onehot(v, opts): return [1.0 if v == o else 0.0 for o in opts]
def feats(p):
    """attributes only: no sales, so it works for a product that has not launched. Missing values -> 0 plus a 'known' flag."""
    f = onehot(p["cat"], CATS) + onehot(p["seg"], SEGS) + onehot(p["tech"], TECH) + onehot(p["pack"], PACK) + onehot(p["peak"], PEAK)
    f += onehot(p.get("launch_type") if p["new"] else None, LT) + [1.0 if p["new"] else 0.0]
    f += onehot(p.get("launch_season") if p["new"] else None, SEAS)
    f += onehot(p.get("comp_level"), COMP)
    f += [np.log(p["asp"]) - 4.5, (np.log(p["dist"] / REF) if p["dist"] else 0.0), 1.0 if p["dist"] else 0.0,
          (np.log(p["shelf"] / 260) if p["shelf"] else 0.0), 1.0 if p["shelf"] else 0.0, (p["scheme"] or 0.0), 1.0 if p["scheme"] is not None else 0.0]
    return f
X = np.array([feats(p) for p in P], np.float32)
LV = np.log(np.array([p["level"] for p in P], float)); LV_MU = LV.mean()
IDX = np.log(np.array([p["idx"] for p in P], float)); IDX = IDX - IDX.mean(1, keepdims=True)
HAS_S = np.array([p.get("idx_from") != "category" for p in P])
launched = [i for i, p in enumerate(P) if p["code"] in R]
RAMP = np.zeros((len(P), 52), np.float32); HAS_R = np.zeros(len(P), bool)
for i in launched:
    a = R[P[i]["code"]]["ratio"]; RAMP[i] = [a[min(w, len(a) - 1)] for w in range(52)]; HAS_R[i] = True
SRC = np.array([0.0 if p["src"] == "market" else 1.0 for p in P], np.float32)   # source flag: lets the net learn own vs market level

class Net(nn.Module):
    def __init__(s, d, h=24, drop=0.2):
        super().__init__()
        s.enc = nn.Sequential(nn.Linear(d, h), nn.GELU(), nn.Dropout(drop), nn.Linear(h, h), nn.GELU())
        s.level = nn.Linear(h, 1); s.season = nn.Linear(h, 12); s.ramp = nn.Linear(h, 3)   # ramp: plateau-time, steepness, overshoot
        s.t = torch.arange(52, dtype=torch.float32)
    def forward(s, x):
        z = s.enc(x); r = s.ramp(z)
        k = 1 + 20 * torch.sigmoid(r[:, :1]); sl = 0.05 + 0.5 * torch.sigmoid(r[:, 1:2]); ov = 1 + 0.4 * torch.sigmoid(r[:, 2:3])
        ramp = ov * torch.sigmoid(sl * 4 * (s.t[None] - k))
        return s.level(z).squeeze(1), s.season(z) - s.season(z).mean(1, keepdim=True), torch.clamp(ramp, 0, 1.4)

def train(tr, seed, epochs=400):
    torch.manual_seed(seed); np.random.seed(seed)
    net = Net(X.shape[1]); opt = torch.optim.AdamW(net.parameters(), lr=0.01, weight_decay=0.02)
    x = torch.tensor(X[tr]); y = torch.tensor(LV[tr] - LV_MU, dtype=torch.float32); s = torch.tensor(IDX[tr], dtype=torch.float32)
    r = torch.tensor(RAMP[tr]); ms = torch.tensor(HAS_S[tr]); mr = torch.tensor(HAS_R[tr])
    for ep in range(epochs):
        net.train(); opt.zero_grad(); noise = x + 0.03 * torch.randn_like(x)
        lv, se, ra = net(noise); loss = (lv - y).abs().mean()
        if ms.any(): loss = loss + 2.0 * (se[ms] - s[ms]).abs().mean()
        if mr.any(): loss = loss + 2.0 * (ra[mr] - r[mr]).abs().mean()
        loss.backward(); opt.step()
    return net.eval()

def predict(nets, i):
    with torch.no_grad():
        o = [n(torch.tensor(X[i:i + 1])) for n in nets]
    lv = np.array([a[0].item() for a in o]) + LV_MU; se = np.mean([a[1][0].numpy() for a in o], 0); ra = np.mean([a[2][0].numpy() for a in o], 0)
    return lv, se, ra

def score(nets, i):
    lv, se, ra = predict(nets, i); out = {"level": float(abs(lv.mean() - LV[i]))}
    if HAS_S[i]: out["season"] = float(np.abs(se - IDX[i]).mean())
    if HAS_R[i]: out["ramp"] = float(np.abs(ra - RAMP[i]).sum() / max(RAMP[i].sum(), 1e-9))
    return out

if __name__ == "__main__":
    SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    rs = np.random.RandomState(1); fold = {}
    for sg in SEGS:                      # same fold construction as fit_weights.py
        ids = [i for i in range(len(P)) if P[i]["seg"] == sg]; rs.shuffle(ids)
        for r, i in enumerate(ids): fold[i] = r % 5
    res = {"level": [], "season": [], "ramp": []}; cover = []
    for f in range(5):
        tr = [i for i in range(len(P)) if fold[i] != f]; te = [i for i in range(len(P)) if fold[i] == f]
        nets = [train(tr, s) for s in range(SEEDS)]
        for i in te:
            for k, v in score(nets, i).items(): res[k].append(v)
            lv, _, _ = predict(nets, i); lo, hi = np.percentile(lv, [10, 90]); cover.append(lo - 0.15 <= LV[i] <= hi + 0.15)
        print("fold", f, "done", flush=True)
    cv = {k: round(float(np.mean(v)), 4) for k, v in res.items()}
    print("neural CV", cv, "level range coverage", round(float(np.mean(cover)), 2))
    json.dump(dict(cv=cv, seeds=SEEDS, level_range_coverage=float(np.mean(cover)), note="same folds and errors as fit_weights.py; compare with npd_weights.json match{}"), open("npd_neural.json", "w"), indent=1)
