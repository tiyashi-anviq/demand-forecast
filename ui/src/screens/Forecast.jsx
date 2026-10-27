import { useApp } from '../context.js';
import { useApi } from '../lib/api.js';
import Page, { Empty } from '../components/Page.jsx';
import Tabs from '../components/Tabs.jsx';
import { Select } from '../components/Controls.jsx';
import WeeklyView from './WeeklyView.jsx';
import ScenarioDrawer from '../components/ScenarioDrawer.jsx';
import { isBase } from '../lib/scenario.js';
import MonthlyView from './MonthlyView.jsx';
import { labFull } from '../lib/format.js';

const TABS = [
  { v: 'weekly', label: 'Weekly outlook', hint: 'Every week to March 2027' },
  { v: 'monthly', label: 'Monthly runs (M3 · M2 · M1)', hint: 'Each month against actuals and the sales team' },
];

export default function Forecast() {
  const { level, route, navigate, useSS, lev } = useApp();
  const view = route.view === 'monthly' ? 'monthly' : 'weekly';
  const { data: VA } = useApi('/api/vintages');
  const V = VA?.levels[level];
  const { data: FD } = useApi('/api/forecast?level=' + encodeURIComponent(level));
  const fcFrom = FD?.weeks?.[FD.histN];   // first forecast week, read from the data
  const [vm, setVm] = useSS('fc.vm', '2026-11');
  const [, setCmpOpen] = useSS('vt.cmp', false);
  const [run, setRun] = useSS('vt.run', 'm3');   // which run the monthly view shows; M3 by default

  const head = view === 'weekly'
    ? { sub: "Weekly primary sales, the model's outlook to the end of March 2027, and how it compares with the sales team and budget up to the last actuals. After that, only the model forecast.",
        tags: <><span className="tag">Model: seasonal naive + ETS + LightGBM</span><span className="tag out">{fcFrom ? 'From ' + labFull(fcFrom) + ': model forecast only' : 'Model forecast only after the last actuals'}</span></> }
    : { sub: 'The M3, M2 and M1 runs of the model for each month, against actuals and the sales team. Future months fill in as each month closes.',
        tags: <><span className="tag">Runs retrained at each month-end</span><span className="tag out">National and Kolkata depots</span></> };
  const tabs = <Tabs label="Forecast views" value={view} onChange={(v) => navigate('fc', { view: v })} options={TABS} />;
  const extra = view === 'monthly' && V
    ? <><Select id="vr" label="Run" value={run} onChange={setRun} options={[{ v: 'm3', label: 'M3 (3 months ahead)' }, { v: 'm2', label: 'M2 (2 months ahead)' }, { v: 'm1', label: 'M1 (1 month ahead)' }]} />
      <Select id="vm" label="Target month" value={vm} onChange={(x) => { setVm(x); setCmpOpen(true); }} options={V.months.map((x) => ({ v: x.m, label: x.label + (x.complete ? '' : ' (open)') }))} /></>
    : null;

  return (
    <Page crumb="Forecast & accuracy" title="Forecast & accuracy" {...head} tabs={tabs} extra={extra} scenario>
      <ScenarioDrawer />
      {view === 'monthly' && !isBase(lev) && <p className="callout"><b>A scenario is applied to the weekly outlook.</b> The monthly runs show the model as it made each forecast, without scenario controls.</p>}
      {view === 'weekly' && <WeeklyView />}
      {view === 'monthly' && (V ? <MonthlyView V={V} vm={vm} onPick={setVm} run={run} /> : <Empty title="Loading monthly runs" text="Fetching from the API…" />)}
    </Page>
  );
}
