// Scenario controls: simple overlays on the forecast weeks. The models are not re-run.
export const PRESETS = [
  { id: 'base', name: 'Base case', desc: 'The forecast as the model made it.', lev: { shift: 0, fest: 0, avail: 100 } },
  { id: 'weak', name: 'Weak festive season', desc: 'Softer demand overall and in festival weeks.', lev: { shift: -3, fest: -15, avail: 100 } },
  { id: 'strong', name: 'Strong festive season', desc: 'A little more demand overall, much more in festival weeks.', lev: { shift: 2, fest: 15, avail: 100 } },
  { id: 'supply', name: 'Supply squeeze', desc: 'Plants can ship only 88% of what is asked for.', lev: { shift: 0, fest: 0, avail: 88 } },
];
export const BASE = PRESETS[0].lev;
export const isBase = (l) => l.shift === 0 && l.fest === 0 && l.avail === 100;
export const presetOf = (l) => PRESETS.find((p) => p.lev.shift === l.shift && p.lev.fest === l.fest && p.lev.avail === l.avail);
export const scenName = (l) => (isBase(l) ? null : presetOf(l)?.name || 'Custom');
/** true for weeks in a festival or its sell-in period, from the drivers file */
export const festFlags = (DR, W) => W.map((w) => { const t = DR ? DR.weeks.indexOf(w) : -1, x = t >= 0 ? DR.info[t] : null; return !!(x && (x.fest || x.sellin)); });
export const mult = (l, fw, i) => (1 + l.shift / 100) * (fw[i] ? 1 + l.fest / 100 : 1);
/** the node's series with the levers applied to forecast weeks (index >= HN) */
export const applyScenario = (n, l, fw, HN) => {
  if (!n || isBase(l)) return n;
  const f = (a) => a.map((v, i) => (v != null && i >= HN ? v * mult(l, fw, i) : v));
  return { ...n, model: f(n.model), p50: f(n.p50) };
};
