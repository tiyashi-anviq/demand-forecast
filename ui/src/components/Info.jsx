import { useEffect, useLayoutEffect, useRef, useState } from 'react';

// Toggletip: (i) button opening a popover. `text` is a string, or { what, how, read }
// (what it is, how it is worked out, how to read it). Closes on outside click or Escape;
// flips to stay inside the viewport.
export default function Info({ text }) {
  const [open, setOpen] = useState(false);
  const [shift, setShift] = useState(0);
  const pop = useRef(null);
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const key = (e) => e.key === 'Escape' && close();
    document.addEventListener('click', close); document.addEventListener('keydown', key);
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', key); };
  }, [open]);
  useLayoutEffect(() => {
    if (!open || !pop.current) { setShift(0); return; }
    const r = pop.current.getBoundingClientRect(), m = 12;
    const base = r.left - shift;
    setShift(base + r.width > window.innerWidth - m ? window.innerWidth - m - r.width - base : Math.max(0, m - base));
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const rows = typeof text === 'string' ? [[null, text]] : [['What it is', text.what], ['How it is worked out', text.how], ['How to read it', text.read]].filter((r) => r[1]);
  return (
    <button type="button" className="info" aria-expanded={open} aria-label="About this figure"
      onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}>
      i{open && (
        <span className="pop" role="status" ref={pop} style={{ left: shift }} onClick={(e) => e.stopPropagation()}>
          {rows.map(([h, t]) => <span className="pr" key={h || 'x'}>{h && <b>{h}</b>}{t}</span>)}
        </span>
      )}
    </button>
  );
}
