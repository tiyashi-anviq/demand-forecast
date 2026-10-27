import { useEffect, useMemo } from 'react';
import { useApp } from '../context.js';
import AccuracyCard from '../components/AccuracyCard.jsx';
import Stat from '../components/Stat.jsx';
import { InShort, DriverCols, HowEstimated, Agreement, aggInfo, monthInfos, weekShare, buildModelRows, buildFacts } from '../components/Drivers.jsx';
import { useApi } from '../lib/api.js';
import Kpis from '../components/Kpis.jsx';
import Legend from '../components/Legend.jsx';
import ChartCanvas from '../components/ChartCanvas.jsx';
import { SegBare } from '../components/Controls.jsx';
import { css, tooltipBase, baseOptions, xScale, yScale } from '../lib/chart.js';
import { MON, p2, fK, fCr, fN, fS, fP, endOf, labFull } from '../lib/format.js';

const RUNS = [
  { k: 'actual', name: 'Actual', col: '--reiq-chart-1', cls: '' },
  { k: 'm3', name: 'Model M3 run', col: '--reiq-chart-2', cls: 'dash' },
  { k: 'm2', name: 'Model M2 run', col: '--reiq-chart-6', cls: 'dash' },
  { k: 'm1', name: 'Model M1 run', col: '--reiq-chart-5', cls: 'dash' },
  { k: 'latest', name: 'Latest run', col: '--reiq-text-primary', cls: 'dot' },
  { k: 's3', name: 'Sales team M3', col: '--reiq-chart-3', cls: 'dash' },
  { k: 's2', name: 'Sales team M2', col: '--reiq-chart-3', cls: 'dot' },
  { k: 's1', name: 'Sales team M1', col: '--reiq-chart-3', cls: '' },
];
const cutText = (m, k) => { const d = new Date(Date.UTC(+m.slice(0, 4), +m.slice(5, 7) - k, 0)); return p2(d.getUTCDate()) + ' ' + MON[d.getUTCMonth()] + ' ' + d.getUTCFullYear(); };
const vErr = (f, a) => (f != null && a ? fS(f / a - 1) : '');
const mLab = (m) => MON[+m.slice(5, 7) - 1] + ' ' + m.slice(2, 4);
const shift = (m, k) => { const d = new Date(Date.UTC(+m.slice(0, 4), +m.slice(5, 7) - 1 + k, 1)); return d.getUTCFullYear() + '-' + p2(d.getUTCMonth() + 1); };
const AGO = { 3: 'three months', 2: 'two months', 1: 'one month' };

let pendingScroll = false;

export default function MonthlyView({ V, vm, onPick, run = 'm3' }) {
  const K = +run.slice(1);   // the run picked in the dropdown: 3, 2 or 1 months ahead
  const { D, level, mea, nodeKey, theme, useSS } = useApp();
  const lastAct = D.weeks[D.histN - 1], toDate = endOf(lastAct), fromWk = labFull(lastAct);   // last actual week, read from the data
  const RUNS_SHOWN = RUNS.filter((s) => !/^[ms][123]$/.test(s.k) || s.k.endsWith(String(K))).map((s) => (s.k === 'latest' ? { ...s, name: 'Latest run (data to ' + toDate.slice(0, 6) + ')' } : s));
  const [view, setView] = useSS('vt.view', 'chart');
  const [hidden, setHidden] = useSS('vt.hidden', { s3: true, s2: true, s1: true });
  const [cmpOpen, setCmpOpen] = useSS('vt.cmp', false);
  const [basis, setBasis] = useSS('vt.basis', 'mom');
  const { data: DR } = useApi('/api/drivers?level=' + encodeURIComponent(level));
  useEffect(() => {
    if (!pendingScroll) return; pendingScroll = false;
    setTimeout(() => document.getElementById('mcmp')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
  }, [vm, cmpOpen]);
  const VM = V?.months;
  const vnode = V?.nodes[nodeKey]; const n = vnode?.[mea];

  const config = useMemo(() => {
    if (!n) return null;
    const ds = RUNS_SHOWN.map((s) => { const c = css(s.col); const isA = s.k === 'actual', isL = s.k === 'latest';
      return { label: s.name, data: n[s.k], borderColor: c, backgroundColor: c, borderWidth: isA ? 2.5 : 1.75, borderDash: s.cls === 'dash' ? [6, 4] : (s.cls === 'dot' ? [2, 3] : []),
        pointRadius: isA ? 3 : (isL ? 3.5 : 2.5), pointStyle: s.k.startsWith('s') ? 'rectRot' : 'circle', spanGaps: false, hidden: !!hidden[s.k], _k: s.k, order: isA ? 0 : (isL ? 1 : 2) }; });
    const vals = ds.filter((d) => !d.hidden).flatMap((d) => d.data.filter((v) => v != null)); const lo = Math.min(...vals) * 0.85; const step = lo >= 1e7 ? 5e6 : (lo >= 1e5 ? 5e5 : undefined);
    const selIdx = VM.findIndex((x) => x.m === vm);
    const monthBand = { id: 'monthBand', beforeDatasetsDraw(c) { if (selIdx < 0) return; const xs = c.scales.x; const w = xs.getPixelForValue(1) - xs.getPixelForValue(0); const x = xs.getPixelForValue(selIdx); const a = c.chartArea; const g = c.ctx; g.save(); g.fillStyle = css('--reiq-layer-hover'); g.globalAlpha = 0.8; g.fillRect(x - w / 2, a.top, w, a.bottom - a.top); g.restore(); } };
    return {
      type: 'line', data: { labels: VM.map((x) => x.label), datasets: ds }, plugins: [monthBand],
      options: { ...baseOptions(),
        onClick: (e, _el, chart) => { const q = chart.getElementsAtEventForMode(e, 'index', { intersect: false }, false)[0]; if (q) { pendingScroll = true; setCmpOpen(true); onPick(VM[q.index].m); } },
        scales: { x: xScale({ ticks: { color: css('--reiq-text-secondary'), maxRotation: 0, font: { family: css('--font-sans') } } }), y: yScale(mea === 'u' ? 'Units per month' : '₹ per month', (v) => fK(v), { min: step ? Math.floor(lo / step) * step : undefined }) },
        plugins: { legend: { display: false }, tooltip: { ...tooltipBase(), filter: (i) => i.raw != null, callbacks: {
          title: (i) => VM[i[0].dataIndex].label + (VM[i[0].dataIndex].complete ? '' : ' (not complete)'),
          label: (i) => { const a = n.actual[i.dataIndex]; const e = (a && i.dataset._k !== 'actual') ? '  (' + fS(i.raw / a - 1) + ' vs actual)' : ''; return ' ' + i.dataset.label + ': ' + fN(i.raw) + e; } } } } },
    };
  }, [n, mea, hidden, vm, theme, VM, K]);

  const label = D.levels[level].nodes[nodeKey].label;
  const idx = VM.findIndex((x) => x.m === vm), mm = VM[idx], A = n.actual[idx];
  const tiles = [K].map((k) => { const v = n['m' + k][idx];
    const base = { what: 'The model\'s forecast for ' + mm.label + ' from the M' + k + ' run, the run made ' + AGO[k] + ' before the month starts, using actuals to ' + cutText(mm.m, k) + '.',
      how: 'Sum of the weekly forecasts from that run for weeks that fall in ' + mm.label + ' (a week that straddles two months is split by days, for example 4/7 to one month and 3/7 to the next).' };
    return v != null
      ? { l: 'M' + k + ' forecast', v: fCr(v), d: mm.complete ? <>vs actual <span className="chip">{vErr(v, A)}</span></> : <>data to <span className="chip">{cutText(mm.m, k)}</span></>,
          i: { ...base, read: mm.complete ? 'The percentage under the number is the gap to actual sales: positive means the run over-forecast, negative means it under-forecast.' : 'The month is still open, so there is no actual to compare with yet.' } }
      : { l: 'M' + k + ' forecast', v: '—', d: 'needs actuals to ' + cutText(mm.m, k),
          i: { ...base, read: 'Not available yet: this run can only be made once actuals to ' + cutText(mm.m, k) + ' exist.' } }; });
  if (mm.complete) tiles.push({ l: 'Actual', v: fCr(A), d: mm.weeks + ' weeks',
    i: { what: 'What was actually sold (primary sales) in ' + mm.label + '.', how: 'Sum of weekly primary sales for the ' + mm.weeks + ' weeks\' worth of days in the month (a week that straddles two months is split by days).', read: 'This is the benchmark the M3, M2 and M1 tiles are measured against.' } });
  else { const L = n.latest[idx]; tiles.push({ l: mm.actualWeeks ? 'Latest run, part actual' : 'Latest run', v: L != null ? fCr(L) : '—', d: mm.actualWeeks ? `${mm.actualWeeks} of ${mm.weeks} weeks actual` : 'data to ' + toDate,
    i: { what: 'The most recent view of ' + mm.label + ', from the latest run (data to the week of ' + fromWk + ').', how: mm.actualWeeks ? 'Weeks already sold are actuals; the remaining weeks come from the latest run.' : 'All weeks come from the latest run, as there are no actuals for this month yet.', read: 'Use it as the current best estimate. It will settle as the month closes and actuals replace forecast weeks.' } }); }

  const cell = (v, a) => (v == null ? <td>–</td> : <td>{fN(v)}{a ? <> <span style={{ color: 'var(--reiq-text-helper)', fontSize: 11 }}>{vErr(v, a)}</span></> : null}</td>);
  // month-on-month and year-on-year: actuals where the month is complete, otherwise the latest run
  const H = V?.hist, hn = H?.nodes[nodeKey]?.[mea];
  const monthVal = (m) => {
    const i = VM.findIndex((x) => x.m === m);
    if (i >= 0 && !VM[i].complete) { const v = n.latest[i]; return v == null ? null : { v, w: VM[i].weeks, k: VM[i].actualWeeks ? 'latest run, part actual' : 'latest run' }; }
    const h = H?.months.findIndex((x) => x.m === m);
    if (h >= 0 && hn) return { v: hn[h], w: H.months[h].weeks, k: 'actual' };
    if (i >= 0 && n.actual[i] != null) return { v: n.actual[i], w: VM[i].weeks, k: 'actual' };
    return null;
  };
  const cur = monthVal(vm);
  const compare = (ref) => {
    const o = monthVal(ref);
    if (!cur || !o) return { ref, o: null };
    const t = cur.v / o.v - 1, pw = (cur.v / cur.w) / (o.v / o.w) - 1;
    return { ref, o, t, pw, diff: cur.v - o.v };
  };
  const cmps = [{ title: 'Against last month', ...compare(shift(vm, -1)) }, { title: 'Against the same month last year', ...compare(shift(vm, -12)) }];
  const closeCmp = () => setCmpOpen(false);

  return (
    <>
      <Kpis tiles={tiles} label="Selected month" />
      <section className="card" aria-labelledby="vct">
        <div className="card-head"><h2 id="vct">Forecast runs by month, {label}</h2>
          <SegBare ariaLabel="View" value={view} onChange={setView} options={[{ v: 'chart', label: 'Chart' }, { v: 'table', label: 'Table' }]} /></div>
        <details className="wdetails more"><summary>About this view</summary><p className="note">Monthly totals of weekly primary sales (a week that straddles two months is split by days). Each run is a full retrain with data only up to its cut-off, so nothing in it knows what happened after. Selected month: <strong>{mm.label}</strong>. Showing: <strong>{label}</strong>, {level === 'National' ? 'national' : 'Kolkata depots'}.</p></details>
        {view === 'chart' ? (
          <div><Legend series={RUNS_SHOWN} hidden={hidden} onToggle={(k) => setHidden((h) => ({ ...h, [k]: !h[k] }))} />
            <ChartCanvas config={config} label={"Monthly demand: actual and the M" + K + " forecast run"} />
            {cmpOpen && cur ? <CompareCard mm={mm} cur={cur} cmps={cmps} mea={mea} onClose={closeCmp} DR={DR} V={V} nodeKey={nodeKey} vm={vm} basis={basis} setBasis={setBasis} />
              : <p className="foot">Click any month on the chart, or pick a target month, to compare it with last month and with the same month last year.</p>}</div>
        ) : (
          <div className="tablewrap"><table>
            <thead><tr><th>Month</th><th>Actual</th><th>Model M{K}</th><th>Latest run</th><th>Sales M{K}</th></tr></thead>
            <tbody>{VM.map((m, i) => { const a = n.actual[i]; return (
              <tr key={m.m} className={m.m === vm ? 'sel' : ''}><td>{m.label}{!m.complete && <span className="pill">open</span>}</td>{cell(a)}{cell(n['m' + K][i], a)}{cell(n.latest[i], null)}{cell(n['s' + K][i], a)}</tr>); })}</tbody>
          </table></div>
        )}
        <details className="wdetails more"><summary>Notes and limits</summary><p className="foot">M3, M2 and M1 are runs made with data to the end of the month 3, 2 and 1 months before the target month; a run appears only once its cut-off has passed and the data exists, so November M1 needs October actuals and December M2 and M1 need Oct and Nov actuals. Latest run covers weeks after {fromWk} and the 26-week horizon ends at the end of March 2027. Sales-team forecasts exist only to Sep 2026. {level === 'National' ? '' : 'Depot runs use seasonal naive and LightGBM only (no ETS), and single depots are noisier than the national total. '}The ensemble weights were set by hand while looking at this same period, so completed-month accuracy is optimistic. All data is synthetic.</p></details>
      </section>
      <AccuracyCard V={V} />
    </>
  );
}

const MON_L = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const BASESM = (vm) => ({ mom: { ref: shift(vm, -1), short: 'last month', sub: 'How the three models pull the forecast away from last month, after allowing for month length.', facts: 'last month' },
                          yoy: { ref: shift(vm, -12), short: 'last year', sub: 'How the three models pull the forecast away from the same month last year, after allowing for month length.', facts: 'the same month last year' } });

function CompareCard({ mm, cur, cmps, mea, onClose, DR, V, nodeKey, vm, basis, setBasis }) {
  const unit = mea === 'v' ? '₹' : 'units';
  const B = BASESM(vm)[basis];
  const i = V.months.findIndex((x) => x.m === vm);
  const fc = !V.months[i].complete;
  const a = DR ? aggInfo(monthInfos(DR, vm)) : null, b = DR ? aggInfo(monthInfos(DR, B.ref)) : null;
  // weeks of this month inside the 52-week window the models were saved for (April 2026 onward)
  const win = DR ? DR.weeks.slice(-52) : [];
  const js = win.map((w, ix) => (weekShare(w, vm) > 0 ? ix : -1)).filter((ix) => ix >= 0), jw = js.map((ix) => weekShare(win[ix], vm));
  const cm = cmps[basis === 'mom' ? 0 : 1];
  const M = DR && cm.o && a && js.length === a.n ? buildModelRows({ mdl: DR.nodes[nodeKey]?.mdl, weights: DR.weights, js, jw, mea, cur: cur.v, ref: cm.o.v, adj: cur.w / cm.o.w, actual: !fc, events: a.ev, short: basis === 'mom' ? 'last month' : 'the same month last year' }) : null;
  const facts = a && b ? buildFacts(a, b, B.short, fc, nodeKey.startsWith('cat:') ? nodeKey.slice(4) : null) : [];
  // months differ in length: say why, once, in plain words
  const odd = cmps.filter((c) => c.o && c.o.w !== cur.w);
  return (
    <aside className="why" id="mcmp" tabIndex={-1} aria-label={'Comparison for ' + mm.label}>
      <div className="why-h">
        <div>
          <div className="why-eyebrow">{mm.label} <span className={'pill ' + (cur.k === 'actual' ? '' : 'fc')}>{cur.k === 'actual' ? 'Actual' : 'Forecast'}</span></div>
          <h3>{fCr(cur.v)} <small>{cur.k === 'actual' ? 'sold' : cur.k} · {cur.w} weeks</small></h3>
        </div>
        <button className="x" onClick={onClose} aria-label="Close comparison">×</button>
      </div>
      <div className="stats">
        {cmps.map((c, k) => {
          const key = k === 0 ? 'mom' : 'yoy', differ = c.o && c.o.w !== cur.w;
          return <Stat key={c.title} title={c.title} pct={c.o ? fS(c.t) : null} up={c.t >= 0} active={basis === key} onSelect={() => setBasis(key)}
            detail={c.o ? <><b>{fCr(cur.v)}</b> against <b>{fCr(c.o.v)}</b></> : mLab(c.ref) + ' is not in the data'}
            sub={c.o ? `${mLab(c.ref)} (${c.o.k}) · ${c.diff >= 0 ? '+' : '−'}${fCr(Math.abs(c.diff))} ${unit}` : null}
            alt={differ ? { label: 'Per week, like for like', pct: fS(c.pw), up: c.pw >= 0 } : null} />;
        })}
      </div>
      {odd.length > 0 && (
        <p className="callout">
          <b>Why the total and the per-week figure differ.</b> Months have 28 to 31 days, about 4 to 4.4 weeks: {mm.label} has {cur.w}{odd.map((c) => <span key={c.title}>; {mLab(c.ref)} has {c.o.w}</span>)}.
          {' '}The per-week figure takes month length out, so it shows the change in demand.
        </p>
      )}
      {M && <InShort text={M.story} />}
      {DR && <DriverCols title="What each model says" sub={M ? B.sub : 'The model breakdown covers months from April 2026. Earlier months show the plain facts only.'} rows={M ? M.rows : []}
        note={M && <Agreement spread={M.spread} vals={M.vals} errs={M.errs} />} facts={facts} factsNote={B.facts} basis={basis} setBasis={setBasis}
        options={[{ v: 'mom', label: 'Last month' }, { v: 'yoy', label: 'Same month last year' }]} />}
      {DR && <HowEstimated fc={fc} />}
    </aside>
  );
}
