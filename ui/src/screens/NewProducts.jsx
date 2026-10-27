import { useMemo } from 'react';
import { useApp } from '../context.js';
import { useApi } from '../lib/api.js';
import Page, { Empty } from '../components/Page.jsx';
import Kpis from '../components/Kpis.jsx';
import Info from '../components/Info.jsx';
import ChartCanvas from '../components/ChartCanvas.jsx';
import { Select, SegBare } from '../components/Controls.jsx';
import { css, tooltipBase, baseOptions, xScale, yScale } from '../lib/chart.js';
import { lab, labFull, fK, fN, MON } from '../lib/format.js';
import Tabs from '../components/Tabs.jsx';
import LaunchCase from './LaunchCase.jsx';
import { DRIVERS, DEFAULT_W, SEASONS, SEASON_LABEL, SHELF, LTYPES, COMP, rank, forecast, MIN_SAME } from '../lib/similarity.js';

const DEFAULT_IN = { cat: 'Emergency & rechargeable LED', tech: 'Advanced', pack: 'Single', price: '520', season: 'Summer', shelf: '260',
  ltype: LTYPES[0], launch: '2026-11-02', dist: '55', scheme: '1', comp: 'Auto' };
const W_OPTS = Array.from({ length: 41 }, (_, v) => ({ v, label: String(v) }));
const num = (x) => (x === '' || x == null || isNaN(parseFloat(x)) ? '' : parseFloat(x));
const opt = (list) => list.map((v) => ({ v, label: v }));


// (i) text for each launch input: what it is, how the similarity score uses it, how to read it
const INFO = {
  cat: { what: 'The product family the launch belongs to, for example alkaline batteries or liquid mosquito vaporizers.',
    how: 'Same category scores 100, same business segment scores 50, anything else 0. It also decides which competitors and launches appear under Market context.',
    read: 'The heaviest driver by default (weight 25). If we have no product in this category, the volume is borrowed from other categories and the page says so.' },
  tech: { what: 'Whether the product is a basic version or a more advanced one, for example smart, Wi-Fi or solar-charged.',
    how: 'Same level scores 100, different scores 0.',
    read: 'Competitor launches do not carry this field, so it is skipped when scoring them and the other drivers are rescaled.' },
  pack: { what: 'How the product is sold: a single unit, or a bundle such as a multi-pack or a machine with its refill.',
    how: 'Same format scores 100, different scores 0.',
    read: 'The second heaviest driver (weight 20). In past launches, packs of the same category differed most on this, for example a machine-and-refill combo sells about a tenth of a refill each week.' },
  price: { what: 'The selling price of one unit, in rupees.',
    how: 'Scored on how far apart the two prices are in ratio terms: the same price scores 100, and a price 4 times higher or lower scores 0.',
    read: 'The line under the box compares your price with the median competitor price in the category, so you can see if you are positioned premium or low.' },
  season: { what: 'The time of year the product sells most: Festive (Sep to Nov), Winter (Dec to Feb), Summer (Mar to May), Monsoon (Jun to Aug) or year-round.',
    how: 'Same peak scores 100. A neighbouring season, or year-round against seasonal, scores 40. Anything further apart scores 0. The weekly shape of the forecast also follows the closest matches’ seasonal pattern.',
    read: 'Pick the season your own sales plan expects, not the launch month. The launch month is scored separately under Planned launch week.' },
  shelf: { what: 'How long the product stays sellable on the shelf: about 2, 5 or 10 years.',
    how: 'Same band scores 100, the next band 50, the farthest 0.',
    read: 'A small weight (3). It matters for write-off risk more than for volume. Competitor launches do not carry it.' },
  ltype: { what: 'How the launch relates to the brand: a new product from an existing brand, a line extension, or a new brand.',
    how: 'Same type scores 100. A line extension scores 50 against the other types, and other mismatches 20. Established products, which were not launched in the data, score 30.',
    read: 'New brands usually start slower because they begin with less distribution and awareness.' },
  launch: { what: 'The first week the product is on sale. The forecast starts here and runs 52 weeks.',
    how: 'It fixes the calendar of the forecast, so the seasonal shape is applied to the right months. It is also scored against the season in which each launched product started (same season 100, neighbouring 50).',
    read: 'A launch just before the festive season behaves differently from one at the start of the monsoon, even for the same product.' },
  dist: { what: 'Weighted distribution: the share of category sales made through outlets that stock the product, weighting big outlets more than small ones. It is not a count of outlets.',
    how: 'Used twice. In scoring, products within 30 points of your value score higher. In the volume, each match’s weekly run-rate is scaled by your distribution divided by its own, limited to between 0.4 and 2.5 times.',
    read: 'It is the main lever on volume. The line under the box shows how far competitor launches in this category had reached by week 13.' },
  scheme: { what: 'The discount offered to distributors and retailers on this product, as a percentage of price.',
    how: 'Products within 2 points of your value score highest, falling to 0 at 2 points apart. Competitor launches do not carry it.',
    read: 'A small weight (2). A much deeper scheme than the matches have is a sign the launch is being pushed harder, which this page does not model.' },
  comp: { what: 'How crowded and promotional the category is: Low, Medium or High.',
    how: 'Auto takes the level from the competitor file for this category, based on the number of brands, the share of sales on promotion and recent launches. Choosing a level overrides it. Same level scores 100, neighbouring 50.',
    read: 'A small weight (5). High pressure means a new product has to win its share from established brands.' },
  k: { what: 'How many of our closest products set the weekly volume and the seasonal shape.',
    how: 'The forecast averages those products’ settled weekly sales, weighted by their similarity scores. The launch curve always uses all launched products, ours and the market’s, whatever you pick here.',
    read: '1 follows the single best match. 3 or 5 smooths out the quirks of one product, but pulls in less similar ones.' },
};
const L = (text, key) => <span className="lbi">{text}<Info text={INFO[key]} /></span>;

function Num({ id, label, value, onChange, step = 1, min = 0, hint }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="number" inputMode="decimal" min={min} step={step} value={value} onChange={(e) => onChange(e.target.value)} aria-describedby={hint ? id + '-h' : undefined} />
      {hint && <span className="hint" id={id + '-h'}>{hint}</span>}
    </div>
  );
}

function Explorer({ tabs }) {
  const { theme, useSS } = useApp();
  const { data } = useApi('/api/new-products');
  const [raw, setRaw] = useSS('np.in', DEFAULT_IN);
  const { data: FW } = useApi('/api/new-products/weights');
  const [wset, setWset] = useSS('np.wset', 'impact');        // impact | predict | manual | custom
  const [Wc, setWc] = useSS('np.w', DEFAULT_W);               // the weights as last edited by hand
  const [K, setK] = useSS('np.k', '3');
  const [view, setView] = useSS('np.view', 'chart');
  const [all, setAll] = useSS('np.all', 'top');
  const [src, setSrc] = useSS('np.src', 'all');
  const [curve, setCurve] = useSS('np.curve', 'both');
  const [mk, setMk] = useSS('np.mk', 'comp');
  const set = (k) => (v) => setRaw((p) => ({ ...p, [k]: v }));
  const MK = data?.market?.[raw.cat];
  const inp = useMemo(() => ({ ...raw, price: num(raw.price), dist: num(raw.dist), scheme: num(raw.scheme), shelf: raw.shelf ? Number(raw.shelf) : '', comp: raw.comp === 'Auto' ? (MK ? MK.level : '') : raw.comp }), [raw, MK]);
  const segName = data && raw.cat ? (data.products.find((p) => p.cat === raw.cat) || {}).seg : null;
  const W = useMemo(() => {
    if (wset === 'custom') return Wc;
    if (wset === 'manual' || !FW) return DEFAULT_W;
    if (wset === 'predict') return FW.predict.global;
    return (segName && FW.impact.segments[segName]) || FW.impact.global;
  }, [wset, Wc, FW, segName]);
  const setWt = (k) => (v) => { setWc({ ...W, [k]: parseFloat(v) }); setWset('custom'); };
  const ranked = useMemo(() => (data ? rank(data.products, inp, W) : []), [data, inp, W]);
  const F = useMemo(() => (data && ranked.length ? forecast(data, ranked, inp, Number(K), 52, curve === 'both') : null), [data, ranked, inp, K, curve]);

  const charts = useMemo(() => {
    if (!F) return null;
    const labels = F.rows.map((r) => lab(r.date)), base = baseOptions();
    return { type: 'line', data: { labels, datasets: [
      { label: 'Low', data: F.rows.map((r) => r.lo), borderColor: css('--reiq-chart-4'), borderWidth: 1, borderDash: [4, 4], pointRadius: 0, fill: false },
      { label: 'High', data: F.rows.map((r) => r.hi), borderColor: css('--reiq-chart-4'), borderWidth: 1, borderDash: [4, 4], pointRadius: 0, backgroundColor: css('--reiq-band'), fill: '-1' },
      { label: 'Expected', data: F.rows.map((r) => r.f), borderColor: css('--reiq-chart-1'), borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 4 }] },
      options: { ...base, scales: { x: xScale(), y: yScale('Units per week', (v) => fK(v), { min: 0, afterFit(s) { s.width = 72; } }) },
        plugins: { legend: { display: false }, tooltip: { ...tooltipBase(), callbacks: {
          title: (i) => 'Week ' + F.rows[i[0].dataIndex].week + ', beginning ' + labFull(F.rows[i[0].dataIndex].date), label: (i) => ' ' + i.dataset.label + ': ' + fN(i.raw) } } } } };
  }, [F, theme]);

  const head = { crumb: 'New products', title: 'New products', tabs,
    sub: 'Describe a product you plan to launch. The tool scores how alike it is to every product already in the range, then builds a launch forecast from the closest matches.',
    tags: <><span className="tag">Similarity index, 0 to 100</span><span className="tag out">Analogue-based launch forecast, National</span></> };
  if (!data) return <Page {...head} showFilters={false} showMeasure={false}><div className="empty"><b>Loading product profiles</b><span>Fetching from the API…</span></div></Page>;

  const prefill = (code) => {
    const p = data.products.find((x) => x.code === code); if (!p) return;
    setRaw((r) => ({ ...r, cat: p.cat, tech: p.tech, pack: p.pack, price: String(Math.round(p.asp)), season: p.peak, shelf: String(p.shelf), comp: 'Auto',
      dist: p.dist != null ? String(Math.round(p.dist)) : r.dist, scheme: String(p.scheme) }));
  };
  const top = F ? F.top : [], used = new Set(top.map((t) => t.p.code));
  const conf = top.length ? top.reduce((s, t) => s + t.index, 0) / top.length : 0, cover = top.length ? top.reduce((s, t) => s + t.coverage, 0) / top.length : 0;
  const confLabel = conf >= 70 ? 'High' : conf >= 50 ? 'Medium' : 'Low';
  const sumRows = (a, b, key) => (F ? F.rows.slice(a, b).reduce((s, r) => s + r[key], 0) : 0);
  const tiles = F ? [
    { l: 'Closest match', v: top[0].p.name.replace(/ \(NPD-\d+\)/, ''), d: <>index <span className="chip">{top[0].index.toFixed(0)}</span> of 100</>, i: 'The existing product that scores highest across the drivers below, on the weights you have set.' },
    { l: 'Match confidence', v: confLabel, cls: confLabel === 'Low' ? 'neg' : confLabel === 'High' ? 'pos' : '', d: <>top {top.length} average <span className="chip">{conf.toFixed(0)}</span>, {(cover * 100).toFixed(0)}% of weight scored</>, i: 'The average index of the analogues used. High is 70 or more, medium 50 to 70, low below 50. A low score means no existing product is close, so treat the forecast as a rough guide.' },
    { l: 'Mature weekly run-rate', v: fK(F.level), d: 'units a week after the ramp', i: 'Similarity-weighted weekly volume of the closest matches once they had settled, scaled by planned distribution against theirs.' },
    { l: 'First 13 weeks', v: fK(sumRows(0, 13, 'f')), d: <>range <span className="chip">{fK(sumRows(0, 13, 'lo'))}</span> to <span className="chip">{fK(sumRows(0, 13, 'hi'))}</span></>, i: 'Total forecast units in the first quarter after launch, with the range from the spread of the analogues.' },
    { l: 'First 26 weeks', v: fK(sumRows(0, 26, 'f')), d: <>range <span className="chip">{fK(sumRows(0, 26, 'lo'))}</span> to <span className="chip">{fK(sumRows(0, 26, 'hi'))}</span></>, i: 'Total forecast units in the first half-year.' },
  ] : [];

  const sameOnly = ranked.some((r) => r.same);   // enough products in the chosen category: show only those
  const pool = ranked.filter((r) => (!sameOnly || r.same) && (src === 'all' || (src === 'own' ? r.p.src === 'own' : r.p.src === 'market')));
  const shown = all === 'top' ? pool.slice(0, 10) : pool;
  const cw = {}; if (F) F.npd.forEach((n) => { cw[n.code] = n.w; });
  const nOwn = ranked.filter((r) => r.p.src === 'own').length;
  const poorOwn = top.length > 0 && top[0].index < 50 && !F?.volFromMarket;
  const cellCls = (v) => (v == null ? '' : v >= 0.8 ? 'good' : v <= 0.2 ? 'bad' : '');
  const months = []; if (F) F.rows.forEach((r) => { const m = r.date.slice(0, 7); let g = months[months.length - 1]; if (!g || g.m !== m) { g = { m, f: 0, lo: 0, hi: 0 }; months.push(g); } g.f += r.f; g.lo += r.lo; g.hi += r.hi; });
  const mLab = (m) => MON[Number(m.slice(5, 7)) - 1] + ' ' + m.slice(2, 4);
  const groups = [...new Set(DRIVERS.map((d) => d.group))];

  return (
    <Page {...head} showFilters={false} showMeasure={false}>
      <section className="card" aria-labelledby="npi">
        <div className="card-head"><h2 id="npi">Launch inputs</h2>
          <Select id="np-pre" label="Start from an existing product" value="" onChange={prefill}
            options={[{ v: '', label: 'Choose a product to copy its details…' }, ...data.products.filter((p) => p.src === 'own').map((p) => ({ v: p.code, label: p.name }))]} /></div>
        <p className="note">Fill in what you know; blank inputs are skipped.</p>
        <div className="ctl ctlgrid" style={{ marginTop: 0 }}>
          <Select id="np-cat" label={L('Category', 'cat')} value={raw.cat} onChange={set('cat')} options={[{ v: '', label: 'Not set' }, ...data.cats.map((c) => ({ v: c, label: c }))]} />
          <div className="field"><span className="lab" id="np-tech-l">{L('Technology level', 'tech')}</span><SegBare labelledby="np-tech-l" value={raw.tech} onChange={set('tech')} options={opt(['Standard', 'Advanced'])} /></div>
          <Num id="np-price" label={L('Selling price (₹)', 'price')} value={raw.price} onChange={set('price')} min={1} hint={MK && inp.price > 0 ? (inp.price / MK.price_med).toFixed(1) + 'x the median competitor price (₹' + Math.round(MK.price_med) + ')' : undefined} />
          <Select id="np-lt" label={L('Launch type', 'ltype')} value={raw.ltype} onChange={set('ltype')} options={[{ v: '', label: 'Not set' }, ...opt(LTYPES)]} />
          <div className="field"><label htmlFor="np-launch">{L('Planned launch week', 'launch')}</label><input id="np-launch" type="date" value={raw.launch} onChange={(e) => set('launch')(e.target.value)} /></div>
          <Num id="np-dist" label={L('Weighted distribution at launch (%)', 'dist')} value={raw.dist} onChange={set('dist')} min={1} hint={MK ? 'By week 13 competitor launches here reached ' + [MK.dist13['New brand'] != null && MK.dist13['New brand'] + '% (new brand)', MK.dist13['New product from existing brand'] != null && MK.dist13['New product from existing brand'] + '% (existing brand)'].filter(Boolean).join(', ') : 'Share of outlets stocking it, weighted by size'} />
        </div>
        <details className="wdetails">
          <summary>More inputs</summary>
          <div className="ctl ctlgrid">
          <div className="field"><span className="lab" id="np-pack-l">{L('Pack format', 'pack')}</span><SegBare labelledby="np-pack-l" value={raw.pack} onChange={set('pack')} options={opt(['Single', 'Bundle'])} /></div>
          <Select id="np-season" label={L('Seasonal pattern', 'season')} value={raw.season} onChange={set('season')}
            options={[{ v: '', label: 'Not set' }, ...[...SEASONS, 'Flat'].map((v) => ({ v, label: SEASON_LABEL[v] }))]} />
          <Select id="np-shelf" label={L('Shelf life', 'shelf')} value={raw.shelf} onChange={set('shelf')} options={[{ v: '', label: 'Not set' }, ...SHELF.map((s) => ({ v: String(s.v), label: s.label }))]} />
          <Num id="np-sch" label={L('Trade scheme discount (%)', 'scheme')} value={raw.scheme} onChange={set('scheme')} step={0.1} />
          <div className="field"><span className="lab" id="np-comp-l">{L('Competitive pressure', 'comp')}</span><SegBare labelledby="np-comp-l" value={raw.comp} onChange={set('comp')} options={opt(['Auto', ...COMP])} /><span className="hint">{raw.comp === 'Auto' ? (MK ? 'Auto: ' + MK.level + ', from competitor.csv' : 'Auto: pick a category') : 'Set by you'}</span></div>
          <div className="field"><span className="lab" id="np-k-l">{L('Closest matches to use', 'k')}</span><SegBare labelledby="np-k-l" value={K} onChange={setK} options={['1', '2', '3', '5'].map((v) => ({ v, label: v }))} /></div>
          </div>
        </details>
        <details className="wdetails">
          <summary>Driver weights</summary>
          <div className="ctl">
            {groups.map((g) => DRIVERS.filter((d) => d.group === g).map((d) => (
              <Select key={d.k} id={'np-w-' + d.k} label={d.label} value={W[d.k]} onChange={setWt(d.k)} options={W_OPTS} />)))}
            <button className="btn" onClick={() => setWset('impact')}>Reset to sales-impact weights</button>
          </div>
          {FW && <div className="field" style={{ marginTop: 12 }}><span className="lab" id="np-ws-l">Weight set</span>
            <SegBare labelledby="np-ws-l" value={wset} onChange={setWset} options={[{ v: 'impact', label: 'Sales impact' + (segName ? ', ' + segName : '') }, { v: 'predict', label: 'Fitted to match products' }, { v: 'manual', label: 'Hand-set' }]} /></div>}
          <p className="foot" style={{ marginTop: 8 }}>Weights are relative: they are rescaled to add up to 100 over the drivers that can be scored, and a weight of 0 ignores a driver.{wset === 'custom' ? ' You have changed them by hand.' : ''}{FW ? ' By default each weight is how much that driver moves the sales of products in this segment, measured on the sales history of our products and the market\'s.' : ''}</p>
          {FW && (<details className="wdetails" style={{ marginTop: 8 }}><summary>How the weights compare and how they were set</summary>
            <div className="tablewrap" style={{ marginTop: 8 }}><table className="ctab">
              <thead><tr><th>Driver</th><th>Hand-set</th><th>Fitted to match products</th><th>Sales impact, overall</th>{segName && FW.impact.segments[segName] && <th>Sales impact, {segName}</th>}<th>Share of sales variation, overall (± resampling)</th></tr></thead>
              <tbody>{DRIVERS.map((d) => <tr key={d.k}><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{d.label}</td><td>{FW.manual[d.k]}</td><td>{FW.predict.global[d.k]}</td><td>{FW.impact.global[d.k]}</td>{segName && FW.impact.segments[segName] && <td><b>{FW.impact.segments[segName][d.k]}</b></td>}<td>{FW.impact.share_global[d.k].toFixed(1)}% ± {FW.impact.spread[d.k].toFixed(1)}</td></tr>)}</tbody>
            </table></div>
            <div className="tablewrap" style={{ marginTop: 8 }}><table className="ctab">
              <thead><tr><th>How well the closest matches predict our existing products</th><th>Volume error</th><th>Seasonal shape error</th><th>Launch curve error</th></tr></thead>
              <tbody>{[['manual', 'Hand-set weights'], ['equal', 'Equal weights'], ['predict_cv', 'Fitted to match products (cross-validated)'], ['impact_overall', 'Sales impact, overall'], ['impact_segment', 'Sales impact, by segment']].map(([k, l]) => <tr key={k}><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{l}</td><td>{FW.match[k].level.toFixed(2)}</td><td>{FW.match[k].season.toFixed(3)}</td><td>{FW.match[k].ramp.toFixed(3)}</td></tr>)}</tbody>
            </table></div>
            <p className="foot" style={{ marginTop: 8 }}>How the sales-impact weights were set. For each segment, a model predicts the weekly sales of products from these same drivers, on our own products and on the market's products in competitor.csv. Each driver's importance is how much worse the model predicts products it has not seen when that driver is scrambled, so it measures how much the driver explains of the sales of the segment's products over time, and how it would help with a new product. Importances are averaged over our products and the market's, turned into weights that add to 100, and no driver goes below {FW.impact.floor}. A segment with few products leans on the overall importances. The model predicts the market's products well (R² 0.7 to 0.9) and our own much less well in Batteries and Lighting (R² 0.1 and 0.04), so the segment weights there rest mainly on the market's products.</p>
            <p className="foot">How to read it. Price, technology level and distribution move a product's sales the most. Seasonality gets a small share because a product's sales swing about a third through the year, while two products in the same segment differ by a factor of five or more; the seasonal pattern still shapes the forecast week by week. These are associations in the sales history, not tested effects, and in the synthetic data price and promotion move together, so treat the exact split with care. The resampling spread shows which weights are firm: technology level and price move by several points, while the small ones are stable. At picking analogues, sales-impact weights do about as well as the hand-set ones for volume and launch curve and slightly worse for seasonal shape; weights fitted to match do slightly better, but that is not what you asked them to measure. Refit with <code>driver_importance.py</code> and <code>combine_weights.py</code> when products or history are added.</p>
          </details>)}
        </details>
      </section>

      {!F ? <Empty title="Add a planned launch week" text="The forecast needs a launch date, and at least one driver with a non-zero weight." /> : (<>
        <Kpis tiles={tiles} label="Launch summary" />
        {F?.volFromMarket && <p className="callout"><b>Volume from the market.</b> We sell nothing in this category, so the weekly volume and seasonal shape come from the closest competitor launches in it. Their numbers are retail sell-out for other companies, not our sales to distributors. Treat the volume as a market benchmark, and set our share against it.</p>}
        {poorOwn && <p className="callout"><b>No close product of ours.</b> The best match scores {top[0].index.toFixed(0)}, so the volume borrows from products in other categories. Use the launch curve and the market benchmarks below, and treat the volume as a rough guide.</p>}
        {MK && (
          <section className="card" aria-labelledby="npk">
            <div className="card-head"><h2 id="npk">Market context, {raw.cat}</h2>
              <SegBare ariaLabel="Market view" value={mk} onChange={setMk} options={[{ v: 'comp', label: 'Competitors' }, { v: 'launch', label: 'Recent launches (' + MK.launches.length + ')' }]} /></div>
            <details className="wdetails more"><summary>About this view</summary><p className="note">Competitive pressure here is <strong>{MK.level.toLowerCase()}</strong>: {MK.brands} brands, {MK.promo}% of sales on promotion over the last year, {MK.launches52} {MK.launches52 === 1 ? 'launch' : 'launches'} in the last 52 weeks. The median competitor price is ₹{Math.round(MK.price_med)}{inp.price > 0 ? <>, so your price is <strong>{(inp.price / MK.price_med).toFixed(1)}x</strong> the market</> : ''}.{!MK.own && ' We sell nothing in this category today.'}</p></details>
            <div className="tablewrap" style={{ maxHeight: 360 }}>{mk === 'comp' ? (
              <table className="ctab"><thead><tr><th>Brand</th><th>Type</th><th>Products</th><th>Price (₹)</th><th>Value share</th><th>Distribution</th><th>On promotion</th><th>Units a week</th></tr></thead>
                <tbody>{MK.top.map((b) => <tr key={b.brand}><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{b.brand}</td><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{b.type}</td><td>{b.products}</td><td>{b.price.toFixed(0)}</td><td>{(b.share * 100).toFixed(1)}%</td><td>{b.dist.toFixed(0)}%</td><td>{b.promo.toFixed(1)}%</td><td>{fN(b.units)}</td></tr>)}</tbody></table>
            ) : MK.launches.length ? (
              <table className="ctab"><thead><tr><th>Listed</th><th>Product</th><th>Type</th><th>Price (₹)</th><th>Distribution at wk 13</th><th>Units a week, first 13</th><th>First 26</th><th>Last 13 weeks</th></tr></thead>
                <tbody>{MK.launches.map((l) => <tr key={l.code}><td style={{ textAlign: 'left' }}>{l.launch}</td><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{l.name}</td><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{l.type}</td><td>{l.price.toFixed(0)}</td><td>{l.d13.toFixed(0)}%</td><td>{fN(l.u13)}</td><td>{fN(l.u26)}</td><td>{fN(l.unow)}</td></tr>)}</tbody></table>
            ) : <div className="empty"><b>No launches with 26 weeks of history</b><span>Nothing in this category has been listed long enough to use as a launch curve.</span></div>}</div>
            <p className="foot">Source: competitor.csv, national retail sell-out. Shares are of competitor sales only.</p>
          </section>)}
        <section className="card" aria-labelledby="npm">
          <div className="card-head"><h2 id="npm">Closest existing products</h2>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <SegBare ariaLabel="Products shown" value={src} onChange={setSrc} options={[{ v: 'all', label: 'All' }, { v: 'own', label: 'Our products' }, { v: 'market', label: 'Market launches' }]} />
              <SegBare ariaLabel="Rows" value={all} onChange={setAll} options={[{ v: 'top', label: 'Top 10' }, { v: 'all', label: 'All ' + pool.length }]} /></div></div>
          <details className="wdetails more"><summary>About this view</summary><p className="note">{sameOnly ? <>Only products in the {inp.cat} category are listed. </> : inp.cat ? <>Fewer than {MIN_SAME} products exist in the {inp.cat} category, so the list falls back to the closest products from any category. </> : null}The first {top.length} {top.length === 1 ? 'product sets' : 'products set'} the volume and seasonal pattern. The launch curve comes from launched products, ours and competitors', weighted by how similar each is: a market launch is a competitor product from competitor.csv, so it can set the shape of the ramp but never our volume. Green cells are a close match on that driver, red are a poor match, a dash means it could not be scored.</p></details>
          <div className="tablewrap" style={{ maxHeight: 520 }}><table className="ctab">
            <thead><tr><th>#</th><th>Product</th><th>Index</th><th>Scored</th>{DRIVERS.filter((d) => W[d.k] > 0).map((d) => <th key={d.k} title={d.label}>{d.short}</th>)}<th>Used for</th></tr></thead>
            <tbody>{shown.map((r, i) => (
              <tr key={r.p.code}>
                <td>{i + 1}</td><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{r.p.name}{r.p.src === 'market' && <span className="sub"> · {r.p.brand}, listed {r.p.launch}</span>}</td>
                <td><b>{r.index.toFixed(0)}</b><span className="sbar" aria-hidden="true"><i style={{ width: r.index + '%' }} /></span></td>
                <td className={r.coverage < 0.75 ? 'bad' : ''}>{(r.coverage * 100).toFixed(0)}%</td>
                {DRIVERS.filter((d) => W[d.k] > 0).map((d) => <td key={d.k} className={cellCls(r.sc[d.k])}>{r.sc[d.k] == null ? '–' : Math.round(r.sc[d.k] * 100)}</td>)}
                <td className="fl">{used.has(r.p.code) && <span className="flag">Volume and season</span>}{cw[r.p.code] >= 0.03 && <span className="flag stk">Launch curve {(cw[r.p.code] * 100).toFixed(0)}%</span>}</td>
              </tr>))}</tbody>
          </table></div>
        </section>
        <section className="card" aria-labelledby="npf">
          <div className="card-head"><h2 id="npf">Launch forecast, first 52 weeks</h2>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}><SegBare ariaLabel="Launch curve sources" value={curve} onChange={setCurve} options={[{ v: 'both', label: 'Our and market launches' }, { v: 'own', label: 'Our launches only' }]} />
            <SegBare ariaLabel="View" value={view} onChange={setView} options={[{ v: 'chart', label: 'Chart' }, { v: 'table', label: 'Table' }]} /></div></div>
          <p className="note">Expected weekly units from {labFull(F.rows[0].date)}, built on {top.map((t) => t.p.name.replace(/ \(NPD-\d+\)/, '')).join(', ')}. Launch curve: {F.npd.slice(0, 4).map((n) => n.name.replace(/ \(NPD-\d+\)/, '') + ' ' + (n.w * 100).toFixed(0) + '%').join(', ')}{F.npd.length > 4 ? ' and ' + (F.npd.length - 4) + ' others' : ''}.</p>
          {view === 'chart' ? (<div>
            <div className="legendrow"><span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span className="sw" style={{ color: 'var(--reiq-chart-1)' }} />Expected</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span className="sw band" />Range, one spread either side</span></div>
            <ChartCanvas config={charts} height={380} label="Forecast units per week for the first 52 weeks after launch, with range" />
          </div>) : (
            <div className="tablewrap"><table className="ctab"><thead><tr><th>Month</th><th>Low</th><th>Expected</th><th>High</th></tr></thead>
              <tbody>{months.map((g) => <tr key={g.m}><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{mLab(g.m)}{g === months[0] || g === months[months.length - 1] ? ' (part)' : ''}</td><td>{fN(g.lo)}</td><td>{fN(g.f)}</td><td>{fN(g.hi)}</td></tr>)}</tbody></table></div>
          )}
          <details className="wdetails"><summary>How the forecast is built and its limits</summary><p className="foot">How it works. Each product is scored 0 to 100 against your inputs on the drivers above, weighted as set. Volume: the closest {top.length} of OUR products give a mature weekly run-rate, averaged by similarity and scaled by your planned distribution against theirs (products with no distribution on file are taken as 60%). Shape: the launch ramp is the similarity-weighted average of launched products' ramps, each shown as a share of its own mature volume with the seasonal swing removed. {curve === 'both' ? 'This includes competitor launches from competitor.csv; they are retail sell-out, which builds more smoothly than our sell-in to distributors, so they flatten the early weeks a little.' : 'Only our four launched products are used.'} Seasonality: the analogues' own monthly pattern. Range: one standard deviation of the analogues' volumes and the launch curves. Competitive pressure comes from competitor.csv: brand count, promotion share and launches in the last year. Limits: our four launches are all new products from an existing brand, so launch type barely separates our products; established products have no launch date or distribution on file, so those drivers cannot be scored for them (see the Scored column). Price is compared as a ratio, not as a demand elasticity. All data is synthetic.</p></details>
        </section>
      </>)}
    </Page>
  );
}

const TABS = [{ v: 'explore', label: 'Launch explorer', hint: 'Any product, closest matches' }, { v: 'case', label: 'Worked case: liquid vaporizer', hint: 'Learned from five past launches' }];
export default function NewProducts() {
  const { useSS } = useApp();
  const [view, setView] = useSS('np.view', 'explore');
  const tabs = <Tabs label="New product views" value={view} onChange={setView} options={TABS} />;
  return view === 'case' ? <LaunchCase tabs={tabs} /> : <Explorer tabs={tabs} />;
}
