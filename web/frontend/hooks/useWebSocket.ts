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
  const manualCloseRef = useRef(false);
  const onMessageRef = useRef(onMessage);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);
  const onErrorRef = useRef(onError);
  const maxReconnectAttempts = 5;
  const ephemeralSessionIdRef = useRef<string>(`session-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`);
  const resolvedSessionId = sessionId === "new" ? ephemeralSessionIdRef.current : sessionId;

  useEffect(() => {
    onMessageRef.current = onMessage;
    onConnectRef.current = onConnect;
    onDisconnectRef.current = onDisconnect;
    onErrorRef.current = onError;
  }, [onConnect, onDisconnect, onError, onMessage]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }
    manualCloseRef.current = false;

    // 根据环境确定 WebSocket URL
    // 注意：WebSocket 服务器在后端 (8000端口)，不是前端开发服务器 (3000端口)
    const getWebSocketUrl = () => {
      if (typeof window !== "undefined") {
        // 开发环境下使用固定的后端端口
        const isDev = window.location.port === "3000";
        const wsHost = isDev ? "localhost:8000" : window.location.host;
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        return `${protocol}//${wsHost}/ws/chat/${resolvedSessionId}`;
      }
      return `ws://localhost:8000/ws/chat/${resolvedSessionId}`;
    };

    const wsUrl = getWebSocketUrl();
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected");
      setIsConnected(true);
      reconnectAttempts.current = 0;
      onConnectRef.current?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current(data);
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setIsConnected(false);
      onDisconnectRef.current?.();

      // Attempt to reconnect
      if (!manualCloseRef.current && reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current += 1;
        const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30000);
        console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      onErrorRef.current?.(error);
    };

    wsRef.current = ws;
  }, [resolvedSessionId]);

  const disconnect = useCallback(() => {
    manualCloseRef.current = true;
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
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    sendMessage,
    isConnected,
    connect,
    disconnect,
  };
}
