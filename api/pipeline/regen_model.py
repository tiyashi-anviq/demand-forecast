"""Design matrix and ridge fit used to rebuild the Sep 2022 - Sep 2023 year (make_extra_year2.py).

Each series' log1p(primary_sales_units) over the three real years (Oct 2023 - Sep 2026) is explained by
  trend, smooth annual season (Fourier), festival effects placed on each festival's actual week, and weather
  (rain, previous-week rain, max temperature, power cuts, heatwave, cyclone week).
The fitted effects are then applied to 2022-23 with its own festival dates and weather.
"""
import re
import numpy as np, pandas as pd

PRIORITY = ["Durga Puja", "Kali Puja / Diwali"]
MINOR = {"jagaddhatri": ["Jagaddhatri Puja"], "xmas": ["Christmas / Park Street festival"], "gangasagar": ["Gangasagar Mela"],
         "bookfair": ["Kolkata International Book Fair"], "saraswati": ["Saraswati Puja"], "holi": ["Dol Jatra / Holi"],
         "eid": ["Eid ul-Fitr"], "poila": ["Poila Baisakh", "Chaitra Sale"], "jamai": ["Jamai Sasthi"], "rath": ["Rath Yatra"],
         "ganesh": ["Ganesh Chaturthi"], "vishwa": ["Vishwakarma Puja"]}
DURGA_OFF = list(range(-6, 9))          # weeks around the first Durga Puja week (same stretch the models use)
DIWALI_OFF = list(range(-2, 4))
MIN_OFF = (-1, 0, 1)
MON_SHOCK = {"2025-06-09", "2025-06-16", "2025-06-23", "2025-06-30", "2025-07-07", "2025-07-14", "2025-07-21", "2025-07-28", "2025-08-04", "2025-08-11"}
MON_SKUS = {"rch", "hyb", "cvt"}


def keys(s):
    if not isinstance(s, str): return []
    return [k for k in (re.sub(r"\s*\(.*", "", p).strip() for p in s.split(";")) if k]


def anchors(weeks, fest, name):
    """weeks (DatetimeIndex) at which a festival group with `name` starts: first week of every cluster of consecutive labelled weeks"""
    hit = [w for w in weeks if name in keys(fest.get(w))]
    out, prev = [], None
    for w in hit:
        if prev is None or (w - prev).days > 21: out.append(w)
        prev = w
    return out


def design(weeks, fest, wx):
    """rows = weeks; fest: dict week -> festival string; wx: DataFrame indexed by week with rainfall_mm, temp_max_c, power_cut_hours, heatwave_flag, cyclone_event."""
    n = len(weeks); idx = {w: i for i, w in enumerate(weeks)}
    cols, names = [], []
    def add(v, nm): cols.append(np.asarray(v, float)); names.append(nm)
    t0 = pd.Timestamp("2023-10-02")
    t = np.array([(w - t0).days / 7.0 for w in weeks]); add(t / 52.0, "trend")
    doy = np.array([w.dayofyear + 3 for w in weeks]) / 365.25 * 2 * np.pi            # mid-week
    for k in (1, 2, 3):
        add(np.sin(k * doy), f"sin{k}"); add(np.cos(k * doy), f"cos{k}")
    dur = anchors(weeks, fest, "Durga Puja"); diw = anchors(weeks, fest, "Kali Puja / Diwali")
    for off in DURGA_OFF:
        v = np.zeros(n)
        for a in dur:
            j = idx[a] + off
            if 0 <= j < n: v[j] = 1
        add(v, f"durga{off:+d}")
    for off in DIWALI_OFF:
        v = np.zeros(n)
        for a in diw:
            j = idx[a] + off
            if 0 <= j < n: v[j] = 1
        add(v, f"diwali{off:+d}")
    for g, ks in MINOR.items():
        occ = [w for w in weeks if any(k in keys(fest.get(w)) for k in ks)]
        for off in MIN_OFF:
            v = np.zeros(n)
            for a in occ:
                j = idx[a] + off
                if 0 <= j < n: v[j] = 1
            add(v, f"{g}{off:+d}")
    w = wx.reindex(weeks)
    rain = w.rainfall_mm.values; add((rain - 34) / 42, "rain"); add(np.r_[0, (rain[:-1] - 34) / 42], "rain_l1")
    add((w.temp_max_c.values - 32) / 3.4, "temp"); add((w.power_cut_hours.values - 4) / 3.2, "power")
    add(w.heatwave_flag.fillna(0).values, "heat"); add(w.cyclone_event.notna().astype(float).values, "cyclone")
    return np.column_stack(cols), names


def penalty(names, alpha):
    p = np.full(len(names), alpha, float)
    for i, nm in enumerate(names):
        if nm == "trend" or nm.startswith(("sin", "cos")): p[i] = 1e-3
    return p


def ridge(X, y, wts, pen):
    Xa = np.column_stack([np.ones(len(X)), X]); P = np.diag(np.r_[1e-6, pen])
    W = wts[:, None]
    return np.linalg.solve(Xa.T @ (W * Xa) + P, Xa.T @ (wts * y))


def predict(beta, X):
    return beta[0] + X @ beta[1:]
