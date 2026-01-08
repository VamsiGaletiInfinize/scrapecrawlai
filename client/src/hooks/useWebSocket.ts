import { useState, useEffect, useCallback, useRef } from 'react';
import type { CrawlState } from '../types';

export interface WebSocketStatus {
  state: CrawlState;
  urls_discovered: number;
  urls_processed: number;
  current_depth: number;
  queue_size?: number;
  timing?: {
    total_ms: number;
    crawling_ms: number;
    scraping_ms: number;
  };
}

export interface WebSocketMessage {
  type: 'initial_status' | 'status_update' | 'job_completed' | 'job_failed' | 'heartbeat';
  job_id: string;
  data?: WebSocketStatus;
  error?: string;
}

interface UseWebSocketOptions {
  onStatusUpdate?: (status: WebSocketStatus) => void;
  onCompleted?: (status: WebSocketStatus) => void;
  onFailed?: (error: string) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
}

interface UseWebSocketReturn {
  connect: (jobId: string) => void;
  disconnect: () => void;
  isConnected: boolean;
  lastStatus: WebSocketStatus | null;
  error: string | null;
}

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [lastStatus, setLastStatus] = useState<WebSocketStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const optionsRef = useRef(options);

  // Keep options ref updated
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
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
    setLastStatus(null);

    const wsUrl = `${WS_BASE_URL}/api/ws/${jobId}`;
    console.log(`[WS] Connecting to ${wsUrl}`);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS] Connected');
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
          const message: WebSocketMessage = JSON.parse(event.data);
          console.log('[WS] Message:', message.type);

          switch (message.type) {
            case 'initial_status':
            case 'status_update':
              if (message.data) {
                setLastStatus(message.data);
                optionsRef.current.onStatusUpdate?.(message.data);
              }
              break;

            case 'job_completed':
              if (message.data) {
                setLastStatus(message.data);
                optionsRef.current.onCompleted?.(message.data);
              }
              break;

            case 'job_failed':
              setError(message.error || 'Job failed');
              optionsRef.current.onFailed?.(message.error || 'Job failed');
              break;

            case 'heartbeat':
              // Just a keepalive, no action needed
              break;
          }
        } catch (e) {
          // Handle non-JSON messages (like pong)
          if (event.data === 'pong') {
            console.log('[WS] Pong received');
          }
        }
      };

      ws.onerror = (event) => {
        console.error('[WS] Error:', event);
        setError('WebSocket connection error');
      };

      ws.onclose = (event) => {
        console.log(`[WS] Closed: code=${event.code}, reason=${event.reason}`);
        setIsConnected(false);
        clearTimers();
        optionsRef.current.onDisconnected?.();
      };

    } catch (e) {
      console.error('[WS] Failed to create WebSocket:', e);
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
    lastStatus,
    error,
  };
}
