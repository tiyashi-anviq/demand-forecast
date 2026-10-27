const ICON = {
  overview: 'M2 2h5v5H2zM9 2h5v5H9zM2 9h5v5H2zM9 9h5v5H9z', forecast: 'M2 13l4-5 3 3 5-7M2 14h12',
  qc: 'M2 3h2l1.5 7h7L14 5H5M6.5 13.5a.5.5 0 100-1 .5.5 0 000 1zM11.5 13.5a.5.5 0 100-1 .5.5 0 000 1z',
  wx: 'M4 11a3 3 0 010-6 4 4 0 017.5 1A2.5 2.5 0 0112 11zM6 13l-1 2M9 13l-1 2M12 13l-1 2', chal: 'M3 2v12M3 3h9l-2 3 2 3H3',
  vint: 'M2 3v10h12M4 11l3-4 2 2 4-5M4 12l3-2 2 1 4-3', newp: 'M8 2v12M2 8h12', supply: 'M2 5l6-3 6 3v6l-6 3-6-3zM2 5l6 3 6-3M8 8v6',
  channels: 'M2 4h12M2 8h12M2 12h12', guide: 'M8 2a6 6 0 100 12A6 6 0 008 2zM6.5 6.5a1.6 1.6 0 113 .5c0 1-1.5 1.2-1.5 2.3M8 11.5v.1',
};
// [label, icon, screen key when built]
export const SECTIONS = [
  ['Plan', [['Overview', 'overview'], ['Forecast & accuracy', 'forecast', 'fc'], ['Forecast challenge', 'chal', 'ch'],
    ['Weather & shocks', 'wx', 'wx'], ['Quick commerce', 'qc', 'qc'], ['New products', 'newp', 'np']]],
  ['Operate', [['Supply & inventory', 'supply'], ['Channels & events', 'channels']]],
  ['Assist', [['Guide', 'guide']]],
];

export default function Rail({ screen, open, collapsed, onSelect }) {
  return (
    <nav className={'rail' + (open ? ' open' : '') + (collapsed ? ' collapsed' : '')} aria-label="Screens">
      {SECTIONS.map(([sec, items]) => (
        <div key={sec} style={{ display: 'contents' }}>
          <div className="sec">{sec}</div>
          {items.map(([name, ic, key]) => (
            <a key={name} href="#" className={key === screen ? 'active' : ''} aria-current={key === screen ? 'page' : undefined}
              aria-disabled={key ? undefined : 'true'} title={key ? undefined : 'Not built yet'}
              onClick={(e) => { e.preventDefault(); if (key) onSelect(key); }}>
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="square"><path d={ICON[ic]} /></svg>
              <span className="lbl">{name}</span>
            </a>
          ))}
        </div>
      ))}
    </nav>
  );
}
