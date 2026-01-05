import type { CrawlResults } from '../types';
import { TimingBreakdown } from './TimingBreakdown';
import { getDownloadUrl } from '../services/api';

interface ResultsDashboardProps {
  results: CrawlResults;
}

export function ResultsDashboard({ results }: ResultsDashboardProps) {
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
        </div>
      </div>

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
        <div className="summary-card">
          <span className="summary-value">{results.summary.total_links_found}</span>
          <span className="summary-label">Links Found</span>
        </div>
        <div className="summary-card">
          <span className="summary-value">{results.summary.avg_page_time_ms.toFixed(0)}ms</span>
          <span className="summary-label">Avg Time/Page</span>
        </div>
      </div>

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
                <tr key={idx} className={page.error ? 'error-row' : ''}>
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
                  <td>{page.timing_ms.toFixed(0)}ms</td>
                  <td>
                    {page.error ? (
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
