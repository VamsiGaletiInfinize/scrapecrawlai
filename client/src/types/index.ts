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

// ============================================================================
// Knowledge Base Types
// ============================================================================

export type KBCrawlState = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

export interface KnowledgeBaseConfig {
  kb_id: string;
  name: string;
  description?: string;
  entry_urls: string[];
  is_active: boolean;
  max_depth?: number;
}

export interface KnowledgeBaseCrawlStatus {
  kb_id: string;
  kb_name: string;
  state: KBCrawlState;
  entry_urls: string[];
  allowed_prefixes: string[];
  urls_discovered: number;
  urls_processed: number;
  urls_queued: number;
  urls_skipped_out_of_scope: number;
  current_depth: number;
  max_depth: number;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number;
  error: string | null;
  pages_scraped: number;
  pages_crawled: number;
  pages_failed: number;
}

export interface KBPageResult extends PageResult {
  kb_id: string;
  kb_name: string;
  matched_prefix: string;
}

export interface KBDepthStats {
  depth: number;
  urls_count: number;
  urls: string[];
}

export interface KBCrawlResult {
  kb_id: string;
  kb_name: string;
  entry_urls: string[];
  allowed_prefixes: string[];
  state: KBCrawlState;
  pages: KBPageResult[];
  urls_by_depth: KBDepthStats[];
  urls_discovered: number;
  urls_processed: number;
  urls_out_of_scope: number;
  pages_scraped: number;
  pages_crawled: number;
  pages_failed: number;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number;
  error: string | null;
}

export interface MultiKBCrawlRequest {
  domain: string;
  knowledge_bases: KnowledgeBaseConfig[];
  mode: CrawlMode;
  max_depth: number;
  worker_count: number;
  respect_robots_txt?: boolean;
  allow_subdomains?: boolean;
  include_child_pages?: boolean;
  parallel_kbs?: number;
  auto_discover_prefixes?: boolean;
}

export interface MultiKBSummary {
  total_kbs: number;
  kbs_completed: number;
  kbs_failed: number;
  kbs_skipped: number;
  total_pages: number;
  total_pages_scraped: number;
  total_pages_failed: number;
  total_urls_discovered: number;
  total_urls_out_of_scope: number;
  total_duration_ms: number;
  pages_by_kb: Record<string, number>;
}

export interface MultiKBCrawlStatus {
  job_id: string;
  domain: string;
  state: CrawlState;
  mode: CrawlMode;
  total_kbs: number;
  kbs_completed: number;
  kbs_failed: number;
  kbs_running: number;
  kbs_pending: number;
  knowledge_bases: KnowledgeBaseCrawlStatus[];
  total_urls_discovered: number;
  total_urls_processed: number;
  total_urls_out_of_scope: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface MultiKBCrawlResult {
  job_id: string;
  domain: string;
  mode: CrawlMode;
  state: CrawlState;
  max_depth: number;
  worker_count: number;
  allow_subdomains: boolean;
  include_child_pages: boolean;
  auto_discover_prefixes: boolean;
  knowledge_bases: KBCrawlResult[];
  summary: MultiKBSummary;
  started_at: string | null;
  completed_at: string | null;
  total_duration_ms: number;
  error: string | null;
}

export interface MultiKBStartResponse {
  job_id: string;
  message: string;
  domain: string;
  mode: CrawlMode;
  max_depth: number;
  worker_count: number;
  parallel_kbs: number;
  knowledge_bases: Array<{
    kb_id: string;
    name: string;
    entry_urls: string[];
    allowed_prefixes: string[];
  }>;
  warnings?: {
    overlapping_scopes: string[];
    message: string;
  };
}

export interface MultiKBValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  knowledge_bases: Array<{
    kb_id: string;
    name: string;
    entry_urls: string[];
    allowed_prefixes: string[];
    is_active: boolean;
  }>;
}
