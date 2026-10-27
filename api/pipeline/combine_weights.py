"""Merge the weight sets for the New products screen into npd_weights.json:
   impact   weights from how much each driver matters for a segment's sales (driver_importance.py)  <- default on the screen
   predict  weights fitted to make the closest matches predict volume, season and launch curve (fit_weights.py)
   manual   the original hand-set weights
plus how each set does at picking analogues for the products we already have (error of the prediction from the closest matches)."""
import json, numpy as np
import fit_weights as F
I = json.load(open("impact_weights.json")); Pw = json.load(open("predict_weights.json"))
vec = lambda w: np.array([w[k] for k in F.DR], float)
def err(pick):
    out = {"level": [], "season": [], "ramp": []}
    for kind, i, cs in F.TASKS: out[kind].append(F.task_loss(kind, i, cs, pick(F.P[i]["seg"])))
    return {k: round(float(np.mean(v)), 4) for k, v in out.items()}
match = {"manual": err(lambda s: F.wM), "equal": err(lambda s: np.ones(11)),
         "predict_cv": Pw["cv"]["fitted_global"],                               # cross-validated: the fit never saw the product it is scored on
         "impact_overall": err(lambda s: vec(I["global"])), "impact_segment": err(lambda s: vec(I["segments"][s]))}   # not tuned to these errors, so scoring them here is fair
out = dict(drivers=F.DR, manual=F.MANUAL,
           impact=dict(global_=I["global"], segments=I["segments"], share_global=I["share_global"], share_segments=I["share_segments"], spread=I["spread"], n_products=I["n_products"], n0=I["n0"], floor=I["floor"],
                       r2={k: v["r2"] for k, v in I["by_source"].items()}),
           predict=dict(global_=Pw["global"], segments=Pw["segments"]), match=match)
out["impact"]["global"] = out["impact"].pop("global_"); out["predict"]["global"] = out["predict"].pop("global_")
json.dump(out, open("npd_weights.json", "w"), indent=1); print(json.dumps(match, indent=1))
