export type CrawlMode = 'only_crawl' | 'only_scrape' | 'crawl_scrape';

export type CrawlState = 'pending' | 'running' | 'completed' | 'failed';

export interface CrawlRequest {
  seed_url: string;
  mode: CrawlMode;
  max_depth: number;
  worker_count: number;
}

export interface TimingMetrics {
  url_discovery_ms: number;
  url_discovery_pct?: number;
  crawling_ms: number;
  crawling_pct?: number;
  scraping_ms: number;
  scraping_pct?: number;
  total_ms: number;
}

export interface DepthStats {
  depth: number;
  count: number;
  urls?: string[];
}

export interface PageResult {
  url: string;
  parent_url: string | null;
  depth: number;
  title: string | null;
  links_found: number;
  timing_ms: number;
  has_content: boolean;
  error: string | null;
}

export interface CrawlStatus {
  job_id: string;
  state: CrawlState;
  seed_url: string;
  mode: CrawlMode;
  max_depth: number;
  worker_count: number;
  current_depth: number;
  urls_discovered: number;
  urls_processed: number;
  urls_by_depth: DepthStats[];
  timing: TimingMetrics;
  error: string | null;
}

export interface CrawlSummary {
  total_pages: number;
  successful_pages: number;
  failed_pages: number;
  scraped_pages: number;
  total_links_found: number;
  depth_distribution: Record<number, number>;
  avg_page_time_ms: number;
  mode: CrawlMode;
}

export interface CrawlResults {
  job_id: string;
  seed_url: string;
  mode: CrawlMode;
  max_depth: number;
  worker_count: number;
  state: CrawlState;
  timing: TimingMetrics;
  summary: CrawlSummary;
  urls_by_depth: DepthStats[];
  pages: PageResult[];
}

export interface StartCrawlResponse {
  job_id: string;
  message: string;
  seed_url: string;
  mode: CrawlMode;
  max_depth: number;
  worker_count: number;
}
