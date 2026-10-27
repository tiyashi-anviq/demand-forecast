import { useMemo } from 'react';
import { useApp } from '../context.js';
import { useApi } from '../lib/api.js';
import Page from '../components/Page.jsx';
import Kpis from '../components/Kpis.jsx';
import ChartCanvas from '../components/ChartCanvas.jsx';
import { Select, SegBare } from '../components/Controls.jsx';
import { css, tooltipBase, baseOptions, xScale, yScale } from '../lib/chart.js';
import { dt, labFull, fK, fN, fP } from '../lib/format.js';

const FMT = ['Refill 35', 'Refill 45', 'Combo'];
const DEFAULT = { ltype: 'new', parent: 'Mozzex', sel: { 'Refill 35': true, 'Refill 45': true, Combo: true }, prices: {}, launch: '2026-11-02', wd: '30', priceOn: false };
const num = (x) => (x === '' || x == null || isNaN(parseFloat(x)) ? null : parseFloat(x));
const isoWeek = (d) => {
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())); const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day); const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return Math.min(52, Math.ceil(((t - y0) / 864e5 + 1) / 7));
};
const addDays = (d, n) => new Date(d.getTime() + n * 864e5);
const iso = (d) => d.toISOString().slice(0, 10);
const td = { textAlign: 'left', fontFamily: 'var(--font-sans)' };
const rs = (v) => '₹' + (v >= 1e7 ? (v / 1e7).toFixed(2) + ' Cr' : v >= 1e5 ? (v / 1e5).toFixed(1) + ' L' : fN(v));

/** Worked launch case: a liquid mosquito vaporizer, learned from the five launches already in the market data. */
export default function LaunchCase({ tabs }) {
  const { theme, useSS } = useApp();
  const { data: D } = useApi('/api/new-products/launch-case');
  const [raw, setRaw] = useSS('np.case', DEFAULT);
  const [bt, setBt] = useSS('np.bt', '');
  const set = (k) => (v) => setRaw((p) => ({ ...p, [k]: v }));
  const head = { crumb: 'New products', title: 'New products', tabs,
    sub: 'A worked launch for a liquid mosquito vaporizer. The model learns how the five launches already in the market data ramped up, is tested by forecasting each one without it, and then plans a new launch.',
    tags: <><span className="tag">Learned from 5 past launches</span><span className="tag out">Illustrative case, synthetic market data</span></> };
  const L = D ? D.launches : [], B = D ? D.backtest : null;
  const lo = B ? 1 / B.ratio_hi : 1, hi = B ? 1 / B.ratio_lo : 1;       // range implied by the back-test: actual / forecast across the five launches
  const btName = L.some((l) => l.name === bt) ? bt : (L[0] ? L[0].name : '');
  const bl = L.find((l) => l.name === btName) || null;
  const parents = D ? Object.keys(D.parents).sort() : [];

  // ---- scenario
  const S = useMemo(() => {
    if (!D) return null;
    const start = dt(raw.launch || '2026-11-02'); const wd = num(raw.wd);
    const skus = FMT.filter((f) => raw.sel[f]).map((f) => {
      const par = D.parents[raw.parent] && D.parents[raw.parent][f];
      const ros = raw.ltype === 'new' ? D.new_ros[f] : par ? par.ros * D.ext_ratio : null;
      const pref = raw.ltype === 'new' ? D.new_price[f] : par ? par.price : null;
      return { f, ros, pref, price: num(raw.prices[f]) || pref };
    }).filter((s) => s.ros != null);
    if (!skus.length || !wd || wd <= 0) return null;
    const rows = []; let value = 0;
    for (let a = 0; a < 52; a++) {
      const d = addDays(start, 7 * a), w = isoWeek(d) - 1; let u = 0;
      skus.forEach((s) => { const x = wd * s.ros * (raw.priceOn ? Math.pow(s.price / s.pref, D.elasticity.b) : 1) * D.season[w] * D.ramp[a]; u += x; value += x * s.price; });
      const cat = D.cat_units * D.season[w];
      rows.push({ a, date: iso(d), u, lo: u * lo, hi: u * hi, share: u / (cat + u) });
    }
    return { rows, skus, value, u52: rows.reduce((s, r) => s + r.u, 0), u13: rows.slice(0, 13).reduce((s, r) => s + r.u, 0), peak: Math.max(...rows.map((r) => r.share)),
      wk90: D.ramp.findIndex((x) => x >= 0.9) + 1 };
  }, [raw, D]);

  const cRamp = useMemo(() => {
    if (!D) return null;
    const base = baseOptions();
    return { type: 'line', data: { labels: D.ramp.map((_, i) => 'Wk ' + (i + 1)), datasets: [
      { label: 'Low', data: D.ramp_lo.map((v) => v * 100), borderColor: css('--reiq-chart-4'), borderWidth: 1, borderDash: [4, 4], pointRadius: 0, fill: false },
      { label: 'High', data: D.ramp_hi.map((v) => v * 100), borderColor: css('--reiq-chart-4'), borderWidth: 1, borderDash: [4, 4], pointRadius: 0, backgroundColor: css('--reiq-band'), fill: '-1' },
      { label: 'Typical launch', data: D.ramp.map((v) => v * 100), borderColor: css('--reiq-chart-1'), borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 4 }] },
      options: { ...base, scales: { x: xScale(), y: yScale('% of steady-state sales', (v) => v + '%', { min: 0, afterFit(s) { s.width = 64; } }) },
        plugins: { legend: { display: false }, tooltip: { ...tooltipBase(), callbacks: { label: (i) => ' ' + i.dataset.label + ': ' + Math.round(i.raw) + '%' } } } } };
  }, [D, theme]);

  const cBt = useMemo(() => {
    if (!bl) return null;
    const base = baseOptions();
    return { type: 'line', data: { labels: bl.actual.map((_, i) => 'Wk ' + (i + 1)), datasets: [
      { label: 'Actual', data: bl.actual, borderColor: css('--reiq-chart-2'), borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 4 },
      { label: 'Forecast without this launch', data: bl.pred, borderColor: css('--reiq-chart-1'), borderWidth: 2, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 4 }] },
      options: { ...base, scales: { x: xScale(), y: yScale('Units per week', (v) => fK(v), { min: 0, afterFit(s) { s.width = 72; } }) },
        plugins: { legend: { display: false }, tooltip: { ...tooltipBase(), callbacks: { label: (i) => ' ' + i.dataset.label + ': ' + fN(i.raw) } } } } };
  }, [bl, theme]);

  const cFc = useMemo(() => {
    if (!S) return null; const base = baseOptions();
    return { type: 'line', data: { labels: S.rows.map((r) => 'Wk ' + (r.a + 1)), datasets: [
      { label: 'Low', data: S.rows.map((r) => r.lo), borderColor: css('--reiq-chart-4'), borderWidth: 1, borderDash: [4, 4], pointRadius: 0, fill: false },
      { label: 'High', data: S.rows.map((r) => r.hi), borderColor: css('--reiq-chart-4'), borderWidth: 1, borderDash: [4, 4], pointRadius: 0, backgroundColor: css('--reiq-band'), fill: '-1' },
      { label: 'Expected', data: S.rows.map((r) => r.u), borderColor: css('--reiq-chart-1'), borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 4 }] },
      options: { ...base, scales: { x: xScale(), y: yScale('Units per week', (v) => fK(v), { min: 0, afterFit(s) { s.width = 72; } }) },
        plugins: { legend: { display: false }, tooltip: { ...tooltipBase(), callbacks: {
          title: (i) => 'Week ' + (i[0].dataIndex + 1) + ', beginning ' + labFull(S.rows[i[0].dataIndex].date), label: (i) => ' ' + i.dataset.label + ': ' + fN(i.raw) } } } } };
  }, [S, theme]);

  if (!D) return <Page {...head} showFilters={false} showMeasure={false}><div className="empty"><b>Loading the launch case</b><span>Fetching from the API…</span></div></Page>;
  const tiles = [
    { l: 'Launches tested', v: String(L.length), d: <>each forecast without itself</>, i: 'Every past launch in the market data is forecast using only the other four. For each, the real distribution it reached is used as the plan, so this tests how sales respond to distribution, not whether distribution can be won.' },
    { l: 'Typical miss, 52-week units', v: fP(B.mean_abs_err52), d: <>range <span className="chip">{B.ratio_lo.toFixed(2)}× to {B.ratio_hi.toFixed(2)}×</span> of actual</>, i: 'The average gap between forecast and actual total units over the first 52 weeks. The range is the lowest and highest forecast-to-actual ratio across the five launches, and it sets the low and high band on a new launch.' },
    { l: 'Typical miss, weekly', v: fP(B.wmape), d: <>a plain average of past launches: <span className="chip">{fP(B.naive_wmape)}</span></>, i: 'Weekly error summed over the first year against actual units. The plain average compares with the average launched pack of the same size scaled to its distribution, without knowing the brand or the season.' },
    { l: 'Sales reach 90% of steady', v: 'Week ' + (D.ramp.findIndex((x) => x >= 0.9) + 1), d: <>about a third by week 8, about a tenth in week 1</>, i: 'From the five launches: sales build with distribution and awareness for about five months before they settle. Seasonality then moves them up and down.' },
  ];

  return (
    <Page {...head} showFilters={false} showMeasure={false}>
      <Kpis tiles={tiles} label="Launch case summary" />
      <p className="callout"><b>Illustrative case.</b> The market data here is synthetic and no Eveready product exists in this category in it, so the launch below is a what-if. The method is what is on show: it runs end to end on this file and takes a standard Nielsen-style extract with the same columns, so it can be run on Eveready's own file.</p>

      <section className="card" aria-labelledby="lcr">
        <div className="card-head"><h2 id="lcr">How past launches behaved</h2></div>
        <p className="note">Sales as a share of each launch's steady level, by week since listing, for the five launches. The line is the typical launch and the band is the spread between launches. Seasonality is taken out.</p>
        <ChartCanvas config={cRamp} height={300} label="Typical launch curve: sales as a share of steady state by week since listing, with spread" />
        <h3 style={{ marginTop: 24 }}>The market it enters</h3>
        <p className="note">Liquid vaporizers, national, last 52 weeks. Rate of sale is units a week for each point of weighted distribution, the number that separates a leader from a niche brand. {D.category}.</p>
        <div className="tablewrap"><table className="ctab">
          <thead><tr><th>Brand</th><th>Type</th><th>Refill 45 ml price (₹)</th><th>Protection (hours)</th><th>Distribution</th><th>Share of units</th><th>Rate of sale</th></tr></thead>
          <tbody>{[...D.positioning].sort((a, b) => b.share - a.share).map((p) => <tr key={p.brand}><td style={td}>{p.brand}</td><td style={td}>{p.btype}</td><td>{p.price.toFixed(0)}</td><td>{p.prot}</td><td>{p.wd.toFixed(0)}%</td><td>{fP(p.share)}</td><td>{fN(p.ros)}</td></tr>)}</tbody>
        </table></div>
      </section>

      <section className="card" aria-labelledby="lcb">
        <div className="card-head"><h2 id="lcb">Back-test: forecast each past launch without it</h2>
          <SegBare ariaLabel="Launch" value={btName} onChange={setBt} options={L.map((l) => ({ v: l.name, label: l.name }))} /></div>
        <details className="wdetails more"><summary>About this view</summary><p className="note"><strong>{bl.name}</strong> ({bl.ltype.toLowerCase()}, listed {labFull(bl.start)}, {bl.skus.join(' + ')}), planned at {bl.wd}% distribution. Forecast made from the other four launches, then compared with what happened: <b>{fN(bl.p52)}</b> forecast against <b>{fN(bl.u52)}</b> actual units over 52 weeks ({bl.r52.toFixed(2)}×), weekly error {fP(bl.wmape)} against {fP(bl.naive_wmape)} for a plain average.</p></details>
        <div className="legendrow"><span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span className="sw" style={{ color: 'var(--reiq-chart-2)' }} />Actual</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span className="sw" style={{ color: 'var(--reiq-chart-1)' }} />Forecast without this launch</span></div>
        <ChartCanvas config={cBt} height={320} label="Actual against back-tested forecast, units per week, first 52 weeks" />
        <div className="tablewrap" style={{ marginTop: 16 }}><table className="ctab">
          <thead><tr><th>Launch</th><th>Type</th><th>Distribution</th><th>First 13 weeks, forecast vs actual</th><th>52 weeks, forecast</th><th>52 weeks, actual</th><th>Ratio</th><th>Weekly error</th><th>Plain average</th></tr></thead>
          <tbody>{L.map((l) => <tr key={l.name}><td style={td}>{l.name}</td><td style={td}>{l.ltype}</td><td>{l.wd}%</td><td>{(l.p13 / l.u13).toFixed(2)}×</td><td>{fN(l.p52)}</td><td>{fN(l.u52)}</td><td className={Math.abs(l.r52 - 1) > 0.2 ? 'bad' : ''}>{l.r52.toFixed(2)}×</td><td>{fP(l.wmape)}</td><td>{fP(l.naive_wmape)}</td></tr>)}</tbody>
        </table></div>
        <details className="wdetails more"><summary>Notes and limits</summary><p className="foot">Only five launches, so treat the ranges as indicative. A new brand's first year is harder to call than a line extension from an established brand: the two new brands are the least accurate rows. The back-test gives each launch the distribution it actually reached as its plan. Protection hours and pack design are not separate drivers: with five launches there is too little to separate them from brand strength.</p></details>
      </section>

      <section className="card" aria-labelledby="lcp">
        <div className="card-head"><h2 id="lcp">Plan a launch</h2></div>
        <p className="note">Choose who is launching and what, then the plan for distribution. The forecast applies the typical launch curve, the season, and the rate of sale of comparable products.</p>
        <div className="ctl" style={{ marginTop: 0 }}>
          <div className="field"><span className="lab" id="lc-t">Launch type</span>
            <SegBare labelledby="lc-t" value={raw.ltype} onChange={(v) => setRaw((p) => ({ ...p, ltype: v, sel: v === 'ext' ? { 'Refill 35': false, 'Refill 45': true, Combo: false } : { 'Refill 35': true, 'Refill 45': true, Combo: true } }))} options={[{ v: 'new', label: 'New brand in the category' }, { v: 'ext', label: 'Extension of a brand already there' }]} /></div>
          {raw.ltype === 'ext' && <Select id="lc-par" label="Parent brand" value={raw.parent} onChange={set('parent')} options={parents.map((b) => ({ v: b, label: b }))} />}
          <div className="field"><label htmlFor="lc-wd">Distribution plan, weighted % at plateau</label><input id="lc-wd" type="number" min="1" max="100" step="1" value={raw.wd} onChange={(e) => set('wd')(e.target.value)} /></div>
          <div className="field"><label htmlFor="lc-d">Planned launch week</label><input id="lc-d" type="date" value={raw.launch} onChange={(e) => set('launch')(e.target.value)} /></div>
        </div>
        <div className="ctl">
          {FMT.map((f) => { const ref = raw.ltype === 'new' ? D.new_price[f] : (D.parents[raw.parent] && D.parents[raw.parent][f] ? D.parents[raw.parent][f].price : null); return (
            <div className="field" key={f}>
              <label htmlFor={'lc-p-' + f}><input type="checkbox" checked={!!raw.sel[f]} onChange={(e) => setRaw((p) => ({ ...p, sel: { ...p.sel, [f]: e.target.checked } }))} /> {f === 'Combo' ? 'Machine + 45 ml combo' : f.replace('Refill', 'Refill') + ' ml'} price (₹)</label>
              <input id={'lc-p-' + f} type="number" min="1" step="1" disabled={!raw.sel[f]} placeholder={ref ? ref.toFixed(0) : ''} value={raw.prices[f] ?? ''} onChange={(e) => setRaw((p) => ({ ...p, prices: { ...p.prices, [f]: e.target.value } }))} />
              <span className="sub">{ref ? 'Market ' + ref.toFixed(0) : ''}</span>
            </div>); })}
          <div className="field"><label htmlFor="lc-po"><input id="lc-po" type="checkbox" checked={raw.priceOn} onChange={(e) => set('priceOn')(e.target.checked)} /> Apply an indicative price effect</label>
            <span className="sub">Off by default: not supported by the five launches</span></div>
        </div>
        {!S ? <div className="empty"><b>Pick at least one pack and a distribution plan</b><span>The forecast needs a pack, and a distribution above zero.</span></div> : (<>
          <Kpis label="Launch forecast summary" tiles={[
            { l: 'First 52 weeks, units', v: fK(S.u52), d: <>range <span className="chip">{fK(S.u52 * lo)} to {fK(S.u52 * hi)}</span></>, i: 'Expected units over the first 52 weeks from the planned launch week. The range applies the lowest and highest actual-to-forecast ratios from the back-test, so it is wide on purpose.' },
            { l: 'First 13 weeks, units', v: fK(S.u13), d: <>about {fP(S.u13 / S.u52)} of the year</>, i: 'The build-up: most of the first quarter is spent ramping, so a launch is judged against its curve, not a flat weekly number.' },
            { l: 'First 52 weeks, retail value', v: rs(S.value), d: <>{S.skus.map((s) => s.f.replace('Refill ', 'R')).join(' + ')}</>, i: 'Units times the shelf price entered for each pack, at retail.' },
            { l: 'Peak share of units', v: fP(S.peak), d: <>of the category, if the launch adds to it</>, i: 'The launch\'s units against category units for the same week (established products, seasonal), assuming the launch adds to the category. Real share also depends on who loses sales to it, which this does not model.' },
          ]} />
          <div className="legendrow"><span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span className="sw" style={{ color: 'var(--reiq-chart-1)' }} />Expected</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span className="sw band" />Range from the back-test</span></div>
          <ChartCanvas config={cFc} height={360} label="Forecast units per week for the first 52 weeks after launch, with range" />
          <details className="wdetails more"><summary>Notes and limits</summary><p className="foot">How it works. Units in a week = distribution plan × rate of sale × season × launch curve, for each pack, added together. Rate of sale: for a new brand, what the new entrants in the data achieved for that pack; for an extension, the parent brand's own rate of sale for that pack × {D.ext_ratio.toFixed(2)}, the average of the extensions in the data. Season: the category's weekly index from established products. Launch curve: the typical launch above.{raw.priceOn ? ' Price effect: rate of sale moves with (price ÷ market price) to the power ' + D.elasticity.b + ', an indicative value from price moves on established products; it ranges from −0.9 to −1.7 depending on how the yearly price drift is treated, and adding it made the back-test worse, so treat it as a rough guide.' : ' The shelf price is shown but not used: adding a price effect made the back-test worse.'} All data is synthetic.</p></details>
        </>)}
      </section>
    </Page>
  );
}
