import { useEffect, useMemo } from 'react';
import { useApp } from '../context.js';
import Kpis from '../components/Kpis.jsx';
import Legend from '../components/Legend.jsx';
import ChartCanvas from '../components/ChartCanvas.jsx';
import WeekMap from '../components/WeekMap.jsx';
import { monthOf } from '../components/Drivers.jsx';
import WhyWeek from '../components/WhyWeek.jsx';
import { festFlags, applyScenario, isBase } from '../lib/scenario.js';
import { useApi } from '../lib/api.js';
import { SegBare } from '../components/Controls.jsx';
import { css, tooltipBase, baseOptions, xScale, yScale, dividerPlugin } from '../lib/chart.js';
import { lab, labFull, endOf, fK, fCr, fN, fS, fP, sum } from '../lib/format.js';

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

let pendingScroll = false;
// shaded column behind the week picked for the "why this week" panel
const selPlugin = (j) => ({
  id: 'sel',
  beforeDatasetsDraw(c) {
    if (j == null) return;
    const x0 = c.scales.x.getPixelForValue(j - 0.5), x1 = c.scales.x.getPixelForValue(j + 0.5), a = c.chartArea, g = c.ctx;
    g.save(); g.fillStyle = css('--reiq-text-helper'); g.globalAlpha = 0.18; g.fillRect(x0, a.top, x1 - x0, a.bottom - a.top); g.restore();
  },
});

export default function WeeklyView() {
  const { D, level, mea, nodeKey, theme, useSS, lev } = useApp();
  const [hidden, setHidden] = useSS('fc.hidden', { budget: true, m3: true, m2: true, m1: true });
  const [view, setView] = useSS('fc.view', 'chart');
  const [sel, setSel] = useSS('fc.week', null);
  const [basis, setBasis] = useSS('fc.basis', 'yoy');
  const { data: DR } = useApi('/api/drivers?level=' + encodeURIComponent(level));
  // setting state remounts this view (refresh pulse), so remember across mounts that a click asked to scroll
  useEffect(() => {
    if (!pendingScroll) return; pendingScroll = false;
    setTimeout(() => document.getElementById('why')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
  }, [sel, DR]);
  const W = D.weeks, HN = D.histN, FN = D.fcN, N = W.length;
  const nd = D.levels[level].nodes[nodeKey];
  const n0 = nd?.[mea];
  const act = !isBase(lev), fw = useMemo(() => festFlags(DR, W), [DR, W]);
  const n = useMemo(() => applyScenario(n0, lev, fw, HN), [n0, lev, fw, HN]);

  const config = useMemo(() => {
    if (!n) return null;
    const cs = (k) => css(SERIES.find((s) => s.k === k).col); const H = hidden;
    const ds = [
      { label: 'P50 (median)', data: n.p50, borderColor: cs('p50'), borderWidth: 2, borderDash: [5, 3], pointRadius: 0, pointHoverRadius: 4, spanGaps: false, _k: 'p50', hidden: !!H.p50, order: 1 },
      { label: 'Last year', data: n.ly, borderColor: cs('ly'), borderWidth: 1.5, borderDash: [2, 3], pointRadius: 0, spanGaps: true, _k: 'ly', hidden: !!H.ly, order: 4 },
      { label: 'Supply-constrained', data: n.model.map((v, i) => (lev.avail < 100 && v != null && i >= HN - 1 ? (i >= HN ? v * lev.avail / 100 : v) : null)), borderColor: cs('supply'), borderWidth: 2, borderDash: [2, 3], pointRadius: 0, spanGaps: false, _k: 'supply', hidden: !!H.supply, order: 1 },
      { label: 'Budget', data: n.budget.map((v, i) => (i >= HN ? null : v)), borderColor: cs('budget'), borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, spanGaps: true, _k: 'budget', hidden: !!H.budget, order: 3 },
      { label: 'Sales-team forecast (3 months ahead)', data: n.sales, borderColor: cs('sales'), borderWidth: 1.5, borderDash: [6, 4], pointRadius: 2, pointHoverRadius: 4, _k: 'sales', hidden: !!H.sales, order: 2 },
      { label: 'Model M3 run', data: n.m3, borderColor: cs('m3'), borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 4, spanGaps: false, _k: 'm3', hidden: !!H.m3, order: 1 },
      { label: 'Model M2 run', data: n.m2, borderColor: cs('m2'), borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 4, spanGaps: false, _k: 'm2', hidden: !!H.m2, order: 1 },
      { label: 'Model M1 run', data: n.m1, borderColor: cs('m1'), borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 4, spanGaps: false, _k: 'm1', hidden: !!H.m1, order: 1 },
      { label: 'Forecast (ensemble)', data: n.model, borderColor: cs('model'), backgroundColor: cs('model'), borderWidth: 2, pointRadius: (c) => (c.dataIndex >= HN ? 3.5 : 0), pointHoverRadius: 5, segment: { borderWidth: (c) => (c.p0DataIndex >= HN - 1 ? 3 : 1.75) }, _k: 'model', hidden: !!H.model, order: 1 },
      { label: 'Actual', data: n.actual, borderColor: cs('actual'), backgroundColor: cs('actual'), borderWidth: 2, pointRadius: 2.5, pointHoverRadius: 4, _k: 'actual', hidden: !!H.actual, order: 0 },
    ];
    const vals = ds.flatMap((d) => d.data.filter((v) => v != null));
    const yMin = Math.min(...vals) * 0.8; const step = yMin >= 5e6 ? 5e6 : (yMin >= 5e4 ? 5e4 : undefined);
    return {
      type: 'line', data: { labels: W.map(lab), datasets: ds }, plugins: [dividerPlugin('startLine', HN, 'Forecast starts'), selPlugin(sel)],
      options: {
        ...baseOptions(),
        onClick: (e, _el, chart) => { const p = chart.getElementsAtEventForMode(e, 'index', { intersect: false }, false)[0]; if (p) { pendingScroll = true; setSel(p.index); } },
        scales: { x: xScale(), y: yScale(mea === 'u' ? 'Units per week' : '₹ per week', (v) => fK(v), { min: step ? Math.floor(yMin / step) * step : undefined }) },
        plugins: {
          legend: { display: false },
          tooltip: {
            ...tooltipBase(), filter: (i) => i.raw != null,
            callbacks: {
              title: (i) => 'Week beginning ' + labFull(W[i[0].dataIndex]) + (i[0].dataIndex >= HN ? ' (forecast)' : ''),
              label: (i) => ' ' + i.dataset.label + ': ' + fN(i.raw),
            },
          },
        },
      },
    };
  }, [n, mea, hidden, theme, HN, W, sel, lev]);

  if (!nd) return <div className="empty"><b>No forecast for this selection</b><span>Pick another category or product, or switch the level.</span></div>;

  const F = n.model.slice(HN), LY = n.ly.slice(HN), REC = sum(n.actual.slice(HN - FN, HN));
  const tot = sum(F), ly = sum(LY); let pk = 0; F.forEach((v, i) => { if (v > F[pk]) pk = i; });
  const ar = nd.accR, vb = tot / REC - 1, vl = tot / ly - 1, unit = mea === 'u' ? 'units' : 'rupees';
  const lastW = labFull(W[HN - 1]), firstW = labFull(W[HN]);
  const tiles = [
    { l: 'Forecast, next ' + FN + ' weeks', v: fCr(tot), d: <span>{lab(W[HN])} – {endOf(W[N - 1])}{act && n0 && <> · base case <span className="chip">{fCr(sum(n0.model.slice(HN)))}</span></>}</span>,
      i: { what: 'Total demand the model expects over the next ' + FN + ' weeks, in ' + unit + ' (1 Cr = 10 million).',
           how: 'Sum of the ensemble forecast for each week from ' + firstW + ', the first week after the last actuals (week of ' + lastW + ').',
           read: 'Use it as the planning volume. It follows the Category, Product, Level and Measure filters above.' } },
    { l: 'Vs last ' + FN + ' weeks', v: fS(vb), cls: vb >= 0 ? 'pos' : 'neg', d: <>last {FN} weeks <span className="chip">{fCr(REC)}</span></>,
      i: { what: 'How the coming ' + FN + ' weeks compare with the ' + FN + ' weeks that just ended.',
           how: 'Forecast total for the next ' + FN + ' weeks divided by actual sales in the previous ' + FN + ' weeks, minus 1.',
           read: 'A fall is not automatically a warning: the windows sit in different seasons, so festival and monsoon timing drives most of this gap. Compare with the same-weeks-last-year tile for a like-for-like view.' } },
    { l: 'Vs same weeks last year', v: fS(vl), cls: vl >= 0 ? 'pos' : 'neg', d: <>last year <span className="chip">{fCr(ly)}</span></>,
      i: { what: 'Growth the model is projecting against the same calendar weeks a year earlier.',
           how: 'Forecast total for the next ' + FN + ' weeks divided by actual sales in the same weeks 52 weeks ago, minus 1.',
           read: 'The cleanest growth check, since the season is the same. Festival dates move between years, so a single week can differ much more than the total.' } },
    { l: 'Peak week', v: lab(W[HN + pk]), d: <><span className="chip">{fCr(F[pk])}</span> {unit}</>,
      i: { what: 'The single forecast week with the highest expected demand, and its volume.',
           how: 'Largest weekly value of the forecast line over the next ' + FN + ' weeks. It is the highest week, not a trend or a date range.',
           read: 'Check it against the chart. If it is the first forecast week, the model is carrying recent demand forward and the festival build-up later is lower; if it is later, it is usually a festival sell-in week.' } },
    { l: 'Weekly accuracy, last ' + ar[3] + ' weeks', v: ar[0] == null ? '—' : <>{fP(ar[0])}<small className="vt">M3</small></>,
      d: <><span className="accp"><b>M2</b><span className="chip">{ar[1] == null ? '–' : fP(ar[1])}</span></span><span className="accp"><b>M1</b><span className="chip">{ar[2] == null ? '–' : fP(ar[2])}</span></span></>,
      i: { what: 'How close the M3 run (the big number), M2 run and M1 run were to actual weekly sales over the last ' + ar[3] + ' weeks.',
           how: '1 minus (total weekly error, ignoring direction) divided by total actual sales, in units. M3, M2 and M1 are the month-end runs made 3, 2 and 1 months before each week\'s month.',
           read: 'Higher is better; M1 should beat M3 because it has more recent data. Single products score lower than the total because errors cancel out when products are added together.' } },
  ];
  const q = nd.band; const c = (v) => (v == null ? '-' : fN(v));

  return (
    <>
      <Kpis tiles={tiles} label="Headline figures" />
      <section className="card" aria-labelledby="ct">
        <div className="card-head"><h2 id="ct">Demand outlook, {labFull(W[HN])} – {endOf(W[N - 1])}</h2>
          <SegBare ariaLabel="View" value={view} onChange={setView} options={[{ v: 'chart', label: 'Chart' }, { v: 'table', label: 'Table' }]} /></div>
        <details className="wdetails more"><summary>About this view</summary><p className="note">Last {HN} weeks of actual sales, then the model forecast for the next {FN} weeks, from {labFull(W[HN])} to the week ending {endOf(W[N - 1])}. In past weeks the Forecast line is the ensemble's forecast made 13 weeks ahead, and the M3, M2 and M1 lines are the month-end runs made 3, 2 and 1 months before each week's month, the same runs as the monthly view. Showing: <strong>{nd.label}</strong>, {level.toLowerCase()}.</p></details>
        {view === 'chart' ? (
          <div>
            <Legend series={SERIES.filter((s) => s.k !== 'supply' || lev.avail < 100)} hidden={hidden} onToggle={(k) => setHidden((h) => ({ ...h, [k]: !h[k] }))} />
            <ChartCanvas config={config} label="Weekly demand: actual, forecast, sales-team forecast, last year and budget" />
            {DR && <WeekMap weeks={DR.weeks} m={monthOf(W[sel ?? HN])} />}
            {sel == null
              ? <p className="foot">Click any week on the chart to compare it with last week and with the same week last year, and to see what pushed demand up or down.</p>
              : (DR
                ? <WhyWeek j={sel} data={DR} W={W} nodeKey={nodeKey} node={nd.label} mea={mea} n={n0} HN={HN} scen={act} basis={basis} setBasis={setBasis} onClose={() => setSel(null)}
                    cat={nodeKey.startsWith('cat:') ? nodeKey.slice(4) : nodeKey.startsWith('sku:') ? D.levels[level].products.find((p) => 'sku:' + p.code === nodeKey)?.cat : null} />
                : <p className="foot">Loading the week breakdown…</p>)}
          </div>
        ) : (
          <div className="tablewrap"><table>
            <thead><tr><th>Week beginning</th><th>Actual</th><th>Forecast</th><th>M3 run</th><th>M2 run</th><th>M1 run</th><th>P50</th><th>Sales team</th><th>Last year</th><th>Budget</th></tr></thead>
            <tbody>{W.map((w, i) => { const f = i >= HN; return (
              <tr key={w} className={f ? 'fc' : ''}><td>{labFull(w)}{f && <span className="pill">Forecast</span>}</td><td>{c(n.actual[i])}</td><td>{c(n.model[i])}</td><td>{c(n.m3[i])}</td><td>{c(n.m2[i])}</td><td>{c(n.m1[i])}</td><td>{c(n.p50[i])}</td><td>{c(n.sales[i])}</td><td>{c(n.ly[i])}</td><td>{f ? '-' : c(n.budget[i])}</td></tr>); })}</tbody>
          </table></div>
        )}
        <details className="wdetails more"><summary>Notes and limits</summary><p className="foot">P50 is the forecast times the median of how past 13-week-ahead forecasts compared with actual sales for this selection ({(q[2] * 100).toFixed(0)}%), so half of past weeks came in above it and half below. Budget and sales-team lines stop at the last actuals (week of 28 Sep 2026); the forecast weeks show the model only. All data is synthetic.</p></details>
      </section>
    </>
  );
}
