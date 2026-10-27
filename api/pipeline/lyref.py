"""Festival-aware 'same week last year' reference.

For every week returns the index (into the same week list) of the comparison week one year earlier:
 - a festival week -> the week the SAME festival fell in last year (from the dated festival calendar in ext_ext.csv)
 - a non-festival week inside the Durga Puja / Diwali stretch -> last year's week at the same distance from the nearest
   Durga Puja / Diwali anchor
 - any other week -> 52 weeks earlier
Returns (ref_idx, label) arrays; label is the festival name used for the match, or None.
"""
import re
import numpy as np, pandas as pd

PRIORITY = ["Durga Puja", "Kali Puja / Diwali"]


def _keys(s):
    if not isinstance(s, str): return []
    out = []
    for p in s.split(";"):
        k = re.sub(r"\s*\(.*", "", p).strip()
        if k: out.append(k)
    return sorted(out, key=lambda k: (PRIORITY.index(k) if k in PRIORITY else 99))


def ly_ref(weeks, ext):
    e = ext.copy()
    e["week_beginning"] = pd.to_datetime(e["week_beginning"])
    fest = e.set_index("week_beginning")["festival"].reindex(weeks)
    keys = [_keys(x) for x in fest.values]
    n = len(weeks)
    ref = np.arange(n) - 52
    lab = [None] * n
    # anchors of the two big festivals
    anch = {k: [i for i in range(n) if k in keys[i]] for k in PRIORITY}
    dur = anch[PRIORITY[0]]
    inst = lambda i: any(-6 <= i - a <= 8 for a in dur)   # same festive stretch as the model (Durga -6..+8 weeks)
    for i in range(n):
        done = False
        for k in keys[i]:                       # same festival, previous year (40-64 weeks back)
            prev = [j for j in range(n) if k in keys[j] and 40 <= i - j <= 64]
            if prev:
                ref[i] = prev[-1]; lab[i] = k; done = True; break
    return ref, lab


if __name__ == "__main__":
    e = pd.read_csv("ext_ext.csv", parse_dates=["week_beginning"])
    wk = pd.date_range("2023-10-02", "2027-03-29", freq="7D")
    r, l = ly_ref(wk, e)
    for i in range(len(wk)):
        if l[i] and wk[i].year >= 2025 and (wk[i].month >= 9 or wk[i].month <= 4):
            print(wk[i].date(), "->", wk[r[i]].date() if r[i] >= 0 else None, l[i])
