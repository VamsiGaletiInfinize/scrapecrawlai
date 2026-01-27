import { useState, useEffect, useCallback, useRef } from 'react';
import type { CrawlState, KBCrawlState, KnowledgeBaseCrawlStatus } from '../types';

export interface MultiKBWebSocketOverall {
  state: CrawlState;
  kbs_pending: number;
  kbs_running: number;
  kbs_completed: number;
  kbs_failed: number;
  total_urls_discovered: number;
  total_urls_processed: number;
  total_urls_out_of_scope: number;
}

export interface MultiKBWebSocketKBUpdate {
  kb_id: string;
  kb_name: string;
  state: KBCrawlState;
  urls_discovered: number;
  urls_processed: number;
  urls_queued: number;
  urls_skipped_out_of_scope: number;
  current_depth: number;
  max_depth: number;
  pages_scraped: number;
  pages_failed: number;
}

export interface MultiKBWebSocketMessage {
  type:
    | 'initial_status'
    | 'job_started'
    | 'multi_kb_progress'
    | 'page_complete'
    | 'kb_completed'
    | 'kb_failed'
    | 'job_completed'
    | 'job_failed'
    | 'heartbeat';
  job_id: string;
  timestamp?: string;
  // For initial_status
  data?: {
    state: CrawlState;
    total_kbs: number;
    kbs_completed: number;
    kbs_running: number;
    kbs_failed: number;
    total_urls_discovered: number;
    total_urls_processed: number;
    knowledge_bases?: Array<{
      kb_id: string;
      kb_name: string;
      state: KBCrawlState;
      urls_discovered: number;
      urls_processed: number;
    }>;
  };
  // For multi_kb_progress
  overall?: MultiKBWebSocketOverall;
  kb_update?: MultiKBWebSocketKBUpdate;
  // For page_complete
  kb_id?: string;
  kb_name?: string;
  url?: string;
  status?: string;
  depth?: number;
  matched_prefix?: string;
  // For kb_completed/kb_failed
  stats?: {
    urls_discovered: number;
    urls_processed: number;
    urls_out_of_scope: number;
    pages_scraped: number;
    pages_failed: number;
    duration_ms: number;
  };
  // For job_completed
  summary?: {
    total_kbs: number;
    kbs_completed: number;
    kbs_failed: number;
    total_pages: number;
    total_urls_discovered: number;
    total_urls_out_of_scope: number;
    pages_by_kb: Record<string, number>;
  };
  // For errors
  error?: string;
  partial_stats?: Record<string, unknown>;
}

interface UseMultiKBWebSocketOptions {
  onInitialStatus?: (data: MultiKBWebSocketMessage['data']) => void;
  onMultiKBProgress?: (overall: MultiKBWebSocketOverall, kbUpdate: MultiKBWebSocketKBUpdate) => void;
  onPageComplete?: (kbId: string, kbName: string, url: string, status: string, depth: number) => void;
  onKBCompleted?: (kbId: string, kbName: string, stats: MultiKBWebSocketMessage['stats']) => void;
  onKBFailed?: (kbId: string, kbName: string, error: string) => void;
  onJobCompleted?: (summary: MultiKBWebSocketMessage['summary']) => void;
  onJobFailed?: (error: string) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
}

interface UseMultiKBWebSocketReturn {
  connect: (jobId: string) => void;
  disconnect: () => void;
  isConnected: boolean;
  error: string | null;
}

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export function useMultiKBWebSocket(options: UseMultiKBWebSocketOptions = {}): UseMultiKBWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const optionsRef = useRef(options);

  // Keep options ref updated
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  const clearTimers = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    clearTimers();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, [clearTimers]);

  const connect = useCallback((jobId: string) => {
    // Clean up existing connection
    disconnect();
    setError(null);

    // Connect to KB WebSocket endpoint
    const wsUrl = `${WS_BASE_URL}/api/kb/ws/${jobId}`;
    console.log(`[WS-KB] Connecting to ${wsUrl}`);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS-KB] Connected');
        setIsConnected(true);
        setError(null);
        optionsRef.current.onConnected?.();

        // Start ping interval to keep connection alive
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        try {
          const message: MultiKBWebSocketMessage = JSON.parse(event.data);
          console.log('[WS-KB] Message:', message.type);

          switch (message.type) {
            case 'initial_status':
              if (message.data) {
                optionsRef.current.onInitialStatus?.(message.data);
              }
              break;

            case 'job_started':
              // Job has started, initial notification
              console.log('[WS-KB] Job started');
              break;

            case 'multi_kb_progress':
              if (message.overall && message.kb_update) {
                optionsRef.current.onMultiKBProgress?.(message.overall, message.kb_update);
              }
              break;

            case 'page_complete':
              if (message.kb_id && message.kb_name && message.url && message.status !== undefined && message.depth !== undefined) {
                optionsRef.current.onPageComplete?.(
                  message.kb_id,
                  message.kb_name,
                  message.url,
                  message.status,
                  message.depth
                );
              }
              break;

            case 'kb_completed':
              if (message.kb_id && message.kb_name && message.stats) {
                optionsRef.current.onKBCompleted?.(message.kb_id, message.kb_name, message.stats);
              }
              break;

            case 'kb_failed':
              if (message.kb_id && message.kb_name && message.error) {
                optionsRef.current.onKBFailed?.(message.kb_id, message.kb_name, message.error);
              }
              break;

            case 'job_completed':
              if (message.summary) {
                optionsRef.current.onJobCompleted?.(message.summary);
              }
              break;

            case 'job_failed':
              setError(message.error || 'Job failed');
              optionsRef.current.onJobFailed?.(message.error || 'Job failed');
              break;

            case 'heartbeat':
              // Just a keepalive, no action needed
              break;
          }
        } catch (e) {
          // Handle non-JSON messages (like pong)
          if (event.data === 'pong') {
            console.log('[WS-KB] Pong received');
          }
        }
      };

      ws.onerror = (event) => {
        console.error('[WS-KB] Error:', event);
        setError('WebSocket connection error');
      };

      ws.onclose = (event) => {
        console.log(`[WS-KB] Closed: code=${event.code}, reason=${event.reason}`);
        setIsConnected(false);
        clearTimers();
        optionsRef.current.onDisconnected?.();
      };

    } catch (e) {
      console.error('[WS-KB] Failed to create WebSocket:', e);
      setError('Failed to connect to WebSocket');
    }
  }, [disconnect, clearTimers]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    connect,
    disconnect,
    isConnected,
    error,
  };
}
