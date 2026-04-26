"use client";

import { useState, useRef, useCallback, useMemo, useEffect } from "react";
import {
  Send,
  Mic,
  Hand,
  Shield,
  ChevronDown,
  Check,
  Paperclip,
  FileText,
  Image,
  X,
  Laptop,
  GitBranch,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { fetchModels, type ChatAttachment, type ModelSummary, type WorkspaceInfo } from "@/lib/api";

interface ChatInputProps {
  onSend: (message: string, options: { permissions: string; model: string; attachments?: ChatAttachment[] }) => void;
  isConnected: boolean;
  disabled?: boolean;
  workspaceInfo: WorkspaceInfo | null;
  tokenUsage: {
    used: number;
    total: number;
  };
}

const permissions = [
  { id: "default", name: "默认权限", icon: Hand },
  { id: "full", name: "完全访问权限", icon: Shield },
];

export function ChatInput({
  onSend,
  disabled,
  workspaceInfo,
  tokenUsage,
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [selectedPermission, setSelectedPermission] = useState(permissions[0]);
  const [modelOptions, setModelOptions] = useState<ModelSummary[]>([]);
  const availableModels = useMemo(() => {
    const configuredModel = workspaceInfo?.model
      ? [{ id: workspaceInfo.model, name: workspaceInfo.model }]
      : [];
    const fetchedModels = modelOptions.map((model) => ({ id: model.id, name: model.name }));
    return [...configuredModel, ...fetchedModels].filter(
      (model, index, all) => all.findIndex((item) => item.id === model.id) === index
    );
  }, [modelOptions, workspaceInfo]);
  const [selectedModel, setSelectedModel] = useState(availableModels[0]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (availableModels.length === 0) return;
    setSelectedModel((current) =>
      availableModels.some((model) => model.id === current?.id) ? current : availableModels[0]
    );
  }, [availableModels]);

  useEffect(() => {
    fetchModels()
      .then(setModelOptions)
      .catch((error) => console.error("Failed to load models:", error));
  }, []);

  const handleSubmit = useCallback(() => {
    if ((!input.trim() && attachments.length === 0) || disabled || !selectedModel) return;

    onSend(input.trim(), {
      permissions: selectedPermission.id,
      model: selectedModel.id,
      attachments,
    });
    setInput("");
    setAttachments([]);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [attachments, input, disabled, onSend, selectedPermission, selectedModel]);

  const handleFileChange = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) {
      return;
    }

    const loaded = await Promise.all(
      files.slice(0, 5).map(async (file) => {
        const isImage = file.type.startsWith("image/");
        const content = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onerror = () => reject(reader.error);
          reader.onload = () => resolve(String(reader.result || ""));
          if (isImage) {
            reader.readAsDataURL(file);
          } else {
            reader.readAsText(file);
          }
        });

        return {
          name: file.name,
          type: isImage ? "image" : "file",
          content,
          mime_type: file.type || undefined,
        } satisfies ChatAttachment;
      })
    );

    setAttachments((prev) => [...prev, ...loaded].slice(0, 5));
    event.target.value = "";
  }, []);

  const removeAttachment = useCallback((index: number) => {
    setAttachments((prev) => prev.filter((_, currentIndex) => currentIndex !== index));
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInput(e.target.value);

      // Auto-resize textarea
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = `${Math.min(
          textareaRef.current.scrollHeight,
          200
        )}px`;
      }
    },
    []
  );

  const usagePercent = tokenUsage.total > 0
    ? Math.min(100, Math.round((tokenUsage.used / tokenUsage.total) * 100))
    : 0;
  const remainingPercent = Math.max(0, 100 - usagePercent);
  const usedDisplay = `${Math.max(0, Math.round(tokenUsage.used / 1024))}k`;
  const totalInK = Number.isFinite(tokenUsage.total) && tokenUsage.total > 0
    ? Math.round(tokenUsage.total / 1024)
    : 0;
  const totalDisplay = `${totalInK}k`;

  return (
    <TooltipProvider delayDuration={120}>
      <div className="px-4 pb-4 pt-2">
        <div className="relative mx-auto max-w-3xl">
          <div className="pointer-events-none absolute -inset-x-4 -top-4 h-16 rounded-[24px] bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.95),rgba(255,255,255,0))]" />

        <div className="relative overflow-hidden rounded-[24px] border border-neutral-200/80 bg-white shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neutral-100 to-transparent" />

          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 px-4 pt-3">
              {attachments.map((attachment, index) => {
                const AttachmentIcon = attachment.type === "image" ? Image : FileText;
                return (
                  <div
                    key={`${attachment.name}-${index}`}
                    className="flex max-w-[220px] items-center gap-2 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-xs text-neutral-600"
                  >
                    <AttachmentIcon className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{attachment.name}</span>
                    <button
                      type="button"
                      className="rounded p-0.5 text-neutral-400 hover:bg-neutral-200 hover:text-neutral-700"
                      onClick={() => removeAttachment(index)}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          <Textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="要求后续变更"
            className="min-h-[64px] resize-none border-0 bg-transparent px-5 pb-2 pt-4 text-[15px] leading-6 text-neutral-800 placeholder:text-neutral-400 focus-visible:ring-0 focus-visible:ring-offset-0"
            disabled={disabled}
            rows={1}
          />

          <div className="flex items-center justify-between px-3 pb-2 pt-1">
            {/* Left side tools */}
            <div className="flex items-center gap-0.5">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 rounded-md text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600"
                onClick={() => fileInputRef.current?.click()}
              >
                <Paperclip className="h-4 w-4" />
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                multiple
                accept="image/*,.txt,.md,.json,.yaml,.yml,.toml,.py,.js,.ts,.tsx,.css,.html,.csv"
                onChange={handleFileChange}
              />

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1 rounded-md px-2 text-xs text-neutral-500 hover:bg-neutral-100 hover:text-neutral-700"
                  >
                    <Hand className="h-3.5 w-3.5" />
                    <span>{selectedPermission.name}</span>
                    <ChevronDown className="h-3 w-3" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="min-w-[140px]">
                  {permissions.map((permission) => (
                    <DropdownMenuItem
                      key={permission.id}
                      onClick={() => setSelectedPermission(permission)}
                      className="flex items-center gap-2 text-sm"
                    >
                      <permission.icon className="h-3.5 w-3.5" />
                      {permission.name}
                      {selectedPermission.id === permission.id && (
                        <Check className="ml-auto h-3.5 w-3.5" />
                      )}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Right side controls */}
            <div className="flex items-center gap-0.5">
              {/* Model selector */}
              <Select
                value={selectedModel?.id || ""}
                onValueChange={(value) => {
                  const model = availableModels.find((m) => m.id === value);
                  if (model) setSelectedModel(model);
                }}
              >
                <SelectTrigger className="h-7 w-auto min-w-[80px] gap-1 rounded-md border-0 bg-transparent px-2 text-xs text-neutral-500 hover:bg-neutral-100 hover:text-neutral-700 [&>svg]:hidden">
                  <SelectValue />
                  <ChevronDown className="h-3 w-3 text-neutral-400" />
                </SelectTrigger>
                <SelectContent>
                  {availableModels.map((model) => (
                    <SelectItem key={model.id} value={model.id} className="text-xs">
                      {model.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Language selector */}
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-0.5 rounded-md px-1.5 text-xs text-neutral-500 hover:bg-neutral-100 hover:text-neutral-700"
              >
                <span>中</span>
                <ChevronDown className="h-3 w-3" />
              </Button>

              {/* Mic button */}
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 rounded-md text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600"
              >
                <Mic className="h-3.5 w-3.5" />
              </Button>

              {/* Send button */}
              <Button
                size="icon"
                className="ml-0.5 h-7 w-7 rounded-full bg-neutral-700 text-white shadow-none hover:bg-neutral-800 disabled:opacity-40"
                onClick={handleSubmit}
                disabled={(!input.trim() && attachments.length === 0) || disabled || !selectedModel}
              >
                <Send className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 px-2 text-xs text-neutral-400">
          <div className="flex items-center gap-1.5">
            <Laptop className="h-3.5 w-3.5" />
            <span>{workspaceInfo?.project_name || "本地工作"}</span>
            <ChevronDown className="h-3 w-3" />
          </div>
          <div className="flex items-center gap-1.5">
            <GitBranch className="h-3.5 w-3.5" />
            <span>{workspaceInfo?.branch || "main"}</span>
            <ChevronDown className="h-3 w-3" />
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-1.5 text-neutral-400 transition-colors hover:text-neutral-600"
              >
                <span>{usagePercent}% 已用</span>
                <div className="h-1 w-16 overflow-hidden rounded-full bg-neutral-200">
                  <div
                    className="h-full rounded-full bg-neutral-400 transition-all"
                    style={{ width: `${usagePercent}%` }}
                  />
                </div>
              </button>
            </TooltipTrigger>
            <TooltipContent
              side="top"
              align="end"
              sideOffset={12}
              className="w-[260px] rounded-[16px] border border-neutral-200/80 bg-white/95 px-4 py-3 text-center shadow-[0_8px_30px_rgba(0,0,0,0.08)]"
            >
              <p className="text-xs text-neutral-400">背景信息窗口：</p>
              <p className="mt-1 text-sm font-medium text-neutral-800">
                {usagePercent}% 已用（剩余 {remainingPercent}%）
              </p>
              <p className="mt-0.5 text-xs text-neutral-500">
                已用 {usedDisplay} 标记，共 {totalDisplay}
              </p>
              <p className="mt-2 text-xs font-medium text-neutral-700">
                Hermes 自动整理其背景信息
              </p>
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
      </div>
    </TooltipProvider>
  );
}
