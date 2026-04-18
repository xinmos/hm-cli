"use client";

import { useState, useCallback, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar/Sidebar";
import { Header } from "@/components/Header/Header";
import { ChatArea } from "@/components/Chat/ChatArea";
import { useWebSocket } from "@/hooks/useWebSocket";
import { cn } from "@/lib/utils";

export interface Chat {
  id: string;
  title: string;
  project_id?: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  tool_calls?: any[];
  isStreaming?: boolean;
}

export default function Home() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [chats, setChats] = useState<Chat[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");

  const { sendMessage, isConnected, connect, disconnect } = useWebSocket({
    sessionId: currentChatId || "new",
    onMessage: useCallback((data) => {
      handleWebSocketMessage(data);
    }, []),
    onConnect: () => setConnectionStatus("connected"),
    onDisconnect: () => setConnectionStatus("disconnected"),
  });

  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case "connected":
        console.log("Connected to session:", data.session_id);
        break;
      case "stream_start":
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}`,
            role: "assistant",
            content: "",
            created_at: new Date().toISOString(),
            isStreaming: true,
          },
        ]);
        break;
      case "stream_delta":
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.isStreaming) {
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, content: lastMsg.content + data.delta },
            ];
          }
          return prev;
        });
        break;
      case "stream_end":
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.isStreaming) {
            return [...prev.slice(0, -1), { ...lastMsg, isStreaming: false }];
          }
          return prev;
        });
        break;
      case "status":
        // 更新 token 使用量等状态
        break;
    }
  };

  const handleSendMessage = async (message: string, options: { permissions: string; model: string }) => {
    if (!currentChatId) {
      // 创建新聊天
      const newChat: Chat = {
        id: `chat-${Date.now()}`,
        title: message.slice(0, 50) || "New Chat",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        message_count: 0,
      };
      setChats((prev) => [newChat, ...prev]);
      setCurrentChatId(newChat.id);

      // 等待连接建立后发送消息
      setTimeout(() => {
        sendMessage({
          type: "chat",
          message,
          permissions: options.permissions,
          model: options.model,
          message_id: `msg-${Date.now()}`,
        });
      }, 500);
    } else {
      sendMessage({
        type: "chat",
        message,
        permissions: options.permissions,
        model: options.model,
        message_id: `msg-${Date.now()}`,
      });
    }

    // 添加用户消息到界面
    setMessages((prev) => [
      ...prev,
      {
        id: `msg-${Date.now()}`,
        role: "user",
        content: message,
        created_at: new Date().toISOString(),
      },
    ]);
  };

  const handleSelectChat = (chatId: string) => {
    setCurrentChatId(chatId);
    // 加载聊天记录
    // fetchMessages(chatId);
  };

  const handleNewChat = () => {
    setCurrentChatId(null);
    setMessages([]);
  };

  useEffect(() => {
    // 加载聊天列表
    fetch("/api/chats")
      .then((res) => res.json())
      .then((data) => setChats(data))
      .catch(console.error);
  }, []);

  return (
    <div className="flex h-screen bg-background">
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        chats={chats}
        currentChatId={currentChatId}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
      />

      <div className={cn("flex flex-col flex-1 min-w-0 transition-all duration-200", isSidebarOpen ? "lg:ml-[240px]" : "")}>
        <Header
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          title={currentChatId ? chats.find((c) => c.id === currentChatId)?.title || "Chat" : "New Chat"}
          connectionStatus={connectionStatus}
        />

        <ChatArea
          messages={messages}
          onSendMessage={handleSendMessage}
          isConnected={isConnected}
        />
      </div>
    </div>
  );
}
