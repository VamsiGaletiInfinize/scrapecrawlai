export type CrawlMode = 'only_crawl' | 'only_scrape' | 'crawl_scrape';

export type CrawlState = 'pending' | 'running' | 'completed' | 'failed';

// Enhanced timing and failure types
export type FailurePhase = 'crawl' | 'scrape' | 'none';

export type FailureType =
  | 'timeout'
  | 'dns_error'
  | 'connection_error'
  | 'ssl_error'
  | 'http_4xx'
  | 'http_5xx'
  | 'robots_blocked'
  | 'redirect_loop'
  | 'empty_content'
  | 'js_blocked'
  | 'parse_error'
  | 'selector_mismatch'
  | 'unknown'
  | 'none';

export type PageCategory = 'same_domain_success' | 'external_domain' | 'error';

export type PageStatus = 'scraped' | 'crawled' | 'skipped' | 'error';

export type SkipReason = 'child_pages_disabled' | 'none';

export interface PageTiming {
  total_ms: number;
  crawl_ms: number;
  scrape_ms: number;
  time_before_failure_ms: number;
}

export interface FailureInfo {
  phase: FailurePhase;
  type: FailureType;
  reason: string | null;
  http_status: number | null;
}

export interface CrawlRequest {
  seed_url: string;
  mode: CrawlMode;
  max_depth: number;
  worker_count: number;
  allow_subdomains?: boolean;
  allowed_domains?: string[];
  include_child_pages?: boolean;
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
  // Enhanced timing and failure fields
  timing?: PageTiming;
  failure?: FailureInfo;
  is_same_domain?: boolean;
  is_subdomain?: boolean;
  category?: PageCategory;
  // Page status tracking
  status?: PageStatus;
  skip_reason?: SkipReason;
}

export interface CrawlStatus {
  job_id: string;
  state: CrawlState;
  seed_url: string;
  mode: CrawlMode;
  max_depth: number;
  worker_count: number;
  allow_subdomains: boolean;
  allowed_domains: string[];
  include_child_pages: boolean;
  current_depth: number;
  urls_discovered: number;
  urls_processed: number;
  urls_by_depth: DepthStats[];
  timing: TimingMetrics;
  error: string | null;
}

export interface TimingBreakdown {
  url_discovery_ms: number;
  crawling_ms: number;
  scraping_ms: number;
  total_ms: number;
  avg_crawl_per_page_ms: number;
  avg_scrape_per_page_ms: number;
}

export interface FailureBreakdown {
  crawl_failures: number;
  scrape_failures: number;
  total_failures: number;
}

export interface CrawlSummary {
  total_pages: number;
  successful_pages: number;
  failed_pages: number;
  scraped_pages: number;
  skipped_pages?: number;
  crawled_pages?: number;
  total_links_found: number;
  depth_distribution: Record<number, number>;
  avg_page_time_ms: number;
  mode: CrawlMode;
  // Enhanced timing and failure breakdown
  timing_breakdown?: TimingBreakdown;
  failure_breakdown?: FailureBreakdown;
}

export interface CrawlResults {
  job_id: string;
  seed_url: string;
  mode: CrawlMode;
  max_depth: number;
  worker_count: number;
  allow_subdomains: boolean;
  allowed_domains: string[];
  include_child_pages: boolean;
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
  allow_subdomains: boolean;
  allowed_domains: string[];
  include_child_pages: boolean;
}

// Three-group organization types for BY_STATUS
export interface FailureSummary {
  type: FailureType;
  count: number;
  phase: FailurePhase;
  example_urls: string[];
}

export interface SameDomainSuccessGroup {
  page_count: number;
  total_word_count: number;
  avg_timing_ms: number;
  avg_crawl_ms: number;
  avg_scrape_ms: number;
  depth_distribution: Record<number, number>;
  content_types: Record<string, number>;
  pages: PageResult[];
}

export interface ExternalDomainGroup {
  page_count: number;
  domains: string[];
  subdomain_count: number;
  external_count: number;
  depth_distribution: Record<number, number>;
  status_distribution: Record<string, number>;
  pages: PageResult[];
}

export interface ErrorGroup {
  page_count: number;
  crawl_failures: number;
  scrape_failures: number;
  total_time_wasted_ms: number;
  failure_types: FailureSummary[];
  depth_distribution: Record<number, number>;
  pages: PageResult[];
}

export interface ThreeGroupOutput {
  same_domain_success: SameDomainSuccessGroup;
  external_domain: ExternalDomainGroup;
  errors: ErrorGroup;
}
