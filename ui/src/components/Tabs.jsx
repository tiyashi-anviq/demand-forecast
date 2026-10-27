import { useRef } from 'react';

/** Accessible tab bar: arrow keys move between tabs. options: [{ v, label, hint }] */
export default function Tabs({ label, value, onChange, options }) {
  const refs = useRef([]);
  const onKey = (e, i) => {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const j = (i + d + options.length) % options.length;
    onChange(options[j].v); refs.current[j]?.focus();
  };
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {options.map((o, i) => (
        <button key={o.v} ref={(el) => { refs.current[i] = el; }} role="tab" type="button" aria-selected={o.v === value} tabIndex={o.v === value ? 0 : -1}
          className="tab" onClick={() => onChange(o.v)} onKeyDown={(e) => onKey(e, i)}>
          <span>{o.label}</span>{o.hint && <small>{o.hint}</small>}
        </button>
      ))}
    </div>
  );
}
