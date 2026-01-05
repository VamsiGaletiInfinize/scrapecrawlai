import type { TimingMetrics } from '../types';

interface TimingBreakdownProps {
  timing: TimingMetrics;
}

export function TimingBreakdown({ timing }: TimingBreakdownProps) {
  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(2)}ms`;
    return `${(ms / 1000).toFixed(3)}s`;
  };

  const categories = [
    {
      label: 'URL Discovery',
      value: timing.url_discovery_ms,
      pct: timing.url_discovery_pct ?? (timing.total_ms > 0 ? (timing.url_discovery_ms / timing.total_ms) * 100 : 0),
      color: '#8b5cf6',
    },
    {
      label: 'Crawling',
      value: timing.crawling_ms,
      pct: timing.crawling_pct ?? (timing.total_ms > 0 ? (timing.crawling_ms / timing.total_ms) * 100 : 0),
      color: '#3b82f6',
    },
    {
      label: 'Scraping',
      value: timing.scraping_ms,
      pct: timing.scraping_pct ?? (timing.total_ms > 0 ? (timing.scraping_ms / timing.total_ms) * 100 : 0),
      color: '#10b981',
    },
  ];

  return (
    <div className="timing-breakdown">
      <h3>Timing Breakdown</h3>

      <div className="timing-total">
        <span className="total-label">Total Execution Time</span>
        <span className="total-value">{formatTime(timing.total_ms)}</span>
      </div>

      <div className="timing-bar">
        {categories.map((cat) => (
          <div
            key={cat.label}
            className="timing-segment"
            style={{
              width: `${cat.pct}%`,
              backgroundColor: cat.color,
            }}
            title={`${cat.label}: ${formatTime(cat.value)} (${cat.pct.toFixed(1)}%)`}
          />
        ))}
      </div>

      <div className="timing-legend">
        {categories.map((cat) => (
          <div key={cat.label} className="legend-item">
            <div className="legend-color" style={{ backgroundColor: cat.color }} />
            <div className="legend-details">
              <span className="legend-label">{cat.label}</span>
              <span className="legend-value">{formatTime(cat.value)}</span>
              <span className="legend-pct">({cat.pct.toFixed(1)}%)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
