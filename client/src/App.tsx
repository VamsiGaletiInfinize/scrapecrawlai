import { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';
import { CrawlForm, StatusPanel, ResultsDashboard } from './components';
import { startCrawl, getCrawlStatus, getCrawlResults } from './services/api';
import type { CrawlRequest, CrawlStatus, CrawlResults } from './types';

function App() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<CrawlStatus | null>(null);
  const [results, setResults] = useState<CrawlResults | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);

  const pollingRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(async (id: string) => {
    try {
      const currentStatus = await getCrawlStatus(id);
      setStatus(currentStatus);

      if (currentStatus.state === 'completed') {
        stopPolling();
        const crawlResults = await getCrawlResults(id);
        setResults(crawlResults);
        setElapsedTime(currentStatus.timing.total_ms);
      } else if (currentStatus.state === 'failed') {
        stopPolling();
        setError(currentStatus.error || 'Crawl failed');
      }
    } catch (err) {
      console.error('Error polling status:', err);
    }
  }, [stopPolling]);

  const startPolling = useCallback((id: string) => {
    startTimeRef.current = Date.now();

    // Start elapsed time timer
    timerRef.current = window.setInterval(() => {
      setElapsedTime(Date.now() - startTimeRef.current);
    }, 100);

    // Start status polling
    pollingRef.current = window.setInterval(() => {
      pollStatus(id);
    }, 1500);

    // Initial poll
    pollStatus(id);
  }, [pollStatus]);

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  const handleSubmit = async (request: CrawlRequest) => {
    setIsLoading(true);
    setError(null);
    setResults(null);
    setStatus(null);
    setElapsedTime(0);

    try {
      const response = await startCrawl(request);
      setJobId(response.job_id);
      startPolling(response.job_id);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start crawl';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewCrawl = () => {
    stopPolling();
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
          <StatusPanel status={status} elapsedTime={elapsedTime} />
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
