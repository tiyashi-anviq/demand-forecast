export function Seg({ id, label, value, onChange, options }) {
  return (
    <div className="field">
      <span className="lab" id={id + '-l'}>{label}</span>
      <SegBare labelledby={id + '-l'} value={value} onChange={onChange} options={options} />
    </div>
  );
}
export function SegBare({ labelledby, ariaLabel, value, onChange, options }) {
  return (
    <div className="seg" role="radiogroup" aria-labelledby={labelledby} aria-label={ariaLabel}>
      {options.map((o) => (
        <button key={o.v} role="radio" aria-checked={o.v === value} disabled={o.disabled} title={o.title} onClick={() => onChange(o.v)}>{o.label}</button>
      ))}
    </div>
  );
}
export function Select({ id, label, value, onChange, options }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o.v} value={o.v}>{o.label}</option>)}
      </select>
    </div>
  );
}
