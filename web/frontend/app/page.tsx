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

interface ActiveStreamSnapshot {
  id: string;
  content: string;
  created_at: string;
  currentAction?: string;
  streamPhase?: "thinking" | "responding";
}

function sortChatsByUpdatedAt(chats: Chat[]): Chat[] {
  return [...chats].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
}

function withStreamingSnapshot(messages: Message[], snapshot: ActiveStreamSnapshot): Message[] {
  const streamingMessage: Message = {
    id: snapshot.id,
    role: "assistant",
    content: snapshot.content,
    created_at: snapshot.created_at,
    currentAction: snapshot.currentAction,
    isStreaming: true,
    streamPhase: snapshot.streamPhase,
  };
  const index = messages.findIndex((message) => message.id === snapshot.id);

  if (index === -1) {
    return [...messages, streamingMessage];
  }

  return [
    ...messages.slice(0, index),
    streamingMessage,
    ...messages.slice(index + 1),
  ];
}

export default function Home() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isWorkspaceOpen, setIsWorkspaceOpen] = useState(false);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [chats, setChats] = useState<Chat[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingOutbound, setPendingOutbound] = useState<PendingOutboundMessage | null>(null);
  const [workspaceInfo, setWorkspaceInfo] = useState<WorkspaceInfo | null>(null);
  const [tokenUsage, setTokenUsage] = useState({ used: 0, total: 256 * 1024 });
  const [streamingChatIds, setStreamingChatIds] = useState<Set<string>>(() => new Set());
  const streamAbortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const activeStreamsRef = useRef<Map<string, ActiveStreamSnapshot>>(new Map());
  const currentChatIdRef = useRef<string | null>(null);

  useEffect(() => {
    currentChatIdRef.current = currentChatId;
  }, [currentChatId]);

  const markChatStreaming = useCallback((chatId: string, isStreaming: boolean) => {
    setStreamingChatIds((prev) => {
      const next = new Set(prev);
      if (isStreaming) {
        next.add(chatId);
      } else {
        next.delete(chatId);
      }
      return next;
    });
  }, []);

  const applyActiveStreamSnapshot = useCallback((chatId: string) => {
    const snapshot = activeStreamsRef.current.get(chatId);
    if (!snapshot || currentChatIdRef.current !== chatId) {
      return;
    }

    setMessages((prev) => withStreamingSnapshot(prev, snapshot));
  }, []);

  const handleStreamEvent = useCallback((chatId: string, data: any) => {
    switch (data.type) {
      case "stream_start":
        markChatStreaming(chatId, true);
        activeStreamsRef.current.set(chatId, {
          id: `stream-${chatId}-${Date.now()}`,
          content: "",
          created_at: new Date().toISOString(),
          currentAction: "正在分析你的问题",
          streamPhase: "thinking",
        });
        applyActiveStreamSnapshot(chatId);
        break;
      case "tool_start":
        {
          const snapshot = activeStreamsRef.current.get(chatId);
          if (!snapshot) {
            break;
          }
          activeStreamsRef.current.set(chatId, {
            ...snapshot,
            currentAction: data.tool_display || "正在处理中",
          });
          applyActiveStreamSnapshot(chatId);
        }
        break;
      case "stream_delta":
        {
          const snapshot = activeStreamsRef.current.get(chatId) ?? {
            id: `stream-${chatId}-${Date.now()}`,
            content: "",
            created_at: new Date().toISOString(),
          };
          activeStreamsRef.current.set(chatId, {
            ...snapshot,
            content: snapshot.content + (data.delta || ""),
            currentAction: undefined,
            streamPhase: "responding",
          });
          applyActiveStreamSnapshot(chatId);
        }
        break;
      case "stream_end":
        {
          const snapshot = activeStreamsRef.current.get(chatId);
          if (snapshot && currentChatIdRef.current === chatId) {
            setMessages((prev) => {
              const withSnapshot = withStreamingSnapshot(prev, snapshot);
              return withSnapshot.map((message) => (
                message.id === snapshot.id
                  ? { ...message, isStreaming: false, streamPhase: undefined, currentAction: undefined }
                  : message
              ));
            });
          }
          activeStreamsRef.current.delete(chatId);
          markChatStreaming(chatId, false);
        }
        break;
      case "error":
        {
          const errorText = data.error || "请求失败，请稍后重试。";
          const snapshot = activeStreamsRef.current.get(chatId);
          activeStreamsRef.current.delete(chatId);
          markChatStreaming(chatId, false);

          if (currentChatIdRef.current !== chatId) {
            return;
          }

          setMessages((prev) => {
            if (snapshot) {
              const withSnapshot = withStreamingSnapshot(prev, {
                ...snapshot,
                content: snapshot.content || errorText,
                currentAction: undefined,
                streamPhase: undefined,
              });
              return withSnapshot.map((message) => (
                message.id === snapshot.id
                  ? { ...message, isStreaming: false, streamPhase: undefined, currentAction: undefined }
                  : message
              ));
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
        }
        break;
      case "status":
        if (currentChatIdRef.current === chatId) {
          setTokenUsage({
            used: data.tokens_used || 0,
            total: data.tokens_total || workspaceInfo?.context_window || 256 * 1024,
          });
        }
        markChatStreaming(chatId, false);
        break;
    }
  }, [applyActiveStreamSnapshot, markChatStreaming, workspaceInfo]);

  const loadChats = useCallback(async () => {
    try {
      const data = await fetchChats();
      setChats(sortChatsByUpdatedAt(data));
    } catch (error) {
      console.error("Failed to load chats:", error);
    }
  }, []);

  const loadWorkspaceInfo = useCallback(async () => {
    try {
      const data = await fetchWorkspaceInfo();
      setWorkspaceInfo(data);
      setTokenUsage((prev) => ({
        used: prev.used,
        total: data.context_window,
      }));
    } catch (error) {
      console.error("Failed to load workspace info:", error);
    }
  }, []);

  const startStream = useCallback(async (chatId: string, payload: PendingOutboundMessage["payload"]) => {
    if (streamAbortControllersRef.current.has(chatId)) {
      return;
    }

    const controller = new AbortController();
    streamAbortControllersRef.current.set(chatId, controller);
    markChatStreaming(chatId, true);

    try {
      await streamChatMessage(chatId, payload, {
        signal: controller.signal,
        onEvent: (event) => handleStreamEvent(chatId, event),
      });
      await loadChats();
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }

      console.error("Failed to stream chat message:", error);
      handleStreamEvent(chatId, {
        type: "error",
        error: "请求失败，请稍后重试。",
      });
    } finally {
      if (streamAbortControllersRef.current.get(chatId) === controller) {
        streamAbortControllersRef.current.delete(chatId);
      }
      markChatStreaming(chatId, false);
    }
  }, [handleStreamEvent, loadChats, markChatStreaming]);

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

    if (streamAbortControllersRef.current.has(targetChatId)) {
      return;
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
    currentChatIdRef.current = chatId;
    setCurrentChatId(chatId);
    // 加载聊天记录
    try {
      const loadedMessages = await fetchMessages(chatId);
      if (currentChatIdRef.current !== chatId) {
        return;
      }
      const snapshot = activeStreamsRef.current.get(chatId);
      setMessages(snapshot ? withStreamingSnapshot(loadedMessages, snapshot) : loadedMessages);
    } catch (error) {
      console.error("Failed to load messages:", error);
    }
  };

  const handleNewChat = async () => {
    currentChatIdRef.current = null;
    setCurrentChatId(null);
    setMessages([]);
  };

  const handleDeleteChats = async (chatIds: string[]) => {
    if (chatIds.length === 0) {
      return;
    }

    try {
      await Promise.all(chatIds.map((chatId) => deleteChat(chatId)));
      chatIds.forEach((chatId) => {
        streamAbortControllersRef.current.get(chatId)?.abort();
        streamAbortControllersRef.current.delete(chatId);
        activeStreamsRef.current.delete(chatId);
      });
      setChats((prev) => prev.filter((chat) => !chatIds.includes(chat.id)));

      if (currentChatId && chatIds.includes(currentChatId)) {
        currentChatIdRef.current = null;
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
      currentChatIdRef.current = newChat.id;
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
  }, [loadChats, loadWorkspaceInfo]);

  useEffect(() => {
    if (!pendingOutbound) {
      return;
    }
    startStream(pendingOutbound.chatId, pendingOutbound.payload);
    setPendingOutbound(null);
  }, [pendingOutbound, startStream]);

  useEffect(() => {
    const streamAbortControllers = streamAbortControllersRef.current;
    return () => {
      streamAbortControllers.forEach((controller) => controller.abort());
      streamAbortControllers.clear();
    };
  }, []);

  const isCurrentChatStreaming = currentChatId ? streamingChatIds.has(currentChatId) : false;

  return (
    <div className="flex h-screen bg-background">
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        chats={chats}
        currentChatId={currentChatId}
        streamingChatIds={streamingChatIds}
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
          messages={messages}
        />

        <ChatArea
          messages={messages}
          onSendMessage={handleSendMessage}
          isConnected={!isCurrentChatStreaming}
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
