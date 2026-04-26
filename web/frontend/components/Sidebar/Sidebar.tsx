"use client";

import { useState } from "react";
import { Plus, Search, Sparkles, Bot, Settings, Pencil, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SettingsPanel } from "@/components/Settings/SettingsPanel";
import { SkillsPanel } from "@/components/Skills/SkillsPanel";
import type { Chat } from "@/app/page";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  chats: Chat[];
  currentChatId: string | null;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
  onDeleteChats?: (chatIds: string[]) => Promise<void>;
  onRenameChat?: (chatId: string, title: string) => Promise<void>;
}

export function Sidebar({
  isOpen,
  onClose,
  chats,
  currentChatId,
  onSelectChat,
  onNewChat,
  onDeleteChats,
  onRenameChat,
}: SidebarProps) {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isSkillsOpen, setIsSkillsOpen] = useState(false);
  const [placeholderPanel, setPlaceholderPanel] = useState<"search" | "automation" | null>(null);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [contextMenu, setContextMenu] = useState<{ chat: Chat; x: number; y: number } | null>(null);

  const groupedChats = chats.reduce((groups, chat) => {
    const date = new Date(chat.updated_at);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    let group = "更早";
    if (diffDays === 0) group = "今天";
    else if (diffDays === 1) group = "昨天";
    else if (diffDays <= 7) group = "最近 7 天";
    else if (diffDays <= 30) group = "最近 30 天";

    if (!groups[group]) groups[group] = [];
    groups[group].push(chat);
    return groups;
  }, {} as Record<string, Chat[]>);

  const groupOrder = ["今天", "昨天", "最近 7 天", "最近 30 天", "更早"];
  const placeholderTitle = placeholderPanel === "search" ? "搜索" : "自动化";
  const PlaceholderIcon = placeholderPanel === "search" ? Search : Bot;

  const handleRename = async (chat: Chat) => {
    setContextMenu(null);
    setEditingChatId(chat.id);
    setEditingTitle(chat.title);
  };

  const handleRenameSubmit = async (chatId: string) => {
    if (!editingTitle.trim()) {
      setEditingChatId(null);
      return;
    }
    await onRenameChat?.(chatId, editingTitle.trim());
    setEditingChatId(null);
  };

  const handleDelete = async (chat: Chat) => {
    setContextMenu(null);
    const confirmed = window.confirm(`确认删除"${chat.title}"吗？`);
    if (!confirmed) return;
    await onDeleteChats?.([chat.id]);
  };

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          "fixed left-0 top-0 bottom-0 z-50 w-[240px] bg-[#f5f5f5] border-r border-border transition-transform duration-200 ease-in-out flex flex-col",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Tools Menu - VERTICAL COLUMN with icons and text */}
        <div className="flex flex-col p-2 shrink-0">
          <Button
            variant="ghost"
            className="justify-start gap-3 h-10 px-3 mb-0.5 bg-white shadow-sm"
            onClick={onNewChat}
          >
            <Plus className="h-4 w-4" />
            新对话
          </Button>
          <Button
            variant="ghost"
            className={cn(
              "justify-start gap-3 h-10 px-3 mb-0.5",
              placeholderPanel === "search" && "bg-white shadow-sm"
            )}
            onClick={() => setPlaceholderPanel("search")}
          >
            <Search className="h-4 w-4" />
            搜索
          </Button>
          <Button
            variant="ghost"
            className={cn(
              "justify-start gap-3 h-10 px-3 mb-0.5",
              isSkillsOpen && "bg-white shadow-sm"
            )}
            onClick={() => setIsSkillsOpen(true)}
          >
            <Sparkles className="h-4 w-4" />
            技能
          </Button>
          <Button
            variant="ghost"
            className={cn(
              "justify-start gap-3 h-10 px-3",
              placeholderPanel === "automation" && "bg-white shadow-sm"
            )}
            onClick={() => setPlaceholderPanel("automation")}
          >
            <Bot className="h-4 w-4" />
            自动化
          </Button>
        </div>

        {/* Chat List Area */}
        <div className="flex-1 overflow-hidden flex flex-col min-h-0 px-2">
          <div className="py-2 shrink-0">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-muted-foreground px-2">
                聊天列表
              </span>
            </div>
          </div>
          <ScrollArea className="flex-1 min-h-0">
            <div className="pb-2">
              {groupOrder.map((group) => {
                const groupChats = groupedChats[group];
                if (!groupChats || groupChats.length === 0) return null;

                return (
                  <div key={group} className="mb-2">
                    <h3 className="text-[11px] font-medium text-muted-foreground px-2 mb-1">
                      {group}
                    </h3>
                    <div className="space-y-0.5">
                      {groupChats.map((chat) => (
                        <div
                          key={chat.id}
                          onContextMenu={(event) => {
                            event.preventDefault();
                            setContextMenu({ chat, x: event.clientX, y: event.clientY });
                          }}
                          className={cn(
                            "flex w-full items-center rounded text-sm transition-colors",
                            currentChatId === chat.id
                              ? "bg-white shadow-sm"
                              : "hover:bg-white/50"
                          )}
                        >
                          {editingChatId === chat.id ? (
                            <div className="w-full px-2 py-1.5">
                              <input
                                autoFocus
                                value={editingTitle}
                                onChange={(e) => setEditingTitle(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    void handleRenameSubmit(chat.id);
                                  } else if (e.key === "Escape") {
                                    setEditingChatId(null);
                                  }
                                }}
                                onBlur={() => void handleRenameSubmit(chat.id)}
                                className="w-full rounded border border-input bg-background px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-ring"
                              />
                            </div>
                          ) : (
                            <button
                              onClick={() => onSelectChat(chat.id)}
                              className="min-w-0 flex-1 overflow-hidden px-2 py-1.5 text-left"
                            >
                              <div className="truncate pr-1">{chat.title}</div>
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </div>

        {/* New Chat & Settings Buttons */}
        <div className="shrink-0 border-t border-border p-2 space-y-1">
          <Button
            variant="ghost"
            className={cn(
              "w-full justify-start gap-3 h-10 px-3",
              isSettingsOpen && "bg-white shadow-sm"
            )}
            onClick={() => setIsSettingsOpen(true)}
          >
            <Settings className="h-4 w-4" />
            设置
          </Button>
        </div>
      </aside>

      {contextMenu && (
        <>
          <div
            className="fixed inset-0 z-[55]"
            onClick={() => setContextMenu(null)}
            onContextMenu={(event) => {
              event.preventDefault();
              setContextMenu(null);
            }}
          />
          <div
            className="fixed z-[60] w-32 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            <button
              type="button"
              className="flex w-full items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground"
              onClick={() => void handleRename(contextMenu.chat)}
            >
              <Pencil className="mr-2 h-4 w-4" />
              重命名
            </button>
            <button
              type="button"
              className="flex w-full items-center rounded-sm px-2 py-1.5 text-sm text-destructive outline-none transition-colors hover:bg-accent hover:text-destructive"
              onClick={() => void handleDelete(contextMenu.chat)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              删除
            </button>
          </div>
        </>
      )}

      {/* Settings Panel */}
      {placeholderPanel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="relative w-full max-w-md rounded-xl bg-background p-6 shadow-2xl">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setPlaceholderPanel(null)}
              className="absolute right-3 top-3 h-8 w-8"
            >
              <X className="h-4 w-4" />
            </Button>
            <div className="flex items-center gap-2">
              <PlaceholderIcon className="h-4 w-4" />
              <h2 className="font-semibold">{placeholderTitle}</h2>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">开发中</p>
          </div>
        </div>
      )}
      <SkillsPanel isOpen={isSkillsOpen} onClose={() => setIsSkillsOpen(false)} />
      <SettingsPanel isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </>
  );
}
