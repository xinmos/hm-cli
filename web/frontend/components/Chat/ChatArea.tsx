"use client";

import { useRef, useEffect } from "react";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import type { Message } from "@/app/page";

interface ChatAreaProps {
  messages: Message[];
  onSendMessage: (message: string, options: { permissions: string; model: string }) => void;
  isConnected: boolean;
}

export function ChatArea({ messages, onSendMessage, isConnected }: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (!bottomRef.current) return;

    bottomRef.current.scrollIntoView({
      behavior: lastMessage?.isStreaming ? "auto" : "smooth",
      block: "end",
    });
  }, [messages]);

  return (
    <div className="flex flex-col flex-1 min-h-0 bg-background">
      {/* Message List */}
      <div className="flex-1 overflow-y-auto">
        <MessageList messages={messages} bottomRef={bottomRef} />
      </div>

      {/* Chat Input - Centered in main content area */}
      <div className="border-t border-border bg-background w-full flex justify-center">
        <div className="w-full max-w-4xl px-4">
          <ChatInput
            onSend={onSendMessage}
            isConnected={isConnected}
            disabled={false}
          />
        </div>
      </div>
    </div>
  );
}
