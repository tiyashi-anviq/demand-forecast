// Similarity index and analogue-based launch forecast for the New products screen. Pure functions, no React.
// Each driver scores 0-1 between the new product's inputs and one existing product; the index is the weighted
// average (0-100) over the drivers where both sides have a value, so a blank input or a missing product fact drops
// that driver and the rest are rescaled. `coverage` is the share of the chosen weight that could be scored.

export const DRIVERS = [
  { k: 'cat', label: 'Category', short: 'Category', w: 25, group: 'What it is' },
  { k: 'tech', label: 'Technology level', short: 'Tech', w: 3, group: 'What it is' },
  { k: 'pack', label: 'Pack format', short: 'Pack', w: 20, group: 'What it is' },
  { k: 'price', label: 'Price point', short: 'Price', w: 12, group: 'What it is' },
  { k: 'season', label: 'Seasonal pattern', short: 'Season', w: 8, group: 'How it sells' },
  { k: 'shelf', label: 'Shelf life', short: 'Shelf', w: 3, group: 'How it sells' },
  { k: 'ltype', label: 'Launch type', short: 'Launch', w: 6, group: 'How it launches' },
  { k: 'dist', label: 'Distribution at launch', short: 'Distrib.', w: 12, group: 'How it launches' },
  { k: 'scheme', label: 'Trade scheme', short: 'Scheme', w: 2, group: 'How it launches' },
  { k: 'timing', label: 'Launch timing', short: 'Timing', w: 4, group: 'Market' },
  { k: 'comp', label: 'Competitive pressure', short: 'Compet.', w: 5, group: 'Market' },
];
export const DEFAULT_W = Object.fromEntries(DRIVERS.map((d) => [d.k, d.w]));
export const SEASONS = ['Festive', 'Winter', 'Summer', 'Monsoon'];            // calendar order: Sep-Nov, Dec-Feb, Mar-May, Jun-Aug
export const SEASON_LABEL = { Festive: 'Festive (Sep to Nov)', Winter: 'Winter (Dec to Feb)', Summer: 'Summer (Mar to May)', Monsoon: 'Monsoon (Jun to Aug)', Flat: 'Year-round, no clear peak' };
export const SHELF = [{ v: 104, label: 'Short, about 2 years' }, { v: 260, label: 'Medium, about 5 years' }, { v: 520, label: 'Long, about 10 years' }];
export const LTYPES = ['New product from existing brand', 'Line extension', 'New brand'];
export const COMP = ['Low', 'Medium', 'High'];

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const near = (list, a, b) => (a === b ? 1 : Math.abs(list.indexOf(a) - list.indexOf(b)) === 1 ? 0.5 : 0);
const cyc = (a, b) => { const i = SEASONS.indexOf(a), j = SEASONS.indexOf(b); if (i < 0 || j < 0) return 0; const d = Math.abs(i - j); return Math.min(d, 4 - d); };
export const seasonOfMonth = (m) => (m >= 9 && m <= 11 ? 'Festive' : m === 12 || m <= 2 ? 'Winter' : m <= 5 ? 'Summer' : 'Monsoon');
export const monthOf = (iso) => Number(iso.slice(5, 7));

/** score of one driver, or null when it cannot be scored */
function score(k, inp, p, segOf) {
  switch (k) {
    case 'cat': return !inp.cat ? null : p.cat === inp.cat ? 1 : p.seg === segOf[inp.cat] ? 0.5 : 0;
    case 'tech': return !inp.tech || p.tech == null ? null : p.tech === inp.tech ? 1 : 0;
    case 'pack': return !inp.pack || p.pack == null ? null : p.pack === inp.pack ? 1 : 0;
    case 'price': return !(inp.price > 0) ? null : clamp01(1 - Math.abs(Math.log(inp.price / p.asp)) / Math.log(4));
    case 'season': { if (!inp.season) return null; if (p.peak === inp.season) return 1; if (p.peak === 'Flat' || inp.season === 'Flat') return 0.4; return cyc(p.peak, inp.season) === 1 ? 0.4 : 0; }
    case 'shelf': return !inp.shelf || p.shelf == null ? null : near([104, 260, 520], Number(inp.shelf), p.shelf);
    case 'ltype': return !inp.ltype || (p.new && !p.launch_type) ? null : !p.new ? 0.3 : p.launch_type === inp.ltype ? 1 : inp.ltype === 'Line extension' ? 0.5 : 0.2;
    case 'dist': return !(inp.dist > 0) || p.dist == null ? null : clamp01(1 - Math.abs(inp.dist - p.dist) / 30);
    case 'scheme': return p.scheme == null || inp.scheme === '' || inp.scheme == null || isNaN(inp.scheme) ? null : clamp01(1 - Math.abs(inp.scheme - p.scheme) / 2);
    case 'timing': return !inp.launch || !p.launch_season ? null : (() => { const c = cyc(seasonOfMonth(monthOf(inp.launch)), p.launch_season); return c === 0 ? 1 : c === 1 ? 0.5 : 0; })();
    case 'comp': return !inp.comp ? null : near(COMP, inp.comp, p.comp_level);
    default: return null;
  }
}

/** every product scored against the inputs, best first */
export function rank(products, inp, W) {
  const segOf = {}; products.forEach((p) => { segOf[p.cat] = p.seg; });
  const asked = DRIVERS.filter((d) => (W[d.k] || 0) > 0);
  const askedW = asked.reduce((s, d) => s + W[d.k], 0);
  const out = products.map((p) => {
    const sc = {}; let num = 0, den = 0;
    for (const d of asked) { const v = score(d.k, inp, p, segOf); sc[d.k] = v; if (v != null) { num += W[d.k] * v; den += W[d.k]; } }
    return { p, sc, index: den ? (100 * num) / den : 0, coverage: askedW ? den / askedW : 0 };
  });
  out.sort((a, b) => b.index - a.index);
  // what the product is for comes first: when the chosen category has enough products (ours or the market's), those rank above everything else
  const same = inp.cat ? out.filter((r) => r.p.cat === inp.cat) : [];
  if (same.length >= MIN_SAME) { same.forEach((r) => { r.same = true; }); return [...same, ...out.filter((r) => !r.same)]; }
  return out;
}
export const MIN_SAME = 3;

const sum = (a) => a.reduce((s, x) => s + x, 0);
const wmean = (vals, w) => sum(vals.map((v, i) => v * w[i])) / (sum(w) || 1);
const wsd = (vals, w) => { const m = wmean(vals, w); return Math.sqrt(wmean(vals.map((v) => (v - m) ** 2), w)); };
const addDays = (iso, n) => { const d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };

/** Launch forecast from the closest K analogues.
 *  volume   = similarity-weighted mature weekly run-rate of the analogues, scaled by planned distribution
 *  shape    = similarity-weighted launch ramp of launched products: our four, and (optionally) competitors' launches from competitor.csv
 *  only OUR products set the volume: competitor launches are retail sell-out for other companies, so they supply shape and benchmarks only
 *  seasonal = similarity-weighted monthly index of the analogues
 *  range    = one standard deviation of the analogues' volumes and the launch curves */
export function forecast(data, ranked, inp, K = 3, weeks = 52, useMarket = true) {
  const sameCat = ranked.filter((r) => r.same);                         // products in the chosen category, ours and the market's
  const ownSame = sameCat.filter((r) => r.p.src !== 'market');
  // volume and season: our own products; if we have none in this category, the market's launches in it (retail sell-out, flagged to the user)
  const volFromMarket = sameCat.length >= MIN_SAME && ownSame.length === 0;
  const top = (volFromMarket ? sameCat : ranked.filter((r) => r.p.src !== 'market')).slice(0, K).filter((r) => r.index > 0);
  if (!top.length || !inp.launch) return null;
  const ref = data.ref_dist;
  const scale = (p) => (inp.dist > 0 ? Math.max(0.4, Math.min(2.5, inp.dist / (p.dist ?? ref))) : 1);
  const s = top.map((r) => r.index), lv = top.map((r) => r.p.level * scale(r.p));
  const level = wmean(lv, s), cvLevel = level ? wsd(lv, s) / level : 0;
  const idx = Array.from({ length: 12 }, (_, m) => wmean(top.map((r) => r.p.idx[m]), s)); const im = sum(idx) / 12; const seas = idx.map((v) => v / im);
  let npd = ranked.filter((r) => data.ramps[r.p.code] && (useMarket || r.p.src !== 'market'));
  const npdSame = npd.filter((r) => r.same);                             // launch curve from the same category when it has at least 3 launches
  if (npdSame.length >= MIN_SAME) npd = npdSame;
  const nw = npd.map((r) => Math.max(r.index, 1) ** 2);
  const at = (code, w) => { const a = data.ramps[code].ratio; return a[Math.min(w, a.length - 1)]; };
  const ramp = [], rampSd = [];
  for (let w = 0; w < weeks; w++) { const v = npd.map((r) => at(r.p.code, w)); ramp.push(Math.min(1.25, wmean(v, nw))); rampSd.push(wsd(v, nw)); }
  const rows = [];
  for (let w = 0; w < weeks; w++) {
    const date = addDays(inp.launch, 7 * w), m = monthOf(date) - 1;
    const f = level * ramp[w] * seas[m];
    const cv = Math.min(0.6, Math.sqrt(cvLevel ** 2 + (ramp[w] ? (rampSd[w] / ramp[w]) ** 2 : 0)));
    rows.push({ date, week: w + 1, f, lo: f * (1 - cv), hi: f * (1 + cv), ramp: ramp[w] });
  }
  return { top, volFromMarket, curveSameCat: npdSame.length >= MIN_SAME, level, rows, seas, npd: npd.map((r, i) => ({ code: r.p.code, name: r.p.name, src: r.p.src, w: nw[i] / sum(nw) })).sort((a, b) => b.w - a.w) };
}
