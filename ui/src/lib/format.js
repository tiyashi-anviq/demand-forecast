export const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const dt = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(Date.UTC(y, m - 1, d)); };
export const p2 = (n) => String(n).padStart(2, '0');
export const lab = (s) => { const d = dt(s); return p2(d.getUTCDate()) + ' ' + MON[d.getUTCMonth()] + ' ' + p2(d.getUTCFullYear() % 100); };
export const labFull = (s) => { const d = dt(s); return p2(d.getUTCDate()) + ' ' + MON[d.getUTCMonth()] + ' ' + d.getUTCFullYear(); };
export const endOf = (s) => { const d = dt(s); d.setUTCDate(d.getUTCDate() + 6); return p2(d.getUTCDate()) + ' ' + MON[d.getUTCMonth()] + ' ' + d.getUTCFullYear(); };
// Indian number formats: lakh (L) and crore (Cr)
export const fK = (v) => {
  if (v == null || isNaN(v)) return '-';
  const a = Math.abs(v);
  if (a >= 1e7) return (v / 1e7).toFixed(a >= 1e8 ? 0 : 2).replace(/\.?0+$/, '') + 'Cr';
  if (a >= 1e5) return (v / 1e5).toFixed(a >= 1e6 ? 0 : 1).replace(/\.0$/, '') + 'L';
  if (a >= 1e3) return (v / 1e3).toFixed(0) + 'k';
  return String(Math.round(v));
};
export const fCr = (v) => (v / 1e7).toFixed(2) + ' Cr';
export const fN = (v) => (v == null ? '-' : Math.round(v).toLocaleString('en-IN'));
export const fS = (v) => (v >= 0 ? '+' : '−') + Math.abs(v * 100).toFixed(1) + '%';
export const fP = (v) => (v * 100).toFixed(1) + '%';
export const sum = (a) => a.reduce((s, x) => s + (x || 0), 0);
