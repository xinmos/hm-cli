"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  User,
  Bot,
  Loader2,
  Sparkles,
  Clock3,
  Command,
  FileText,
  Edit3,
  Search,
  Globe,
  Terminal,
  Check,
  Copy,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Message } from "@/app/page";

interface MessageListProps {
  messages: Message[];
  bottomRef?: React.RefObject<HTMLDivElement>;
}

const actionIcons: Record<string, React.ElementType> = {
  Bash: Command,
  Read: FileText,
  Write: Edit3,
  Edit: Edit3,
  Grep: Search,
  Glob: Search,
  WebFetch: Globe,
  WebSearch: Globe,
  memory: Clock3,
  default: Loader2,
};

function ThinkingStatus({ currentAction }: { currentAction?: string }) {
  const [dotCount, setDotCount] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => {
      setDotCount((current) => (current + 1) % 3);
    }, 450);
    return () => window.clearInterval(timer);
  }, []);

  const action = currentAction || "正在分析你的问题";
  const toolName = action.includes("(") ? action.split("(", 1)[0].trim() : "";
  const CurrentIcon = actionIcons[toolName] || actionIcons.default;
  const dots = ".".repeat(dotCount + 1);

  return (
    <div className="rounded-3xl border border-sky-200/80 bg-[linear-gradient(135deg,rgba(240,249,255,0.95),rgba(239,246,255,0.72))] px-4 py-4 text-sky-900 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/85 shadow-sm ring-1 ring-sky-200/70">
          <CurrentIcon className={cn("h-4 w-4 text-sky-700", CurrentIcon === Loader2 && "animate-spin")} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tracking-[0.01em]">Hermes 正在处理</span>
            <span className="inline-flex items-center rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium text-sky-700 ring-1 ring-sky-200/80">
              当前动作
            </span>
          </div>
          <p className="mt-1 text-sm text-sky-800/85">{action}</p>
          <p className="mt-2 text-xs text-sky-700/70">我在整理结果{dots}</p>
        </div>
      </div>
    </div>
  );
}

async function copyTextToClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function MarkdownMessage({ content, isStreaming }: { content: string; isStreaming?: boolean }) {
  return (
    <div className="markdown-body text-[15px] leading-[1.75] text-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-3 leading-[1.75] last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-6 leading-[1.75]">{children}</ul>,
          ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-6 leading-[1.75]">{children}</ol>,
          li: ({ children }) => <li className="mb-1 marker:text-muted-foreground last:mb-0">{children}</li>,
          h1: ({ children }) => <h1 className="mb-2 mt-4 text-2xl font-semibold leading-[1.3] first:mt-0">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-2 mt-4 text-xl font-semibold leading-[1.3] first:mt-0">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-2 mt-4 text-lg font-semibold leading-[1.3] first:mt-0">{children}</h3>,
          blockquote: ({ children }) => (
            <blockquote className="my-4 border-l-4 border-border bg-muted/40 px-4 py-3 leading-[1.8] text-muted-foreground">
              {children}
            </blockquote>
          ),
          code: ({ children, className }) =>
            className ? (
              <code className="block overflow-x-auto rounded-xl bg-zinc-950 px-4 py-3 font-mono text-sm leading-6 text-zinc-100">
                {children}
              </code>
            ) : (
              <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.9em] text-foreground">
                {children}
              </code>
            ),
          pre: ({ children }) => <pre className="my-4 overflow-x-auto leading-[1.8]">{children}</pre>,
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
  const [isCopied, setIsCopied] = useState(false);
  const canCopy = message.content.trim().length > 0;

  useEffect(() => {
    if (!isCopied) {
      return;
    }

    const timeoutId = window.setTimeout(() => setIsCopied(false), 2000);
    return () => window.clearTimeout(timeoutId);
  }, [isCopied]);

  const handleCopy = async () => {
    if (!canCopy) {
      return;
    }

    await copyTextToClipboard(message.content);
    setIsCopied(true);
  };

  return (
    <div
      data-role={message.role}
      className={cn(
        "chat-message-item px-4 py-2 md:px-6",
        isUser ? "bg-muted/30" : "bg-background"
      )}
    >
      <div className="mx-auto flex max-w-3xl items-start gap-3">
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
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex h-8 items-center gap-2">
            <span className="text-sm font-medium leading-none">
              {isUser ? "你" : "Hermes"}
            </span>
            <span className="text-xs leading-none text-muted-foreground">
              {new Date(message.created_at).toLocaleTimeString("zh-CN", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
            {isAssistant && message.isStreaming && (
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium leading-none text-blue-700">
                <Sparkles className="h-3 w-3" />
                {message.streamPhase === "thinking" ? "处理中" : "输出中"}
              </span>
            )}
          </div>

          <div className="max-w-none">
            {message.isStreaming && message.streamPhase === "thinking" ? (
              <ThinkingStatus currentAction={message.currentAction} />
            ) : isUser ? (
              <div className="whitespace-pre-wrap text-[15px] leading-[1.65]">{message.content}</div>
            ) : (
              <MarkdownMessage content={message.content} isStreaming={message.isStreaming} />
            )}
          </div>

          <div className="mt-0.5 flex h-6 justify-end">
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  aria-label="复制这条消息"
                  disabled={!canCopy}
                  onClick={handleCopy}
                  className="flex h-6 w-6 items-center justify-center rounded-full bg-transparent text-[#6b7280] opacity-70 transition-all duration-150 ease-in-out hover:bg-[rgba(0,0,0,0.05)] hover:text-[#111827] hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-[#6b7280]"
                >
                  {isCopied ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{isCopied ? "已复制" : "复制"}</p>
              </TooltipContent>
            </Tooltip>
          </div>
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
          我是一个面向个人工作的智能 Agent，正在朝你的 Jarvis 进化：理解目标、调用技能、管理上下文，并协助你推进复杂任务。
        </p>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={120}>
      <div>
        {messages.map((message) => (
          <MessageItem key={message.id} message={message} />
        ))}
        <div ref={bottomRef} className="h-0" />
      </div>
    </TooltipProvider>
  );
}
