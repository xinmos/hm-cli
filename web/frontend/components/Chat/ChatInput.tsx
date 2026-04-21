"use client";

import { useState, useRef, useCallback } from "react";
import { Send, Mic, Hand, Shield, ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";
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

interface ChatInputProps {
  onSend: (message: string, options: { permissions: string; model: string }) => void;
  isConnected: boolean;
  disabled?: boolean;
}

const permissions = [
  { id: "default", name: "默认权限", icon: Hand },
  { id: "full", name: "完全访问权限", icon: Shield },
];

const models = [
  { id: "doubao-seed-2.0", name: "Doubao-Seed-2.0" },
  { id: "gpt-4", name: "GPT-4" },
];

export function ChatInput({ onSend, isConnected, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [selectedPermission, setSelectedPermission] = useState(permissions[0]);
  const [selectedModel, setSelectedModel] = useState(models[0]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    if (!input.trim() || disabled) return;

    onSend(input.trim(), {
      permissions: selectedPermission.id,
      model: selectedModel.id,
    });
    setInput("");

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [input, disabled, onSend, selectedPermission, selectedModel]);

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

  return (
    <div className="p-4">
      {/* Input Container */}
      <div className="relative rounded-2xl border border-border bg-background shadow-sm">
        {/* Textarea */}
        <Textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="输入消息..."
          className="min-h-[80px] resize-none border-0 bg-transparent px-4 py-3 text-base focus-visible:ring-0 focus-visible:ring-offset-0"
          disabled={disabled}
          rows={1}
        />

        {/* Bottom Toolbar */}
        <div className="flex items-center justify-between px-3 py-2 border-t border-border">
          <div className="flex items-center gap-1">
            {/* Permission Selector */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                >
                  <selectedPermission.icon className="h-3.5 w-3.5" />
                  {selectedPermission.name}
                  <ChevronDown className="h-3 w-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                {permissions.map((permission) => (
                  <DropdownMenuItem
                    key={permission.id}
                    onClick={() => setSelectedPermission(permission)}
                    className="flex items-center gap-2"
                  >
                    <permission.icon className="h-4 w-4" />
                    {permission.name}
                    {selectedPermission.id === permission.id && (
                      <Check className="h-4 w-4 ml-auto" />
                    )}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Model Selector */}
            <Select
              value={selectedModel.id}
              onValueChange={(value) => {
                const model = models.find((m) => m.id === value);
                if (model) setSelectedModel(model);
              }}
            >
              <SelectTrigger className="h-8 w-[140px] text-xs border-0 bg-transparent hover:bg-accent">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {models.map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    {model.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-1">
            {/* Voice Input Button */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
            >
              <Mic className="h-4 w-4" />
            </Button>

            {/* Send Button */}
            <Button
              size="icon"
              className="h-8 w-8 rounded-full"
              onClick={handleSubmit}
              disabled={!input.trim() || disabled}
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Token Usage Bar */}
      <div className="mt-3 flex items-center gap-3 px-4">
        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all"
            style={{ width: "0%" }}
          />
        </div>
        <span className="text-xs text-muted-foreground">0k/200k</span>
      </div>
    </div>
  );
}
