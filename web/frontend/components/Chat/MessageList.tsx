"use client";

import { User, Bot, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ToolCallDisplay, type ToolCall } from "./ToolCallDisplay";
import type { Message } from "@/app/page";

interface MessageListProps {
  messages: Message[];
}

function MessageItem({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";

  return (
    <div
      className={cn(
        "py-4 px-4 md:px-6",
        isUser ? "bg-muted/30" : "bg-background"
      )}
    >
      <div className="max-w-3xl mx-auto flex gap-4">
        {/* Avatar */}
        <div className="flex-shrink-0">
          {isUser ? (
            <Avatar className="h-8 w-8 bg-primary">
              <AvatarFallback className="bg-primary text-primary-foreground text-sm">
                <User className="h-4 w-4" />
              </AvatarFallback>
            </Avatar>
          ) : (
            <Avatar className="h-8 w-8 bg-gradient-to-br from-blue-500 to-purple-600">
              <AvatarFallback className="bg-transparent text-white text-sm">
                <Bot className="h-4 w-4" />
              </AvatarFallback>
            </Avatar>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm">
              {isUser ? "你" : "Hermes"}
            </span>
            <span className="text-xs text-muted-foreground">
              {new Date(message.created_at).toLocaleTimeString("zh-CN", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>

          <div className="prose prose-sm max-w-none dark:prose-invert">
            {message.isStreaming && message.content === "" ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>思考中...</span>
              </div>
            ) : (
              <div className="whitespace-pre-wrap">{message.content}</div>
            )}
          </div>

          {/* Tool calls if any */}
          {message.tool_calls && message.tool_calls.length > 0 && (
            <ToolCallDisplay
              toolCalls={message.tool_calls.map((tool: any, idx: number) => ({
                id: tool.id || `tool-${idx}`,
                name: tool.name || tool.function?.name || "unknown",
                args: tool.args || tool.function?.arguments || {},
                status: tool.status || "success",
                result: tool.result,
                error: tool.error,
                startTime: tool.startTime,
                endTime: tool.endTime,
              }))}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export function MessageList({ messages }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <div className="w-16 h-16 mb-4 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <Bot className="h-8 w-8 text-white" />
        </div>
        <h2 className="text-xl font-semibold mb-2">欢迎使用 Hermes</h2>
        <p className="text-muted-foreground max-w-sm">
          我是你的 AI 编程助手。我可以帮你写代码、调试、解释概念，或者讨论技术方案。
        </p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="divide-y divide-border/50">
        {messages.map((message) => (
          <MessageItem key={message.id} message={message} />
        ))}
      </div>
    </ScrollArea>
  );
}
