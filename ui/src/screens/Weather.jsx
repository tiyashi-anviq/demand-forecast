import { useEffect, useMemo } from 'react';
import { useApp } from '../context.js';
import { useApi } from '../lib/api.js';
import Page, { Empty } from '../components/Page.jsx';
import Kpis from '../components/Kpis.jsx';
import ChartCanvas from '../components/ChartCanvas.jsx';
import { Select, SegBare } from '../components/Controls.jsx';
import { css, tooltipBase, baseOptions, xScale, yScale, dividerPlugin } from '../lib/chart.js';
import { lab, labFull, fK, fN, fS } from '../lib/format.js';

const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');

function calc(X, nd) {
  const c = X.cut, n = X.weeks.length; const dev = [], ph = [];
  for (let i = 0; i < n; i++) dev.push(i >= c && nd.f[i] ? nd.a[i] / nd.f[i] - 1 : null);
  let seen = false;
  for (let i = 0; i < n; i++) { const v = dev[i]; if (v == null) { ph.push(''); continue; } if (v < -0.25) { ph.push('Shock'); seen = true; } else if (seen && v > 0.10) ph.push('Recovery'); else ph.push('Normal'); }
  const onset = (arr, th) => { for (let i = c; i < n; i++) if (arr[i] != null && arr[i] >= th) return i; return -1; };
  const noFc = nd.f.every((v) => v == null);
  const ex = onset(X.exp, 40), ac = onset(X.rain, 40);
  let worst = -1; dev.forEach((v, i) => { if (v != null && (worst < 0 || v < dev[worst])) worst = i; });
  let lost = 0, regained = 0, sa = 0, sf = 0;
  for (let i = c; i < n; i++) { if (nd.f[i] == null) continue; sa += nd.a[i]; sf += nd.f[i]; if (ph[i] === 'Shock') lost += nd.f[i] - nd.a[i]; if (ph[i] === 'Recovery') regained += nd.a[i] - nd.f[i]; }
  let peak = -1; dev.forEach((v, i) => { if (ph[i] === 'Recovery' && (peak < 0 || v > dev[peak])) peak = i; });
  return { noFc, c, n, dev, ph, ex, ac, worst, lost, regained, net: sf ? sa / sf - 1 : 0, peak, nShock: ph.filter((p) => p === 'Shock').length, nRec: ph.filter((p) => p === 'Recovery').length };
}

export default function Weather() {
  const { D, level, cat, nodeKey, theme, setFilter, useSS } = useApp();
  const { data: WX } = useApi('/api/weather');
  const [yr, setYr] = useSS('wx.yr', '2025');
  const [view, setView] = useSS('wx.view', 'chart');
  const [init, setInit] = useSS('wx.init', false);

  // first visit: start on rechargeable torches, where the 2025 shock is clearest
  useEffect(() => { if (!init && level === 'National') { setInit(true); setFilter({ cat: 'Flashlights — rechargeable', prod: '' }); } }, [init, level]); // eslint-disable-line

  const X = WX?.seasons[yr]; const nd = X?.nodes[nodeKey];
  const R = useMemo(() => (X && nd ? calc(X, nd) : null), [X, nd]);

  const charts = useMemo(() => {
    if (!R) return null;
    const labels = X.weeks.map(lab); const base = baseOptions();
    const phaseBands = { id: 'phaseBands', beforeDatasetsDraw(c) { const xs = c.scales.x, a = c.chartArea, g = c.ctx; const w = xs.getPixelForValue(1) - xs.getPixelForValue(0);
      R.ph.forEach((p, i) => { if (p !== 'Shock' && p !== 'Recovery') return; const x = xs.getPixelForValue(i); g.save(); g.globalAlpha = 0.22; g.fillStyle = p === 'Shock' ? css('--reiq-neg') : css('--reiq-pos'); g.fillRect(x - w / 2, a.top, w, a.bottom - a.top); g.restore(); }); } };
    const cutText = R.noFc ? '' : 'Forecast made ' + lab(X.weeks[X.cut - 1]).slice(0, 6);
    const c1 = { type: 'line', data: { labels, datasets: [
      { label: 'Forecast', data: nd.f, borderColor: css('--reiq-chart-2'), borderWidth: 2, borderDash: [6, 4], pointRadius: 0, spanGaps: false },
      { label: 'Actual', data: nd.a, borderColor: css('--reiq-chart-1'), backgroundColor: css('--reiq-chart-1'), borderWidth: 2.5, pointRadius: 3, pointHoverRadius: 5 }] },
      plugins: [phaseBands, dividerPlugin('cutLine', X.cut, cutText)],
      options: { ...base, scales: { x: xScale(), y: yScale('Units per week', (v) => fK(v), { afterFit(s) { s.width = 72; } }) },
        plugins: { legend: { display: false }, tooltip: { ...tooltipBase(), filter: (i) => i.raw != null, callbacks: {
          title: (i) => 'Week beginning ' + labFull(X.weeks[i[0].dataIndex]), label: (i) => ' ' + i.dataset.label + ': ' + fN(i.raw),
          afterBody: (i) => { const v = R.dev[i[0].dataIndex]; return v == null ? '' : 'vs forecast: ' + fS(v) + (R.ph[i[0].dataIndex] && R.ph[i[0].dataIndex] !== 'Normal' ? ' (' + R.ph[i[0].dataIndex].toLowerCase() + ')' : ''); } } } } } };
    const c2 = { type: 'bar', data: { labels, datasets: [
      { type: 'bar', label: 'Actual rain', data: X.rain, backgroundColor: css('--reiq-chart-1'), order: 2 },
      { type: 'line', label: 'Expected rain', data: X.exp, borderColor: css('--reiq-chart-3'), borderWidth: 2, borderDash: [6, 4], pointRadius: 0, order: 1 }] },
      options: { ...base, scales: { x: xScale({ ticks: { display: false } }), y: yScale('Rain, mm per week', undefined, { afterFit(s) { s.width = 72; } }) },
        plugins: { legend: { display: false }, tooltip: { ...tooltipBase(), callbacks: { title: (i) => 'Week beginning ' + labFull(X.weeks[i[0].dataIndex]), label: (i) => (i.raw == null ? '' : ' ' + i.dataset.label + ': ' + i.raw.toFixed(0) + ' mm') } } } } };
    return { c1, c2 };
  }, [R, X, nd, theme]);

  const head = { crumb: 'Weather & shocks', title: 'Weather & shocks',
    sub: 'How a weather surprise moved demand away from the forecast made just before it, and how demand recovered afterwards.',
    tags: <><span className="tag">Pre-shock forecast vs actual</span><span className="tag out">National only</span></> };
  const extra = (
    <Select id="wsn" label="Season" value={yr} onChange={setYr} options={['2024', '2025', '2026'].map((y) => ({ v: y, label: 'Monsoon ' + y }))} />
  );
  if (level !== 'National') return <Page {...head} showMeasure={false} extra={extra}><Empty title="Shock analysis is built for National only" text="Switch Level to National to see how weather moved demand against the forecast." /></Page>;
  if (!WX || !nd) return <Page {...head} showMeasure={false} extra={extra}><Empty title="Loading weather runs" text="Fetching from the API…" /></Page>;

  const wLab = (i) => lab(X.weeks[i]);
  const label = D.levels.National.nodes[nodeKey].label;
  const delay = (R.ex >= 0 && R.ac >= 0) ? R.ac - R.ex : null; const cutDay = lab(X.weeks[X.cut - 1]).slice(0, 6);
  const tiles = [
    { l: 'Monsoon arrival', v: delay == null ? (R.ac >= 0 ? 'Week of ' + wLab(R.ac) : '—') : (delay > 0 ? plural(delay, 'week') + ' late' : (delay < 0 ? plural(-delay, 'week') + ' early' : 'On time')), cls: delay > 0 ? 'neg' : '',
      d: R.ex >= 0 && R.ac >= 0 ? <>expected <span className="chip">{wLab(R.ex)}</span> arrived <span className="chip">{wLab(R.ac)}</span></> : 'no planning outlook for this year', i: 'Rain counts as arrived in the first week at or above 40 mm. Expected rain is the planning-time outlook, actual is measured rainfall.' },
    { l: 'Worst week vs forecast', v: R.worst < 0 ? '—' : fS(R.dev[R.worst]), cls: R.worst >= 0 && R.dev[R.worst] < 0 ? 'neg' : '', d: R.worst >= 0 ? <>week of <span className="chip">{wLab(R.worst)}</span></> : '', i: 'Actual sales against the forecast made on 26 May, before the shock, for the same week.' },
    { l: 'Weeks in shock', v: String(R.nShock), d: R.nShock ? 'more than 25% below forecast' : 'none below the 25% line', i: 'Weeks where actual sales ran more than 25% below the pre-shock forecast.' },
    { l: 'Recovery spillover', v: R.peak < 0 ? '—' : fS(R.dev[R.peak]), cls: R.peak >= 0 ? 'pos' : '', d: R.peak >= 0 ? <>peak <span className="chip">{wLab(R.peak)}</span> · {R.nRec} weeks above</> : 'no rebound above forecast', i: 'After a shock, deferred purchases come back. Recovery weeks are weeks more than 10% above forecast after the shock. The peak is the highest of them.' },
    { l: 'Net over 16 weeks', v: fS(R.net), cls: R.net >= 0 ? 'pos' : 'neg', d: <>lost <span className="chip">{fK(R.lost)}</span> regained <span className="chip">{fK(R.regained)}</span></>, i: 'Total actual against total forecast across the 16 weeks after 26 May. Lost is the shortfall in shock weeks, regained is the excess in recovery weeks.' },
  ];
  if (R.noFc) for (let k = 1; k < 5; k++) { tiles[k] = { ...tiles[k], v: '—', cls: '', d: 'no forecast for this season' }; }

  const note = R.noFc
    ? <>No forecast was built for monsoon {yr}: there was not enough earlier history. Showing actual sales and rainfall only. {delay == null && R.ac >= 0 ? 'Rain reached 40 mm in the week of ' + wLab(R.ac) + '.' : ''}</>
    : <>
        {delay != null && delay > 0 && <>Monsoon rains arrived <strong>{plural(delay, 'week')} late</strong> (week of {wLab(R.ac)} against {wLab(R.ex)} expected). </>}
        {R.worst >= 0 && R.dev[R.worst] < 0
          ? <>{label} sold <strong>{Math.abs(R.dev[R.worst] * 100).toFixed(0)}% below</strong> the forecast in the worst week ({wLab(R.worst)}) and ran more than 25% below for {plural(R.nShock, 'week')}. </>
          : <>{label} stayed close to the forecast. </>}
        {R.peak >= 0 && <>Demand then rebounded, up to <strong>{(R.dev[R.peak] * 100).toFixed(0)}% above</strong> forecast in the week of {wLab(R.peak)}, as purchases put off during the dry spell came back. </>}
        Over the 16 weeks after the forecast, sales were {Math.abs(R.net * 100).toFixed(0)}% {R.net < 0 ? 'below' : 'above'} forecast in total.
      </>;
  const c = (v) => (v == null ? '–' : fN(v));
  const dot = (col) => <span style={{ width: 14, height: 10, background: col, opacity: 0.4, display: 'inline-block' }} />;
  const item = (col, sw, text) => <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: col }}>{sw}<span style={{ color: 'var(--reiq-text-secondary)' }}>{text}</span></span>;

  return (
    <Page {...head} showMeasure={false} extra={extra}>
      <Kpis tiles={tiles} label="Shock summary" />
      <section className="card" aria-labelledby="wct">
        <div className="card-head"><h2 id="wct">{R.noFc ? 'Demand and rainfall, ' : 'Demand against the pre-shock forecast, '}{label}, monsoon {yr}</h2>
          <SegBare ariaLabel="View" value={view} onChange={setView} options={[{ v: 'chart', label: 'Chart' }, { v: 'table', label: 'Table' }]} /></div>
        <p className="note">{note}</p>
        {yr === '2026' && <p className="note" style={{ color: 'var(--reiq-chart-3)' }}>Read with care: the 2026 forecast learned from history that includes the unusual 2025 monsoon dip and rebound, so single torch products can differ from a normal monsoon. Rain was only about a week late.</p>}
        {view === 'chart' ? (
          <div>
            <div className="legendrow">
              {item('var(--reiq-chart-1)', <span className="sw" />, 'Actual')}
              {item('var(--reiq-chart-2)', <span className="sw dash" />, R.noFc ? 'No forecast for this season' : 'Forecast made ' + cutDay)}
              {item(undefined, dot('var(--reiq-neg)'), 'Shock (more than 25% below)')}
              {item(undefined, dot('var(--reiq-pos)'), 'Recovery (more than 10% above)')}
            </div>
            <ChartCanvas config={charts.c1} height={340} label="Weekly demand, with the forecast made before the monsoon where one exists" />
            <ChartCanvas config={charts.c2} height={170} style={{ marginTop: 2 }} label="Weekly rainfall, actual against expected" />
          </div>
        ) : (
          <div className="tablewrap"><table className="ctab">
            <thead><tr><th>Week beginning</th><th>Actual</th><th>Forecast</th><th>vs forecast</th><th>Rain, mm</th><th>Expected rain, mm</th><th>Phase</th></tr></thead>
            <tbody>{X.weeks.map((w, i) => { const v = R.dev[i]; return (
              <tr key={w}><td>{labFull(w)}</td><td>{c(nd.a[i])}</td><td>{c(nd.f[i])}</td>
                <td className={R.ph[i] === 'Shock' ? 'bad' : (R.ph[i] === 'Recovery' ? 'good' : '')}>{v == null ? '–' : fS(v)}</td>
                <td>{X.rain[i].toFixed(0)}</td><td>{X.exp[i] == null ? '–' : X.exp[i].toFixed(0)}</td><td style={{ fontFamily: 'var(--font-sans)' }}>{R.ph[i] || '–'}</td></tr>); })}</tbody>
          </table></div>
        )}
        <details className="wdetails more"><summary>Notes and limits</summary><p className="foot">The forecast is the model run made on {lab(X.weeks[X.cut - 1])} from data up to that week, so it does not know about the late rain. Sub-seasonal shocks show up as the gap between this forecast and actual sales. Single products are noisier than categories. All data is synthetic.</p></details>
      </section>
    </Page>
  );
}
