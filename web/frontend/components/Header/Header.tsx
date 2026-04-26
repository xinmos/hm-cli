"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Code2, Copy, ExternalLink, Menu } from "lucide-react";
import type { Message } from "@/app/page";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface HeaderProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  onToggleWorkspace: () => void;
  title: string;
  messages: Message[];
}

const ROLE_LABELS: Record<Message["role"], string> = {
  user: "用户",
  assistant: "Hermes",
  system: "系统",
};

function getLocalDateStamp(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function sanitizeFilenamePart(value: string): string {
  return value
    .trim()
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .slice(0, 80);
}

function buildMarkdown(title: string, messages: Message[]): string {
  const normalizedTitle = title.trim() || "未命名对话";
  const exportedAt = new Date().toLocaleString("zh-CN", { hour12: false });
  const sections = messages.map((message, index) => {
    const label = ROLE_LABELS[message.role] || message.role;
    const timestamp = message.created_at
      ? new Date(message.created_at).toLocaleString("zh-CN", { hour12: false })
      : "";
    const heading = `## ${index + 1}. ${label}${timestamp ? ` (${timestamp})` : ""}`;
    const content = message.content.trim() || "_空消息_";

    return `${heading}\n\n${content}`;
  });

  return [`# ${normalizedTitle}`, "", `> 导出时间：${exportedAt}`, "", "---", "", ...sections].join("\n");
}

async function copyMarkdownToClipboard(markdown: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(markdown);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = markdown;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

export function Header({
  isSidebarOpen,
  onToggleSidebar,
  onToggleWorkspace,
  title,
  messages,
}: HeaderProps) {
  const [successAction, setSuccessAction] = useState<"export" | "copy" | null>(null);
  const hasMessages = messages.length > 0;
  const markdown = useMemo(() => buildMarkdown(title, messages), [title, messages]);

  useEffect(() => {
    if (!successAction) {
      return;
    }

    const timeoutId = window.setTimeout(() => setSuccessAction(null), 2000);
    return () => window.clearTimeout(timeoutId);
  }, [successAction]);

  const handleExport = () => {
    if (!hasMessages) {
      return;
    }

    const filenameTitle = sanitizeFilenamePart(title) || "未命名对话";
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download = `${filenameTitle}_${getLocalDateStamp()}.md`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setSuccessAction("export");
  };

  const handleCopy = async () => {
    if (!hasMessages) {
      return;
    }

    await copyMarkdownToClipboard(markdown);
    setSuccessAction("copy");
  };

  return (
    <TooltipProvider>
      <header className="h-14 border-b border-border flex items-center justify-between px-4 bg-background">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9"
            onClick={onToggleSidebar}
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div className="flex min-w-0 items-center gap-2">
            <span className="font-semibold text-sm">Hermes</span>
            <span className="text-muted-foreground">|</span>
            <span className="truncate text-sm text-muted-foreground">{title}</span>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild disabled={!hasMessages}>
                  <button
                    type="button"
                    aria-label="导出对话"
                    disabled={!hasMessages}
                    className="flex h-8 w-8 items-center justify-center rounded-full bg-transparent text-[#6b7280] transition-all duration-150 ease-in-out hover:bg-[rgba(0,0,0,0.05)] hover:text-[#111827] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-[#6b7280]"
                  >
                    {successAction ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <ExternalLink className="h-4 w-4" />
                    )}
                  </button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent>
                <p>{successAction === "copy" ? "已复制" : successAction === "export" ? "已导出" : "导出对话"}</p>
              </TooltipContent>
            </Tooltip>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleExport}>
                <ExternalLink className="mr-2 h-4 w-4" />
                导出 Markdown
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleCopy}>
                <Copy className="mr-2 h-4 w-4" />
                复制 Markdown
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="h-9 w-9" onClick={onToggleWorkspace}>
                <Code2 className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>打开工作区编辑器</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </header>
    </TooltipProvider>
  );
}
