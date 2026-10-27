import { useEffect, useMemo, useRef, useState } from 'react';
import { useApp } from '../context.js';
import { useApi } from '../lib/api.js';
import { PRESETS, BASE, isBase, presetOf, festFlags, applyScenario } from '../lib/scenario.js';
import { fCr, fS, sum } from '../lib/format.js';

const LEVERS = [
  { k: 'shift', label: 'Overall demand', min: -20, max: 20, step: 1, text: (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v) + '%', help: 'Moves every forecast week up or down by the same percentage.' },
  { k: 'fest', label: 'Festive weeks', min: -30, max: 30, step: 1, text: (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v) + '%', help: 'Extra change in weeks that fall in a festival or its sell-in period.' },
  { k: 'avail', label: 'Supply availability', min: 80, max: 100, step: 1, text: (v) => v + '%', help: 'Share of demand the plants can ship. Shows as a separate line; demand itself does not change.' },
];

/** Right-hand panel: edit a draft, nothing changes on the page until Apply (draft-then-apply). */
export default function ScenarioDrawer() {
  const { D, level, nodeKey, mea, lev, applyLev, drawerOpen, setDrawerOpen } = useApp();
  return drawerOpen ? <Body key="open" {...{ D, level, nodeKey, mea, lev, applyLev, close: () => setDrawerOpen(false) }} /> : null;
}

function Body({ D, level, nodeKey, mea, lev, applyLev, close }) {
  const [draft, setDraft] = useState(lev);
  const first = useRef(null);
  const { data: DR } = useApi('/api/drivers?level=' + encodeURIComponent(level));
  useEffect(() => { first.current?.focus(); const k = (e) => { if (e.key === 'Escape') close(); }; window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k); }, [close]);
  const n = D.levels[level].nodes[nodeKey]?.[mea], HN = D.histN;
  const fw = useMemo(() => festFlags(DR, D.weeks), [DR, D.weeks]);
  const base = n ? sum(n.model.slice(HN)) : 0;
  const tot = (l) => (n ? sum(applyScenario(n, l, fw, HN).model.slice(HN)) : 0);
  const t = tot(draft), dirty = JSON.stringify(draft) !== JSON.stringify(lev), pre = presetOf(draft);
  const unit = mea === 'v' ? '₹' : 'units';
  return (
    <aside className="drawer" role="dialog" aria-label="Scenario controls">
      <div className="drawer-h"><h2>Scenario controls</h2><button className="x" onClick={close} aria-label="Close scenario controls">×</button></div>
      <div className="drawer-b">
        <p className="foot">Scenarios scale the forecast weeks of the weekly outlook. The models are not re-run.</p>
        <h3>Presets</h3>
        <div className="presets">
          {PRESETS.map((p, i) => (
            <button key={p.id} ref={i === 0 ? first : null} className={'preset' + (pre?.id === p.id ? ' on' : '')} aria-pressed={pre?.id === p.id} onClick={() => setDraft(p.lev)}>
              <b>{p.name}</b><span>{p.desc}</span>
            </button>
          ))}
        </div>
        <h3>Levers</h3>
        {LEVERS.map((L) => (
          <div className="lever" key={L.k}>
            <div className="lever-t"><label htmlFor={'lv-' + L.k}>{L.label}</label><b>{L.text(draft[L.k])}</b></div>
            <input id={'lv-' + L.k} type="range" min={L.min} max={L.max} step={L.step} value={draft[L.k]} onChange={(e) => setDraft({ ...draft, [L.k]: +e.target.value })}
              aria-valuetext={L.text(draft[L.k])} />
            <span className="foot">{L.help}</span>
          </div>
        ))}
        <h3>Impact on this selection</h3>
        <div className="impact">
          <div><span>Base case</span><b>{fCr(base)}</b></div>
          <div><span>With these levers</span><b>{fCr(t)}</b>{base ? <em className={t >= base ? 'pos' : 'neg'}>{t >= base ? '▲' : '▼'} {fS(t / base - 1)}</em> : null}</div>
          {draft.avail < 100 && <div><span>Shippable</span><b>{fCr(t * draft.avail / 100)}</b></div>}
        </div>
        <span className="foot">Next 26 weeks, {unit}, for the filters on the page.</span>
      </div>
      <div className="drawer-f">
        <button className="btn primary" disabled={!dirty} onClick={() => { applyLev(draft); close(); }}>Apply</button>
        <button className="btn" disabled={JSON.stringify(draft) === JSON.stringify(BASE)} onClick={() => setDraft(BASE)}>Reset</button>
      </div>
    </aside>
  );
}
