import { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';
import {
  CrawlForm,
  StatusPanel,
  ResultsDashboard,
  KBCrawlForm,
  MultiKBStatusPanel,
  MultiKBResultsDashboard,
} from './components';
import { startCrawl, getCrawlResults, startMultiKBCrawl, getMultiKBResults } from './services/api';
import { useWebSocket, useMultiKBWebSocket } from './hooks';
import type {
  CrawlRequest,
  CrawlStatus,
  CrawlResults,
  MultiKBCrawlRequest,
  MultiKBCrawlStatus,
  MultiKBCrawlResult,
} from './types';

type CrawlModeTab = 'single' | 'multi-kb';

function App() {
  // Tab state
  const [activeTab, setActiveTab] = useState<CrawlModeTab>('single');

  // Single URL crawl state
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<CrawlStatus | null>(null);
  const [results, setResults] = useState<CrawlResults | null>(null);

  // Multi-KB crawl state
  const [multiKBJobId, setMultiKBJobId] = useState<string | null>(null);
  const [multiKBStatus, setMultiKBStatus] = useState<MultiKBCrawlStatus | null>(null);
  const [multiKBResults, setMultiKBResults] = useState<MultiKBCrawlResult | null>(null);

  // Shared state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);

  const timerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const currentJobIdRef = useRef<string | null>(null);
  const currentMultiKBJobIdRef = useRef<string | null>(null);

  // Single URL WebSocket hook
  const { connect, disconnect, isConnected } = useWebSocket({
    onStatusUpdate: (wsStatus) => {
      setStatus((prev) => prev ? {
        ...prev,
        state: wsStatus.state,
        urls_discovered: wsStatus.urls_discovered,
        urls_processed: wsStatus.urls_processed,
        current_depth: wsStatus.current_depth,
      } : null);
    },
    onCompleted: async (wsStatus) => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      setStatus((prev) => prev ? {
        ...prev,
        state: 'completed',
        urls_discovered: wsStatus.urls_discovered,
        urls_processed: wsStatus.urls_processed,
        current_depth: wsStatus.current_depth,
      } : null);

      if (currentJobIdRef.current) {
        try {
          const crawlResults = await getCrawlResults(currentJobIdRef.current);
          setResults(crawlResults);
          setElapsedTime(crawlResults.timing.total_ms);
        } catch (err) {
          console.error('Error fetching results:', err);
        }
      }
    },
    onFailed: (errorMsg) => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setError(errorMsg);
    },
    onConnected: () => setWsConnected(true),
    onDisconnected: () => setWsConnected(false),
  });

  // Multi-KB WebSocket hook
  const {
    connect: connectMultiKB,
    disconnect: disconnectMultiKB,
  } = useMultiKBWebSocket({
    onMultiKBProgress: (overall, kbUpdate) => {
      setMultiKBStatus((prev) => {
        if (!prev) return null;
        // Update overall stats
        const updated = {
          ...prev,
          state: overall.state,
          total_urls_discovered: overall.total_urls_discovered,
          total_urls_processed: overall.total_urls_processed,
          total_urls_out_of_scope: overall.total_urls_out_of_scope,
          kbs_completed: overall.kbs_completed,
          kbs_failed: overall.kbs_failed,
          kbs_running: overall.kbs_running,
          kbs_pending: overall.kbs_pending,
        };
        // Update specific KB
        if (kbUpdate) {
          updated.knowledge_bases = prev.knowledge_bases.map((kb) => {
            if (kb.kb_id === kbUpdate.kb_id) {
              return {
                ...kb,
                state: kbUpdate.state,
                urls_discovered: kbUpdate.urls_discovered,
                urls_processed: kbUpdate.urls_processed,
                urls_skipped_out_of_scope: kbUpdate.urls_skipped_out_of_scope,
                current_depth: kbUpdate.current_depth,
                pages_scraped: kbUpdate.pages_scraped,
                pages_failed: kbUpdate.pages_failed,
              };
            }
            return kb;
          });
        }
        return updated;
      });
    },
    onKBCompleted: (kbId, _kbName, stats) => {
      setMultiKBStatus((prev) => {
        if (!prev) return null;
        const updatedKBs = prev.knowledge_bases.map((kb) => {
          if (kb.kb_id === kbId) {
            return {
              ...kb,
              state: 'completed' as const,
              urls_discovered: stats?.urls_discovered ?? kb.urls_discovered,
              urls_processed: stats?.urls_processed ?? kb.urls_processed,
              urls_skipped_out_of_scope: stats?.urls_out_of_scope ?? kb.urls_skipped_out_of_scope,
              pages_scraped: stats?.pages_scraped ?? kb.pages_scraped,
              pages_failed: stats?.pages_failed ?? kb.pages_failed,
              duration_ms: stats?.duration_ms ?? kb.duration_ms,
            };
          }
          return kb;
        });
        return { ...prev, knowledge_bases: updatedKBs };
      });
    },
    onKBFailed: (kbId, _kbName, error) => {
      setMultiKBStatus((prev) => {
        if (!prev) return null;
        const updatedKBs = prev.knowledge_bases.map((kb) => {
          if (kb.kb_id === kbId) {
            return { ...kb, state: 'failed' as const, error };
          }
          return kb;
        });
        return { ...prev, knowledge_bases: updatedKBs };
      });
    },
    onJobCompleted: async () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      if (currentMultiKBJobIdRef.current) {
        try {
          const kbResults = await getMultiKBResults(currentMultiKBJobIdRef.current);
          setMultiKBResults(kbResults);
          setElapsedTime(kbResults.total_duration_ms);
        } catch (err) {
          console.error('Error fetching multi-KB results:', err);
        }
      }
    },
    onJobFailed: (errorMsg: string) => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setError(errorMsg);
    },
    onConnected: () => setWsConnected(true),
    onDisconnected: () => setWsConnected(false),
  });

  const stopTimers = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startTimers = useCallback(() => {
    startTimeRef.current = Date.now();
    timerRef.current = window.setInterval(() => {
      setElapsedTime(Date.now() - startTimeRef.current);
    }, 100);
  }, []);

  useEffect(() => {
    return () => {
      stopTimers();
      disconnect();
      disconnectMultiKB();
    };
  }, [stopTimers, disconnect, disconnectMultiKB]);

  // Single URL crawl handlers
  const handleSubmit = async (request: CrawlRequest) => {
    setIsLoading(true);
    setError(null);
    setResults(null);
    setStatus(null);
    setElapsedTime(0);

    try {
      const response = await startCrawl(request);
      setJobId(response.job_id);
      currentJobIdRef.current = response.job_id;

      setStatus({
        job_id: response.job_id,
        state: 'pending',
        seed_url: response.seed_url,
        mode: response.mode,
        max_depth: response.max_depth,
        worker_count: response.worker_count,
        allow_subdomains: response.allow_subdomains,
        allowed_domains: response.allowed_domains,
        include_child_pages: response.include_child_pages,
        current_depth: 0,
        urls_discovered: 0,
        urls_processed: 0,
        urls_by_depth: [],
        timing: { url_discovery_ms: 0, crawling_ms: 0, scraping_ms: 0, total_ms: 0 },
        error: null,
      });

      startTimers();
      connect(response.job_id);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start crawl';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewCrawl = () => {
    stopTimers();
    disconnect();
    currentJobIdRef.current = null;
    setJobId(null);
    setStatus(null);
    setResults(null);
    setError(null);
    setElapsedTime(0);
  };

  // Multi-KB crawl handlers
  const handleMultiKBSubmit = async (request: MultiKBCrawlRequest) => {
    setIsLoading(true);
    setError(null);
    setMultiKBResults(null);
    setMultiKBStatus(null);
    setElapsedTime(0);

    try {
      const response = await startMultiKBCrawl(request);
      setMultiKBJobId(response.job_id);
      currentMultiKBJobIdRef.current = response.job_id;

      // Initialize status with request data
      const initialKBStatuses = response.knowledge_bases.map((kb) => ({
        kb_id: kb.kb_id,
        kb_name: kb.name,
        state: 'pending' as const,
        entry_urls: kb.entry_urls,
        allowed_prefixes: kb.allowed_prefixes,
        urls_discovered: 0,
        urls_processed: 0,
        urls_queued: 0,
        urls_skipped_out_of_scope: 0,
        current_depth: 0,
        max_depth: request.max_depth,
        started_at: null,
        completed_at: null,
        duration_ms: 0,
        error: null,
        pages_scraped: 0,
        pages_crawled: 0,
        pages_failed: 0,
      }));

      setMultiKBStatus({
        job_id: response.job_id,
        domain: response.domain,
        state: 'pending',
        mode: response.mode,
        total_kbs: response.knowledge_bases.length,
        kbs_completed: 0,
        kbs_failed: 0,
        kbs_running: 0,
        kbs_pending: response.knowledge_bases.length,
        knowledge_bases: initialKBStatuses,
        total_urls_discovered: 0,
        total_urls_processed: 0,
        total_urls_out_of_scope: 0,
        started_at: null,
        completed_at: null,
        error: null,
      });

      startTimers();
      connectMultiKB(response.job_id);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start multi-KB crawl';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewMultiKBCrawl = () => {
    stopTimers();
    disconnectMultiKB();
    currentMultiKBJobIdRef.current = null;
    setMultiKBJobId(null);
    setMultiKBStatus(null);
    setMultiKBResults(null);
    setError(null);
    setElapsedTime(0);
  };

  // Handle tab change
  const handleTabChange = (tab: CrawlModeTab) => {
    // Only allow tab change if no active job
    const hasActiveSingleJob = jobId && !results;
    const hasActiveMultiKBJob = multiKBJobId && !multiKBResults;

    if (hasActiveSingleJob || hasActiveMultiKBJob) {
      // Could show a warning here if desired
      return;
    }

    setActiveTab(tab);
    setError(null);
  };

  const hasActiveSingleJob = jobId && !results;
  const hasActiveMultiKBJob = multiKBJobId && !multiKBResults;

  return (
    <div className="app">
      <header className="app-header">
        <h1>ScrapeCrawlAI</h1>
        <p>BFS Web Crawler & Scraper with Multi-Worker Architecture</p>
      </header>

      <main className="app-main">
        {/* Tab Navigation - only show when no active job */}
        {!hasActiveSingleJob && !hasActiveMultiKBJob && !results && !multiKBResults && (
          <div className="crawl-mode-tabs">
            <button
              className={`tab-btn ${activeTab === 'single' ? 'active' : ''}`}
              onClick={() => handleTabChange('single')}
            >
              Single URL Crawl
            </button>
            <button
              className={`tab-btn ${activeTab === 'multi-kb' ? 'active' : ''}`}
              onClick={() => handleTabChange('multi-kb')}
            >
              Multi-KB Crawl
            </button>
          </div>
        )}

        {error && (
          <div className="error-banner">
            <strong>Error:</strong> {error}
            <button
              onClick={activeTab === 'single' ? handleNewCrawl : handleNewMultiKBCrawl}
              className="retry-btn"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Single URL Crawl Mode */}
        {activeTab === 'single' && (
          <>
            {!jobId && !results && (
              <CrawlForm onSubmit={handleSubmit} isLoading={isLoading} />
            )}

            {status && !results && (
              <>
                {wsConnected && (
                  <div className="ws-indicator connected">
                    <span className="ws-dot"></span> Live Updates Connected
                  </div>
                )}
                <StatusPanel status={status} elapsedTime={elapsedTime} />
              </>
            )}

            {results && (
              <>
                <ResultsDashboard results={results} />
                <button onClick={handleNewCrawl} className="new-crawl-btn">
                  Start New Crawl
                </button>
              </>
            )}
          </>
        )}

        {/* Multi-KB Crawl Mode */}
        {activeTab === 'multi-kb' && (
          <>
            {!multiKBJobId && !multiKBResults && (
              <KBCrawlForm onSubmit={handleMultiKBSubmit} isLoading={isLoading} />
            )}

            {multiKBStatus && !multiKBResults && (
              <>
                {wsConnected && (
                  <div className="ws-indicator connected">
                    <span className="ws-dot"></span> Live Updates Connected
                  </div>
                )}
                <MultiKBStatusPanel status={multiKBStatus} elapsedTime={elapsedTime} />
              </>
            )}

            {multiKBResults && (
              <>
                <MultiKBResultsDashboard results={multiKBResults} />
                <button onClick={handleNewMultiKBCrawl} className="new-crawl-btn">
                  Start New Multi-KB Crawl
                </button>
              </>
            )}
          </>
        )}
      </main>

      <footer className="app-footer">
        <p>Powered by Crawl4AI | BFS Traversal | Multi-Worker Concurrency</p>
      </footer>
    </div>
  );
}

export default App;
