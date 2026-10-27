import { useEffect, useMemo } from 'react';
import { useApp } from '../context.js';
import { useApi } from '../lib/api.js';
import Page, { Empty } from '../components/Page.jsx';
import Kpis from '../components/Kpis.jsx';
import ChartCanvas from '../components/ChartCanvas.jsx';
import { Select, SegBare } from '../components/Controls.jsx';
import { css, tooltipBase, baseOptions, xScale, yScale, dividerPlugin } from '../lib/chart.js';
import { lab, labFull, fK, fN, fS, fP, sum } from '../lib/format.js';

const SERIES = [
  { k: 'ordered', name: 'Requested by partners', col: '--reiq-chart-5', cls: 'dash' },
  { k: 'delivered', name: 'Delivered', col: '--reiq-chart-3', cls: 'dot' },
  { k: 'sellout', name: 'Real need (partner sell-out)', col: '--reiq-chart-1', cls: '' },
  { k: 'need', name: 'Forecast need', col: '--reiq-chart-2', cls: 'dash' },
  { k: 'rec', name: 'Recommended shipment', col: '--reiq-chart-6', cls: '' },
];

function corr(a, b) {
  const n = a.length; if (n < 5) return null;
  const ma = sum(a) / n, mb = sum(b) / n; let sab = 0, saa = 0, sbb = 0;
  for (let i = 0; i < n; i++) { sab += (a[i] - ma) * (b[i] - mb); saa += (a[i] - ma) ** 2; sbb += (b[i] - mb) ** 2; }
  return saa && sbb ? sab / Math.sqrt(saa * sbb) : null;
}

export default function QuickCommerce() {
  const { level, cat, prod, setFilter, theme, useSS } = useApp();
  const { data: Q } = useApi('/api/quick-commerce');
  const [win, setWin] = useSS('qc.win', '26');
  const [cov, setCov] = useSS('qc.cov', '2');
  const [hidden, setHidden] = useSS('qc.hidden', { delivered: true });

  const qcCats = useMemo(() => (Q ? new Set(Object.values(Q.skus).map((k) => k.cat)) : null), [Q]);
  // keep the shared Category / Product filters on things quick commerce sells
  useEffect(() => {
    if (!Q) return;
    if ((cat && !qcCats.has(cat)) || (prod && !Q.skus[prod])) setFilter({ cat: qcCats.has(cat) ? cat : '', prod: Q.skus[prod] ? prod : '' });
  }, [Q]); // eslint-disable-line

  const head = { crumb: 'Quick commerce', title: 'Quick commerce & OTIF',
    sub: 'What quick-commerce partners ask for against what they actually sell, how well we deliver it, and what to ship instead.',
    tags: <><span className="tag">Channel: quick commerce and dark stores</span><span className="tag out">National only</span></> };
  const extra = (<>
    <div className="field"><span className="lab" id="qw-l">Window</span>
      <SegBare labelledby="qw-l" value={win} onChange={setWin} options={[{ v: '13', label: '13 weeks' }, { v: '26', label: '26 weeks' }, { v: 'all', label: 'All' }]} /></div>
    <Select id="qcv" label="Buffer stock at partner" value={cov} onChange={setCov} options={[{ v: '1', label: '1 week' }, { v: '2', label: '2 weeks' }, { v: '3', label: '3 weeks' }]} />
  </>);
  const pageProps = { ...head, showMeasure: false, extra, catFilter: (c) => !qcCats || qcCats.has(c), prodFilter: (p) => !Q || !!Q.skus[p.code] };
  if (level !== 'National') return <Page {...pageProps}><Empty title="Quick commerce is built for National only" text="Switch Level to National." /></Page>;
  if (!Q) return <Page {...pageProps}><Empty title="Loading quick-commerce data" text="Fetching from the API…" /></Page>;

  const QH = Q.hist, QN = Q.weeks.length, QF = Q.first_need;
  const qLab = (i) => lab(Q.weeks[i]), qFull = (i) => labFull(Q.weeks[i]);
  const sel = Object.keys(Q.skus).filter((s) => (!cat || Q.skus[s].cat === cat) && (!prod || s === prod));
  if (!sel.length) return <Page {...pageProps}><Empty title="No quick-commerce sales for this selection" text={`Quick commerce covers ${Object.keys(Q.skus).length} products. Pick another category or product.`} /></Page>;
  return <QcBody {...{ Q, QH, QN, QF, qLab, qFull, sel, cat, win, cov, hidden, setHidden, theme, pageProps }} />;
}

function QcBody({ Q, QH, QN, QF, qLab, qFull, sel, cat, win, cov, hidden, setHidden, theme, pageProps }) {
  const { useSS: useSS2 } = useApp();
  const [cu, setCu] = useSS2('qc.coverUnit', 'wk');   // show cover in weeks or days
  const fCov = (w) => (w == null || !isFinite(w) ? '–' : cu === 'd' ? Math.round(w * 7) + ' d' : w.toFixed(1) + ' wk');
  const qSum = (arr, i) => { let v = 0, any = false; sel.forEach((s) => { const x = Q.skus[s][arr][i]; if (x != null) { v += x; any = true; } }); return any ? v : null; };
  const qSumN = (a, b, i) => { let v = 0, any = false; sel.forEach((s) => { const x = Q.skus[s][a][b][i]; if (x != null) { v += x; any = true; } }); return any ? v : null; };
  const ws = win === 'all' ? 0 : Math.max(0, QH - parseInt(win));
  const rng = []; for (let i = ws; i < QH; i++) rng.push(i);
  const T = (a) => sum(rng.map((i) => qSum(a, i) || 0));
  const req = T('ordered'), del = T('delivered'), so = T('sellout'), ret = T('returned'), ln = T('lines'), ot = T('ontime'), inf = T('infull'), of = T('otif');
  const lastSt = qSum('stock', QH - 1), so4 = sum([QH - 4, QH - 3, QH - 2, QH - 1].map((i) => qSum('sellout', i) || 0)) / 4;
  let pk = 0; rng.forEach((i) => { const o = qSum('ordered', i), s_ = qSum('sellout', i); if (s_ > 0 && o / s_ > pk) pk = o / s_; });
  const cw = rng.filter((i) => i >= QF);
  const cfReq = sum(cw.map((i) => qSum('ordered', i) || 0)), cfRec = sum(cw.map((i) => qSumN('rec', cov, i) || 0)), cfSo = sum(cw.map((i) => qSum('sellout', i) || 0)), cfLost = sum(cw.map((i) => qSumN('lost', cov, i) || 0));
  const cover = so4 > 0 ? lastSt / so4 : 0;

  const xs = [], ys = [];
  sel.forEach((s) => rng.forEach((i) => { const k = Q.skus[s]; const o = k.ordered[i], so_ = k.sellout[i], l_ = k.lines[i], f_ = k.otif[i]; if (o && so_ && l_) { xs.push(o / so_); ys.push(f_ / l_); } }));
  const cr = corr(xs, ys);

  const tiles = [
    { l: 'Fulfilment', v: fP(del / req), d: <>delivered <span className="chip">{fK(del)}</span> of <span className="chip">{fK(req)}</span></>, i: 'Units delivered divided by units requested, over the selected weeks. This is the number that looks healthy.' },
    { l: 'OTIF', v: fP(of / ln), cls: of / ln < 0.9 ? 'neg' : '', d: <>on time <span className="chip">{fP(ot / ln)}</span> in full <span className="chip">{fP(inf / ln)}</span></>, i: 'Share of order lines delivered both on time and in full. Fulfilment counts units, OTIF counts whole lines, so OTIF is always lower.' },
    { l: 'Over-order multiple', v: (req / so).toFixed(1) + 'x', cls: req / so > 3 ? 'neg' : '', d: <>peak week <span className="chip">{pk.toFixed(1)}x</span></>, i: 'Units requested by partners divided by units they actually sold to shoppers (partner sell-out). 1.0x would mean they ordered exactly what they needed.' },
    { l: 'Partner stock cover', v: cover.toFixed(1) + ' wk', cls: cover > 4 ? 'neg' : '', d: <>holding <span className="chip">{fK(lastSt)}</span> units</>, i: 'Stock sitting at partners in the last week, divided by their average weekly sell-out over the last four weeks.' },
    { l: 'Shipped vs real need', v: cfReq ? fS(cfRec / cfReq - 1) : '—', cls: 'pos', d: cfReq ? <>recommended <span className="chip">{fK(cfRec)}</span> vs requested <span className="chip">{fK(cfReq)}</span></> : 'no forecast weeks in this window',
      i: 'If we had shipped only what the forecast says partners need plus ' + cov + ' week' + (cov === '1' ? '' : 's') + ' of buffer, instead of what they requested, over the weeks since ' + qFull(QF) + '. In that replay partners would have missed ' + (cfSo ? fP(cfLost / cfSo) : '–') + ' of their sales. The replay starts partners at the target stock, so part of the saving is stock they already held.' },
  ];

  const charts = useMemo(() => {
    const idx = []; for (let i = ws; i < QN; i++) idx.push(i);
    const labels = idx.map(qLab);
    const ser = (k) => idx.map((i) => { if (k === 'need') return qSum('need', i); if (k === 'rec') return qSumN('rec', cov, i); return i < QH ? qSum(k, i) : null; });
    const ds = SERIES.map((s) => { const col = css(s.col); return { label: s.name, data: ser(s.k), borderColor: col, backgroundColor: col, borderWidth: s.k === 'sellout' ? 2.5 : 2, borderDash: s.cls === 'dash' ? [6, 4] : (s.cls === 'dot' ? [2, 3] : []), pointRadius: s.k === 'sellout' ? 2.5 : 0, pointHoverRadius: 4, spanGaps: false, hidden: !!hidden[s.k] }; });
    const c1 = { type: 'line', data: { labels, datasets: ds }, plugins: [dividerPlugin('planLine', QH - ws >= 0 && QH - ws < idx.length ? QH - ws : null, 'Plan starts')],
      options: { ...baseOptions(), scales: { x: xScale(), y: yScale('Units per week', (v) => fK(v), { min: 0, afterFit(s) { s.width = 72; } }) },
        plugins: { legend: { display: false }, tooltip: { ...tooltipBase(), filter: (i) => i.raw != null, callbacks: { title: (i) => 'Week beginning ' + qFull(idx[i[0].dataIndex]) + (idx[i[0].dataIndex] >= QH ? ' (plan)' : ''), label: (i) => ' ' + i.dataset.label + ': ' + fN(i.raw) } } } } };
    const hist = idx.filter((i) => i < QH);
    const pct = (num, den) => hist.map((i) => { const a = qSum(num, i), b = qSum(den, i); return b ? a / b : null; });
    const line = (label, data, col, w, dash, pr) => ({ label, data, borderColor: css(col), backgroundColor: css(col), borderWidth: w, borderDash: dash, pointRadius: pr });
    const c2 = { type: 'line', data: { labels: hist.map(qLab), datasets: [
        line('Fulfilment (units)', pct('delivered', 'ordered'), '--reiq-chart-2', 2, [], 0), line('OTIF (lines)', pct('otif', 'lines'), '--reiq-chart-1', 2.5, [], 2),
        line('On time (lines)', pct('ontime', 'lines'), '--reiq-chart-3', 1.5, [6, 4], 0), line('In full (lines)', pct('infull', 'lines'), '--reiq-chart-5', 1.5, [2, 3], 0)] },
      options: { ...baseOptions(), scales: { x: xScale(), y: yScale('Share', (v) => (v * 100).toFixed(0) + '%', { min: 0.7, max: 1, afterFit(s) { s.width = 72; } }) },
        plugins: { legend: { display: true, position: 'top', align: 'start', labels: { color: css('--reiq-text-secondary'), boxWidth: 22, boxHeight: 2, usePointStyle: false, font: { family: css('--font-sans'), size: 12 } } },
          tooltip: { ...tooltipBase(), callbacks: { title: (i) => 'Week beginning ' + qFull(hist[i[0].dataIndex]), label: (i) => (i.raw == null ? '' : ' ' + i.dataset.label + ': ' + (i.raw * 100).toFixed(1) + '%') } } } } };
    return { c1, c2 };
  }, [sel.join(), ws, cov, hidden, theme]); // eslint-disable-line

  // per-product table
  const rows = sel.map((s) => { const k = Q.skus[s]; const g = (a) => sum(rng.map((i) => k[a][i] || 0));
    const rq = g('ordered'), so_ = g('sellout'), dl = g('delivered'), rt = g('returned'), l = g('lines'), o = g('otif');
    const s4 = sum([QH - 4, QH - 3, QH - 2, QH - 1].map((i) => k.sellout[i] || 0)) / 4;
    const rec = sum(cw.map((i) => k.rec[cov][i] || 0)), rq2 = sum(cw.map((i) => k.ordered[i] || 0));
    return { s, name: k.name, rq, so: so_, ov: rq / so_, cov: s4 > 0 ? k.stock[QH - 1] / s4 : 0, ful: dl / rq, otif: o / l, ret: rt, rec, cut: rq2 ? rec / rq2 - 1 : null }; }).sort((a, b) => b.ov - a.ov);
  const first = [...Array(13).keys()].find((k) => (qSumN('rec', cov, QH + k) || 0) > 0);
  const nm = sel.length === 1 ? Q.skus[sel[0]].name : (cat || 'All quick-commerce products');

  return (
    <Page {...pageProps}>
      <Kpis tiles={tiles} label="Quick commerce summary" />
      <section className="card" aria-labelledby="qct">
        <div className="card-head"><h2 id="qct">Requested against real need, {nm}</h2></div>
        <details className="wdetails more"><summary>About this view</summary><p className="note">Partners requested <strong>{(req / so).toFixed(1)}x</strong> what they sold to shoppers and received almost all of it ({fP(del / req)}). The surplus does not stay: <strong>{fP(ret / del)}</strong> of delivered units were sent back as returns, so we ship, handle and take back most of what is ordered. Partners now hold {cover.toFixed(1)} weeks of cover. The forecast need and recommended shipment lines show what the plan would send instead.</p></details>
        <div className="legendrow" role="group" aria-label="Show or hide lines">
          {SERIES.map((s) => (
            <button key={s.k} type="button" aria-pressed={!hidden[s.k]} style={{ color: `var(${s.col})` }} onClick={() => setHidden((h) => ({ ...h, [s.k]: !h[s.k] }))}>
              <span className={'sw ' + s.cls} /><span style={{ color: 'var(--reiq-text-secondary)' }}>{s.name}</span>
            </button>))}
        </div>
        <ChartCanvas config={charts.c1} height={380} label="Weekly quick-commerce units: requested, delivered, real need, forecast need and recommended shipment" />
        <details className="wdetails more"><summary>Notes and limits</summary><p className="foot">Forecast need is the model's national demand forecast four weeks ahead for the product times the product's recent quick-commerce share of sales (about 9% in this data). Over the weeks tested it missed partner sell-out by about 24.7% per product-week and 12.7% for the total week, against 26% and 15.6% for a plain four-week average, so it is only modestly better than naive at product level. The recommended shipment is forecast need plus buffer cover minus stock the partner already holds, never below zero. From {qLab(QH)} the plan runs from the partner stock actually held on {qLab(QH - 1)}. All data is synthetic.</p></details>
      </section>
      <section className="card" aria-labelledby="qot">
        <div className="card-head"><h2 id="qot">Delivery performance</h2></div>
        <details className="wdetails more"><summary>About this view</summary><p className="note">OTIF is {fP(of / ln)}, against {fP(del / req)} fulfilment, because OTIF scores whole order lines. {cr == null ? '' : `Across product-weeks, OTIF has no real link to how much partners over-ordered (correlation ${cr.toFixed(2)}), so cutting over-ordering will reduce stock and returns but should not be expected to move OTIF on its own. The late and short lines need their own fix.`}</p></details>
        <ChartCanvas config={charts.c2} height={300} label="Weekly fulfilment, OTIF, on-time and in-full rates" />
      </section>
      {Q.lines && (() => { const Lh = Q.lines, pp = (v) => (v * 100).toFixed(1) + '%'; const maxO = Math.max(...Lh.by_size.map((b) => 1 - b.otif)); return (
        <section className="card" aria-labelledby="qlt">
          <div className="card-head"><h2 id="qlt">Why order lines fail, and what right-sized orders would change</h2></div>
          <p className="callout"><b>Simulated order lines.</b> The weekly totals are real to this dataset, but which lines fail and why is assumed, because we have no order-line file. These figures come from <code>qc_line_*</code> columns in the main data file; replace them with Eveready's order-line data to get true results.</p>
          <p className="note">Of {fN(Lh.lines)} order lines, <strong>{pp(Lh.otif)}</strong> arrived on time and in full. If over-sized orders were cut to what partners need, the lines lost to allocation cuts and busy-week dispatch queues would arrive, and OTIF would be <strong>{pp(Lh.otif_right_sized)}</strong>, up {((Lh.otif_right_sized - Lh.otif) * 100).toFixed(1)} points. The rest (stockouts, pick and pack, transport and cut-off) need other fixes.</p>
          <div className="grid2">
            <div className="tablewrap" style={{ maxHeight: 'none' }}><table className="ctab">
              <thead><tr><th>Line size against real need</th><th>Lines</th><th>OTIF</th><th>In full</th><th>Lines missed</th></tr></thead>
              <tbody>{Lh.by_size.map((b) => <tr key={b.band}><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{b.band}</td><td>{fN(b.lines)}</td><td className={b.otif < 0.8 ? 'bad' : ''}>{pp(b.otif)}</td><td>{pp(b.in_full)}</td><td><span className="sbar" aria-hidden="true"><i style={{ width: ((1 - b.otif) / maxO) * 100 + '%' }} /></span>{pp(1 - b.otif)}</td></tr>)}</tbody>
            </table></div>
            <div className="tablewrap" style={{ maxHeight: 'none' }}><table className="ctab">
              <thead><tr><th>Reason a line failed</th><th>Share of failed lines</th><th>Fixed by right-sizing</th></tr></thead>
              <tbody>{Object.entries(Lh.reasons).sort((a, b) => b[1].share_of_failed - a[1].share_of_failed).map(([k, v]) => <tr key={k}><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{k}</td><td>{pp(v.share_of_failed)}</td><td>{v.avoidable ? <span className="flag stk">Yes</span> : 'No'}</td></tr>)}</tbody>
            </table></div>
          </div>
          <details className="wdetails more"><summary>Notes and limits</summary><p className="foot">A line can fail for more than one reason, so shares add to more than 100%. Line size is the units on the line against its share of the week's real partner sell-out. OTIF does not differ by partner or city here because those were assigned at random. In the weekly file the OTIF count is slightly below what its on-time and in-full counts allow in some product-weeks, so this line view shows OTIF about 0.9 points higher than the weekly figure above. The improvement is a what-if built on the assumption that over-sized lines are the ones that fail in full; it is not a measured result.</p></details>
        </section>); })()}
      <section className="card" aria-labelledby="qpt">
        <details className="wdetails" style={{ borderTop: 0, paddingTop: 0 }}><summary id="qpt" style={{ fontSize: '1.25rem', fontWeight: 600 }}>Shipment plan, next 13 weeks</summary>
        <p className="note">{first === 0 ? 'Partners need a shipment from the first plan week.' : (first == null ? 'At the stock partners hold now, no shipment is needed for the whole 13 weeks.' : <>At the stock partners hold now, <strong>no shipment is needed until the week of {qFull(QH + first)}</strong>.</>)}</p>
        <div className="tablewrap" style={{ maxHeight: 'none' }}><table className="ctab">
          <thead><tr><th>Week beginning</th><th>Expected sell-out</th><th>Recommended shipment</th><th>Partner stock after</th><th>Cover ({cu === 'd' ? 'days' : 'weeks'})</th></tr></thead>
          <tbody>{[...Array(13).keys()].map((k) => { const i = QH + k; const nd = qSum('need', i), rc = qSumN('rec', cov, i), sk = qSumN('cfstock', cov, i);
            return <tr className="fc" key={k}><td>{qFull(i)}</td><td>{fN(nd)}</td><td>{fN(rc)}</td><td>{fN(sk)}</td><td>{nd > 0 ? fCov(sk / nd).replace(/ (wk|d)$/, '') : '–'}</td></tr>; })}</tbody>
        </table></div>
        </details>
      </section>
      <section className="card" aria-labelledby="qst">
        <details className="wdetails" style={{ borderTop: 0, paddingTop: 0 }}><summary id="qst" style={{ fontSize: '1.25rem', fontWeight: 600 }}>By product</summary>
        <div style={{ margin: '12px 0' }}><SegBare ariaLabel="Show cover in" value={cu} onChange={setCu} options={[{ v: 'wk', label: 'Cover in weeks' }, { v: 'd', label: 'Cover in days' }]} /></div>
        <div className="tablewrap" style={{ maxHeight: 'none' }}><table className="ctab">
          <thead><tr><th>Product</th><th>Requested</th><th>Real need</th><th>Over-order</th><th>Partner cover</th><th>Fulfilment</th><th>OTIF</th><th>Returned</th><th>Recommended</th><th>vs requested</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.s}><td>{r.name}</td><td>{fN(r.rq)}</td><td>{fN(r.so)}</td><td className={r.ov > 3 ? 'bad' : ''}>{r.ov.toFixed(1)}x</td><td className={r.cov > 4 ? 'bad' : ''}>{fCov(r.cov)}</td>
              <td>{fP(r.ful)}</td><td>{fP(r.otif)}</td><td>{fN(r.ret)}</td><td>{r.cut == null ? '–' : fN(r.rec)}</td><td className={r.cut != null && r.cut < 0 ? 'good' : ''}>{r.cut == null ? '–' : fS(r.cut)}</td></tr>))}</tbody>
        </table></div>
        </details>
      </section>
    </Page>
  );
}
