import { useState } from 'react';

const read = () => { try { return localStorage.getItem('anviq-theme'); } catch { return null; } };
const current = () => document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');

export default function Topbar({ onBurger, expanded }) {
  const [mode, setMode] = useState(current);
  const flip = () => {
    const next = mode === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next; setMode(next);
    try { localStorage.setItem('anviq-theme', next); } catch { /* storage unavailable: choice lasts this visit */ }
  };
  return (
    <header className="topbar">
      <button className="iconbtn" aria-label="Toggle navigation" aria-expanded={expanded} onClick={onBurger}>
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 5h14M3 10h14M3 15h14" /></svg>
      </button>
      <div className="brand"><b>AnvIQ</b><span>Demand Forecasting</span></div>
      <span className="sp" />
      <button className="iconbtn" aria-label={mode === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'} title={mode === 'dark' ? 'Light theme' : 'Dark theme'} onClick={flip}>
        {mode === 'dark'
          ? <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="10" cy="10" r="3.5" /><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.3 4.3l1.4 1.4M14.3 14.3l1.4 1.4M4.3 15.7l1.4-1.4M14.3 5.7l1.4-1.4" /></svg>
          : <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M16.5 11.5A6.5 6.5 0 0 1 8.5 3.5a6.5 6.5 0 1 0 8 8z" /></svg>}
      </button>
      <span className="tag out">Synthetic data</span>
    </header>
  );
}
