import Stat from './Stat.jsx';
import { InShort, DriverCols, HowEstimated, Agreement, aggInfo, buildModelRows, buildFacts, plain } from './Drivers.jsx';
import { lab, labFull, endOf, fS, fCr, dt, p2 } from '../lib/format.js';

const BASES = { yoy: { lag: 52, short: 'last year', sub: 'How the three models pull the forecast away from the same week last year.', facts: 'the same week last year' },
                wow: { lag: 1, short: 'last week', sub: 'How the three models pull the forecast away from last week.', facts: 'last week' } };

export default function WhyWeek({ j, data, W, nodeKey, node, cat, mea, n, HN, basis, setBasis, onClose, scen }) {
  const wv = (i) => (i < 0 ? null : (i < HN ? n.actual[i] : n.model[i]));
  const t = data.weeks.indexOf(W[j]), B = BASES[basis];
  const mdl = data.nodes[nodeKey]?.mdl;
  const ia = data.info[t];
  // festival weeks are compared with the same festival last year (dated calendar), other weeks with 52 weeks back
  const li = ia && ia.lyi != null && ia.lyi >= 0 ? ia.lyi : t - 52, festLY = !!(ia && ia.lyl);
  const ib = data.info[basis === 'yoy' ? li : t - B.lag];
  const pf = !festLY && ia && data.info[t - 52] && data.info[t - 52].fest, pfName = pf ? pf.split(';')[0].replace(/\s*\(.*/, '').trim() : null;
  const stage = festLY && /period$/.test(ia.lyl), lyName = festLY ? ia.lyl.replace(' period', '') : null;
  const lyShort = stage ? 'the same point in the festive season last year' : festLY ? 'the same festival last year' : 'the same week last year';
  const shell = (body) => <aside className="why" id="why" tabIndex={-1} aria-label={'Why ' + lab(W[j])}>{body}</aside>;
  if (!ia || !ib) return shell(<><div className="why-h"><h3>Week of {lab(W[j])}</h3><button className="x" onClick={onClose} aria-label="Close">×</button></div><p className="foot">No breakdown for this week and selection.</p></>);
  const fc = ia.fc, cv = wv(j), sc = mea === 'v' && mdl ? mdl.sc[j] : 1;
  const end = cv;
  const facts = buildFacts(aggInfo([ia]), aggInfo([ib]), basis === 'yoy' ? (festLY ? lyShort : 'last year') : B.short, fc, cat);
  const unit = mea === 'v' ? '₹' : 'units';
  const cmps = [['wow', 'Against last week', wv(j - 1), lab(W[Math.max(j - 1, 0)]), j - 1 < HN ? 'actual' : 'forecast'],
                ['yoy', stage ? 'Against the same point in the festive season last year' : festLY ? 'Against ' + lyName + ' last year' : pfName ? 'Against the same week last year (' + pfName + ')' : 'Against the same week last year', (n.lyf || n.ly)[j], festLY ? lab(data.weeks[li]) : lab(agoStr(W[j], 364)), 'actual']];
  const refV = cmps.find((c) => c[0] === basis)[2];
  const M = mdl && refV && cv != null ? buildModelRows({ mdl, weights: data.weights, js: [j], mea, cur: cv, ref: refV, actual: !fc, events: aggInfo([ia]).ev, short: B.short === 'last week' ? 'last week' : lyShort }) : null;
  return shell(<>
    <div className="why-h">
      <div>
        <div className="why-eyebrow">Week of {labFull(W[j])} <span className={'pill ' + (fc ? 'fc' : '')}>{fc ? 'Forecast' : 'Actual'}</span></div>
        <h3>{plain(end)} <small>{fc ? 'expected' : 'sold'} · {node} · {lab(W[j])} to {endOf(W[j])}</small></h3>
      </div>
      <button className="x" onClick={onClose} aria-label="Close breakdown">×</button>
    </div>
    <div className="stats">
      {cmps.map(([k, title, ref, refLab, rk]) => {
        const ok = ref && cv != null, tt = ok ? cv / ref - 1 : null;
        return <Stat key={k} title={title} pct={ok ? fS(tt) : null} up={tt >= 0} active={basis === k} onSelect={() => setBasis(k)}
          detail={ok ? <><b>{fCr(cv)}</b> against <b>{fCr(ref)}</b></> : 'Not available for this selection'}
          sub={ok ? `Week of ${refLab} (${rk}) · ${cv - ref >= 0 ? '+' : '−'}${fCr(Math.abs(cv - ref))} ${unit}` : null} />;
      })}
    </div>
    {M && <InShort text={M.story} />}
    <DriverCols title="What each model says" sub={basis === 'yoy' && festLY ? B.sub.replace('the same week last year', lyShort) : B.sub} rows={M ? M.rows : []} note={M && <Agreement spread={M.spread} vals={M.vals} errs={M.errs} />} facts={facts} factsNote={basis === 'yoy' && festLY ? lyShort : B.facts}
      basis={basis} setBasis={setBasis} options={[{ v: 'wow', label: 'Last week' }, { v: 'yoy', label: stage ? 'Same festive point last year' : festLY ? 'Same festival last year' : 'Same week last year' }]} />
    {scen && <p className="foot">Scenario controls are not included in this breakdown. It explains the base forecast.</p>}
    <HowEstimated fc={fc} />
  </>);
}

const agoStr = (w, days) => { const d = dt(w); d.setUTCDate(d.getUTCDate() - days); return d.getUTCFullYear() + '-' + p2(d.getUTCMonth() + 1) + '-' + p2(d.getUTCDate()); };
