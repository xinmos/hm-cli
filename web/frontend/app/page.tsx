"use client";

import { useState, useCallback, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar/Sidebar";
import { Header } from "@/components/Header/Header";
import { ChatArea } from "@/components/Chat/ChatArea";
import { useWebSocket } from "@/hooks/useWebSocket";
import { cn } from "@/lib/utils";
import { fetchChats, createChat, fetchMessages, deleteChat } from "@/lib/api";

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
  streamPhase?: "thinking" | "responding";
}

export default function Home() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [chats, setChats] = useState<Chat[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");

  const handleWebSocketMessage = useCallback((data: any) => {
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
            streamPhase: "thinking",
          },
        ]);
        break;
      case "stream_delta":
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.isStreaming) {
            return [
              ...prev.slice(0, -1),
              {
                ...lastMsg,
                content: lastMsg.content + data.delta,
                streamPhase: "responding",
              },
            ];
          }
          return prev;
        });
        break;
      case "stream_end":
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.isStreaming) {
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, isStreaming: false, streamPhase: undefined },
            ];
          }
          return prev;
        });
        break;
      case "status":
        break;
    }
  }, []);

  const handleSocketConnect = useCallback(() => {
    setConnectionStatus("connected");
  }, []);

  const handleSocketDisconnect = useCallback(() => {
    setConnectionStatus("disconnected");
  }, []);

  const { sendMessage, isConnected } = useWebSocket({
    sessionId: currentChatId || "new",
    onMessage: handleWebSocketMessage,
    onConnect: handleSocketConnect,
    onDisconnect: handleSocketDisconnect,
  });

  const handleSendMessage = async (message: string, options: { permissions: string; model: string }) => {
    let targetChatId = currentChatId;

    // 如果没有当前聊天，创建新聊天
    if (!targetChatId) {
      try {
        targetChatId = await handleCreateNewChat(message);
      } catch (error) {
        console.error("Failed to create chat:", error);
        return;
      }
    }

    // 添加用户消息到界面
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: message,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // 发送消息到 WebSocket
    sendMessage({
      type: "chat",
      chat_id: targetChatId,
      message,
      permissions: options.permissions,
      model: options.model,
      message_id: userMessage.id,
    });
  };

  const handleSelectChat = async (chatId: string) => {
    setCurrentChatId(chatId);
    // 加载聊天记录
    try {
      const messages = await fetchMessages(chatId);
      setMessages(messages);
    } catch (error) {
      console.error("Failed to load messages:", error);
    }
  };

  const handleNewChat = async () => {
    setCurrentChatId(null);
    setMessages([]);
  };

  const handleCreateNewChat = async (firstMessage: string) => {
    try {
      const title = firstMessage.slice(0, 50) || "New Chat";
      const newChat = await createChat(title);
      setChats((prev) => [newChat, ...prev]);
      setCurrentChatId(newChat.id);
      return newChat.id;
    } catch (error) {
      console.error("Failed to create chat:", error);
      throw error;
    }
  };

  useEffect(() => {
    // 加载聊天列表
    loadChats();
  }, []);

  const loadChats = async () => {
    try {
      const data = await fetchChats();
      setChats(data);
    } catch (error) {
      console.error("Failed to load chats:", error);
    }
  };

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
