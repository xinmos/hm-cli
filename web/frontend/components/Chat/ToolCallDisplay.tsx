"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Terminal,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  FileText,
  Search,
  Edit3,
  Globe,
  Command,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, any>;
  status: "pending" | "running" | "success" | "error";
  result?: any;
  error?: string;
  startTime?: string;
  endTime?: string;
}

interface ToolCallDisplayProps {
  toolCalls: ToolCall[];
}

const toolIcons: Record<string, React.ElementType> = {
  Read: FileText,
  Write: Edit3,
  Edit: Edit3,
  Bash: Command,
  Grep: Search,
  Glob: Search,
  WebFetch: Globe,
  WebSearch: Globe,
  default: Terminal,
};

const toolColors: Record<string, string> = {
  Read: "bg-blue-500/10 text-blue-600 border-blue-500/20",
  Write: "bg-green-500/10 text-green-600 border-green-500/20",
  Edit: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
  Bash: "bg-purple-500/10 text-purple-600 border-purple-500/20",
  Grep: "bg-orange-500/10 text-orange-600 border-orange-500/20",
  Glob: "bg-pink-500/10 text-pink-600 border-pink-500/20",
  WebFetch: "bg-cyan-500/10 text-cyan-600 border-cyan-500/20",
  WebSearch: "bg-indigo-500/10 text-indigo-600 border-indigo-500/20",
  default: "bg-gray-500/10 text-gray-600 border-gray-500/20",
};

function ToolCallItem({ toolCall }: { toolCall: ToolCall }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const Icon = toolIcons[toolCall.name] || toolIcons.default;
  const colorClass = toolColors[toolCall.name] || toolColors.default;

  const getStatusIcon = () => {
    switch (toolCall.status) {
      case "pending":
        return <Clock className="h-4 w-4 text-muted-foreground" />;
      case "running":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case "success":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "error":
        return <XCircle className="h-4 w-4 text-red-500" />;
    }
  };

  const getStatusText = () => {
    switch (toolCall.status) {
      case "pending":
        return "等待中";
      case "running":
        return "执行中";
      case "success":
        return "成功";
      case "error":
        return "失败";
    }
  };

  const formatDuration = () => {
    if (!toolCall.startTime) return null;
    const start = new Date(toolCall.startTime);
    const end = toolCall.endTime ? new Date(toolCall.endTime) : new Date();
    const duration = end.getTime() - start.getTime();
    if (duration < 1000) return `${duration}ms`;
    return `${(duration / 1000).toFixed(1)}s`;
  };

  return (
    <div className="border rounded-lg overflow-hidden bg-muted/30">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-3 p-3 hover:bg-muted/50 transition-colors text-left"
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}

        <div className={cn("p-1.5 rounded-md", colorClass)}>
          <Icon className="h-4 w-4" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm">{toolCall.name}</span>
            <Badge variant="outline" className="text-xs font-normal">
              {getStatusText()}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground truncate">
            {Object.entries(toolCall.args)
              .map(([k, v]) => `${k}: ${JSON.stringify(v).slice(0, 30)}`)
              .join(", ")}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {getStatusIcon()}
          {formatDuration() && (
            <span className="text-xs text-muted-foreground">{formatDuration()}</span>
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t bg-background/50">
          {/* Arguments */}
          <div className="p-3 border-b">
            <h5 className="text-xs font-medium text-muted-foreground mb-2">参数</h5>
            <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-40">
              {JSON.stringify(toolCall.args, null, 2)}
            </pre>
          </div>

          {/* Result or Error */}
          {toolCall.status === "success" && toolCall.result !== undefined && (
            <div className="p-3 border-b">
              <h5 className="text-xs font-medium text-green-600 mb-2">执行结果</h5>
              <pre className="text-xs bg-green-50 dark:bg-green-950 p-2 rounded overflow-auto max-h-60">
                {typeof toolCall.result === "string"
                  ? toolCall.result
                  : JSON.stringify(toolCall.result, null, 2)}
              </pre>
            </div>
          )}

          {toolCall.status === "error" && toolCall.error && (
            <div className="p-3">
              <h5 className="text-xs font-medium text-red-600 mb-2">错误信息</h5>
              <div className="text-xs bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300 p-2 rounded">
                {toolCall.error}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolCallDisplay({ toolCalls }: ToolCallDisplayProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Terminal className="h-3.5 w-3.5" />
        <span>工具调用 ({toolCalls.length})</span>
      </div>
      <div className="space-y-2">
        {toolCalls.map((toolCall) => (
          <ToolCallItem key={toolCall.id} toolCall={toolCall} />
        ))}
      </div>
    </div>
  );
}
