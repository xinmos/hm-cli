"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Sidebar } from "@/components/Sidebar/Sidebar";
import { Header } from "@/components/Header/Header";
import { ChatArea } from "@/components/Chat/ChatArea";
import { WorkspacePanel } from "@/components/Workspace/WorkspacePanel";
import { cn } from "@/lib/utils";
import {
  fetchChats,
  createChat,
  fetchMessages,
  deleteChat,
  renameChat,
  fetchWorkspaceInfo,
  streamChatMessage,
  type ChatAttachment,
  type WorkspaceInfo,
} from "@/lib/api";

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
  currentAction?: string;
  isStreaming?: boolean;
  streamPhase?: "thinking" | "responding";
}

interface PendingOutboundMessage {
  chatId: string;
  payload: {
    message: string;
    permissions: string;
    model: string;
    message_id: string;
    attachments?: ChatAttachment[];
  };
}

function sortChatsByUpdatedAt(chats: Chat[]): Chat[] {
  return [...chats].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
}

export default function Home() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isWorkspaceOpen, setIsWorkspaceOpen] = useState(false);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [chats, setChats] = useState<Chat[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  const [pendingOutbound, setPendingOutbound] = useState<PendingOutboundMessage | null>(null);
  const [workspaceInfo, setWorkspaceInfo] = useState<WorkspaceInfo | null>(null);
  const [tokenUsage, setTokenUsage] = useState({ used: 0, total: 256 * 1024 });
  const [isStreaming, setIsStreaming] = useState(false);
  const streamAbortRef = useRef<AbortController | null>(null);

  const handleStreamEvent = useCallback((data: any) => {
    switch (data.type) {
      case "stream_start":
        setIsStreaming(true);
        setConnectionStatus("connecting");
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}`,
            role: "assistant",
            content: "",
            created_at: new Date().toISOString(),
            currentAction: "正在分析你的问题",
            isStreaming: true,
            streamPhase: "thinking",
          },
        ]);
        break;
      case "tool_start":
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (!lastMsg?.isStreaming) {
            return prev;
          }

          return [
            ...prev.slice(0, -1),
            {
              ...lastMsg,
              currentAction: data.tool_display || "正在处理中",
            },
          ];
        });
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
                currentAction: undefined,
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
      case "error":
        setIsStreaming(false);
        setConnectionStatus("disconnected");
        setMessages((prev) => {
          const errorText = data.error || "请求失败，请稍后重试。";
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.isStreaming) {
            return [
              ...prev.slice(0, -1),
              {
                ...lastMsg,
                content: lastMsg.content || errorText,
                currentAction: undefined,
                isStreaming: false,
                streamPhase: undefined,
              },
            ];
          }

          return [
            ...prev,
            {
              id: `msg-${Date.now()}`,
              role: "assistant",
              content: errorText,
              created_at: new Date().toISOString(),
              isStreaming: false,
            },
          ];
        });
        break;
      case "status":
        setTokenUsage({
          used: data.tokens_used || 0,
          total: data.tokens_total || workspaceInfo?.context_window || 256 * 1024,
        });
        setIsStreaming(false);
        setConnectionStatus("connected");
        break;
    }
  }, [workspaceInfo]);

  const startStream = useCallback(async (chatId: string, payload: PendingOutboundMessage["payload"]) => {
    streamAbortRef.current?.abort();
    const controller = new AbortController();
    streamAbortRef.current = controller;
    setConnectionStatus("connecting");

    try {
      await streamChatMessage(chatId, payload, {
        signal: controller.signal,
        onEvent: handleStreamEvent,
      });
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }

      console.error("Failed to stream chat message:", error);
      handleStreamEvent({
        type: "error",
        error: "请求失败，请稍后重试。",
      });
      setIsStreaming(false);
      setConnectionStatus("disconnected");
    } finally {
      if (streamAbortRef.current === controller) {
        streamAbortRef.current = null;
      }
    }
  }, [handleStreamEvent]);

  const handleSendMessage = async (
    message: string,
    options: { permissions: string; model: string; attachments?: ChatAttachment[] },
  ) => {
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

    const payload = {
      message,
      permissions: options.permissions,
      model: options.model,
      message_id: userMessage.id,
      attachments: options.attachments,
    };

    setPendingOutbound({
      chatId: targetChatId,
      payload,
    });
  };

  const handleSelectChat = async (chatId: string) => {
    streamAbortRef.current?.abort();
    setIsStreaming(false);
    setConnectionStatus("connected");
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
    streamAbortRef.current?.abort();
    setIsStreaming(false);
    setConnectionStatus("connected");
    setCurrentChatId(null);
    setMessages([]);
  };

  const handleDeleteChats = async (chatIds: string[]) => {
    if (chatIds.length === 0) {
      return;
    }

    try {
      await Promise.all(chatIds.map((chatId) => deleteChat(chatId)));
      setChats((prev) => prev.filter((chat) => !chatIds.includes(chat.id)));

      if (currentChatId && chatIds.includes(currentChatId)) {
        setCurrentChatId(null);
        setMessages([]);
      }
    } catch (error) {
      console.error("Failed to delete chats:", error);
    }
  };

  const handleRenameChat = async (chatId: string, title: string) => {
    try {
      const updatedChat = await renameChat(chatId, title);
      setChats((prev) => sortChatsByUpdatedAt(prev.map((chat) => (chat.id === chatId ? updatedChat : chat))));
    } catch (error) {
      console.error("Failed to rename chat:", error);
      throw error;
    }
  };

  const handleCreateNewChat = async (firstMessage: string) => {
    try {
      const title = firstMessage.slice(0, 50) || "New Chat";
      const newChat = await createChat(title);
      setChats((prev) => sortChatsByUpdatedAt([newChat, ...prev]));
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
    loadWorkspaceInfo();
  }, []);

  useEffect(() => {
    if (!pendingOutbound) {
      return;
    }
    startStream(pendingOutbound.chatId, pendingOutbound.payload);
    setPendingOutbound(null);
  }, [pendingOutbound, startStream]);

  const loadChats = async () => {
    try {
      const data = await fetchChats();
      setChats(sortChatsByUpdatedAt(data));
    } catch (error) {
      console.error("Failed to load chats:", error);
    }
  };

  const loadWorkspaceInfo = async () => {
    try {
      const data = await fetchWorkspaceInfo();
      setWorkspaceInfo(data);
      setConnectionStatus("connected");
      setTokenUsage((prev) => ({
        used: prev.used,
        total: data.context_window,
      }));
    } catch (error) {
      console.error("Failed to load workspace info:", error);
    }
  };

  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort();
    };
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
        onDeleteChats={handleDeleteChats}
        onRenameChat={handleRenameChat}
      />

      <div className={cn("flex flex-col flex-1 min-w-0 transition-all duration-200", isSidebarOpen ? "lg:ml-[240px]" : "")}>
        <Header
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          onToggleWorkspace={() => setIsWorkspaceOpen((prev) => !prev)}
          title={currentChatId ? chats.find((c) => c.id === currentChatId)?.title || "Chat" : "New Chat"}
          connectionStatus={connectionStatus}
        />

        <ChatArea
          messages={messages}
          onSendMessage={handleSendMessage}
          isConnected={!isStreaming}
          workspaceInfo={workspaceInfo}
          tokenUsage={tokenUsage}
        />
      </div>

      <WorkspacePanel
        isOpen={isWorkspaceOpen}
        onClose={() => setIsWorkspaceOpen(false)}
      />
    </div>
  );
}
