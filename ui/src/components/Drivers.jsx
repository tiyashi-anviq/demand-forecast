import { dt, p2 } from '../lib/format.js';
import { SegBare } from './Controls.jsx';

export const money = (v) => { const a = Math.abs(v), s = v < 0 ? '−' : '+'; return a >= 1e5 ? s + (a / 1e7).toFixed(2) + ' Cr' : s + (a / 1e3).toFixed(0) + ' K'; };
export const plain = (v) => (Math.abs(v) >= 1e5 ? (v / 1e7).toFixed(2) + ' Cr' : (v / 1e3).toFixed(0) + ' K');
const MIN_SHARE = 0.01, MAX_ROWS = 4;
const mean = (a) => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0);
const uniq = (a) => [...new Set(a)];

/** Facts for one or more weeks, combined (one week for the weekly view, the weeks of a month for the monthly view). */
export function aggInfo(infos) {
  const I = infos.filter(Boolean);
  const split = (s) => (s ? s.split(';').map((x) => x.trim()).filter(Boolean) : []);
  const comp = {};
  I.forEach((i) => Object.entries(i.comp || {}).forEach(([c, v]) => { comp[c] = uniq([...(comp[c] || []), ...v]); }));
  return { n: I.length, fc: I.some((i) => i.fc), sellinN: I.filter((i) => i.sellin).length, festN: I.filter((i) => i.fest).length,
    fests: uniq(I.flatMap((i) => split(i.fest))), sells: uniq(I.map((i) => i.sellin).filter(Boolean)),
    rain: mean(I.map((i) => i.rain)), temp: mean(I.map((i) => i.temp)), power: mean(I.map((i) => i.power)), ev: uniq(I.flatMap((i) => i.ev || [])), comp };
}
// Weeks straddling two months are pro-rated by days. weekShare = fraction of the week's seven days (Mon-Sun) that fall in month m.
export const weekShare = (w, m) => { let c = 0; for (let k = 0; k < 7; k++) { const d = dt(w); d.setUTCDate(d.getUTCDate() + k); if (d.getUTCFullYear() + '-' + p2(d.getUTCMonth() + 1) === m) c++; } return c / 7; };
// the month holding a week's Thursday (used only to pick which month to show for a selected week)
export const monthOf = (w) => { const d = dt(w); d.setUTCDate(d.getUTCDate() + 3); return d.getUTCFullYear() + '-' + p2(d.getUTCMonth() + 1); };
export const monthInfos = (data, m) => data.weeks.map((w, i) => (weekShare(w, m) > 0 ? data.info[i] : null)).filter(Boolean);

const MODELS = [
  { k: 'sn', label: 'Seasonal naive', what: "last year's same week, scaled by recent growth" },
  { k: 'et', label: 'Damped ETS', what: 'smoothed level, trend and seasonality of the sales history' },
  { k: 'gb', label: 'LightGBM', what: 'learns from sales history, festivals, weather and price' },
];

/** How the three models in the blend pull the forecast away from the reference.
 *  ensemble = sum of weight x model, so (ensemble - reference) splits exactly into each model's pull; anything the ensemble missed
 *  (cur - ensemble) is shown as the forecast miss, and a different month length is taken out first.
 *  mdl: node's per-model weekly forecasts; js: display-week indices that make up the period; cur / ref: values in the display measure. */
export function buildModelRows({ mdl, weights, js, jw, mea, cur, ref, adj = 1, actual, events = [], ahead = '13 weeks', short = 'the starting point' }) {
  if (!mdl || !js.length) return null;
  const sc = (j) => (mea === 'v' ? mdl.sc[j] : 1);
  const raw = MODELS.map((m, i) => (weights[i] > 0 && mdl[m.k] ? js.reduce((t, j, q) => t + (mdl[m.k][j] == null ? NaN : mdl[m.k][j] * sc(j) * (jw ? jw[q] : 1)), 0) : null));
  if (raw.some((v, i) => weights[i] > 0 && (v == null || Number.isNaN(v)))) return null;
  const ens = raw.reduce((t, v, i) => t + (v == null ? 0 : weights[i] * v), 0);
  const refAdj = ref * adj, len = refAdj - ref, miss = cur - ens, mat = MIN_SHARE * ref;
  const rows = [];
  if (Math.abs(len) >= mat) rows.push({ k: 'len', label: 'Month length', v: len, why: 'Months have 28 to 31 days, so the starting point is scaled to this month\'s length first.' });
  MODELS.forEach((m, i) => { if (raw[i] != null) rows.push({ k: m.k, label: `${m.label}`, tag: Math.round(weights[i] * 100) + '% of the blend', v: weights[i] * (raw[i] - refAdj), why: `On its own it says ${plain(raw[i])}.`, more: `What it does: ${m.what}.` }); });
  if (Math.abs(miss) >= mat) rows.push(actual
    ? { k: 'miss', label: 'What the forecast missed', v: miss, ens, cur, ahead, events, pct: ens ? miss / ens : 0 }
    : { k: 'miss', label: 'Latest run difference', v: miss, why: 'The latest run totals differ slightly from the weekly forecast.' });
  const vals = raw.filter((v, i) => v != null && weights[i] > 0), spread = ens ? (Math.max(...vals) - Math.min(...vals)) / ens : 0;
  const errs = actual ? MODELS.map((m, i) => (raw[i] != null && cur ? { label: m.label, pct: raw[i] / cur - 1 } : null)).filter(Boolean).sort((x, y) => Math.abs(x.pct) - Math.abs(y.pct)) : null;
  const chg = ens - refAdj, big = rows.filter((r) => MODELS.some((m) => m.k === r.k) && Math.abs(r.v) >= 0.05 * Math.abs(chg)).sort((a, b) => Math.abs(b.v) - Math.abs(a.v)).slice(0, 2);
  const g = cur / ref - 1, dir = Math.abs(g) < 0.005 ? 'level with' : `${Math.abs(g * 100).toFixed(1)}% ${g > 0 ? 'above' : 'below'}`;
  const story = [`${actual ? 'Sales were' : 'The forecast is'} ${plain(cur)}, ${dir} ${short}.`,
    big.length ? big.map((r, i) => `${r.label} ${r.v >= 0 ? (i ? 'pushed it up' : 'pushed the forecast up') : (i ? 'pulled it down' : 'pulled the forecast down')} by ${plain(Math.abs(r.v))}`).join(' and ') + '.' : 'No single model moves the forecast much.',
    rows.some((r) => r.k === 'len') ? 'Part of the gap is month length.' : '',
    actual && Math.abs(miss) >= mat ? `Sales then came in ${plain(Math.abs(miss))} ${miss > 0 ? 'above' : 'below'} what was forecast.` : ''].filter(Boolean).join(' ');
  return { rows, ens, spread, vals, errs, story };
}

export function buildFacts(a, b, short, fc, cat) {
  const F = [], pre = fc ? 'Expected ' : '';
  const t = (arr) => arr.join('; ') || 'none';
  if (a.fests.length || b.fests.length) F.push(['Festivals', `${t(a.fests)} (${short}: ${t(b.fests)})`]);
  if (t(a.sells) !== t(b.sells)) F.push(['Sell-in period', `${t(a.sells)} (${short}: ${t(b.sells)})`]);
  if (Math.abs(a.rain - b.rain) >= 15) F.push([pre + 'rain' + (a.n > 1 ? ' (weekly average)' : ''), `${Math.round(a.rain)} mm vs ${Math.round(b.rain)} mm ${short}`]);
  if (Math.abs(a.temp - b.temp) >= 1.5) F.push([pre + 'peak temperature', `${a.temp.toFixed(1)}°C vs ${b.temp.toFixed(1)}°C ${short}`]);
  if (Math.abs(a.power - b.power) >= 1) F.push([pre + 'power cuts' + (a.n > 1 ? ' (weekly average)' : ''), `${a.power.toFixed(1)} h vs ${b.power.toFixed(1)} h ${short}`]);
  if (a.ev.length) F.push(['Market events', a.ev.join(', ') + (b.ev.length ? ` (${short}: ${b.ev.join(', ')})` : '')]);
  const cats = cat ? [cat] : Object.keys(a.comp);
  const comp = uniq(cats.flatMap((c) => a.comp[c] || []));
  if (comp.length) F.push(['Competitors', comp.join('; ')]);
  return F;
}

/** Left column: ranked rows with a bar each (what pulled the forecast), with a switch for the comparison; right column: plain facts. */
/** The part no model explains: forecast against what sold, shown as two bars, kept visually apart from the model rows. */
function Missed({ r }) {
  const mx = Math.max(r.ens, r.cur), up = r.v >= 0, pc = (r.pct >= 0 ? '+' : '−') + Math.abs(r.pct * 100).toFixed(1) + '%';
  return (
    <li className="drv-miss">
      <div className="drv-top"><b>{r.label}</b><span className={'drv-v ' + (up ? 'pos' : 'neg')}>{money(r.v)} <span className="drv-pc">({pc})</span></span></div>
      <p className="drv-why">Not a model pulling the forecast: this is what happened after the forecast was made.</p>
      <div className="vs" role="img" aria-label={`Forecast ${plain(r.ens)}, actual ${plain(r.cur)}`}>
        <span>Forecast, {r.ahead} earlier</span><div className="vs-track"><i className="vs-f" style={{ width: (r.ens / mx) * 100 + '%' }} /></div><b>{plain(r.ens)}</b>
        <span>Actually sold</span><div className="vs-track"><i className={'vs-a ' + (up ? 'pos' : 'neg')} style={{ width: (r.cur / mx) * 100 + '%' }} /></div><b>{plain(r.cur)}</b>
      </div>
      <div className="drv-why">{r.events.length ? <>Market events that period: {r.events.map((e) => <span className="chip" key={e}>{e}</span>)}</> : 'No market event is recorded for this period.'} The models cannot see sudden events, order timing or stock levels, so a gap like this is usually one of those.</div>
    </li>
  );
}

export function InShort({ text }) {
  return text ? <p className="short"><b>In short</b>{text}</p> : null;
}

export function DriverCols({ rows, note, facts, basis, setBasis, options, title, sub, factsNote }) {
  const mx = Math.max(...rows.map((r) => Math.abs(r.v)), 1);
  return (
    <div className="why-cols">
      <section>
        <div className="sec-h">
          <h4>{title}</h4>
          <SegBare ariaLabel="Compare against" value={basis} onChange={setBasis} options={options} />
        </div>
        <p className="sec-sub">{sub}</p>
        {rows.length ? (
          <ul className="drv">
            {rows.map((r) => (r.ens != null ? <Missed key={r.k} r={r} /> : (
              <li key={r.k}>
                <div className="drv-top"><b>{r.label}{r.tag && <span className="drv-tag">{r.tag}</span>}</b><span className={'drv-v ' + (r.v >= 0 ? 'pos' : 'neg')}>{money(r.v)}</span></div>
                <div className="drv-track" aria-hidden="true"><i className={r.v >= 0 ? 'pos' : 'neg'} style={{ width: (Math.abs(r.v) / mx) * 50 + '%', [r.v >= 0 ? 'left' : 'right']: '50%' }} /></div>
                <div className="drv-why">{r.why}</div>
                {r.more && <details className="drv-more"><summary>Detail</summary><p>{r.more}</p></details>}
              </li>
            )))}
          </ul>
        ) : <p className="foot">No model breakdown for this period and selection.</p>}
        {note}
      </section>
      <section>
        <h4>What was going on</h4>
        {facts.length ? <dl className="facts">{facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
          : <p className="foot">Nothing unusual in festivals, weather or market events compared with {factsNote}.</p>}
      </section>
    </div>
  );
}

/** One line on how far apart the three models are. */
export function Agreement({ spread, vals, errs }) {
  if (!vals || vals.length < 2) return null;
  const p = (spread * 100).toFixed(0) + '%', lo = Math.min(...vals), hi = Math.max(...vals);
  const nm = vals.length === 2 ? 'two' : 'three', tone = spread < 0.08 ? `The ${nm} models agree closely` : spread < 0.2 ? `The ${nm} models are somewhat apart` : `The ${nm} models disagree`;
  return (
    <p className="callout">
      <b>{tone}.</b> Their forecasts span {plain(lo)} to {plain(hi)}, {p} of the blend.
      {spread >= 0.2 ? ' Treat this forecast with more caution.' : spread < 0.08 ? ' That makes the blend more dependable.' : ''}
      {errs && errs.length > 1 && <> Against what actually sold, <b>{errs[0].label}</b> was closest ({(errs[0].pct >= 0 ? '+' : '−') + Math.abs(errs[0].pct * 100).toFixed(1)}%){errs.slice(1).map((e) => `, then ${e.label} (${(e.pct >= 0 ? '+' : '−') + Math.abs(e.pct * 100).toFixed(1)}%)`).join('')}.</>}
    </p>
  );
}

export function HowEstimated({ fc }) {
  return (
    <details className="how">
      <summary>How this is worked out</summary>
      <p>The forecast is a fixed blend of three models. Each bar is that model's own forecast minus the starting point, times its weight in the blend, so the bars add up exactly to the change in the forecast. Each model's own forecast is the one it made 13 weeks ahead for past weeks and the latest run for coming weeks. This explains what the models lean on, not what caused demand to move.{fc ? ' For a forecast period there are no actuals to check against yet.' : ''}</p>
    </details>
  );
}
