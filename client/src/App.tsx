import { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';
import { CrawlForm, StatusPanel, ResultsDashboard } from './components';
import { startCrawl, getCrawlResults } from './services/api';
import { useWebSocket } from './hooks';
import type { CrawlRequest, CrawlStatus, CrawlResults } from './types';

function App() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<CrawlStatus | null>(null);
  const [results, setResults] = useState<CrawlResults | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);

  const timerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const currentJobIdRef = useRef<string | null>(null);

  // WebSocket hook for real-time updates
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
      // Stop timer
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      // Update status
      setStatus((prev) => prev ? {
        ...prev,
        state: 'completed',
        urls_discovered: wsStatus.urls_discovered,
        urls_processed: wsStatus.urls_processed,
        current_depth: wsStatus.current_depth,
      } : null);

      // Fetch full results
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
    };
  }, [stopTimers, disconnect]);

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

      // Initialize status with request data
      setStatus({
        job_id: response.job_id,
        state: 'pending',
        seed_url: response.seed_url,
        mode: response.mode,
        max_depth: response.max_depth,
        worker_count: response.worker_count,
        allow_subdomains: response.allow_subdomains,
        allowed_domains: response.allowed_domains,
        current_depth: 0,
        urls_discovered: 0,
        urls_processed: 0,
        urls_by_depth: [],
        timing: { url_discovery_ms: 0, crawling_ms: 0, scraping_ms: 0, total_ms: 0 },
        error: null,
      });

      // Start elapsed time timer
      startTimers();

      // Connect to WebSocket for real-time updates
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

  return (
    <div className="app">
      <header className="app-header">
        <h1>ScrapeCrawlAI</h1>
        <p>BFS Web Crawler & Scraper with Multi-Worker Architecture</p>
      </header>

      <main className="app-main">
        {!jobId && !results && (
          <CrawlForm onSubmit={handleSubmit} isLoading={isLoading} />
        )}

        {error && (
          <div className="error-banner">
            <strong>Error:</strong> {error}
            <button onClick={handleNewCrawl} className="retry-btn">
              Try Again
            </button>
          </div>
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
      </main>

      <footer className="app-footer">
        <p>Powered by Crawl4AI | BFS Traversal | Multi-Worker Concurrency</p>
      </footer>
    </div>
  );
}

export default App;
