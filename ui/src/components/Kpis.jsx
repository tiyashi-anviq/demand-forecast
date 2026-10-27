import Info from './Info.jsx';

export default function Kpis({ tiles, label }) {
  return (
    <section className="kpis" aria-label={label}>
      {tiles.map((t) => (
        <div className="kpi" key={t.l}>
          <div className="l"><span>{t.l}</span><Info text={t.i} /></div>
          <div className={'v ' + (t.cls || '')}>{t.v}</div>
          <div className="d">{t.d}</div>
        </div>
      ))}
    </section>
  );
}
