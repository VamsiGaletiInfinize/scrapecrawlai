import { useState, useEffect } from 'react';
import {
  getExportSummary,
  getOrganizedExportUrl,
  getZipExportUrl,
  getSubdomainExportUrl,
  getDepthExportUrl,
  getContentTypeExportUrl,
  type ExportSummary,
  type OrganizationType,
  type OutputFormat,
} from '../services/api';

interface ExportPanelProps {
  jobId: string;
}

export function ExportPanel({ jobId }: ExportPanelProps) {
  const [summary, setSummary] = useState<ExportSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedOrg, setSelectedOrg] = useState<OrganizationType>('flat');
  const [selectedFormat, setSelectedFormat] = useState<OutputFormat>('json');
  const [includeContent, setIncludeContent] = useState(true);
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSummary() {
      try {
        setLoading(true);
        const data = await getExportSummary(jobId);
        setSummary(data);
      } catch (err) {
        setError('Failed to load export options');
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchSummary();
  }, [jobId]);

  const handleOrganizedExport = () => {
    window.open(getOrganizedExportUrl(jobId, selectedOrg, selectedFormat, includeContent), '_blank');
  };

  const handleZipExport = () => {
    window.open(getZipExportUrl(jobId, includeContent), '_blank');
  };

  const handleSubdomainExport = (subdomain: string) => {
    window.open(getSubdomainExportUrl(jobId, subdomain, selectedFormat), '_blank');
  };

  const handleDepthExport = (depth: number) => {
    window.open(getDepthExportUrl(jobId, depth, selectedFormat), '_blank');
  };

  const handleContentTypeExport = (contentType: string) => {
    window.open(getContentTypeExportUrl(jobId, contentType, selectedFormat), '_blank');
  };

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  if (loading) {
    return <div className="export-panel loading">Loading export options...</div>;
  }

  if (error || !summary) {
    return <div className="export-panel error">{error || 'Failed to load'}</div>;
  }

  return (
    <div className="export-panel">
      <h3>Export Options</h3>

      {/* Quick Stats */}
      <div className="export-stats">
        <div className="stat">
          <span className="stat-value">{summary.summary.total_word_count.toLocaleString()}</span>
          <span className="stat-label">Total Words</span>
        </div>
        <div className="stat">
          <span className="stat-value">{summary.summary.subdomain_count}</span>
          <span className="stat-label">Subdomains</span>
        </div>
        <div className="stat">
          <span className="stat-value">{Object.keys(summary.summary.content_type_distribution).length}</span>
          <span className="stat-label">Content Types</span>
        </div>
      </div>

      {/* Failure Breakdown Stats */}
      {summary.summary.failure_breakdown && summary.summary.failure_breakdown.total_failures > 0 && (
        <div className="export-failure-stats">
          <h4>Failure Breakdown</h4>
          <div className="failure-stat-row">
            <div className="failure-stat crawl">
              <span className="failure-stat-value">{summary.summary.failure_breakdown.crawl_failures}</span>
              <span className="failure-stat-label">Crawl Failures</span>
            </div>
            <div className="failure-stat scrape">
              <span className="failure-stat-value">{summary.summary.failure_breakdown.scrape_failures}</span>
              <span className="failure-stat-label">Scrape Failures</span>
            </div>
            <div className="failure-stat total">
              <span className="failure-stat-value">{summary.summary.failure_breakdown.total_failures}</span>
              <span className="failure-stat-label">Total Failures</span>
            </div>
          </div>
        </div>
      )}

      {/* Export Controls */}
      <div className="export-controls">
        <div className="control-group">
          <label>Organization:</label>
          <select value={selectedOrg} onChange={(e) => setSelectedOrg(e.target.value as OrganizationType)}>
            <option value="flat">Flat (All Pages)</option>
            <option value="by_subdomain">By Subdomain</option>
            <option value="by_depth">By Depth Level</option>
            <option value="by_content_type">By Content Type</option>
            <option value="by_status">By Status (Success/External/Errors)</option>
          </select>
        </div>

        <div className="control-group">
          <label>Format:</label>
          <select value={selectedFormat} onChange={(e) => setSelectedFormat(e.target.value as OutputFormat)}>
            <option value="json">JSON</option>
            <option value="markdown">Markdown</option>
            <option value="csv">CSV</option>
          </select>
        </div>

        <div className="control-group checkbox">
          <label>
            <input
              type="checkbox"
              checked={includeContent}
              onChange={(e) => setIncludeContent(e.target.checked)}
            />
            Include page content
          </label>
        </div>
      </div>

      {/* Main Export Buttons */}
      <div className="export-buttons">
        <button onClick={handleOrganizedExport} className="export-btn primary">
          Export {selectedFormat.toUpperCase()}
        </button>
        <button onClick={handleZipExport} className="export-btn zip">
          Download Complete ZIP
        </button>
      </div>

      {/* Expandable Sections */}
      <div className="export-sections">
        {/* By Subdomain */}
        <div className="export-section">
          <button
            className={`section-header ${expandedSection === 'subdomain' ? 'expanded' : ''}`}
            onClick={() => toggleSection('subdomain')}
          >
            <span>By Subdomain ({summary.available_organizations.by_subdomain.length})</span>
            <span className="expand-icon">{expandedSection === 'subdomain' ? '−' : '+'}</span>
          </button>
          {expandedSection === 'subdomain' && (
            <div className="section-content">
              {summary.available_organizations.by_subdomain.map((item) => (
                <div key={item.subdomain} className="export-item">
                  <span className="item-name">{item.subdomain}</span>
                  <span className="item-count">{item.page_count} pages</span>
                  <button onClick={() => handleSubdomainExport(item.subdomain)} className="item-btn">
                    Export
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* By Depth */}
        <div className="export-section">
          <button
            className={`section-header ${expandedSection === 'depth' ? 'expanded' : ''}`}
            onClick={() => toggleSection('depth')}
          >
            <span>By Depth ({summary.available_organizations.by_depth.length} levels)</span>
            <span className="expand-icon">{expandedSection === 'depth' ? '−' : '+'}</span>
          </button>
          {expandedSection === 'depth' && (
            <div className="section-content">
              {summary.available_organizations.by_depth.map((item) => (
                <div key={item.depth} className="export-item">
                  <span className="item-name">Depth {item.depth}</span>
                  <span className="item-count">{item.page_count} pages</span>
                  <button onClick={() => handleDepthExport(item.depth)} className="item-btn">
                    Export
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* By Content Type */}
        <div className="export-section">
          <button
            className={`section-header ${expandedSection === 'content' ? 'expanded' : ''}`}
            onClick={() => toggleSection('content')}
          >
            <span>By Content Type ({summary.available_organizations.by_content_type.length})</span>
            <span className="expand-icon">{expandedSection === 'content' ? '−' : '+'}</span>
          </button>
          {expandedSection === 'content' && (
            <div className="section-content">
              {summary.available_organizations.by_content_type.map((item) => (
                <div key={item.content_type} className="export-item">
                  <span className="item-name">{item.content_type}</span>
                  <span className="item-count">{item.page_count} pages</span>
                  <button onClick={() => handleContentTypeExport(item.content_type)} className="item-btn">
                    Export
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* By Status (Three Groups) */}
        {summary.available_organizations.by_status && (
          <div className="export-section">
            <button
              className={`section-header ${expandedSection === 'status' ? 'expanded' : ''}`}
              onClick={() => toggleSection('status')}
            >
              <span>By Status (3 groups)</span>
              <span className="expand-icon">{expandedSection === 'status' ? '−' : '+'}</span>
            </button>
            {expandedSection === 'status' && (
              <div className="section-content by-status-content">
                <div className="status-group success">
                  <span className="status-icon">&#10003;</span>
                  <span className="item-name">Same Domain Success</span>
                  <span className="item-count">{summary.available_organizations.by_status.same_domain_success} pages</span>
                </div>
                <div className="status-group external">
                  <span className="status-icon">&#8599;</span>
                  <span className="item-name">External Domain</span>
                  <span className="item-count">{summary.available_organizations.by_status.external_domain} pages</span>
                </div>
                <div className="status-group errors">
                  <span className="status-icon">&#10007;</span>
                  <span className="item-name">Errors</span>
                  <span className="item-count">{summary.available_organizations.by_status.errors} pages</span>
                </div>
                <div className="status-export-hint">
                  Select "By Status" organization above and click Export to download all three groups
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Content Type Distribution */}
      <div className="content-distribution">
        <h4>Content Type Distribution</h4>
        <div className="distribution-bars">
          {Object.entries(summary.summary.content_type_distribution).map(([type, count]) => {
            const percentage = (count / summary.summary.total_pages) * 100;
            return (
              <div key={type} className="distribution-item">
                <div className="distribution-label">
                  <span className="type-name">{type}</span>
                  <span className="type-count">{count}</span>
                </div>
                <div className="distribution-bar">
                  <div
                    className={`bar-fill type-${type}`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
