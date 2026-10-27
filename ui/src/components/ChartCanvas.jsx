import { useEffect, useRef } from 'react';
import { Chart } from '../lib/chart.js';

// Builds a Chart.js chart from `config` (memoise it in the parent) and rebuilds when the config changes
export default function ChartCanvas({ config, height, label, style }) {
  const ref = useRef(null);
  useEffect(() => {
    const ch = new Chart(ref.current, config);
    return () => ch.destroy();
  }, [config]);
  return (
    <div className="chartbox" style={{ ...(height ? { height } : {}), ...style }}>
      <canvas ref={ref} role="img" aria-label={label} />
    </div>
  );
}
