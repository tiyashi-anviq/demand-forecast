import { useMemo } from 'react';
import { useApp } from '../context.js';
import Kpis from '../components/Kpis.jsx';
import Legend from '../components/Legend.jsx';
import ChartCanvas from '../components/ChartCanvas.jsx';
import { weekShare } from '../components/Drivers.jsx';
import { festFlags, applyScenario, isBase } from '../lib/scenario.js';
import { useApi } from '../lib/api.js';
import { SegBare } from '../components/Controls.jsx';
import { css, tooltipBase, baseOptions, xScale, yScale, dividerPlugin } from '../lib/chart.js';
import { MON, p2, fK, fCr, fN, fS, fP, sum } from '../lib/format.js';

const SERIES = [
  { k: 'actual', name: 'Actual', col: '--reiq-chart-1', cls: '' },
  { k: 'model', name: 'Forecast (ensemble)', col: '--reiq-text-primary', cls: '' },
  { k: 'm3', name: 'Model M3 run', col: '--reiq-chart-2', cls: 'dash' },
  { k: 'm2', name: 'Model M2 run', col: '--reiq-chart-6', cls: 'dash' },
  { k: 'm1', name: 'Model M1 run', col: '--reiq-chart-5', cls: 'dash' },
  { k: 'p50', name: 'P50 (median)', col: '--reiq-chart-7', cls: 'dash' },
  { k: 'sales', name: 'Sales-team forecast (3 months ahead)', col: '--reiq-chart-3', cls: 'dash' },
  { k: 'ly', name: 'Last year', col: '--reiq-chart-4', cls: 'dot' },
  { k: 'supply', name: 'Supply-constrained', col: '--reiq-chart-2', cls: 'dot' },
  { k: 'budget', name: 'Budget', col: '--reiq-chart-8', cls: 'dash' },
];

const mLab = (m) => MON[+m.slice(5, 7) - 1] + ' ' + m.slice(2, 4);
const mFull = (m) => MON[+m.slice(5, 7) - 1] + ' ' + m.slice(0, 4);
const shift = (m, k) => { const d = new Date(Date.UTC(+m.slice(0, 4), +m.slice(5, 7) - 1 + k, 1)); return d.getUTCFullYear() + '-' + p2(d.getUTCMonth() + 1); };
const daysIn = (m) => new Date(Date.UTC(+m.slice(0, 4), +m.slice(5, 7), 0)).getUTCDate();

/** The weekly forecast rolled up to months. A week that straddles two months is split by days (pro-rata).
 *  A month is only reported when every one of its days is covered by the weekly data. */
function rollUp(W, arrs) {
  const first = W[0], last = W[W.length - 1];
  const ms = []; let m = first.slice(0, 7);
  const lastDay = new Date(last + 'T00:00:00Z'); lastDay.setUTCDate(lastDay.getUTCDate() + 6);
  const lastM = lastDay.getUTCFullYear() + '-' + p2(lastDay.getUTCMonth() + 1);
  while (m <= lastM) { ms.push(m); m = shift(m, 1); }
  const sh = ms.map((mm) => W.map((w) => weekShare(w, mm)));
  const covered = ms.map((mm, j) => Math.abs(sh[j].reduce((t, x) => t + x, 0) * 7 - daysIn(mm)) < 1e-6);
  const keep = ms.map((_, j) => j).filter((j) => covered[j]);
  const out = {};
  Object.entries(arrs).forEach(([k, a]) => {
    out[k] = keep.map((j) => {
      let t = 0;
      for (let i = 0; i < W.length; i++) { if (sh[j][i] > 0) { if (a[i] == null) return null; t += sh[j][i] * a[i]; } }
      return t;
    });
  });
  return { months: keep.map((j) => ms[j]), ...out };
}

export default function MonthlyOutlook() {
  const { D, level, mea, nodeKey, theme, useSS, lev } = useApp();
  const [hidden, setHidden] = useSS('fc.hidden', { budget: true });
  const [view, setView] = useSS('fc.view', 'chart');
  const { data: DR } = useApi('/api/drivers?level=' + encodeURIComponent(level));
  const { data: VA } = useApi('/api/vintages');
  const W = D.weeks, HN = D.histN;
  const nd = D.levels[level].nodes[nodeKey];
  const n0 = nd?.[mea];
  const act = !isBase(lev), fw = useMemo(() => festFlags(DR, W), [DR, W]);
  const n = useMemo(() => applyScenario(n0, lev, fw, HN), [n0, lev, fw, HN]);
  const V = VA?.levels[level], H = V?.hist, HV = H?.nodes[nodeKey]?.[mea];

  const M = useMemo(() => {
    if (!n) return null;
    const supply = n.model.map((v, i) => (lev.avail < 100 && v != null && i >= HN - 1 ? (i >= HN ? v * lev.avail / 100 : v) : null));
    const r = rollUp(W, { model: n.model, p50: n.p50.map((v, i) => (v == null && i === HN - 1 ? n.actual[i] : v)), m3: n.m3, m2: n.m2, m1: n.m1, sales: n.sales, budget: n.budget.map((v, i) => (i >= HN ? null : v)), supply });
    const hv = (m) => { const i = H ? H.months.findIndex((x) => x.m === m) : -1; return i >= 0 && HV ? HV[i] : null; };
    r.actual = r.months.map(hv);
    r.ly = r.months.map((m) => hv(shift(m, -12)));
    r.fi = r.actual.findIndex((v) => v == null);          // first forecast month
    return r;
  }, [n, W, HN, H, HV, lev]);

  const config = useMemo(() => {
    if (!M) return null;
    const cs = (k) => css(SERIES.find((s) => s.k === k).col); const Hd = hidden, FI = M.fi < 0 ? M.months.length : M.fi;
    const ds = [
      { label: 'P50 (median)', data: M.p50, borderColor: cs('p50'), borderWidth: 2, borderDash: [5, 3], pointRadius: 0, pointHoverRadius: 4, spanGaps: false, _k: 'p50', hidden: !!Hd.p50, order: 1 },
      { label: 'Last year', data: M.ly, borderColor: cs('ly'), borderWidth: 1.5, borderDash: [2, 3], pointRadius: 0, spanGaps: true, _k: 'ly', hidden: !!Hd.ly, order: 4 },
      { label: 'Supply-constrained', data: M.supply, borderColor: cs('supply'), borderWidth: 2, borderDash: [2, 3], pointRadius: 0, spanGaps: false, _k: 'supply', hidden: !!Hd.supply, order: 1 },
      { label: 'Budget', data: M.budget, borderColor: cs('budget'), borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, spanGaps: true, _k: 'budget', hidden: !!Hd.budget, order: 3 },
      { label: 'Sales-team forecast (3 months ahead)', data: M.sales, borderColor: cs('sales'), borderWidth: 1.5, borderDash: [6, 4], pointRadius: 2, pointHoverRadius: 4, _k: 'sales', hidden: !!Hd.sales, order: 2 },
      { label: 'Model M3 run', data: M.m3, borderColor: cs('m3'), borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 4, spanGaps: false, _k: 'm3', hidden: !!Hd.m3, order: 1 },
      { label: 'Model M2 run', data: M.m2, borderColor: cs('m2'), borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 4, spanGaps: false, _k: 'm2', hidden: !!Hd.m2, order: 1 },
      { label: 'Model M1 run', data: M.m1, borderColor: cs('m1'), borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 4, spanGaps: false, _k: 'm1', hidden: !!Hd.m1, order: 1 },
      { label: 'Forecast (ensemble)', data: M.model, borderColor: cs('model'), backgroundColor: cs('model'), borderWidth: 2, pointRadius: (c) => (c.dataIndex >= FI ? 3.5 : 2), pointHoverRadius: 5, segment: { borderWidth: (c) => (c.p0DataIndex >= FI - 1 ? 3 : 1.75) }, _k: 'model', hidden: !!Hd.model, order: 1 },
      { label: 'Actual', data: M.actual, borderColor: cs('actual'), backgroundColor: cs('actual'), borderWidth: 2, pointRadius: 3, pointHoverRadius: 4, _k: 'actual', hidden: !!Hd.actual, order: 0 },
    ];
    const vals = ds.flatMap((d) => d.data.filter((v) => v != null));
    const yMin = Math.min(...vals) * 0.8; const step = yMin >= 5e6 ? 5e6 : (yMin >= 5e4 ? 5e4 : undefined);
    return {
      type: 'line', data: { labels: M.months.map(mLab), datasets: ds }, plugins: [dividerPlugin('startLine', FI, 'Forecast starts')],
      options: {
        ...baseOptions(),
        scales: { x: xScale(), y: yScale(mea === 'u' ? 'Units per month' : '₹ per month', (v) => fK(v), { min: step ? Math.floor(yMin / step) * step : undefined }) },
        plugins: {
          legend: { display: false },
          tooltip: {
            ...tooltipBase(), filter: (i) => i.raw != null,
            callbacks: {
              title: (i) => mFull(M.months[i[0].dataIndex]) + (i[0].dataIndex >= FI ? ' (forecast)' : ''),
              label: (i) => ' ' + i.dataset.label + ': ' + fN(i.raw),
            },
          },
        },
      },
    };
  }, [M, mea, hidden, theme]);

  if (!nd) return <div className="empty"><b>No forecast for this selection</b><span>Pick another category or product, or switch the level.</span></div>;
  if (!M || !M.months.length) return <div className="empty"><b>Loading the monthly outlook</b><span>Fetching from the API…</span></div>;

  const FI = M.fi < 0 ? M.months.length : M.fi, FM = M.months.slice(FI), FN = FM.length;
  const F = M.model.slice(FI), tot = sum(F), unit = mea === 'u' ? 'units' : 'rupees';
  const hv = (m) => { const i = H ? H.months.findIndex((x) => x.m === m) : -1; return i >= 0 && HV ? HV[i] : null; };
  const prev = FM.map((_, j) => shift(M.months[FI], j - FN)), recent = prev.map(hv), lastYr = FM.map((m) => hv(shift(m, -12)));
  const REC = recent.every((v) => v != null) ? sum(recent) : null, ly = lastYr.every((v) => v != null) ? sum(lastYr) : null;
  let pk = 0; F.forEach((v, i) => { if (v > F[pk]) pk = i; });
  const vb = REC ? tot / REC - 1 : null, vl = ly ? tot / ly - 1 : null;
  // accuracy of the M3 / M2 / M1 runs over completed months (same definition as the Monthly runs tab)
  const VN = V?.nodes[nodeKey]?.[mea], okM = V ? V.months.map((x, i) => x.complete && VN && VN.actual[i] != null) : [];
  const accOf = (k) => { if (!VN) return null; let e = 0, a = 0, c = 0; V.months.forEach((x, i) => { if (okM[i] && VN[k][i] != null) { e += Math.abs(VN[k][i] - VN.actual[i]); a += VN.actual[i]; c++; } }); return c && a ? { v: 1 - e / a, c } : null; };
  const a3 = accOf('m3'), a2 = accOf('m2'), a1 = accOf('m1');
  const first = mFull(FM[0]), lastM = mFull(FM[FN - 1]);
  const tiles = [
    { l: 'Forecast, next ' + FN + ' months', v: fCr(tot), d: <span>{mLab(FM[0])} – {mLab(FM[FN - 1])}{act && n0 && <> · base case <span className="chip">{fCr(sum(rollUp(W, { x: n0.model }).x.slice(FI)))}</span></>}</span>,
      i: { what: 'Total demand the model expects over the next ' + FN + ' months, in ' + unit + ' (1 Cr = 10 million).',
           how: 'Sum of the ensemble forecast for each month from ' + first + ' to ' + lastM + '. Each month adds up its weekly forecasts; a week that straddles two months is split by days.',
           read: 'Use it as the planning volume. It follows the Category, Product, Level and Measure filters above.' } },
    { l: 'Vs last ' + FN + ' months', v: vb == null ? '—' : fS(vb), cls: vb == null ? '' : vb >= 0 ? 'pos' : 'neg', d: <>last {FN} months <span className="chip">{REC == null ? '–' : fCr(REC)}</span></>,
      i: { what: 'How the coming ' + FN + ' months compare with the ' + FN + ' months that just ended.',
           how: 'Forecast total for the next ' + FN + ' months divided by actual sales in the previous ' + FN + ' months, minus 1.',
           read: 'A fall is not automatically a warning: the windows sit in different seasons, so festival and monsoon timing drives most of this gap. Compare with the same-months-last-year tile for a like-for-like view.' } },
    { l: 'Vs same months last year', v: vl == null ? '—' : fS(vl), cls: vl == null ? '' : vl >= 0 ? 'pos' : 'neg', d: <>last year <span className="chip">{ly == null ? '–' : fCr(ly)}</span></>,
      i: { what: 'Growth the model is projecting against the same calendar months a year earlier.',
           how: 'Forecast total for the next ' + FN + ' months divided by actual sales in the same months a year ago, minus 1.',
           read: 'The cleanest growth check, since the season is the same. Festival dates move between years, so a single month can differ much more than the total.' } },
    { l: 'Peak month', v: mFull(FM[pk]), d: <><span className="chip">{fCr(F[pk])}</span> {unit}</>,
      i: { what: 'The single forecast month with the highest expected demand, and its volume.',
           how: 'Largest monthly value of the forecast line over the next ' + FN + ' months. It is the highest month, not a trend or a date range.',
           read: 'Check it against the chart. If it is the first forecast month, the model is carrying recent demand forward and the festival build-up later is lower; if it is later, it is usually a festival sell-in month.' } },
    { l: 'Monthly accuracy, last ' + (a3 ? a3.c : 0) + ' months', v: a3 ? fP(a3.v) : '—', d: <>M2 <span className="chip">{a2 ? fP(a2.v) : '–'}</span> M1 <span className="chip">{a1 ? fP(a1.v) : '–'}</span></>,
      i: { what: 'How close the M3 run (big number), M2 run and M1 run were to actual monthly sales over the last ' + (a3 ? a3.c : 0) + ' completed months.',
           how: '1 minus (total monthly error, ignoring direction) divided by total actual sales, in ' + unit + '. M3, M2 and M1 are the month-end runs made 3, 2 and 1 months before each month.',
           read: 'Higher is better; M1 should beat M3 because it has more recent data. Single products score lower than the total because errors cancel out when products are added together.' } },
  ];
  const q = nd.band; const c = (v) => (v == null ? '-' : fN(v));

  return (
    <>
      <Kpis tiles={tiles} label="Headline figures" />
      <section className="card" aria-labelledby="ct">
        <div className="card-head"><h2 id="ct">Demand outlook, {first} – {lastM}</h2>
          <SegBare ariaLabel="View" value={view} onChange={setView} options={[{ v: 'chart', label: 'Chart' }, { v: 'table', label: 'Table' }]} /></div>
        <details className="wdetails more"><summary>About this view</summary><p className="note">Actual monthly sales, then the model forecast for the next {FN} months, from {first} to {lastM}. In past months the Forecast line is the ensemble's forecast made 13 weeks ahead, and the M3, M2 and M1 lines are the month-end runs made 3, 2 and 1 months before each month, the same runs as the Monthly runs tab. Showing: <strong>{nd.label}</strong>{level === 'National' ? ', national' : ', Kolkata depots'}. Each month adds up its weekly forecasts, and a week that straddles two months is split by days.</p></details>
        {view === 'chart' ? (
          <div>
            <Legend series={SERIES.filter((s) => s.k !== 'supply' || lev.avail < 100)} hidden={hidden} onToggle={(k) => setHidden((h) => ({ ...h, [k]: !h[k] }))} />
            <ChartCanvas config={config} label="Monthly demand: actual, forecast, sales-team forecast, last year and budget" />
            <p className="foot">To compare a month with last month and with the same month last year, and to see what pushed demand up or down, open the Monthly runs tab and pick the target month.</p>
          </div>
        ) : (
          <div className="tablewrap"><table>
            <thead><tr><th>Month</th><th>Actual</th><th>Forecast</th><th>M3 run</th><th>M2 run</th><th>M1 run</th><th>P50</th><th>Sales team</th><th>Last year</th><th>Budget</th></tr></thead>
            <tbody>{M.months.map((m, i) => { const f = i >= FI; return (
              <tr key={m} className={f ? 'fc' : ''}><td>{mFull(m)}{f && <span className="pill">Forecast</span>}</td><td>{c(M.actual[i])}</td><td>{c(M.model[i])}</td><td>{c(M.m3[i])}</td><td>{c(M.m2[i])}</td><td>{c(M.m1[i])}</td><td>{c(M.p50[i])}</td><td>{c(M.sales[i])}</td><td>{c(M.ly[i])}</td><td>{f ? '-' : c(M.budget[i])}</td></tr>); })}</tbody>
          </table></div>
        )}
        <p className="foot">P50 is the forecast times the median of how past 13-week-ahead forecasts compared with actual sales for this selection ({(q[2] * 100).toFixed(0)}%), so half of past months came in above it and half below. Budget and sales-team lines stop at the last actuals (week of 28 Sep 2026); the forecast months show the model only. All data is synthetic.</p>
      </section>
    </>
  );
}
