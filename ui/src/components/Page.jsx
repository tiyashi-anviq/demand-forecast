import { useApp } from '../context.js';
import { SegBare, Select } from './Controls.jsx';
import { scenName, BASE } from '../lib/scenario.js';

/** Page header (crumbs, title, tags) + the shared filter toolbar. `extra` renders screen-specific filters. */
export default function Page({ crumb, title, sub, tags, tabs, extra, showMeasure = true, showFilters = true, catFilter, prodFilter, scenario, children, bodyClass = '' }) {
  const { D, level, cat, prod, mea, setFilter, pulse, lev, applyLev, setDrawerOpen } = useApp();
  const sn = scenario ? scenName(lev) : null;
  const L = D.levels[level];
  const cats = catFilter ? L.cats.filter(catFilter) : L.cats;
  const prods = L.products.filter((p) => (!cat || p.cat === cat) && (!prodFilter || prodFilter(p)));
  return (
    <>
      <div className="head">
        <div className="crumbs"><span>Demand Forecasting</span><span aria-hidden="true">/</span><span>Plan</span><span aria-hidden="true">/</span><span className="cur" aria-current="page">{crumb}</span></div>
        <div className="title-row"><h1 className="module-page-title">{title}</h1>{scenario && <button className="btn" onClick={() => setDrawerOpen(true)}>Scenario controls</button>}</div>
        <p className="module-page-subtitle">{sub}</p>
        <div className="tags">{tags}{sn && <span className="tag scen">Scenario: {sn}<button onClick={() => applyLev(BASE)} aria-label="Clear scenario">×</button></span>}</div>
        {tabs}
        <div className="ctl" role="group" aria-label="Filters">
          {showFilters && <>
          <Select id="cat" label="Category" value={cat} onChange={(v) => setFilter({ cat: v, prod: '' })}
            options={[{ v: '', label: 'All categories' }, ...cats.map((c) => ({ v: c, label: c }))]} />
          <Select id="prod" label="Product" value={prod} onChange={(v) => setFilter({ prod: v })}
            options={[{ v: '', label: 'All products' }, ...prods.map((p) => ({ v: p.code, label: p.name }))]} />
          <div className="field"><span className="lab" id="lvl-l">Level</span>
            <SegBare labelledby="lvl-l" value={level} onChange={(v) => setFilter({ level: v, cat: '', prod: '' })}
              options={['National', 'Kolkata depots'].map((l) => ({ v: l, label: l, disabled: !D.levels[l], title: D.levels[l] ? undefined : 'Depot-level forecast not available' }))} />
          </div>
          </>}
          {extra}
          {showMeasure && (
            <div className="field"><span className="lab" id="mea-l">Measure</span>
              <SegBare labelledby="mea-l" value={mea} onChange={(v) => setFilter({ mea: v })} options={[{ v: 'u', label: 'Units' }, { v: 'v', label: 'Value (₹)' }]} /></div>
          )}
        </div>
      </div>
      <div className={'body pulse-refresh ' + bodyClass} key={pulse}>{children}</div>
    </>
  );
}

export const Empty = ({ title, text }) => <div className="empty"><b>{title}</b><span>{text}</span></div>;
