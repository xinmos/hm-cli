"use client";

import { useState } from "react";
import { Plus, Search, Puzzle, Bot, Settings, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SettingsPanel } from "@/components/Settings/SettingsPanel";
import type { Chat } from "@/app/page";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  chats: Chat[];
  currentChatId: string | null;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
}

export function Sidebar({
  isOpen,
  onClose,
  chats,
  currentChatId,
  onSelectChat,
  onNewChat,
}: SidebarProps) {
  const [activeSection, setActiveSection] = useState<"chat" | "search" | "plugins" | "automation" | "settings">("chat");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

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
            className={cn(
              "justify-start gap-3 h-10 px-3 mb-0.5",
              activeSection === "chat" && "bg-white shadow-sm"
            )}
            onClick={() => setActiveSection("chat")}
          >
            <MessageSquare className="h-4 w-4" />
            对话
          </Button>
          <Button
            variant="ghost"
            className={cn(
              "justify-start gap-3 h-10 px-3 mb-0.5",
              activeSection === "search" && "bg-white shadow-sm"
            )}
            onClick={() => setActiveSection("search")}
          >
            <Search className="h-4 w-4" />
            搜索
          </Button>
          <Button
            variant="ghost"
            className={cn(
              "justify-start gap-3 h-10 px-3 mb-0.5",
              activeSection === "plugins" && "bg-white shadow-sm"
            )}
            onClick={() => setActiveSection("plugins")}
          >
            <Puzzle className="h-4 w-4" />
            插件
          </Button>
          <Button
            variant="ghost"
            className={cn(
              "justify-start gap-3 h-10 px-3",
              activeSection === "automation" && "bg-white shadow-sm"
            )}
            onClick={() => setActiveSection("automation")}
          >
            <Bot className="h-4 w-4" />
            自动化
          </Button>
        </div>

        {/* Chat List Area */}
        <div className="flex-1 overflow-hidden flex flex-col min-h-0 px-2">
          {activeSection === "chat" ? (
            <>
              <div className="pb-2 shrink-0" />
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
                            <button
                              key={chat.id}
                              onClick={() => onSelectChat(chat.id)}
                              className={cn(
                                "w-full text-left px-2 py-1.5 rounded text-sm transition-colors",
                                currentChatId === chat.id
                                  ? "bg-white shadow-sm"
                                  : "hover:bg-white/50"
                              )}
                            >
                              <div className="truncate">{chat.title}</div>
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-muted-foreground">
                {activeSection === "search" && "搜索功能开发中..."}
                {activeSection === "plugins" && "插件管理开发中..."}
                {activeSection === "automation" && "自动化功能开发中..."}
              </p>
            </div>
          )}
        </div>

        {/* New Chat & Settings Buttons */}
        <div className="shrink-0 border-t border-border p-2 space-y-1">
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 h-10 px-3 bg-white shadow-sm hover:bg-white/80"
            onClick={onNewChat}
          >
            <Plus className="h-4 w-4" />
            新建聊天
          </Button>
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

      {/* Settings Panel */}
      <SettingsPanel isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </>
  );
}
