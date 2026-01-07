import { useState } from 'react';
import type { CrawlMode, CrawlRequest } from '../types';

interface CrawlFormProps {
  onSubmit: (request: CrawlRequest) => void;
  isLoading: boolean;
}

const CRAWL_MODES: { value: CrawlMode; label: string; description: string }[] = [
  {
    value: 'crawl_scrape',
    label: 'Crawl + Scrape',
    description: 'BFS crawl and extract content from all pages',
  },
  {
    value: 'only_crawl',
    label: 'Only Crawl',
    description: 'Discover URLs using BFS without content extraction',
  },
  {
    value: 'only_scrape',
    label: 'Only Scrape',
    description: 'Extract content from seed URL only',
  },
];

export function CrawlForm({ onSubmit, isLoading }: CrawlFormProps) {
  const [seedUrl, setSeedUrl] = useState('');
  const [mode, setMode] = useState<CrawlMode>('crawl_scrape');
  const [maxDepth, setMaxDepth] = useState(3);
  const [workerCount, setWorkerCount] = useState(4);
  const [allowSubdomains, setAllowSubdomains] = useState(false);
  const [allowedDomainsInput, setAllowedDomainsInput] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validate URL
    try {
      new URL(seedUrl);
    } catch {
      setError('Please enter a valid URL (e.g., https://example.com)');
      return;
    }

    // Parse allowed domains from comma-separated input
    const allowedDomains = allowedDomainsInput
      .split(',')
      .map(d => d.trim())
      .filter(d => d.length > 0);

    onSubmit({
      seed_url: seedUrl,
      mode,
      max_depth: maxDepth,
      worker_count: workerCount,
      allow_subdomains: allowSubdomains,
      allowed_domains: allowedDomains,
    });
  };

  return (
    <form className="crawl-form" onSubmit={handleSubmit}>
      <div className="form-group">
        <label htmlFor="seedUrl">Seed URL</label>
        <input
          id="seedUrl"
          type="url"
          value={seedUrl}
          onChange={(e) => setSeedUrl(e.target.value)}
          placeholder="https://example.com"
          required
          disabled={isLoading}
        />
      </div>

      <div className="form-group">
        <label>Crawl Mode</label>
        <div className="mode-selector">
          {CRAWL_MODES.map((m) => (
            <label key={m.value} className={`mode-option ${mode === m.value ? 'selected' : ''}`}>
              <input
                type="radio"
                name="mode"
                value={m.value}
                checked={mode === m.value}
                onChange={(e) => setMode(e.target.value as CrawlMode)}
                disabled={isLoading}
              />
              <span className="mode-label">{m.label}</span>
              <span className="mode-description">{m.description}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label htmlFor="maxDepth">Max Depth: {maxDepth}</label>
          <input
            id="maxDepth"
            type="range"
            min="1"
            max="5"
            value={maxDepth}
            onChange={(e) => setMaxDepth(Number(e.target.value))}
            disabled={isLoading}
          />
          <div className="range-labels">
            <span>1</span>
            <span>2</span>
            <span>3</span>
            <span>4</span>
            <span>5</span>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="workerCount">Workers: {workerCount}</label>
          <input
            id="workerCount"
            type="range"
            min="2"
            max="10"
            value={workerCount}
            onChange={(e) => setWorkerCount(Number(e.target.value))}
            disabled={isLoading}
          />
          <div className="range-labels">
            <span>2</span>
            <span>4</span>
            <span>6</span>
            <span>8</span>
            <span>10</span>
          </div>
        </div>
      </div>

      <div className="form-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={allowSubdomains}
            onChange={(e) => setAllowSubdomains(e.target.checked)}
            disabled={isLoading}
          />
          <span>Allow Subdomains</span>
        </label>
        <span className="checkbox-description">
          Crawl all subdomains of the seed URL's domain (e.g., blog.example.com, docs.example.com)
        </span>
      </div>

      <div className="form-group">
        <label htmlFor="allowedDomains">Additional Allowed Domains</label>
        <input
          id="allowedDomains"
          type="text"
          value={allowedDomainsInput}
          onChange={(e) => setAllowedDomainsInput(e.target.value)}
          placeholder="cdn.example.com, api.example.com"
          disabled={isLoading}
        />
        <span className="input-hint">Comma-separated list of additional domains to crawl</span>
      </div>

      {error && <div className="form-error">{error}</div>}

      <button type="submit" className="submit-button" disabled={isLoading}>
        {isLoading ? 'Starting...' : 'Start Crawl'}
      </button>
    </form>
  );
}
