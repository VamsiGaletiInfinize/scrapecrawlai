import axios from 'axios';
import type {
  CrawlRequest,
  CrawlStatus,
  CrawlResults,
  StartCrawlResponse,
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

export default api;
