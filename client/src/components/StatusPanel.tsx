import { useEffect, useState } from 'react';
import type { CrawlStatus } from '../types';

interface StatusPanelProps {
  status: CrawlStatus | null;
  elapsedTime: number;
}

export function StatusPanel({ status, elapsedTime }: StatusPanelProps) {
  if (!status) return null;

  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const getStateColor = (state: string) => {
    switch (state) {
      case 'running': return '#3b82f6';
      case 'completed': return '#10b981';
      case 'failed': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const progress = status.urls_discovered > 0
    ? Math.round((status.urls_processed / status.urls_discovered) * 100)
    : 0;

  return (
    <div className="status-panel">
      <div className="status-header">
        <div className="status-indicator" style={{ backgroundColor: getStateColor(status.state) }}>
          {status.state.toUpperCase()}
        </div>
        <div className="elapsed-time">
          <span className="time-label">Elapsed:</span>
          <span className="time-value">{formatTime(elapsedTime)}</span>
        </div>
      </div>

      <div className="status-grid">
        <div className="status-item">
          <span className="stat-label">URLs Discovered</span>
          <span className="stat-value">{status.urls_discovered}</span>
        </div>
        <div className="status-item">
          <span className="stat-label">URLs Processed</span>
          <span className="stat-value">{status.urls_processed}</span>
        </div>
        <div className="status-item">
          <span className="stat-label">Current Depth</span>
          <span className="stat-value">{status.current_depth} / {status.max_depth}</span>
        </div>
        <div className="status-item">
          <span className="stat-label">Workers</span>
          <span className="stat-value">{status.worker_count}</span>
        </div>
      </div>

      {status.state === 'running' && (
        <div className="progress-section">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="progress-text">{progress}%</span>
        </div>
      )}

      {status.urls_by_depth.length > 0 && (
        <div className="depth-breakdown">
          <h4>URLs by Depth</h4>
          <div className="depth-list">
            {status.urls_by_depth.map((d) => (
              <div key={d.depth} className="depth-item">
                <span className="depth-label">Depth {d.depth}</span>
                <span className="depth-count">{d.count} URLs</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {status.error && (
        <div className="error-message">
          <strong>Error:</strong> {status.error}
        </div>
      )}
    </div>
  );
}
