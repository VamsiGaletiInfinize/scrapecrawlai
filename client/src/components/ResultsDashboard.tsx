import { useState } from 'react';
import type { CrawlResults } from '../types';
import { TimingBreakdown } from './TimingBreakdown';
import { ExportPanel } from './ExportPanel';
import { getDownloadUrl } from '../services/api';

interface ResultsDashboardProps {
  results: CrawlResults;
}

export function ResultsDashboard({ results }: ResultsDashboardProps) {
  const [showExportPanel, setShowExportPanel] = useState(false);

  const handleDownload = (format: 'json' | 'markdown') => {
    window.open(getDownloadUrl(results.job_id, format), '_blank');
  };

  return (
    <div className="results-dashboard">
      <div className="results-header">
        <h2>Crawl Results</h2>
        <div className="download-buttons">
          <button onClick={() => handleDownload('json')} className="download-btn json">
            Download JSON
          </button>
          <button onClick={() => handleDownload('markdown')} className="download-btn markdown">
            Download Markdown
          </button>
          <button
            onClick={() => setShowExportPanel(!showExportPanel)}
            className={`download-btn export ${showExportPanel ? 'active' : ''}`}
          >
            {showExportPanel ? 'Hide' : 'Advanced'} Export
          </button>
        </div>
      </div>

      {showExportPanel && <ExportPanel jobId={results.job_id} />}

      <div className="results-summary">
        <div className="summary-card">
          <span className="summary-value">{results.summary.total_pages}</span>
          <span className="summary-label">Total Pages</span>
        </div>
        <div className="summary-card">
          <span className="summary-value">{results.summary.successful_pages}</span>
          <span className="summary-label">Successful</span>
        </div>
        <div className="summary-card">
          <span className="summary-value">{results.summary.failed_pages}</span>
          <span className="summary-label">Failed</span>
        </div>
        <div className="summary-card">
          <span className="summary-value">{results.summary.scraped_pages}</span>
          <span className="summary-label">Scraped</span>
        </div>
        {results.summary.skipped_pages !== undefined && results.summary.skipped_pages > 0 && (
          <div className="summary-card skipped">
            <span className="summary-value">{results.summary.skipped_pages}</span>
            <span className="summary-label">Skipped</span>
          </div>
        )}
        <div className="summary-card">
          <span className="summary-value">{results.summary.total_links_found}</span>
          <span className="summary-label">Links Found</span>
        </div>
        <div className="summary-card">
          <span className="summary-value">{results.summary.avg_page_time_ms.toFixed(0)}ms</span>
          <span className="summary-label">Avg Time/Page</span>
        </div>
      </div>

      {/* Enhanced Failure Breakdown */}
      {results.summary.failure_breakdown && results.summary.failure_breakdown.total_failures > 0 && (
        <div className="failure-breakdown-section">
          <h3>Failure Breakdown</h3>
          <div className="failure-cards">
            <div className="failure-card crawl-failure">
              <span className="failure-value">{results.summary.failure_breakdown.crawl_failures}</span>
              <span className="failure-label">Crawl Failures</span>
              <span className="failure-desc">HTTP/Network errors</span>
            </div>
            <div className="failure-card scrape-failure">
              <span className="failure-value">{results.summary.failure_breakdown.scrape_failures}</span>
              <span className="failure-label">Scrape Failures</span>
              <span className="failure-desc">Content extraction errors</span>
            </div>
            <div className="failure-card total-failure">
              <span className="failure-value">{results.summary.failure_breakdown.total_failures}</span>
              <span className="failure-label">Total Failures</span>
              <span className="failure-desc">
                {((results.summary.failure_breakdown.total_failures / results.summary.total_pages) * 100).toFixed(1)}% failure rate
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Enhanced Timing Breakdown */}
      {results.summary.timing_breakdown && (
        <div className="timing-breakdown-section">
          <h3>Per-Page Timing Averages</h3>
          <div className="timing-avg-cards">
            <div className="timing-avg-card">
              <span className="timing-value">{results.summary.timing_breakdown.avg_crawl_per_page_ms.toFixed(1)}ms</span>
              <span className="timing-label">Avg Crawl/Page</span>
            </div>
            <div className="timing-avg-card">
              <span className="timing-value">{results.summary.timing_breakdown.avg_scrape_per_page_ms.toFixed(1)}ms</span>
              <span className="timing-label">Avg Scrape/Page</span>
            </div>
          </div>
        </div>
      )}

      <TimingBreakdown timing={results.timing} />

      <div className="depth-section">
        <h3>URLs by Depth Level</h3>
        <div className="depth-cards">
          {results.urls_by_depth.map((d) => (
            <div key={d.depth} className="depth-card">
              <div className="depth-header">
                <span className="depth-number">Depth {d.depth}</span>
                <span className="depth-total">{d.count} URLs</span>
              </div>
              {d.urls && (
                <ul className="url-list">
                  {d.urls.slice(0, 5).map((url, idx) => (
                    <li key={idx} className="url-item">
                      <a href={url} target="_blank" rel="noopener noreferrer">
                        {url.length > 50 ? url.substring(0, 50) + '...' : url}
                      </a>
                    </li>
                  ))}
                  {d.urls.length > 5 && (
                    <li className="url-more">+{d.urls.length - 5} more</li>
                  )}
                </ul>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="pages-section">
        <h3>Processed Pages</h3>
        <div className="pages-table-wrapper">
          <table className="pages-table">
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
              {results.pages.map((page, idx) => (
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
                      {page.url.length > 40 ? page.url.substring(0, 40) + '...' : page.url}
                    </a>
                  </td>
                  <td>{page.depth}</td>
                  <td className="title-cell">
                    {page.title || '-'}
                  </td>
                  <td>{page.links_found}</td>
                  <td className="timing-cell">
                    <span className="total-time">{page.timing_ms.toFixed(0)}ms</span>
                    {page.timing && (
                      <span className="timing-detail">
                        (C: {page.timing.crawl_ms.toFixed(0)}ms / S: {page.timing.scrape_ms.toFixed(0)}ms)
                      </span>
                    )}
                  </td>
                  <td className="status-cell">
                    {page.status === 'skipped' ? (
                      <div className="skipped-info">
                        <span className="status-skipped" title={page.skip_reason || 'Child pages disabled'}>
                          Skipped
                        </span>
                        <span className="skip-reason">{page.skip_reason === 'child_pages_disabled' ? 'Child page' : page.skip_reason}</span>
                      </div>
                    ) : page.failure && page.failure.phase !== 'none' ? (
                      <div className="failure-info">
                        <span
                          className={`status-error ${page.failure.phase}-failure-badge`}
                          title={page.failure.reason || page.error || 'Unknown error'}
                        >
                          {page.failure.phase === 'crawl' ? 'Crawl' : 'Scrape'} Error
                        </span>
                        <span className="failure-type">{page.failure.type}</span>
                        {page.failure.http_status && (
                          <span className="http-status">HTTP {page.failure.http_status}</span>
                        )}
                      </div>
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
        </div>
      </div>
    </div>
  );
}
