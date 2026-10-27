import { useCallback, useEffect, useMemo, useState } from 'react';
import { AppCtx } from './context.js';
import { useApi } from './lib/api.js';
import Topbar from './components/Topbar.jsx';
import Rail from './components/Rail.jsx';
import Forecast from './screens/Forecast.jsx';
import Challenge from './screens/Challenge.jsx';
import Weather from './screens/Weather.jsx';
import QuickCommerce from './screens/QuickCommerce.jsx';
import NewProducts from './screens/NewProducts.jsx';
import { BASE } from './lib/scenario.js';

const SCREENS = { fc: Forecast, ch: Challenge, wx: Weather, qc: QuickCommerce, np: NewProducts };
const SLUG = { fc: 'forecast', ch: 'challenge', wx: 'weather', qc: 'quick-commerce', np: 'new-products' };
const BY_SLUG = Object.fromEntries(Object.entries(SLUG).map(([k, v]) => [v, k]));

// route lives in the URL hash, e.g. #/forecast?view=monthly, so refresh, back and shared links work
function parseHash() {
  const [path, query = ''] = window.location.hash.replace(/^#\/?/, '').split('?');
  return { screen: BY_SLUG[path] || 'fc', view: new URLSearchParams(query).get('view') || '' };
}

export default function App() {
  const { data: D, error } = useApi('/api/forecast');
  const [route, setRoute] = useState(parseHash);
  const screen = route.screen;
  const [f, setF] = useState({ level: 'National', cat: '', prod: '', mea: 'u' });
  const [ss, setSs] = useState({});          // per-screen state, kept when you switch screens
  const [pulse, setPulse] = useState(0);     // bumps on filter changes for the refresh animation
  const [theme, setTheme] = useState(0);     // bumps on colour-scheme change so charts re-read tokens
  const [lev, setLev] = useState(BASE);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [railCollapsed, setRailCollapsed] = useState(false);

  useEffect(() => {
    const onHash = () => { setRoute(parseHash()); document.getElementById('content')?.scrollTo(0, 0); };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const navigate = useCallback((s, opts = {}) => {
    window.location.hash = '/' + SLUG[s] + (opts.view ? '?view=' + opts.view : '');
  }, []);

  useEffect(() => {
    const bump = () => setTimeout(() => setTheme((t) => t + 1), 50);
    const mq = matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener?.('change', bump);
    const mo = new MutationObserver(bump);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => { mq.removeEventListener?.('change', bump); mo.disconnect(); };
  }, []);

  const setFilter = useCallback((patch) => { setF((p) => ({ ...p, ...patch })); setPulse((n) => n + 1); }, []);
  const useSS = useCallback((key, init) => {
    const val = ss[key] === undefined ? init : ss[key];
    const set = (v) => { setSs((p) => ({ ...p, [key]: typeof v === 'function' ? v(p[key] === undefined ? init : p[key]) : v })); setPulse((n) => n + 1); };
    return [val, set];
  }, [ss]);

  const applyLev = useCallback((l) => { setLev(l); setPulse((n) => n + 1); }, []);
  const nodeKey = f.prod ? 'sku:' + f.prod : f.cat ? 'cat:' + f.cat : 'ALL';
  const ctx = useMemo(() => ({ D, ...f, setFilter, nodeKey, theme, pulse, useSS, screen, route, navigate, lev, applyLev, drawerOpen, setDrawerOpen }), [D, f, setFilter, nodeKey, theme, pulse, useSS, screen, route, navigate, lev, applyLev, drawerOpen]);
  const Screen = SCREENS[screen];

  return (
    <div className="app">
      <Topbar onBurger={() => {
        if (matchMedia('(max-width:671px)').matches) setRailOpen((o) => !o); else setRailCollapsed((c) => !c);
      }} expanded={railOpen || !railCollapsed} />
      <div className="shell">
        <Rail screen={screen} open={railOpen} collapsed={railCollapsed}
          onSelect={(s) => { navigate(s); setRailOpen(false); }} />
        <div className={'scrim' + (railOpen ? ' open' : '')} onClick={() => setRailOpen(false)} />
        <main className="content" id="content">
          <div className="page">
            {error && <div className="empty"><b>Could not reach the API</b><span>{error}. Start it with <code>uvicorn app.main:app</code> in the api folder.</span></div>}
            {!error && !D && <div className="empty"><b>Loading forecast data</b><span>Fetching from the API…</span></div>}
            {D && <AppCtx.Provider value={ctx}><Screen /></AppCtx.Provider>}
          </div>
        </main>
      </div>
    </div>
  );
}
