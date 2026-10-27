import { weekShare } from './Drivers.jsx';

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], DAY = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const add = (iso, n) => { const d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d; };
const key = (d) => d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0');
const short = (d) => d.getUTCDate() + ' ' + MON[d.getUTCMonth()];

/** The weeks that count towards month m, drawn as seven day cells each. A week that straddles two months is split by days:
 *  shaded days count towards this month. `weeks` = Monday dates (ISO) from the data. */
export default function WeekMap({ weeks, m }) {
  const mine = weeks.filter((w) => weekShare(w, m) > 0);
  if (!mine.length) return null;
  const name = MON[+m.slice(5, 7) - 1];
  return (
    <details className="wmap">
      <summary>How weeks count towards {name}</summary>
      <p>Each week is labelled by its Monday. A week that straddles two months is split by days, so only the shaded days count towards {name}. {name} has <b>{mine.reduce((t, w) => t + weekShare(w, m), 0).toFixed(1)} weeks</b> of days.</p>
      <div className="wmap-grid" role="table" aria-label={'Weeks counted in ' + name}>
        <div className="wmap-row wmap-head" role="row"><span role="columnheader">Week</span>{DAY.map((d) => <span key={d} role="columnheader">{d}</span>)}<span role="columnheader">Counts as</span></div>
        {mine.map((w) => {
          const days = DAY.map((_, i) => add(w, i)), inM = days.filter((d) => key(d) === m).length;
          return (
            <div className="wmap-row" role="row" key={w}>
              <span className="wk" role="cell">{short(days[0])} – {short(days[6])}</span>
              {days.map((d, i) => <span key={i} role="cell" className={'wd' + (key(d) === m ? ' in' : '')} title={d.toUTCString().slice(0, 16)}>{d.getUTCDate()}</span>)}
              <span className="cnt" role="cell"><b>{name}</b> <small>{inM} of 7 days</small></span>
            </div>
          );
        })}
      </div>
    </details>
  );
}
