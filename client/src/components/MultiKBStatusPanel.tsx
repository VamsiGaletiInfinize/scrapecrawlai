import type { MultiKBCrawlStatus, KBCrawlState } from '../types';

interface MultiKBStatusPanelProps {
  status: MultiKBCrawlStatus | null;
  elapsedTime: number;
}

export function MultiKBStatusPanel({ status, elapsedTime }: MultiKBStatusPanelProps) {
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
      case 'pending': return '#6b7280';
      case 'skipped': return '#f59e0b';
      default: return '#6b7280';
    }
  };

  const getKBStateIcon = (state: KBCrawlState) => {
    switch (state) {
      case 'running': return '⏳';
      case 'completed': return '✅';
      case 'failed': return '❌';
      case 'pending': return '⏸️';
      case 'skipped': return '⏭️';
      default: return '⏸️';
    }
  };

  const overallProgress = status.total_urls_discovered > 0
    ? Math.round((status.total_urls_processed / status.total_urls_discovered) * 100)
    : 0;

  const kbProgress = status.total_kbs > 0
    ? Math.round((status.kbs_completed / status.total_kbs) * 100)
    : 0;

  return (
    <div className="status-panel multi-kb-status">
      <div className="status-header">
        <div className="status-indicator" style={{ backgroundColor: getStateColor(status.state) }}>
          {status.state.toUpperCase()}
        </div>
        <div className="elapsed-time">
          <span className="time-label">Elapsed:</span>
          <span className="time-value">{formatTime(elapsedTime)}</span>
        </div>
      </div>

      {/* Overall Progress */}
      <div className="overall-progress-section">
        <h4>Overall Progress</h4>
        <div className="status-grid">
          <div className="status-item">
            <span className="stat-label">KBs Progress</span>
            <span className="stat-value">
              {status.kbs_completed} / {status.total_kbs}
            </span>
          </div>
          <div className="status-item">
            <span className="stat-label">URLs Discovered</span>
            <span className="stat-value">{status.total_urls_discovered}</span>
          </div>
          <div className="status-item">
            <span className="stat-label">URLs Processed</span>
            <span className="stat-value">{status.total_urls_processed}</span>
          </div>
          <div className="status-item">
            <span className="stat-label">Out of Scope</span>
            <span className="stat-value out-of-scope">{status.total_urls_out_of_scope}</span>
          </div>
        </div>

        {status.state === 'running' && (
          <div className="progress-section">
            <div className="progress-info">
              <span>KB Completion</span>
              <span>{kbProgress}%</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill kb-progress" style={{ width: `${kbProgress}%` }} />
            </div>
            <div className="progress-info">
              <span>URL Progress</span>
              <span>{overallProgress}%</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill url-progress" style={{ width: `${overallProgress}%` }} />
            </div>
          </div>
        )}
      </div>

      {/* KB Status Summary */}
      <div className="kb-status-summary">
        <div className="kb-status-item">
          <span className="kb-status-icon">⏸️</span>
          <span className="kb-status-count">{status.kbs_pending}</span>
          <span className="kb-status-label">Pending</span>
        </div>
        <div className="kb-status-item running">
          <span className="kb-status-icon">⏳</span>
          <span className="kb-status-count">{status.kbs_running}</span>
          <span className="kb-status-label">Running</span>
        </div>
        <div className="kb-status-item completed">
          <span className="kb-status-icon">✅</span>
          <span className="kb-status-count">{status.kbs_completed}</span>
          <span className="kb-status-label">Completed</span>
        </div>
        <div className="kb-status-item failed">
          <span className="kb-status-icon">❌</span>
          <span className="kb-status-count">{status.kbs_failed}</span>
          <span className="kb-status-label">Failed</span>
        </div>
      </div>

      {/* Per-KB Progress */}
      <div className="per-kb-progress">
        <h4>Knowledge Base Progress</h4>
        <div className="kb-progress-list">
          {status.knowledge_bases.map((kb) => {
            const kbUrlProgress = kb.urls_discovered > 0
              ? Math.round((kb.urls_processed / kb.urls_discovered) * 100)
              : 0;

            return (
              <div key={kb.kb_id} className={`kb-progress-item ${kb.state}`}>
                <div className="kb-progress-header">
                  <span className="kb-state-icon">{getKBStateIcon(kb.state)}</span>
                  <span className="kb-name">{kb.kb_name}</span>
                  <span className="kb-state-badge" style={{ backgroundColor: getStateColor(kb.state) }}>
                    {kb.state}
                  </span>
                </div>

                <div className="kb-progress-stats">
                  <div className="kb-stat">
                    <span className="kb-stat-label">URLs</span>
                    <span className="kb-stat-value">{kb.urls_processed} / {kb.urls_discovered}</span>
                  </div>
                  <div className="kb-stat">
                    <span className="kb-stat-label">Depth</span>
                    <span className="kb-stat-value">{kb.current_depth} / {kb.max_depth}</span>
                  </div>
                  <div className="kb-stat">
                    <span className="kb-stat-label">Scraped</span>
                    <span className="kb-stat-value">{kb.pages_scraped}</span>
                  </div>
                  <div className="kb-stat">
                    <span className="kb-stat-label">Out of Scope</span>
                    <span className="kb-stat-value out-of-scope">{kb.urls_skipped_out_of_scope}</span>
                  </div>
                </div>

                {kb.state === 'running' && (
                  <div className="kb-progress-bar-container">
                    <div className="progress-bar small">
                      <div className="progress-fill" style={{ width: `${kbUrlProgress}%` }} />
                    </div>
                    <span className="progress-text">{kbUrlProgress}%</span>
                  </div>
                )}

                {kb.error && (
                  <div className="kb-error">
                    <strong>Error:</strong> {kb.error}
                  </div>
                )}

                {kb.state === 'completed' && (
                  <div className="kb-completed-stats">
                    <span>
                      {kb.pages_scraped} pages scraped
                      {kb.pages_failed > 0 && `, ${kb.pages_failed} failed`}
                    </span>
                    <span className="kb-duration">{formatTime(kb.duration_ms)}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {status.error && (
        <div className="error-message">
          <strong>Error:</strong> {status.error}
        </div>
      )}
    </div>
  );
}
