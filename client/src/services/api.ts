import axios from 'axios';
import type {
  CrawlRequest,
  CrawlStatus,
  CrawlResults,
  StartCrawlResponse,
  MultiKBCrawlRequest,
  MultiKBCrawlStatus,
  MultiKBCrawlResult,
  MultiKBStartResponse,
  MultiKBValidationResult,
  KBCrawlResult,
} from '../types';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export async function startCrawl(request: CrawlRequest): Promise<StartCrawlResponse> {
  const response = await api.post<StartCrawlResponse>('/start-crawl', request);
  return response.data;
}

export async function getCrawlStatus(jobId: string): Promise<CrawlStatus> {
  const response = await api.get<CrawlStatus>(`/status/${jobId}`);
  return response.data;
}

export async function getCrawlResults(jobId: string): Promise<CrawlResults> {
  const response = await api.get<CrawlResults>(`/results/${jobId}`);
  return response.data;
}

export function getDownloadUrl(jobId: string, format: 'json' | 'markdown'): string {
  return `${API_BASE}/download/${jobId}/${format}`;
}

export async function deleteJob(jobId: string): Promise<void> {
  await api.delete(`/jobs/${jobId}`);
}

// Enhanced Export API
export interface ExportSummary {
  job_id: string;
  metadata: {
    job_id: string;
    seed_url: string;
    mode: string;
    max_depth: number;
    worker_count: number;
    allow_subdomains: boolean;
    allowed_domains: string[];
    state: string;
    total_urls_discovered: number;
    total_pages_scraped: number;
    total_errors: number;
  };
  timing: {
    total_ms: number;
    crawling_ms: number;
    scraping_ms: number;
    url_discovery_ms: number;
    avg_page_time_ms: number;
    fastest_page_ms: number;
    slowest_page_ms: number;
  };
  summary: {
    total_pages: number;
    successful_pages: number;
    failed_pages: number;
    total_word_count: number;
    subdomain_count: number;
    max_depth_reached: number;
    content_type_distribution: Record<string, number>;
    subdomain_distribution: Record<string, number>;
    // Enhanced failure breakdown
    failure_breakdown?: {
      crawl_failures: number;
      scrape_failures: number;
      total_failures: number;
    };
    // Enhanced timing breakdown
    timing_breakdown?: {
      avg_crawl_per_page_ms: number;
      avg_scrape_per_page_ms: number;
    };
  };
  available_organizations: {
    by_subdomain: Array<{ subdomain: string; page_count: number }>;
    by_depth: Array<{ depth: number; page_count: number }>;
    by_content_type: Array<{ content_type: string; page_count: number }>;
    by_status?: {
      same_domain_success: number;
      external_domain: number;
      errors: number;
    };
  };
  export_formats: string[];
}

export type OrganizationType = 'flat' | 'by_subdomain' | 'by_depth' | 'by_content_type' | 'by_status';
export type OutputFormat = 'json' | 'markdown' | 'csv';

export async function getExportSummary(jobId: string): Promise<ExportSummary> {
  const response = await api.get<ExportSummary>(`/export/${jobId}/summary`);
  return response.data;
}

export function getOrganizedExportUrl(
  jobId: string,
  organization: OrganizationType = 'flat',
  format: OutputFormat = 'json',
  includeContent: boolean = true
): string {
  return `${API_BASE}/export/${jobId}/organized?organization=${organization}&format=${format}&include_content=${includeContent}`;
}

export function getZipExportUrl(jobId: string, includeContent: boolean = true): string {
  return `${API_BASE}/export/${jobId}/zip?include_content=${includeContent}`;
}

export function getSubdomainExportUrl(jobId: string, subdomain: string, format: OutputFormat = 'json'): string {
  return `${API_BASE}/export/${jobId}/by-subdomain/${subdomain}?format=${format}`;
}

export function getDepthExportUrl(jobId: string, depth: number, format: OutputFormat = 'json'): string {
  return `${API_BASE}/export/${jobId}/by-depth/${depth}?format=${format}`;
}

export function getContentTypeExportUrl(jobId: string, contentType: string, format: OutputFormat = 'json'): string {
  return `${API_BASE}/export/${jobId}/by-content-type/${contentType}?format=${format}`;
}

// ============================================================================
// Knowledge Base API
// ============================================================================

const KB_API_BASE = '/kb';

export async function startMultiKBCrawl(request: MultiKBCrawlRequest): Promise<MultiKBStartResponse> {
  const response = await api.post<MultiKBStartResponse>(`${KB_API_BASE}/start-crawl`, request);
  return response.data;
}

export async function getMultiKBStatus(jobId: string): Promise<MultiKBCrawlStatus> {
  const response = await api.get<MultiKBCrawlStatus>(`${KB_API_BASE}/status/${jobId}`);
  return response.data;
}

export async function getMultiKBResults(jobId: string): Promise<MultiKBCrawlResult> {
  const response = await api.get<MultiKBCrawlResult>(`${KB_API_BASE}/results/${jobId}`);
  return response.data;
}

export async function getMultiKBResultsSummary(jobId: string): Promise<{
  job_id: string;
  domain: string;
  mode: string;
  state: string;
  summary: MultiKBCrawlResult['summary'];
  knowledge_bases: Array<{
    kb_id: string;
    kb_name: string;
    state: string;
    urls_discovered: number;
    urls_processed: number;
    pages_scraped: number;
    pages_failed: number;
    duration_ms: number;
    error: string | null;
  }>;
}> {
  const response = await api.get(`${KB_API_BASE}/results/${jobId}/summary`);
  return response.data;
}

export async function getKBResults(jobId: string, kbId: string): Promise<KBCrawlResult> {
  const response = await api.get<KBCrawlResult>(`${KB_API_BASE}/results/${jobId}/kb/${kbId}`);
  return response.data;
}

export async function getKBPages(
  jobId: string,
  kbId: string,
  options: {
    includeContent?: boolean;
    depth?: number;
    statusFilter?: string;
    limit?: number;
    offset?: number;
  } = {}
): Promise<{
  kb_id: string;
  kb_name: string;
  total_pages: number;
  offset: number;
  limit: number;
  pages: Array<{
    url: string;
    parent_url: string | null;
    depth: number;
    title: string | null;
    status: string;
    links_found: number;
    matched_prefix: string;
    timing_ms: number;
    error: string | null;
    content: string | null;
  }>;
}> {
  const params = new URLSearchParams();
  if (options.includeContent !== undefined) params.append('include_content', String(options.includeContent));
  if (options.depth !== undefined) params.append('depth', String(options.depth));
  if (options.statusFilter) params.append('status_filter', options.statusFilter);
  if (options.limit !== undefined) params.append('limit', String(options.limit));
  if (options.offset !== undefined) params.append('offset', String(options.offset));

  const response = await api.get(`${KB_API_BASE}/results/${jobId}/kb/${kbId}/pages?${params.toString()}`);
  return response.data;
}

export async function validateMultiKBConfig(request: MultiKBCrawlRequest): Promise<MultiKBValidationResult> {
  const response = await api.post<MultiKBValidationResult>(`${KB_API_BASE}/validate`, request);
  return response.data;
}

export async function deleteMultiKBJob(jobId: string): Promise<void> {
  await api.delete(`${KB_API_BASE}/jobs/${jobId}`);
}

export async function cancelMultiKBJob(jobId: string): Promise<{ message: string }> {
  const response = await api.post(`${KB_API_BASE}/jobs/${jobId}/cancel`);
  return response.data;
}

export function getMultiKBDownloadUrl(jobId: string, format: 'json' | 'markdown'): string {
  return `${API_BASE}${KB_API_BASE}/download/${jobId}/${format}`;
}

export function getKBDownloadUrl(jobId: string, kbId: string, format: 'json'): string {
  return `${API_BASE}${KB_API_BASE}/download/${jobId}/kb/${kbId}/${format}`;
}

export default api;
