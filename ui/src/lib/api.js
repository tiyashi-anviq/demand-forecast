import { useEffect, useState } from 'react';

const cache = new Map();

/** GET a JSON endpoint once and keep it for the session. Pass null to skip. */
export function useApi(url) {
  const [state, setState] = useState(() => ({ data: url ? cache.get(url) : undefined, error: null }));
  useEffect(() => {
    if (!url) { setState({ data: undefined, error: null }); return; }
    if (cache.has(url)) { setState({ data: cache.get(url), error: null }); return; }
    let live = true;
    setState({ data: undefined, error: null });
    fetch(url)
      .then((r) => { if (!r.ok) throw new Error(`${r.status} ${r.statusText}`); return r.json(); })
      .then((d) => { cache.set(url, d); if (live) setState({ data: d, error: null }); })
      .catch((e) => live && setState({ data: undefined, error: e.message }));
    return () => { live = false; };
  }, [url]);
  return state;
}
