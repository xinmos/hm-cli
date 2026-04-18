"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseWebSocketProps {
  sessionId: string;
  onMessage: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  sendMessage: (data: any) => void;
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
}

export function useWebSocket({
  sessionId,
  onMessage,
  onConnect,
  onDisconnect,
  onError,
}: UseWebSocketProps): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  // 使用 ref 存储稳定的 session ID，避免重连时变化
  const stableSessionIdRef = useRef<string>(sessionId === "new" ? `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}` : sessionId);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const wsUrl = `ws://localhost:8000/ws/chat/${stableSessionIdRef.current}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected");
      setIsConnected(true);
      reconnectAttempts.current = 0;
      onConnect?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setIsConnected(false);
      onDisconnect?.();

      // Attempt to reconnect
      if (reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current += 1;
        const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30000);
        console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      onError?.(error);
    };

    wsRef.current = ws;
  }, [sessionId, onMessage, onConnect, onDisconnect, onError]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      console.warn("WebSocket is not connected");
    }
  }, []);

  useEffect(() => {
    // 只在组件挂载时连接，sessionId 变化时不重新连接
    connect();
    return () => {
      disconnect();
    };
    // 依赖项只包含 connect 和 disconnect，不包含 sessionId
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    sendMessage,
    isConnected,
    connect,
    disconnect,
  };
}
