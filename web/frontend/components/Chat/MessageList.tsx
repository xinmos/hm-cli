"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot, Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ToolCallDisplay, type ToolCall } from "./ToolCallDisplay";
import type { Message } from "@/app/page";

interface MessageListProps {
  messages: Message[];
  bottomRef?: React.RefObject<HTMLDivElement | null>;
}

function MarkdownMessage({ content, isStreaming }: { content: string; isStreaming?: boolean }) {
  return (
    <div className="markdown-body text-[15px] leading-7 text-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="mb-4 list-disc pl-6 space-y-2">{children}</ul>,
          ol: ({ children }) => <ol className="mb-4 list-decimal pl-6 space-y-2">{children}</ol>,
          li: ({ children }) => <li className="marker:text-muted-foreground">{children}</li>,
          h1: ({ children }) => <h1 className="mb-4 mt-6 text-2xl font-semibold first:mt-0">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-3 mt-6 text-xl font-semibold first:mt-0">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-3 mt-5 text-lg font-semibold first:mt-0">{children}</h3>,
          blockquote: ({ children }) => (
            <blockquote className="mb-4 border-l-4 border-border bg-muted/40 px-4 py-3 text-muted-foreground">
              {children}
            </blockquote>
          ),
          code: ({ inline, children }) =>
            inline ? (
              <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.9em] text-foreground">
                {children}
              </code>
            ) : (
              <code className="block overflow-x-auto rounded-xl bg-zinc-950 px-4 py-3 font-mono text-sm leading-6 text-zinc-100">
                {children}
              </code>
            ),
          pre: ({ children }) => <pre className="mb-4 mt-4 overflow-x-auto">{children}</pre>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-blue-600 underline underline-offset-4 hover:text-blue-500"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="mb-4 mt-4 overflow-x-auto rounded-xl border border-border">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-muted/50">{children}</thead>,
          th: ({ children }) => <th className="border-b border-border px-3 py-2 text-left font-medium">{children}</th>,
          td: ({ children }) => <td className="border-b border-border px-3 py-2 align-top last:border-b-0">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && content !== "" && (
        <span className="ml-1 inline-block h-5 w-2 translate-y-1 animate-pulse rounded-sm bg-blue-500/80" />
      )}
    </div>
  );
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
            {isAssistant && message.isStreaming && (
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                <Sparkles className="h-3 w-3" />
                {message.streamPhase === "thinking" ? "思考中" : "输出中"}
              </span>
            )}
          </div>

          <div className="max-w-none">
            {message.isStreaming && message.streamPhase === "thinking" ? (
              <div className="flex items-center gap-3 rounded-2xl border border-blue-100 bg-blue-50/80 px-4 py-3 text-blue-700">
                <Loader2 className="h-4 w-4 animate-spin" />
                <div className="flex flex-col">
                  <span className="text-sm font-medium">Hermes 正在思考</span>
                  <span className="text-xs text-blue-600/80">我在整理答案结构，很快开始输出。</span>
                </div>
              </div>
            ) : isUser ? (
              <div className="whitespace-pre-wrap text-[15px] leading-7">{message.content}</div>
            ) : (
              <MarkdownMessage content={message.content} isStreaming={message.isStreaming} />
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

export function MessageList({ messages, bottomRef }: MessageListProps) {
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
    <div className="divide-y divide-border/50">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
      <div ref={bottomRef} className="h-0" />
    </div>
  );
}
