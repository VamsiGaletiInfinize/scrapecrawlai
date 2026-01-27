import { useState, useCallback } from 'react';
import type { CrawlMode, KnowledgeBaseConfig, MultiKBCrawlRequest } from '../types';
import { v4 as uuidv4 } from 'uuid';

interface KBCrawlFormProps {
  onSubmit: (request: MultiKBCrawlRequest) => void;
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
    description: 'Extract content from entry URLs only',
  },
];

interface KBFormEntry {
  id: string;
  name: string;
  entryUrls: string;
  isActive: boolean;
}

function generateKBId(): string {
  return uuidv4().slice(0, 8);
}

export function KBCrawlForm({ onSubmit, isLoading }: KBCrawlFormProps) {
  const [domain, setDomain] = useState('');
  const [mode, setMode] = useState<CrawlMode>('crawl_scrape');
  const [maxDepth, setMaxDepth] = useState(3);
  const [workerCount, setWorkerCount] = useState(4);
  const [parallelKBs, setParallelKBs] = useState(2);
  const [allowSubdomains, setAllowSubdomains] = useState(false);
  const [includeChildPages, setIncludeChildPages] = useState(true);
  const [autoDiscoverPrefixes, setAutoDiscoverPrefixes] = useState(false);
  const [error, setError] = useState('');

  // Knowledge Bases
  const [knowledgeBases, setKnowledgeBases] = useState<KBFormEntry[]>([
    { id: generateKBId(), name: '', entryUrls: '', isActive: true },
  ]);

  const addKnowledgeBase = useCallback(() => {
    setKnowledgeBases((prev) => [
      ...prev,
      { id: generateKBId(), name: '', entryUrls: '', isActive: true },
    ]);
  }, []);

  const removeKnowledgeBase = useCallback((id: string) => {
    setKnowledgeBases((prev) => prev.filter((kb) => kb.id !== id));
  }, []);

  const updateKnowledgeBase = useCallback(
    (id: string, field: keyof KBFormEntry, value: string | boolean) => {
      setKnowledgeBases((prev) =>
        prev.map((kb) => (kb.id === id ? { ...kb, [field]: value } : kb))
      );
    },
    []
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validate domain
    try {
      new URL(domain);
    } catch {
      setError('Please enter a valid domain URL (e.g., https://example.com)');
      return;
    }

    // Validate Knowledge Bases
    const activeKBs = knowledgeBases.filter((kb) => kb.isActive);
    if (activeKBs.length === 0) {
      setError('At least one active Knowledge Base is required');
      return;
    }

    // Validate each KB has name and at least one URL
    for (const kb of activeKBs) {
      if (!kb.name.trim()) {
        setError(`Knowledge Base is missing a name`);
        return;
      }

      const urls = kb.entryUrls
        .split('\n')
        .map((u) => u.trim())
        .filter((u) => u.length > 0);

      if (urls.length === 0) {
        setError(`Knowledge Base "${kb.name}" needs at least one entry URL`);
        return;
      }

      // Validate each URL
      for (const url of urls) {
        try {
          new URL(url);
        } catch {
          setError(`Invalid URL in "${kb.name}": ${url}`);
          return;
        }
      }
    }

    // Build request
    const kbConfigs: KnowledgeBaseConfig[] = knowledgeBases.map((kb) => ({
      kb_id: kb.id,
      name: kb.name.trim(),
      entry_urls: kb.entryUrls
        .split('\n')
        .map((u) => u.trim())
        .filter((u) => u.length > 0),
      is_active: kb.isActive,
    }));

    onSubmit({
      domain,
      knowledge_bases: kbConfigs,
      mode,
      max_depth: maxDepth,
      worker_count: workerCount,
      allow_subdomains: allowSubdomains,
      include_child_pages: includeChildPages,
      parallel_kbs: parallelKBs,
      auto_discover_prefixes: autoDiscoverPrefixes,
    });
  };

  return (
    <form className="crawl-form kb-crawl-form" onSubmit={handleSubmit}>
      <div className="form-section">
        <h3>Domain Configuration</h3>
        <div className="form-group">
          <label htmlFor="domain">Base Domain</label>
          <input
            id="domain"
            type="url"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="https://www.example.edu"
            required
            disabled={isLoading}
          />
          <span className="input-hint">The main domain for all Knowledge Bases</span>
        </div>
      </div>

      <div className="form-section">
        <div className="section-header">
          <h3>Knowledge Bases</h3>
          <button
            type="button"
            className="add-kb-btn"
            onClick={addKnowledgeBase}
            disabled={isLoading}
          >
            + Add Knowledge Base
          </button>
        </div>

        <div className="kb-list">
          {knowledgeBases.map((kb, index) => (
            <div key={kb.id} className={`kb-entry ${!kb.isActive ? 'inactive' : ''}`}>
              <div className="kb-entry-header">
                <span className="kb-number">KB {index + 1}</span>
                <label className="checkbox-label kb-active-toggle">
                  <input
                    type="checkbox"
                    checked={kb.isActive}
                    onChange={(e) => updateKnowledgeBase(kb.id, 'isActive', e.target.checked)}
                    disabled={isLoading}
                  />
                  <span>Active</span>
                </label>
                {knowledgeBases.length > 1 && (
                  <button
                    type="button"
                    className="remove-kb-btn"
                    onClick={() => removeKnowledgeBase(kb.id)}
                    disabled={isLoading}
                  >
                    Remove
                  </button>
                )}
              </div>

              <div className="form-group">
                <label>Name</label>
                <input
                  type="text"
                  value={kb.name}
                  onChange={(e) => updateKnowledgeBase(kb.id, 'name', e.target.value)}
                  placeholder="e.g., Admissions, Academics, Research"
                  disabled={isLoading || !kb.isActive}
                />
              </div>

              <div className="form-group">
                <label>Entry URLs (one per line)</label>
                <textarea
                  value={kb.entryUrls}
                  onChange={(e) => updateKnowledgeBase(kb.id, 'entryUrls', e.target.value)}
                  placeholder="https://www.example.edu/admissions&#10;https://www.example.edu/admissions/apply"
                  rows={3}
                  disabled={isLoading || !kb.isActive}
                />
                <span className="input-hint">
                  URLs define the path scope. Only URLs under these paths will be crawled.
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="form-section">
        <h3>Crawl Settings</h3>

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

          <div className="form-group">
            <label htmlFor="parallelKBs">Parallel KBs: {parallelKBs}</label>
            <input
              id="parallelKBs"
              type="range"
              min="1"
              max="5"
              value={parallelKBs}
              onChange={(e) => setParallelKBs(Number(e.target.value))}
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
            Allow crawling subdomains within each KB's path scope
          </span>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={includeChildPages}
              onChange={(e) => setIncludeChildPages(e.target.checked)}
              disabled={isLoading || mode === 'only_scrape'}
            />
            <span>Include All Child Pages</span>
          </label>
          <span className="checkbox-description">
            {includeChildPages
              ? 'All discovered child pages will be fully crawled and scraped'
              : 'Child pages will be discovered but not scraped'}
          </span>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={autoDiscoverPrefixes}
              onChange={(e) => setAutoDiscoverPrefixes(e.target.checked)}
              disabled={isLoading || mode === 'only_scrape'}
            />
            <span>Auto-Discover Path Prefixes</span>
          </label>
          <span className="checkbox-description">
            {autoDiscoverPrefixes
              ? 'Automatically discover and include additional path prefixes from links on entry pages (recommended for comprehensive crawling)'
              : 'Only crawl URLs under the explicitly specified entry URL paths'}
          </span>
        </div>
      </div>

      {error && <div className="form-error">{error}</div>}

      <button type="submit" className="submit-button" disabled={isLoading}>
        {isLoading ? 'Starting...' : 'Start Multi-KB Crawl'}
      </button>
    </form>
  );
}
