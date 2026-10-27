import { useMemo } from 'react';
import { useApp } from '../context.js';
import ChartCanvas from './ChartCanvas.jsx';
import Info from './Info.jsx';
import Legend from './Legend.jsx';
import { css, tooltipBase, baseOptions, xScale, yScale } from '../lib/chart.js';
import { fP, fCr } from '../lib/format.js';

// Reference points from the CFO workbook: Eveready's own M3 accuracy today, and the industry range (~80% at M3 rising to ~90% at M1; M2 is the midpoint)
export const REF = { eveready: { 3: 0.68 }, industry: { 3: 0.8, 2: 0.85, 1: 0.9 } };
const LO = 0.5;
const TREND_KEY = [{ k: 'm3', name: 'M3 run', col: '--reiq-chart-2', cls: '' }, { k: 'm2', name: 'M2 run', col: '--reiq-chart-6', cls: '' }, { k: 'm1', name: 'M1 run', col: '--reiq-chart-5', cls: '' },
  { k: 'i1', name: 'Industry M1 (~90%)', col: '--reiq-text-helper', cls: 'dash' }, { k: 'i3', name: 'Industry M3 (~80%)', col: '--reiq-text-helper', cls: 'dot' }, { k: 'e3', name: 'Eveready today, M3 (68%)', col: '--reiq-text-helper', cls: '' }];
const pts = (x) => (x >= 0 ? '+' : '−') + Math.abs(x * 100).toFixed(0) + ' pts';

/** Accuracy of the M3 / M2 / M1 runs over the completed months, measured the way the CFO asked:
 *  across all products as one total, against his reference points, with over- and under-forecast called out separately. */
export default function AccuracyCard({ V }) {
  const { D, level, mea, theme } = useApp();
  const VM = V.months, ni = (k) => V.nodes[k]?.[mea];
  const nProducts = D.levels[level].products.length, keys = useMemo(() => ['ALL'], []);
  const done = VM.map((m, i) => (m.complete ? i : -1)).filter((i) => i >= 0);

  const pool = (k, ks, idxs, pre = 'm') => { let a = 0, e = 0, o = 0, u = 0, c = 0, un = 0, on = 0, uF = 0, uA = 0, oF = 0, oA = 0;
    ks.forEach((key) => { const n = ni(key); if (!n) return; idxs.forEach((i) => { const A = n.actual[i], F = n[pre + k][i]; if (A == null || F == null || n['m' + k][i] == null) return; a += A; e += Math.abs(F - A); o += Math.max(F - A, 0); u += Math.max(A - F, 0); c++; if (F < A) { un++; uF += F; uA += A; } else if (F > A) { on++; oF += F; oA += A; } }); });
    return { a, e, o, u, c, un, on, uF, uA, oF, oA }; };
  const rows = [3, 2, 1].map((k) => {
    const p = pool(k, keys, done), sp = pool(k, keys, done, 's'), s = { a: 0, e: 0 };
    keys.forEach((key) => { const n = ni(key); if (n) done.forEach((i) => { const A = n.actual[i], S = n['s' + k][i]; if (A != null && S != null && n['m' + k][i] != null) { s.a += A; s.e += Math.abs(S - A); } }); });
    return { k, months: done.length, acc: p.a ? 1 - p.e / p.a : null, sacc: s.a ? 1 - s.e / s.a : null, sp: { under: sp.u, over: sp.o, ucov: sp.uA ? sp.uF / sp.uA : null, oratio: sp.oA ? sp.oF / sp.oA : null, un: sp.un, on: sp.on, n: sp.c }, over: p.o, under: p.u, a: p.a, n: p.c, un: p.un, on: p.on, ucov: p.uA ? p.uF / p.uA : null, oratio: p.oA ? p.oF / p.oA : null };
  });

  const trend = useMemo(() => {
    const ds = [3, 2, 1].map((k, j) => { const c = css(['--reiq-chart-2', '--reiq-chart-6', '--reiq-chart-5'][j]);
      return { label: 'M' + k + ' run', data: VM.map((m, i) => { if (!m.complete) return null; const p = pool(k, keys, [i]); return p.a && p.c ? 1 - p.e / p.a : null; }),
        borderColor: c, backgroundColor: c, borderWidth: 2, pointRadius: 3, spanGaps: false }; });
    const ref = (name, v, dash) => ({ label: name, data: VM.map(() => v), borderColor: css('--reiq-text-helper'), borderWidth: 1.25, borderDash: dash, pointRadius: 0, order: 9 });
    const lo = Math.min(LO, Math.floor((Math.min(...ds.flatMap((d) => d.data.filter((v) => v != null))) - 0.02) * 10) / 10);
    const last = VM.findLastIndex ? VM.findLastIndex((m) => m.complete) : done[done.length - 1];
    return { type: 'line', data: { labels: VM.slice(0, last + 1).map((m) => m.label), datasets: [...ds, ref('Industry, M1 (~90%)', REF.industry[1], [6, 3]), ref('Industry, M3 (~80%)', REF.industry[3], [2, 3]), ref("Eveready today, M3 (68%)", REF.eveready[3], [])].map((d) => ({ ...d, data: d.data.slice(0, last + 1) })) },
      options: { ...baseOptions(), scales: { x: xScale(), y: yScale('Accuracy', (v) => (v * 100).toFixed(0) + '%', { min: lo, max: 1 }) },
        plugins: { legend: { display: false }, tooltip: { ...tooltipBase(), filter: (i) => i.raw != null, callbacks: { label: (i) => ' ' + i.dataset.label + ': ' + fP(i.raw) } } } } };
  }, [VM, keys, mea, theme]); // eslint-disable-line react-hooks/exhaustive-deps

  const unit = mea === 'v' ? 'rupees' : 'units';
  const worst = rows[0];
  return (
    <section className="card" aria-labelledby="acct">
      <div className="card-head"><h2 id="acct">Accuracy against the reference points<Info text={{ what: 'How close each run was to actual sales over the completed months, next to the CFO\'s reference points.', how: 'Accuracy = 1 minus total absolute error divided by total actual sales, over all products added together, for each completed month. The under- and over-forecast call-outs below are never blended into it.', read: 'Compare each bar with the industry marker. Over- and under-forecasts partly cancel inside the total, which is why they are also reported separately.' }} /></h2></div>
      <p className="note"><strong>All {nProducts} products</strong> added together, whatever the Category and Product filters say. Completed months with runs: <strong>{done.length}</strong> ({VM[done[0]].label} to {VM[done[done.length - 1]].label}). Over- and under-forecasts partly cancel inside the total, so they are reported separately below.</p>
      <div className="accb" role="list">
        {rows.map((r) => { const ind = REF.industry[r.k], ev = REF.eveready[r.k], pos = (v) => Math.max(0, Math.min(1, (v - LO) / (1 - LO))) * 100; const gap = r.acc == null ? null : r.acc - ind;
          return (
            <div className="accb-r" role="listitem" key={r.k}>
              <div className="accb-l"><b>M{r.k}</b><span>{r.k === 3 ? '3 months ahead' : r.k === 2 ? '2 months ahead' : '1 month ahead'}</span></div>
              <div className="accb-t" aria-hidden="true">
                <i className="accb-f" style={{ width: pos(r.acc ?? LO) + '%' }} />
                <i className="accb-k ind" style={{ left: pos(ind) + '%' }} title="Industry reference" />
                {ev && <i className="accb-k ev" style={{ left: pos(ev) + '%' }} title="Eveready today" />}
              </div>
              <div className="accb-v"><b>{r.acc == null ? '–' : fP(r.acc)}</b>
                {gap != null && <span className={gap >= 0 ? 'pos' : 'neg'}>{gap >= 0 ? '▲' : '▼'} {pts(gap)} vs industry {Math.round(ind * 100)}%</span>}
                {ev && <small>Eveready today {Math.round(ev * 100)}%</small>}</div>
            </div>); })}
        <div className="accb-ax" aria-hidden="true"><div><span>50%</span><span>75%</span><span>100%</span></div></div>
        <p className="foot legend-k"><i className="accb-f s" /> Model <i className="accb-k ind s" /> Industry reference <i className="accb-k ev s" /> Eveready today, as quoted by the CFO. The M2 reference is the midpoint of the M3 and M1 figures.</p>
      </div>
      <h3 className="sec-h2">Under- and over-forecast, reported separately</h3>
      <div className="uo">
        {rows.map((r) => { const q = r.sp; return (
          <div className="uo-c" key={r.k}>
            <b>M{r.k}</b>
            <div className="uo-u"><span>Under-forecast (lost sales)</span>
              <b>Model: {r.ucov == null ? '–' : fP(r.ucov)} of demand covered</b>
              <em>{r.n ? fP(r.un / r.n) : '–'} of months · {fCr(r.under)} {unit} short</em>
              <b>Sales team: {q.ucov == null ? '–' : fP(q.ucov)} of demand covered</b>
              <em>{q.n ? fP(q.un / q.n) : '–'} of months · {fCr(q.under)} {unit} short</em></div>
            <div className="uo-o"><span>Over-forecast (above 100%)</span>
              <b>Model: {r.oratio == null ? '–' : fP(r.oratio)} of demand</b>
              <em>{r.n ? fP(r.on / r.n) : '–'} of months · {fCr(r.over)} {unit} extra</em>
              <b>Sales team: {q.oratio == null ? '–' : fP(q.oratio)} of demand</b>
              <em>{q.n ? fP(q.on / q.n) : '–'} of months · {fCr(q.over)} {unit} extra</em></div>
          </div>); })}
      </div>
      <details className="wdetails more"><summary>Notes and limits</summary><p className="foot">Each run is scored on every month and split in two. Where the forecast fell short, the figure is the share of demand it covered (under 100%), and the shortfall is demand the plan did not cover, a sales-loss risk. Where the forecast ran high, the figure is the forecast as a share of demand (over 100%), and the excess is stock built for demand that did not come, which is also a sales-loss signal. The two are never netted against each other.</p></details>
      <h3 className="sec-h2">Accuracy month by month</h3>
      <Legend series={TREND_KEY} hidden={{}} onToggle={() => {}} />
      <ChartCanvas config={trend} label="Monthly accuracy of the M3, M2 and M1 runs against the reference lines" />
      <p className="foot">Solid grey line: Eveready today at M3 (68%). Dotted: industry M3 (~80%). Dashed: industry M1 (~90%). {worst.acc != null && `The M3 run averaged ${fP(worst.acc)}.`}</p>
    </section>
  );
}
