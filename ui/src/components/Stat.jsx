/** One comparison figure: title, big signed percentage (with an arrow, so direction is not colour-only), the two values, and a footnote.
 *  When `onSelect` is given the block is clickable and `active` marks the comparison the factors below explain. */
export default function Stat({ title, pct, up, detail, sub, alt, active, onSelect }) {
  const pick = onSelect ? { role: 'button', tabIndex: 0, 'aria-pressed': !!active, onClick: onSelect,
    onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(); } } } : {};
  return (
    <section className={'stat' + (onSelect ? ' pick' : '') + (active ? ' active' : '')} aria-label={title} {...pick}>
      <h4>{title}</h4>
      {pct == null ? <div className="stat-n muted">—</div>
        : <div className={'stat-n ' + (up ? 'pos' : 'neg')}><span className="arrow" aria-hidden="true">{up ? '▲' : '▼'}</span>{pct}</div>}
      <div className="stat-d">{detail}</div>
      {sub && <div className="stat-s">{sub}</div>}
      {alt && <div className="stat-alt"><span>{alt.label}</span><b className={alt.up ? 'pos' : 'neg'}>{alt.up ? '▲' : '▼'} {alt.pct}</b></div>}
      {onSelect && <div className="stat-k">{active ? 'Factors below explain this change' : 'Show the factors for this'}</div>}
    </section>
  );
}
