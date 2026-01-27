import { useState } from 'react';
import type { MultiKBCrawlResult, KBCrawlResult, KBPageResult } from '../types';
import { getMultiKBDownloadUrl, getKBDownloadUrl } from '../services/api';

interface MultiKBResultsDashboardProps {
  results: MultiKBCrawlResult;
}

interface KBResultsSectionProps {
  kbResult: KBCrawlResult;
  jobId: string;
  isExpanded: boolean;
  onToggle: () => void;
}

function KBResultsSection({ kbResult, jobId, isExpanded, onToggle }: KBResultsSectionProps) {
  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const handleDownload = (format: 'json' | 'markdown') => {
    window.open(getKBDownloadUrl(jobId, kbResult.kb_id, format), '_blank');
  };

  const getStateColor = (state: string) => {
    switch (state) {
      case 'completed': return '#10b981';
      case 'failed': return '#ef4444';
      case 'skipped': return '#f59e0b';
      default: return '#6b7280';
    }
  };

  const getStateIcon = (state: string) => {
    switch (state) {
      case 'completed': return '✅';
      case 'failed': return '❌';
      case 'skipped': return '⏭️';
      default: return '⏸️';
    }
  };

  return (
    <div className={`kb-results-section ${kbResult.state}`}>
      <div className="kb-results-header" onClick={onToggle}>
        <div className="kb-header-left">
          <span className="kb-expand-icon">{isExpanded ? '▼' : '▶'}</span>
          <span className="kb-state-icon">{getStateIcon(kbResult.state)}</span>
          <span className="kb-name">{kbResult.kb_name}</span>
          <span
            className="kb-state-badge"
            style={{ backgroundColor: getStateColor(kbResult.state) }}
          >
            {kbResult.state}
          </span>
        </div>
        <div className="kb-header-right">
          <span className="kb-stat">{kbResult.pages_scraped} scraped</span>
          <span className="kb-stat">{kbResult.pages_failed} failed</span>
          <span className="kb-stat">{formatTime(kbResult.duration_ms)}</span>
        </div>
      </div>

      {isExpanded && (
        <div className="kb-results-content">
          <div className="kb-download-buttons">
            <button onClick={() => handleDownload('json')} className="download-btn json small">
              Download JSON
            </button>
            <button onClick={() => handleDownload('markdown')} className="download-btn markdown small">
              Download Markdown
            </button>
          </div>

          <div className="kb-summary-grid">
            <div className="kb-summary-card">
              <span className="summary-value">{kbResult.urls_discovered}</span>
              <span className="summary-label">URLs Discovered</span>
            </div>
            <div className="kb-summary-card">
              <span className="summary-value">{kbResult.urls_processed}</span>
              <span className="summary-label">URLs Processed</span>
            </div>
            <div className="kb-summary-card">
              <span className="summary-value out-of-scope">{kbResult.urls_out_of_scope}</span>
              <span className="summary-label">Out of Scope</span>
            </div>
            <div className="kb-summary-card">
              <span className="summary-value">{kbResult.pages_scraped}</span>
              <span className="summary-label">Pages Scraped</span>
            </div>
            <div className="kb-summary-card">
              <span className="summary-value">{kbResult.pages_crawled}</span>
              <span className="summary-label">Pages Crawled</span>
            </div>
            <div className="kb-summary-card error">
              <span className="summary-value">{kbResult.pages_failed}</span>
              <span className="summary-label">Failed</span>
            </div>
          </div>

          <div className="kb-entry-urls">
            <h5>Entry URLs</h5>
            <ul>
              {kbResult.entry_urls.map((url, idx) => (
                <li key={idx}>
                  <a href={url} target="_blank" rel="noopener noreferrer">{url}</a>
                </li>
              ))}
            </ul>
          </div>

          <div className="kb-allowed-prefixes">
            <h5>Allowed Prefixes</h5>
            <ul>
              {kbResult.allowed_prefixes.map((prefix, idx) => (
                <li key={idx}><code>{prefix}</code></li>
              ))}
            </ul>
          </div>

          {kbResult.error && (
            <div className="kb-error-message">
              <strong>Error:</strong> {kbResult.error}
            </div>
          )}

          {kbResult.urls_by_depth.length > 0 && (
            <div className="kb-depth-section">
              <h5>URLs by Depth</h5>
              <div className="depth-cards">
                {kbResult.urls_by_depth.map((d) => (
                  <div key={d.depth} className="depth-card small">
                    <div className="depth-header">
                      <span className="depth-number">Depth {d.depth}</span>
                      <span className="depth-total">{d.urls_count} URLs</span>
                    </div>
                    {d.urls && d.urls.length > 0 && (
                      <ul className="url-list">
                        {d.urls.slice(0, 3).map((url, idx) => (
                          <li key={idx} className="url-item">
                            <a href={url} target="_blank" rel="noopener noreferrer">
                              {url.length > 40 ? url.substring(0, 40) + '...' : url}
                            </a>
                          </li>
                        ))}
                        {d.urls.length > 3 && (
                          <li className="url-more">+{d.urls.length - 3} more</li>
                        )}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {kbResult.pages.length > 0 && (
            <div className="kb-pages-section">
              <h5>Processed Pages ({kbResult.pages.length})</h5>
              <div className="pages-table-wrapper">
                <table className="pages-table compact">
                  <thead>
                    <tr>
                      <th>URL</th>
                      <th>Depth</th>
                      <th>Title</th>
                      <th>Links</th>
                      <th>Time</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {kbResult.pages.slice(0, 50).map((page: KBPageResult, idx: number) => (
                      <tr
                        key={idx}
                        className={
                          page.status === 'skipped'
                            ? 'skipped-row'
                            : page.failure?.phase === 'crawl'
                            ? 'error-row crawl-error'
                            : page.failure?.phase === 'scrape'
                            ? 'error-row scrape-error'
                            : page.error
                            ? 'error-row'
                            : ''
                        }
                      >
                        <td className="url-cell">
                          <a href={page.url} target="_blank" rel="noopener noreferrer">
                            {page.url.length > 35 ? page.url.substring(0, 35) + '...' : page.url}
                          </a>
                        </td>
                        <td>{page.depth}</td>
                        <td className="title-cell">
                          {page.title ? (page.title.length > 25 ? page.title.substring(0, 25) + '...' : page.title) : '-'}
                        </td>
                        <td>{page.links_found}</td>
                        <td>{page.timing_ms.toFixed(0)}ms</td>
                        <td className="status-cell">
                          {page.status === 'skipped' ? (
                            <span className="status-skipped">Skipped</span>
                          ) : page.error ? (
                            <span className="status-error" title={page.error}>Error</span>
                          ) : page.has_content ? (
                            <span className="status-scraped">Scraped</span>
                          ) : (
                            <span className="status-crawled">Crawled</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {kbResult.pages.length > 50 && (
                  <div className="pages-more">
                    Showing first 50 of {kbResult.pages.length} pages. Download JSON for complete data.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function MultiKBResultsDashboard({ results }: MultiKBResultsDashboardProps) {
  const [expandedKBs, setExpandedKBs] = useState<Set<string>>(new Set());

  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
    return `${(ms / 60000).toFixed(2)}m`;
  };

  const handleDownload = (format: 'json' | 'markdown') => {
    window.open(getMultiKBDownloadUrl(results.job_id, format), '_blank');
  };

  const toggleKB = (kbId: string) => {
    setExpandedKBs((prev) => {
      const next = new Set(prev);
      if (next.has(kbId)) {
        next.delete(kbId);
      } else {
        next.add(kbId);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedKBs(new Set(results.knowledge_bases.map((kb) => kb.kb_id)));
  };

  const collapseAll = () => {
    setExpandedKBs(new Set());
  };

  const getStateColor = (state: string) => {
    switch (state) {
      case 'completed': return '#10b981';
      case 'failed': return '#ef4444';
      default: return '#6b7280';
    }
  };

  return (
    <div className="results-dashboard multi-kb-results">
      <div className="results-header">
        <h2>Multi-KB Crawl Results</h2>
        <div className="header-info">
          <span className="domain-badge">{results.domain}</span>
          <span
            className="state-badge"
            style={{ backgroundColor: getStateColor(results.state) }}
          >
            {results.state.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="download-section">
        <div className="download-buttons">
          <button onClick={() => handleDownload('json')} className="download-btn json">
            Download All (JSON)
          </button>
          <button onClick={() => handleDownload('markdown')} className="download-btn markdown">
            Download All (Markdown)
          </button>
        </div>
      </div>

      {/* Overall Summary */}
      <div className="results-summary">
        <div className="summary-card">
          <span className="summary-value">{results.summary.total_kbs}</span>
          <span className="summary-label">Total KBs</span>
        </div>
        <div className="summary-card success">
          <span className="summary-value">{results.summary.kbs_completed}</span>
          <span className="summary-label">Completed</span>
        </div>
        <div className="summary-card error">
          <span className="summary-value">{results.summary.kbs_failed}</span>
          <span className="summary-label">Failed</span>
        </div>
        <div className="summary-card">
          <span className="summary-value">{results.summary.total_pages}</span>
          <span className="summary-label">Total Pages</span>
        </div>
        <div className="summary-card">
          <span className="summary-value">{results.summary.total_pages_scraped}</span>
          <span className="summary-label">Pages Scraped</span>
        </div>
        <div className="summary-card">
          <span className="summary-value">{results.summary.total_pages_failed}</span>
          <span className="summary-label">Pages Failed</span>
        </div>
        <div className="summary-card">
          <span className="summary-value">{results.summary.total_urls_discovered}</span>
          <span className="summary-label">URLs Discovered</span>
        </div>
        <div className="summary-card out-of-scope">
          <span className="summary-value">{results.summary.total_urls_out_of_scope}</span>
          <span className="summary-label">Out of Scope</span>
        </div>
        <div className="summary-card">
          <span className="summary-value">{formatTime(results.summary.total_duration_ms)}</span>
          <span className="summary-label">Total Duration</span>
        </div>
      </div>

      {/* Pages by KB Chart */}
      {Object.keys(results.summary.pages_by_kb).length > 0 && (
        <div className="pages-by-kb-section">
          <h3>Pages by Knowledge Base</h3>
          <div className="pages-by-kb-chart">
            {Object.entries(results.summary.pages_by_kb).map(([kbName, count]) => {
              const maxPages = Math.max(...Object.values(results.summary.pages_by_kb));
              const percentage = maxPages > 0 ? (count / maxPages) * 100 : 0;
              return (
                <div key={kbName} className="kb-bar-item">
                  <span className="kb-bar-label">{kbName}</span>
                  <div className="kb-bar-container">
                    <div className="kb-bar-fill" style={{ width: `${percentage}%` }} />
                  </div>
                  <span className="kb-bar-value">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {results.error && (
        <div className="error-message">
          <strong>Error:</strong> {results.error}
        </div>
      )}

      {/* Per-KB Results */}
      <div className="kb-results-list">
        <div className="kb-results-list-header">
          <h3>Knowledge Base Results</h3>
          <div className="expand-controls">
            <button onClick={expandAll} className="expand-btn">Expand All</button>
            <button onClick={collapseAll} className="expand-btn">Collapse All</button>
          </div>
        </div>
        {results.knowledge_bases.map((kb) => (
          <KBResultsSection
            key={kb.kb_id}
            kbResult={kb}
            jobId={results.job_id}
            isExpanded={expandedKBs.has(kb.kb_id)}
            onToggle={() => toggleKB(kb.kb_id)}
          />
        ))}
      </div>
    </div>
  );
}
