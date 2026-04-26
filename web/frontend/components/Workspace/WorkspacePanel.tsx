"use client";

import { useCallback, useEffect, useState } from "react";
import { Code2, File, Folder, Loader2, RefreshCw, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  fetchWorkspaceFile,
  fetchWorkspaceFiles,
  saveWorkspaceFile,
  type WorkspaceFileItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface WorkspacePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function WorkspacePanel({ isOpen, onClose }: WorkspacePanelProps) {
  const [currentPath, setCurrentPath] = useState("");
  const [items, setItems] = useState<WorkspaceFileItem[]>([]);
  const [selectedPath, setSelectedPath] = useState("");
  const [content, setContent] = useState("");
  const [savedContent, setSavedContent] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  const isDirty = content !== savedContent;
  const parentPath = currentPath.split("/").slice(0, -1).join("/");

  const loadFiles = useCallback(async (path: string) => {
    setIsLoading(true);
    setError("");
    try {
      const nextItems = await fetchWorkspaceFiles(path);
      setItems(nextItems);
      setCurrentPath(path);
    } catch (loadError) {
      console.error("Failed to load workspace files:", loadError);
      setError("无法加载目录");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const openFile = useCallback(async (path: string) => {
    setIsLoading(true);
    setError("");
    try {
      const file = await fetchWorkspaceFile(path);
      setSelectedPath(file.path);
      setContent(file.content);
      setSavedContent(file.content);
    } catch (loadError) {
      console.error("Failed to open workspace file:", loadError);
      setError("只能打开 1MB 内的 UTF-8 文本文件");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const saveFile = useCallback(async () => {
    if (!selectedPath || !isDirty) {
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      const file = await saveWorkspaceFile(selectedPath, content);
      setContent(file.content);
      setSavedContent(file.content);
      await loadFiles(currentPath);
    } catch (saveError) {
      console.error("Failed to save workspace file:", saveError);
      setError("保存失败");
    } finally {
      setIsSaving(false);
    }
  }, [content, currentPath, isDirty, loadFiles, selectedPath]);

  useEffect(() => {
    if (isOpen) {
      void loadFiles("");
    }
  }, [isOpen, loadFiles]);

  if (!isOpen) {
    return null;
  }

  return (
    <aside className="hidden h-full w-[420px] shrink-0 border-l border-border bg-white lg:flex lg:flex-col">
      <div className="flex h-14 items-center justify-between border-b border-border px-3">
        <div className="flex min-w-0 items-center gap-2">
          <Code2 className="h-4 w-4 text-neutral-500" />
          <span className="truncate text-sm font-medium">工作区</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => void loadFiles(currentPath)}
          >
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[160px_1fr]">
        <div className="min-h-0 border-r border-border bg-neutral-50/70">
          <div className="flex h-10 items-center gap-1 border-b border-border px-2 text-xs text-neutral-500">
            <button
              type="button"
              className="truncate rounded px-1.5 py-1 hover:bg-white"
              onClick={() => void loadFiles(parentPath)}
              disabled={!currentPath}
            >
              {currentPath || "项目根目录"}
            </button>
          </div>

          <div className="h-[calc(100%-2.5rem)] overflow-y-auto p-1">
            {items.map((item) => {
              const ItemIcon = item.type === "directory" ? Folder : File;
              return (
                <button
                  key={item.path}
                  type="button"
                  className={cn(
                    "flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-neutral-700 hover:bg-white",
                    selectedPath === item.path && "bg-white shadow-sm"
                  )}
                  onClick={() => {
                    if (item.type === "directory") {
                      void loadFiles(item.path);
                      return;
                    }
                    void openFile(item.path);
                  }}
                >
                  <ItemIcon className="h-3.5 w-3.5 shrink-0 text-neutral-400" />
                  <span className="truncate">{item.name}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex min-w-0 flex-col">
          <div className="flex h-10 items-center justify-between gap-2 border-b border-border px-3">
            <span className="min-w-0 truncate text-xs text-neutral-500">
              {selectedPath || "选择一个文本文件"}
            </span>
            <Button
              size="sm"
              className="h-7 gap-1 px-2 text-xs"
              disabled={!selectedPath || !isDirty || isSaving}
              onClick={() => void saveFile()}
            >
              {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              保存
            </Button>
          </div>

          {error && (
            <div className="border-b border-red-100 bg-red-50 px-3 py-2 text-xs text-red-700">
              {error}
            </div>
          )}

          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            spellCheck={false}
            className="min-h-0 flex-1 resize-none bg-white p-3 font-mono text-xs leading-5 text-neutral-800 outline-none"
            placeholder="文件内容会显示在这里"
          />
        </div>
      </div>
    </aside>
  );
}
