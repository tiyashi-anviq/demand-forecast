"""Which festivals / seasons lift which product categories (national, weekly primary sales, units).
Lift = week's sales / the category's own normal level, where normal = centred 27-week rolling median (strips trend and slow seasonality).
For each event, the 'run-up' is the mean lift over the 4 weeks up to and including the event's first week plus 1 week after (offsets -4..+1),
averaged over every year the event occurs in the data; 'peak week' is the offset with the highest average lift.
Output: festival_lift.csv (category, event, runup_lift, peak_offset, peak_lift, n_years) and festival_profile.csv (lift by offset)."""
import numpy as np, pandas as pd
d = pd.read_csv("eveready_mock_data_v2.csv", low_memory=False, parse_dates=["week_beginning"])
n = d[d.reporting_level == "National"]
cat = n.groupby(["week_beginning", "product_category"]).primary_sales_units.sum().unstack()
weeks = cat.index
base = cat.rolling(27, center=True, min_periods=14).median()
lift = cat / base
fest = n.drop_duplicates("week_beginning").set_index("week_beginning").festival.reindex(weeks).fillna("")
EV = {"Durga Puja": r"Durga Puja \(", "Mahalaya": "Mahalaya", "Kojagari Lakshmi Puja": "Kojagari Lakshmi", "Kali Puja / Diwali": "Kali Puja / Diwali",
      "Bhai Phonta": "Bhai Phonta", "Jagaddhatri Puja": "Jagaddhatri", "Ganesh Chaturthi": "Ganesh Chaturthi", "Vishwakarma Puja": "Vishwakarma",
      "Rath Yatra": "Rath Yatra", "Saraswati Puja": "Saraswati Puja", "Dol Jatra / Holi": "Dol Jatra / Holi", "Eid ul-Fitr": "Eid ul-Fitr",
      "Poila Baisakh / Chaitra Sale": "Poila Baisakh|Chaitra Sale", "Gangasagar Mela": "Gangasagar", "Book Fair": "Book Fair", "Christmas / Park Street": "Christmas"}
anch = {}
for k, pat in EV.items():
    f = fest.str.contains(pat).values; a = np.where(f & ~np.r_[False, f[:-1]])[0]; anch[k] = a
wd = weeks.to_series()
anch["Christmas (25 Dec)"] = np.array([i for i, w in enumerate(weeks) if w <= pd.Timestamp(w.year, 12, 25) < w + pd.Timedelta(days=7)])
anch["New Year (1 Jan)"] = np.array([i for i, w in enumerate(weeks) if w <= pd.Timestamp((w + pd.Timedelta(days=6)).year, 1, 1) < w + pd.Timedelta(days=7)])
rows, prof = [], []
for c in cat.columns:
    L = lift[c].values
    for k, a in anch.items():
        occ = [a_ for a_ in a if a_ - 6 >= 0 and a_ + 4 < len(weeks) and not np.isnan(L[a_ - 6:a_ + 5]).all()]
        if not occ: continue
        M = np.array([[L[a_ + o] for o in range(-6, 5)] for a_ in occ]); m = np.nanmean(M, 0)
        run = np.nanmean(M[:, 2:8], 1)                      # offsets -4..+1
        rows.append(dict(category=c, event=k, runup_lift=round(float(np.nanmean(run)), 3), peak_offset=int(np.argmax(m)) - 6, peak_lift=round(float(np.nanmax(m)), 3), n_years=len(occ)))
        for o, v in zip(range(-6, 5), m): prof.append(dict(category=c, event=k, offset=o, lift=round(float(v), 3)))
R = pd.DataFrame(rows); R.to_csv("festival_lift.csv", index=False); pd.DataFrame(prof).to_csv("festival_profile.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
P = R.pivot(index="category", columns="event", values="runup_lift"); print((P - 1).mul(100).round(0).astype("Int64").to_string())
print(); top = R.sort_values("runup_lift", ascending=False).head(14); print(top.to_string(index=False))
print(); print(R.sort_values("runup_lift").head(8).to_string(index=False))
print(R.groupby("event").n_years.max().to_dict())
