"use client";

import * as React from "react";
import { Menu, Check, ChevronDown, Wifi, WifiOff, RefreshCw, Code2 } from "lucide-react";
import { cn } from "@/lib/utils";
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
  connectionStatus: "connecting" | "connected" | "disconnected";
}

const models = [
  { id: "doubao-seed-2.0", name: "Doubao-Seed-2.0", provider: "bytedance" },
  { id: "gpt-4", name: "GPT-4", provider: "openai" },
  { id: "gpt-3.5-turbo", name: "GPT-3.5 Turbo", provider: "openai" },
];

export function Header({
  isSidebarOpen,
  onToggleSidebar,
  onToggleWorkspace,
  title,
  connectionStatus,
}: HeaderProps) {
  const [selectedModel, setSelectedModel] = React.useState(models[0]);

  return (
    <TooltipProvider>
      <header className="h-14 border-b border-border flex items-center justify-between px-4 bg-background">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9"
            onClick={onToggleSidebar}
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm">Hermes</span>
            <span className="text-muted-foreground">|</span>
            <span className="text-sm text-muted-foreground">{title}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
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

          {/* Connection Status */}
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted/50">
                {connectionStatus === "connected" ? (
                  <Wifi className="h-3.5 w-3.5 text-green-500" />
                ) : connectionStatus === "connecting" ? (
                  <RefreshCw className="h-3.5 w-3.5 text-yellow-500 animate-spin" />
                ) : (
                  <WifiOff className="h-3.5 w-3.5 text-red-500" />
                )}
                <span className="text-xs text-muted-foreground">
                  {connectionStatus === "connected"
                    ? "已连接"
                    : connectionStatus === "connecting"
                    ? "连接中..."
                    : "已断开"}
                </span>
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p>
                {connectionStatus === "connected"
                  ? "SSE 流式服务可用"
                  : connectionStatus === "connecting"
                  ? "正在接收流式响应..."
                  : "最近一次流式请求失败"}
              </p>
            </TooltipContent>
          </Tooltip>

          {/* Model Selector */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="gap-1">
                <span className="text-sm">{selectedModel.name}</span>
                <ChevronDown className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {models.map((model) => (
                <DropdownMenuItem
                  key={model.id}
                  onClick={() => setSelectedModel(model)}
                  className="flex items-center justify-between"
                >
                  <div className="flex flex-col">
                    <span className="font-medium">{model.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {model.provider}
                    </span>
                  </div>
                  {selectedModel.id === model.id && (
                    <Check className="h-4 w-4" />
                  )}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
    </TooltipProvider>
  );
}
