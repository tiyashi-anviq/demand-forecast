/** The forecast-challenge rules, shared by the past-months view and the pending-submissions queue.
 *  A forecast is compared with budget, last year and (national only) the model. It is flagged when at least
 *  `need` of the reference checks fall outside their band (or all of them, when fewer exist).
 *  Stock cover is checked on its own and flags a forecast by itself. */
export function check({ f, b, ly, m, stk, wk }, R) {
  const dB = b > 0 ? f / b - 1 : null, dL = ly > 0 ? f / ly - 1 : null, dM = (m != null && m > 0) ? f / m - 1 : null;
  const cov = (stk != null && f > 0) ? stk / (f / wk) : null;
  const fl = []; let nRef = 0, nFail = 0;
  if (dB != null) nRef++; if (dL != null) nRef++; if (dM != null) nRef++;
  if (dB != null && Math.abs(dB) > R.bud) { fl.push(['Budget', dB > 0 ? 'above' : 'below']); nFail++; }
  if (dL != null && Math.abs(dL) > R.ly) { fl.push(['Last year', dL > 0 ? 'above' : 'below']); nFail++; }
  if (dM != null && Math.abs(dM) > R.mod) { fl.push(['Model', dM > 0 ? 'above' : 'below']); nFail++; }
  if (cov != null && cov > R.cov) fl.push(['Stock high', '']); else if (cov != null && cov < R.min) fl.push(['Stock short', '']);
  const stkFlag = fl.some((x) => x[0].startsWith('Stock'));
  const refFlag = nRef > 0 && nFail >= Math.min(R.need, nRef);
  const flagged = stkFlag || refFlag;
  const sev = (flagged ? 100 : 0) + fl.length * 10 + Math.max(...[dB, dL, dM].map((v) => (v == null ? 0 : Math.abs(v))));
  return { dB, dL, dM, cov, fl, flagged, refFlag, stkFlag, sev };
}

/** The range of numbers that would pass every check, found by trying values around the reference points. */
export function passRange(row, R) {
  const refs = [row.b, row.ly, row.m, row.f].filter((v) => v != null && v > 0);
  if (!refs.length) return null;
  const hi = Math.max(...refs) * 2.5, lo = Math.min(...refs) * 0.2, step = (hi - lo) / 600;
  let a = null, z = null;
  for (let f = lo; f <= hi; f += step) { if (!check({ ...row, f }, R).flagged) { if (a == null) a = f; z = f; } }
  return a == null ? null : [a, z];
}
