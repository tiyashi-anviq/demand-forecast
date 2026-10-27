export default function Legend({ series, hidden, onToggle }) {
  return (
    <div className="legendrow" role="group" aria-label="Show or hide lines">
      {series.map((s) => (
        <button key={s.k} type="button" aria-pressed={!hidden[s.k]} style={{ color: `var(${s.col})` }} onClick={() => onToggle(s.k)}>
          <span className={'sw ' + s.cls} /><span style={{ color: 'var(--reiq-text-secondary)' }}>{s.name}</span>
        </button>
      ))}
    </div>
  );
}
