import { Chart, registerables } from 'chart.js';
Chart.register(...registerables);
export { Chart };

export const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

export const tooltipBase = () => ({
  backgroundColor: css('--reiq-layer-01'), titleColor: css('--reiq-text-primary'), bodyColor: css('--reiq-text-secondary'),
  borderColor: css('--reiq-border-strong'), borderWidth: 1, padding: 10, cornerRadius: 0,
});
export const baseOptions = () => ({ responsive: true, maintainAspectRatio: false, animation: false, interaction: { mode: 'index', intersect: false } });
export const xScale = (extra = {}) => ({
  grid: { color: 'transparent' },
  ticks: { color: css('--reiq-text-secondary'), maxRotation: 0, autoSkip: true, maxTicksLimit: 9, font: { family: css('--font-sans') } },
  border: { color: css('--reiq-plot-grid') }, ...extra,
});
export const yScale = (title, fmt, extra = {}) => ({
  grid: { color: css('--reiq-plot-grid') }, border: { display: false },
  ticks: { color: css('--reiq-text-secondary'), callback: fmt, font: { family: css('--font-mono'), size: 11 } },
  title: { display: true, text: title, color: css('--reiq-text-secondary'), font: { family: css('--font-sans') } }, ...extra,
});

// vertical dashed divider with a small label (forecast start / plan start / forecast cut)
export const dividerPlugin = (id, at, text) => ({
  id,
  afterDatasetsDraw(c) {
    if (at == null || !text) return;
    const x = c.scales.x.getPixelForValue(at - 0.5); const a = c.chartArea;
    if (!isFinite(x)) return;
    const g = c.ctx; g.save();
    g.strokeStyle = css('--reiq-text-helper'); g.setLineDash([4, 4]); g.lineWidth = 1; g.beginPath(); g.moveTo(x, a.top); g.lineTo(x, a.bottom); g.stroke(); g.setLineDash([]);
    g.fillStyle = css('--reiq-text-secondary'); g.font = '12px ' + css('--font-sans'); g.textAlign = 'left'; g.fillText(text, x + 6, a.top + 14); g.restore();
  },
});
