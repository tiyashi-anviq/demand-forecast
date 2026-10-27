import { useMemo, useState } from 'react';
import { useApp } from '../context.js';
import { useApi } from '../lib/api.js';
import Page from '../components/Page.jsx';
import Kpis from '../components/Kpis.jsx';
import { Select, SegBare } from '../components/Controls.jsx';
import { fN, fS, fP, labFull } from '../lib/format.js';
import { check, passRange } from '../lib/challengeRules.js';

const pctOpts = (vals) => vals.map((v) => ({ v, label: Math.round(v * 100) + '%' }));
const keyOf = (r) => r.sku + '|' + r.dep + '|' + r.m;

/** Pending sales-forecast submissions, checked on arrival. A flagged number is held until the planner records a reason. */
export default function ChallengeQueue() {
  const { level, cat, prod, useSS } = useApp();
  const { data } = useApi('/api/challenge/pending');
  const lvlName = level === 'National' ? 'National' : 'Kolkata depots';
  const [cm, setCm] = useSS('chq.cm', 'all');
  const [show, setShow] = useSS('chq.show', 'open');
  const [R, setR] = useSS('chq.rule', { bud: 0.5, ly: 0.75, mod: 0.5, cov: 8, min: 0.5, need: 2 });
  const [dec, setDec] = useState({});            // key -> { reason, note }   released with a reason (session only)
  const [pick, setPick] = useState({});          // key -> reason chosen in the row but not yet released
  const [subs, setSubs] = useState({});          // key -> number resubmitted from the try-a-number box (session only)
  const [tryKey, setTryKey] = useState('');
  const [tryVal, setTryVal] = useState('');
  const [paste, setPaste] = useState('');
  const [pasteMsg, setPasteMsg] = useState('');
  const set = (k) => (v) => setR((p) => ({ ...p, [k]: parseFloat(v) }));

  const rows = useMemo(() => {
    if (!data) return [];
    return (data.rows[lvlName] || []).filter((r) => (!cat || r[2] === cat) && (!prod || r[0] === prod) && (cm === 'all' || r[4] === cm)).map((r) => {
      const [sku, name, cat_, dep, m, lead, f0, b, ly, mv, stk, ss, reason, wk] = r;
      const o = { sku, name, cat: cat_, dep, m, lead, f0, b, ly, m_: mv, stk, ss, reason, wk };
      o.key = keyOf(o);
      o.f = subs[o.key] != null ? subs[o.key] : f0;
      o.resub = subs[o.key] != null;
      const c = check({ f: o.f, b, ly, m: mv, stk: lead === 1 ? stk : null, wk }, R);
      return { ...o, ...c };
    }).sort((x, y) => y.sev - x.sev);
  }, [data, lvlName, cat, prod, cm, R, subs]);

  const head = { crumb: 'Forecast challenge', title: 'Forecast challenge',
    sub: 'Sales-team forecasts are checked the moment they are submitted, against budget, last year, the model and stock on hand. A flagged number is held until the planner records a reason.',
    tags: <><span className="tag">Checks: budget, last year, model, stock</span><span className="tag out">Simulated submissions, units</span></> };
  const mo = data ? data.months : [];
  const extra = <>
    {data && <div className="field"><span className="lab" id="chq-m">Target month</span>
      <SegBare labelledby="chq-m" value={cm} onChange={setCm} options={[{ v: 'all', label: 'All' }, ...mo.map((x) => ({ v: x.m, label: x.label + ' · M' + x.lead }))]} /></div>}
  </>;
  if (!data) return <Page {...head} showMeasure={false} extra={extra}><div className="empty"><b>Loading submissions</b><span>Fetching from the API…</span></div></Page>;

  const state = (r) => (!r.flagged ? 'cleared' : dec[r.key] ? 'released' : 'open');
  const open = rows.filter((r) => state(r) === 'open'), rel = rows.filter((r) => state(r) === 'released'), clr = rows.filter((r) => state(r) === 'cleared');
  const nFlag = open.length + rel.length, nStk = rows.filter((r) => r.stkFlag).length;
  const shown = show === 'open' ? open : show === 'flag' ? rows.filter((r) => r.flagged) : rows;
  const cnt = {}; rows.filter((r) => r.flagged).forEach((r) => r.fl.forEach((x) => { cnt[x[0]] = (cnt[x[0]] || 0) + 1; }));
  const ml = (m) => { const x = mo.find((y) => y.m === m); return x ? x.label + ' · M' + x.lead : m; };
  const asof = labFull(data.asof);
  const nRefFlag = rows.filter((r) => r.refFlag).length, nBoth = rows.filter((r) => r.refFlag && r.stkFlag).length;
  const tiles = [
    { l: 'Forecasts checked', v: String(rows.length), d: <>as of <span className="chip">{asof}</span></>, i: 'The sales team\'s submitted forecasts for the months still open: ' + mo.map((x) => x.label + ' (' + x.lead + ' month' + (x.lead > 1 ? 's' : '') + ' ahead)').join(', ') + '. Each is checked as it arrives, and ends up either passed or flagged.' },
    { l: 'Passed', v: String(clr.length), cls: 'pos', d: 'no flag, sent straight to supply planning', i: 'Forecasts that broke no rule. They move on to supply planning without anyone having to look.' },
    { l: 'Flagged', v: String(nFlag), cls: nFlag ? 'neg' : '', d: rows.length ? <><span className="chip">{fP(nFlag / rows.length)}</span> of the {rows.length}. Why: {nRefFlag} differ a lot from budget, last year or the model; {nStk} have too little or too much stock{nBoth ? '; ' + nBoth + ' have both problems' : ''}</> : '', i: 'A forecast is flagged when it is far from at least ' + R.need + ' of: budget, last year and the model (limits under Rules), or when next month\'s stock would last too short or too long a time at the forecast rate. Passed plus flagged equals checked.' },
    { l: 'Released with a reason', v: String(rel.length), cls: rel.length ? 'pos' : '', d: <>{open.length} of the {nFlag} flagged still open{open.length ? ', sales gave no reason for ' + open.filter((r) => !r.reason).length : ''}</>, i: 'Flagged forecasts are held until the planner records a reason, then released to supply planning. Where sales gave a reason with the submission it is pre-filled for the planner to confirm. Released plus still open equals flagged.' },
  ];
  const pc = (v) => Math.round(Math.abs(v) * 100) + '%';
  const why = (r) => r.fl.map((x) => {
    const d = { Budget: r.dB, 'Last year': r.dL, Model: r.dM }[x[0]];
    if (d != null) return pc(d) + ' ' + x[1] + ' ' + (x[0] === 'Budget' ? 'budget' : x[0] === 'Model' ? 'the model' : 'last year');
    return x[0] === 'Stock high' ? 'stock covers ' + r.cov.toFixed(1) + ' weeks, over the ' + R.cov + '-week limit' : 'stock covers only ' + r.cov.toFixed(1) + ' weeks, under the ' + R.min + '-week limit';
  });
  const dev = (v, t) => (v == null ? <td>–</td> : <td className={Math.abs(v) > t ? 'bad' : ''}>{fS(v)}</td>);

  // try-a-number box
  const all = (data.rows[lvlName] || []).filter((r) => (!cat || r[2] === cat) && (!prod || r[0] === prod));
  const tkey = all.some((r) => keyOf({ sku: r[0], dep: r[3], m: r[4] }) === tryKey) ? tryKey : (all.length ? keyOf({ sku: all[0][0], dep: all[0][3], m: all[0][4] }) : '');
  const tr = all.find((r) => keyOf({ sku: r[0], dep: r[3], m: r[4] }) === tkey);
  let tc = null, tin = null, trange = null;
  if (tr) {
    const [sku, name, , dep, m, lead, f0, b, ly, mv, stk, , , wk] = tr;
    const cur = subs[tkey] != null ? subs[tkey] : f0;
    const val = tryVal === '' ? cur : Number(tryVal);
    tin = { sku, name, dep, m, lead, f0, cur, b, ly, mv, stk, wk, val };
    if (isFinite(val) && val >= 0) { tc = check({ f: val, b, ly, m: mv, stk: lead === 1 ? stk : null, wk }, R); trange = passRange({ b, ly, m: mv, stk: lead === 1 ? stk : null, wk }, R); }
  }
  const applyPaste = () => {
    const find = (prod, dep, m) => { const p = prod.toLowerCase(); for (const r of all) if ((String(r[0]).toLowerCase() === p || String(r[1]).toLowerCase() === p) && (level === 'National' || r[3].toLowerCase() === dep.toLowerCase()) && r[4] === m) return keyOf({ sku: r[0], dep: r[3], m: r[4] }); return null; };
    const add = {}; let bad = 0;
    paste.split(/\n/).map((l) => l.trim()).filter(Boolean).forEach((l) => {
      const c = l.split(/[,\t;]/).map((x) => x.trim()); const nat = level === 'National';
      const [prod, dep, m, u] = nat ? [c[0], '', c[1], c[2]] : [c[0], c[1], c[2], c[3]];
      const v = Number(String(u || '').replace(/,/g, '')); const k = prod && m && isFinite(v) && v >= 0 && u !== '' ? find(prod, dep || '', m) : null;
      if (k) add[k] = Math.round(v); else bad++;
    });
    const n = Object.keys(add).length;
    if (n) { setSubs((p) => ({ ...p, ...add })); setDec((p) => { const q = { ...p }; Object.keys(add).forEach((k) => delete q[k]); return q; }); }
    setPasteMsg(n + ' number' + (n === 1 ? '' : 's') + ' applied' + (bad ? ', ' + bad + ' line' + (bad === 1 ? '' : 's') + ' not recognised' : '') + '.');
  };
  const optLabel = (r) => r[1] + (level === 'National' ? '' : ' · ' + r[3].toUpperCase()) + ' · ' + ml(r[4]);

  return (
    <Page {...head} showMeasure={false} extra={extra}>
      <Kpis tiles={tiles} label="Submission queue summary" />
      <section className="card" aria-labelledby="cqr">
        <div className="card-head"><h2 id="cqr">Rules</h2></div>
        <div className="ctl" style={{ marginTop: 0 }}>
          <Select id="q-bud" label="Off budget by more than" value={R.bud} onChange={set('bud')} options={pctOpts([0.2, 0.3, 0.4, 0.5, 0.6])} />
          <Select id="q-ly" label="Off last year by more than" value={R.ly} onChange={set('ly')} options={pctOpts([0.25, 0.5, 0.75, 1.0])} />
          <Select id="q-mod" label="Off the model by more than" value={R.mod} onChange={set('mod')} options={pctOpts([0.25, 0.35, 0.5, 0.75])} />
          <Select id="q-need" label="Flag when this many of the 3 are off" value={R.need} onChange={set('need')} options={[1, 2, 3].map((v) => ({ v, label: v + ' of 3' }))} />
          <Select id="q-min" label="Stock lasts less than" value={R.min} onChange={set('min')} options={[0.25, 0.5, 1, 2].map((v) => ({ v, label: v + (v === 1 ? ' week' : ' weeks') }))} />
          <Select id="q-cov" label="Stock lasts more than" value={R.cov} onChange={set('cov')} options={[6, 8, 10, 12, 16].map((v) => ({ v, label: v + ' weeks' }))} />
        </div>
        <p className="note">Budget, last year and the model are the three comparisons. Stock is a separate check on next month only, since stock held today says little about months further out. Change a limit and the table updates straight away.</p>
      </section>
      <section className="card" aria-labelledby="cqt">
        <div className="card-head"><h2 id="cqt">Submitted forecasts</h2>
          <SegBare ariaLabel="Show" value={show} onChange={setShow} options={[{ v: 'open', label: 'Held for a reason' }, { v: 'flag', label: 'All flagged' }, { v: 'all', label: 'All' }]} /></div>
        <p className="callout"><b>Demo data.</b> The sales-team numbers below are simulated. Budget, last year, stock and the model are real to this dataset. Paste real submissions in the box underneath to see them checked.</p>
        <details className="wdetails more"><summary>About this view</summary><p className="note">Showing {show === 'open' ? 'forecasts held for a reason' : show === 'flag' ? 'all flagged forecasts' : 'all submissions'}, {level === 'National' ? 'national' : 'Kolkata depots'}. Flags raised: {Object.keys(cnt).length ? Object.entries(cnt).map(([k, v]) => `${k} ${v}`).join(', ') : 'none'}. Pick a reason and release a held forecast to send it on; the decision is kept for this session only.</p></details>
        <div className="tablewrap" style={{ maxHeight: 560 }}><table className="ctab">
          <thead><tr><th>Product</th><th>Submitted</th><th>vs budget</th><th>vs last year</th><th>vs model</th><th>Stock cover</th><th>Flags</th><th>Reason</th><th>Status</th></tr></thead>
          <tbody>
            {!shown.length && <tr><td colSpan="9" style={{ textAlign: 'center', padding: 24, fontFamily: 'var(--font-sans)', color: 'var(--reiq-text-secondary)' }}>{rows.length ? (show === 'open' ? 'Nothing is waiting for a reason.' : 'No forecast breaks a rule with these settings.') : 'No submissions for this selection.'}</td></tr>}
            {shown.map((r) => { const s = state(r), d = dec[r.key], chosen = pick[r.key] != null ? pick[r.key] : r.reason; return (
              <tr key={r.key}>
                <td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>{r.name}{level === 'National' ? '' : ' · ' + r.dep.toUpperCase()}<div className="sub">{ml(r.m)}</div></td>
                <td>{fN(r.f)}{r.resub && <span className="sub"> · revised from {fN(r.f0)}</span>}</td>
                {dev(r.dB, R.bud)}{dev(r.dL, R.ly)}{dev(r.dM, R.mod)}
                <td className={r.stkFlag ? 'bad' : ''}>{r.cov == null ? '–' : r.cov.toFixed(1) + ' wk'}</td>
                <td className="fl">{r.fl.length ? why(r).map((t, i) => <span key={i} className={'flag ' + (r.fl[i][0].startsWith('Stock') ? 'stk' : '')}>{t}</span>) : <span style={{ color: 'var(--reiq-text-helper)' }}>–</span>}</td>
                <td className="rs">{s === 'open'
                  ? <select aria-label={'Reason for ' + r.name} value={chosen || ''} onChange={(e) => setPick((p) => ({ ...p, [r.key]: e.target.value }))}>
                      <option value="">Choose a reason</option>
                      {data.reasons.map((x) => <option key={x} value={x}>{x}</option>)}</select>
                  : s === 'released' ? d.reason : (r.reason || '–')}</td>
                <td className="fl">{s === 'open'
                  ? <button className="btn" disabled={!chosen} onClick={() => setDec((p) => ({ ...p, [r.key]: { reason: chosen } }))}>Release</button>
                  : s === 'released' ? <><span className="flag" style={{ borderColor: 'var(--reiq-pos)', color: 'var(--reiq-pos)' }}>Released</span> <button className="btn" style={{ minHeight: '1.5rem' }} onClick={() => setDec((p) => { const n = { ...p }; delete n[r.key]; return n; })}>Hold</button></>
                  : <span style={{ color: 'var(--reiq-pos)' }}>Passed</span>}</td>
              </tr>); })}
          </tbody>
        </table></div>
        <details className="wdetails more"><summary>Notes and limits</summary><p className="foot">Each submission is checked against the budget, last year's sales for the same weeks, the model's current forecast (national only; depots have no model, so two reference checks) and stock on hand at {asof}. A forecast is held when enough of those disagree, or on its own when stock cover is outside the limits. Budget and last year come from the same weeks one year earlier. Stock cover is that stock divided by the forecast's weekly rate, so the later months are tested against stock held today. All data is synthetic.</p></details>
      </section>
      <section className="card" aria-labelledby="cqp">
        <div className="card-head"><h2 id="cqp">Paste real submissions</h2></div>
        <p className="note">One line per forecast: {level === 'National' ? 'product, month, units' : 'product, depot, month, units'}. Product is the name or code shown in the table, month is like 2026-11. Matching lines replace the simulated number for this session.</p>
        <textarea aria-label="Pasted submissions" rows="4" style={{ width: '100%', maxWidth: 720, fontFamily: 'var(--font-mono, monospace)' }} value={paste} onChange={(e) => setPaste(e.target.value)} placeholder={level === 'National' ? 'rch, 2026-11, 52000' : 'rch, kol1, 2026-11, 9000'} />
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 8 }}>
          <button className="btn primary" disabled={!paste.trim()} onClick={applyPaste}>Check these numbers</button>
          {pasteMsg && <span role="status" className="note" style={{ margin: 0 }}>{pasteMsg}</span>}
        </div>
      </section>
      <section className="card" aria-labelledby="cqn">
        <div className="card-head"><h2 id="cqn">Try a number</h2></div>
        <p className="note">Type a forecast for any product and month to see how it would be checked before it is submitted. Submitting replaces the sales team's number in the queue above, for this session.</p>
        <div className="ctl" style={{ marginTop: 0 }}>
          <div className="field"><label htmlFor="try-p">Product and month</label>
            <select id="try-p" value={tkey} onChange={(e) => { setTryKey(e.target.value); setTryVal(''); }}>
              {all.map((r) => <option key={keyOf({ sku: r[0], dep: r[3], m: r[4] })} value={keyOf({ sku: r[0], dep: r[3], m: r[4] })}>{optLabel(r)}</option>)}</select></div>
          <div className="field"><label htmlFor="try-v">Forecast, units</label>
            <input id="try-v" type="number" min="0" step="100" value={tryVal === '' && tin ? Math.round(tin.cur) : tryVal} onChange={(e) => setTryVal(e.target.value)} /></div>
        </div>
        {tin && tc && (<>
          <table className="ctab" style={{ maxWidth: 720 }}>
            <thead><tr><th style={{ textAlign: 'left' }}>Reference</th><th>Value</th><th>This number</th><th>Limit</th></tr></thead>
            <tbody>
              <tr><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>Budget</td><td>{fN(tin.b)}</td>{dev(tc.dB, R.bud)}<td>±{Math.round(R.bud * 100)}%</td></tr>
              <tr><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>Last year</td><td>{fN(tin.ly)}</td>{dev(tc.dL, R.ly)}<td>±{Math.round(R.ly * 100)}%</td></tr>
              <tr><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>Model</td><td>{tin.mv == null ? 'none at depot level' : fN(tin.mv)}</td>{dev(tc.dM, R.mod)}<td>{tin.mv == null ? '–' : '±' + Math.round(R.mod * 100) + '%'}</td></tr>
              <tr><td style={{ textAlign: 'left', fontFamily: 'var(--font-sans)' }}>Stock on hand</td><td>{fN(tin.stk)}</td><td className={tc.stkFlag ? 'bad' : ''}>{tc.cov == null ? '–' : tc.cov.toFixed(1) + ' wk cover'}</td><td>{R.min}–{R.cov} wk</td></tr>
            </tbody></table>
          <p className="callout">{tc.flagged
            ? <><b className="neg">Would be held.</b> {why(tc).join('; ')}. A reason is needed before it is released.</>
            : <><b className="pos">Passes every check.</b> It would move downstream without a reason.</>}
            {trange && <> A number from <b>{fN(trange[0])}</b> to <b>{fN(trange[1])}</b> passes with the current rules.</>}</p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <button className="btn primary" disabled={!isFinite(tin.val) || tin.val < 0 || Math.round(tin.val) === Math.round(tin.cur)} onClick={() => { setSubs((p) => ({ ...p, [tkey]: Math.round(tin.val) })); setDec((p) => { const n = { ...p }; delete n[tkey]; return n; }); setTryVal(''); }}>Submit this number</button>
            {subs[tkey] != null && <button className="btn" onClick={() => { setSubs((p) => { const n = { ...p }; delete n[tkey]; return n; }); setTryVal(''); }}>Back to sales number ({fN(tin.f0)})</button>}
          </div></>)}
      </section>
    </Page>
  );
}
