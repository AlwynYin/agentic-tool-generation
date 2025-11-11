import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { ApiClient } from '../api';
import { WSMessage, WSJobStatusChanged, WSJobProgressUpdated, WSTaskStatusChanged } from '../types';

interface WebSocketContextType {
  isConnected: boolean;
  subscribe: (callback: (message: WSMessage) => void) => () => void;
  sendMessage: (message: any) => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
};

interface WebSocketProviderProps {
  children: React.ReactNode;
  sessionId?: string;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({
  children,
  sessionId = 'web-ui-session'
}) => {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const subscribersRef = useRef<Set<(message: WSMessage) => void>>(new Set());
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(() => {
    try {
      console.log(`[WebSocket] Connecting to session: ${sessionId}`);
      const ws = ApiClient.createWebSocket(sessionId);

      ws.onopen = () => {
        console.log('[WebSocket] Connected');
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;

        // Send initial ping
        ws.send(JSON.stringify({ type: 'ping' }));
      };

      ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data);
          console.log('[WebSocket] Received message:', message);

          // Broadcast to all subscribers
          subscribersRef.current.forEach(callback => {
            try {
              callback(message);
            } catch (error) {
              console.error('[WebSocket] Subscriber callback error:', error);
            }
          });

          // Auto-respond to pings
          if (message.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong' }));
          }
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
      };

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected');
        setIsConnected(false);
        wsRef.current = null;

        // Attempt reconnection
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
        } else {
          console.error('[WebSocket] Max reconnection attempts reached');
        }
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
    }
  }, [sessionId]);

  useEffect(() => {
    connect();

    return () => {
      console.log('[WebSocket] Cleaning up connection');
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const subscribe = useCallback((callback: (message: WSMessage) => void) => {
    subscribersRef.current.add(callback);

    // Return unsubscribe function
    return () => {
      subscribersRef.current.delete(callback);
    };
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('[WebSocket] Cannot send message: not connected');
    }
  }, []);

  const value: WebSocketContextType = {
    isConnected,
    subscribe,
    sendMessage,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

// Custom hooks for specific message types
export const useJobStatusUpdates = (jobId: string | null, onUpdate: (status: string, updatedAt: string) => void) => {
  const { subscribe } = useWebSocket();

  useEffect(() => {
    if (!jobId) return;

    const unsubscribe = subscribe((message: WSMessage) => {
      if (message.type === 'job-status-changed') {
        const data = (message as WSJobStatusChanged).data;
        if (data.jobId === jobId) {
          onUpdate(data.status, data.updatedAt);
        }
      }
    });

    return unsubscribe;
  }, [jobId, subscribe, onUpdate]);
};

export const useJobProgressUpdates = (jobId: string | null, onUpdate: (progress: any) => void) => {
  const { subscribe } = useWebSocket();

  useEffect(() => {
    if (!jobId) return;

    const unsubscribe = subscribe((message: WSMessage) => {
      if (message.type === 'job-progress-updated') {
        const data = (message as WSJobProgressUpdated).data;
        if (data.jobId === jobId) {
          onUpdate(data.progress);
        }
      }
    });

    return unsubscribe;
  }, [jobId, subscribe, onUpdate]);
};

export const useTaskStatusUpdates = (jobId: string | null, onUpdate: (taskId: string, status: string, updatedAt: string) => void) => {
  const { subscribe } = useWebSocket();

  useEffect(() => {
    if (!jobId) return;

    const unsubscribe = subscribe((message: WSMessage) => {
      if (message.type === 'task-status-changed') {
        const data = (message as WSTaskStatusChanged).data;
        if (data.jobId === jobId) {
          onUpdate(data.taskId, data.status, data.updatedAt);
        }
      }
    });

    return unsubscribe;
  }, [jobId, subscribe, onUpdate]);
};
