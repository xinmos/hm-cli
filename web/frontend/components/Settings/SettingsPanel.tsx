"use client";

import { useState, useEffect } from "react";
import {
  Key,
  Shield,
  Palette,
  Globe,
  Keyboard,
  Database,
  Save,
  RefreshCw,
  Check,
  ChevronRight,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
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

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

type SettingsCategory =
  | "model"
  | "permissions"
  | "appearance"
  | "general"
  | "shortcuts"
  | "data";

interface ModelSettings {
  apiKey: string;
  baseUrl: string;
  defaultModel: string;
  temperature: number;
  maxTokens: number;
  topP: number;
}

interface PermissionSettings {
  autoApprove: boolean;
  allowedTools: string[];
  blockedCommands: string[];
  sandboxMode: boolean;
}

interface AppearanceSettings {
  theme: "light" | "dark" | "system";
  fontSize: "small" | "medium" | "large";
  codeTheme: string;
  showLineNumbers: boolean;
  wordWrap: boolean;
}

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const [activeCategory, setActiveCategory] = useState<SettingsCategory>("model");
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");

  // Model settings
  const [modelSettings, setModelSettings] = useState<ModelSettings>({
    apiKey: "",
    baseUrl: "",
    defaultModel: "doubao-seed-2.0",
    temperature: 0.7,
    maxTokens: 2000,
    topP: 1.0,
  });

  // Permission settings
  const [permissionSettings, setPermissionSettings] = useState<PermissionSettings>({
    autoApprove: false,
    allowedTools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    blockedCommands: ["rm -rf", "sudo", "chmod", "chown"],
    sandboxMode: true,
  });

  // Appearance settings
  const [appearanceSettings, setAppearanceSettings] = useState<AppearanceSettings>({
    theme: "system",
    fontSize: "medium",
    codeTheme: "github-dark",
    showLineNumbers: true,
    wordWrap: true,
  });

  // Load settings from localStorage on mount
  useEffect(() => {
    const savedSettings = localStorage.getItem("hermes-settings");
    if (savedSettings) {
      try {
        const parsed = JSON.parse(savedSettings);
        if (parsed.model) setModelSettings(parsed.model);
        if (parsed.permissions) setPermissionSettings(parsed.permissions);
        if (parsed.appearance) setAppearanceSettings(parsed.appearance);
      } catch (e) {
        console.error("Failed to parse settings:", e);
      }
    }
  }, []);

  // Save settings
  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus("idle");

    try {
      const settings = {
        model: modelSettings,
        permissions: permissionSettings,
        appearance: appearanceSettings,
      };
      localStorage.setItem("hermes-settings", JSON.stringify(settings));
      setSaveStatus("success");
      setTimeout(() => setSaveStatus("idle"), 2000);
    } catch (e) {
      setSaveStatus("error");
    } finally {
      setIsSaving(false);
    }
  };

  const categories = [
    { id: "model" as const, name: "模型配置", icon: Key },
    { id: "permissions" as const, name: "权限设置", icon: Shield },
    { id: "appearance" as const, name: "外观设置", icon: Palette },
    { id: "general" as const, name: "通用设置", icon: Globe },
    { id: "shortcuts" as const, name: "快捷键", icon: Keyboard },
    { id: "data" as const, name: "数据管理", icon: Database },
  ];

  // Render model settings
  const renderModelSettings = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-1">模型配置</h3>
        <p className="text-sm text-muted-foreground">配置 LLM 模型的 API 密钥和参数</p>
      </div>

      <Separator />

      <div className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">API Key</label>
          <Input
            type="password"
            placeholder="sk-..."
            value={modelSettings.apiKey}
            onChange={(e) =>
              setModelSettings((prev) => ({ ...prev, apiKey: e.target.value }))
            }
          />
          <p className="text-xs text-muted-foreground">你的 API 密钥将被安全地存储在本地</p>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Base URL (可选)</label>
          <Input
            placeholder="https://api.openai.com/v1"
            value={modelSettings.baseUrl}
            onChange={(e) =>
              setModelSettings((prev) => ({ ...prev, baseUrl: e.target.value }))
            }
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">默认模型</label>
          <Select
            value={modelSettings.defaultModel}
            onValueChange={(value) =>
              setModelSettings((prev) => ({ ...prev, defaultModel: value }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="doubao-seed-2.0">Doubao-Seed-2.0</SelectItem>
              <SelectItem value="gpt-4">GPT-4</SelectItem>
              <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
              <SelectItem value="claude-3-opus">Claude 3 Opus</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Temperature</label>
            <Input
              type="number"
              min="0"
              max="2"
              step="0.1"
              value={modelSettings.temperature}
              onChange={(e) =>
                setModelSettings((prev) => ({
                  ...prev,
                  temperature: parseFloat(e.target.value),
                }))
              }
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Max Tokens</label>
            <Input
              type="number"
              min="1"
              max="32000"
              value={modelSettings.maxTokens}
              onChange={(e) =>
                setModelSettings((prev) => ({
                  ...prev,
                  maxTokens: parseInt(e.target.value),
                }))
              }
            />
          </div>
        </div>
      </div>
    </div>
  );

  // Render permission settings
  const renderPermissionSettings = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-1">权限设置</h3>
        <p className="text-sm text-muted-foreground">配置工具调用的安全权限</p>
      </div>

      <Separator />

      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <label className="text-sm font-medium">自动批准工具调用</label>
            <p className="text-xs text-muted-foreground">允许 LLM 自动执行工具，无需人工确认</p>
          </div>
          <Switch
            checked={permissionSettings.autoApprove}
            onCheckedChange={(checked) =>
              setPermissionSettings((prev) => ({ ...prev, autoApprove: checked }))
            }
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <label className="text-sm font-medium">沙盒模式</label>
            <p className="text-xs text-muted-foreground">限制工具只能访问项目目录，禁止访问系统文件</p>
          </div>
          <Switch
            checked={permissionSettings.sandboxMode}
            onCheckedChange={(checked) =>
              setPermissionSettings((prev) => ({ ...prev, sandboxMode: checked }))
            }
          />
        </div>

        <Separator />

        <div className="space-y-3">
          <label className="text-sm font-medium">允许的工具</label>
          <div className="flex flex-wrap gap-2">
            {["Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebFetch", "WebSearch"].map((tool) => (
              <button
                key={tool}
                onClick={() => {
                  setPermissionSettings((prev) => ({
                    ...prev,
                    allowedTools: prev.allowedTools.includes(tool)
                      ? prev.allowedTools.filter((t) => t !== tool)
                      : [...prev.allowedTools, tool],
                  }));
                }}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  permissionSettings.allowedTools.includes(tool)
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                {tool}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <label className="text-sm font-medium">禁止的命令</label>
          <div className="space-y-2">
            {permissionSettings.blockedCommands.map((cmd, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <code className="flex-1 px-3 py-1.5 bg-muted rounded text-sm font-mono">{cmd}</code>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() =>
                    setPermissionSettings((prev) => ({
                      ...prev,
                      blockedCommands: prev.blockedCommands.filter((_, i) => i !== idx),
                    }))
                  }
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <div className="flex gap-2">
              <Input
                placeholder="输入要禁止的命令..."
                className="flex-1"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    const value = e.currentTarget.value.trim();
                    if (value) {
                      setPermissionSettings((prev) => ({
                        ...prev,
                        blockedCommands: [...prev.blockedCommands, value],
                      }));
                      e.currentTarget.value = "";
                    }
                  }
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Render appearance settings
  const renderAppearanceSettings = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-1">外观设置</h3>
        <p className="text-sm text-muted-foreground">自定义界面主题和显示选项</p>
      </div>

      <Separator />

      <div className="space-y-6">
        <div className="space-y-3">
          <label className="text-sm font-medium">主题</label>
          <div className="grid grid-cols-3 gap-3">
            {[
              { id: "light", name: "浅色", icon: "☀️" },
              { id: "dark", name: "深色", icon: "🌙" },
              { id: "system", name: "跟随系统", icon: "💻" },
            ].map((theme) => (
              <button
                key={theme.id}
                onClick={() =>
                  setAppearanceSettings((prev) => ({ ...prev, theme: theme.id as any }))
                }
                className={cn(
                  "flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all",
                  appearanceSettings.theme === theme.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-muted-foreground"
                )}
              >
                <span className="text-2xl">{theme.icon}</span>
                <span className="text-sm font-medium">{theme.name}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <label className="text-sm font-medium">字体大小</label>
          <Select
            value={appearanceSettings.fontSize}
            onValueChange={(value) =>
              setAppearanceSettings((prev) => ({ ...prev, fontSize: value as any }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="small">小</SelectItem>
              <SelectItem value="medium">中</SelectItem>
              <SelectItem value="large">大</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator />

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <label className="text-sm font-medium">显示行号</label>
              <p className="text-xs text-muted-foreground">在代码块中显示行号</p>
            </div>
            <Switch
              checked={appearanceSettings.showLineNumbers}
              onCheckedChange={(checked) =>
                setAppearanceSettings((prev) => ({ ...prev, showLineNumbers: checked }))
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <label className="text-sm font-medium">自动换行</label>
              <p className="text-xs text-muted-foreground">代码超出宽度时自动换行</p>
            </div>
            <Switch
              checked={appearanceSettings.wordWrap}
              onCheckedChange={(checked) =>
                setAppearanceSettings((prev) => ({ ...prev, wordWrap: checked }))
              }
            />
          </div>
        </div>
      </div>
    </div>
  );

  // Render general settings
  const renderGeneralSettings = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-1">通用设置</h3>
        <p className="text-sm text-muted-foreground">语言和其他通用选项</p>
      </div>

      <Separator />

      <div className="space-y-6">
        <div className="space-y-3">
          <label className="text-sm font-medium">界面语言</label>
          <Select defaultValue="zh-CN">
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="zh-CN">简体中文</SelectItem>
              <SelectItem value="en">English</SelectItem>
              <SelectItem value="zh-TW">繁體中文</SelectItem>
              <SelectItem value="ja">日本語</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-3">
          <label className="text-sm font-medium">时区</label>
          <Select defaultValue="Asia/Shanghai">
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Asia/Shanghai">北京时间 (UTC+8)</SelectItem>
              <SelectItem value="Asia/Tokyo">东京时间 (UTC+9)</SelectItem>
              <SelectItem value="America/New_York">纽约时间 (UTC-5)</SelectItem>
              <SelectItem value="Europe/London">伦敦时间 (UTC+0)</SelectItem>
              <SelectItem value="UTC">UTC</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator />

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <label className="text-sm font-medium">自动保存对话</label>
              <p className="text-xs text-muted-foreground">自动将对话保存到历史记录</p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <label className="text-sm font-medium">发送消息快捷键</label>
              <p className="text-xs text-muted-foreground">Enter 发送，Shift+Enter 换行</p>
            </div>
            <Switch defaultChecked />
          </div>
        </div>
      </div>
    </div>
  );

  // Render shortcuts settings
  const renderShortcutsSettings = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-1">快捷键</h3>
        <p className="text-sm text-muted-foreground">自定义键盘快捷键</p>
      </div>

      <Separator />

      <div className="space-y-4">
        {[
          { action: "新建对话", shortcut: "Ctrl+N", defaultShortcut: "Ctrl+N" },
          { action: "发送消息", shortcut: "Enter", defaultShortcut: "Enter" },
          { action: "换行", shortcut: "Shift+Enter", defaultShortcut: "Shift+Enter" },
          { action: "搜索对话", shortcut: "Ctrl+K", defaultShortcut: "Ctrl+K" },
          { action: "打开设置", shortcut: "Ctrl+,", defaultShortcut: "Ctrl+," },
          { action: "清空对话", shortcut: "Ctrl+Shift+C", defaultShortcut: "Ctrl+Shift+C" },
          { action: "导出对话", shortcut: "Ctrl+E", defaultShortcut: "Ctrl+E" },
        ].map((item, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors"
          >
            <span className="text-sm">{item.action}</span>
            <div className="flex items-center gap-2">
              <kbd className="px-2 py-1 bg-muted rounded text-xs font-mono border">
                {item.shortcut}
              </kbd>
              {item.shortcut !== item.defaultShortcut && (
                <Button variant="ghost" size="sm" className="h-6 text-xs">
                  重置
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // Render data settings
  const renderDataSettings = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-1">数据管理</h3>
        <p className="text-sm text-muted-foreground">管理你的数据和存储</p>
      </div>

      <Separator />

      <div className="space-y-6">
        <div className="space-y-3">
          <h4 className="text-sm font-medium">存储使用情况</h4>
          <div className="p-4 bg-muted/50 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm">已使用</span>
              <span className="text-sm font-medium">128 MB / 1 GB</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div className="h-full bg-primary rounded-full" style={{ width: "12.5%" }} />
            </div>
          </div>
        </div>

        <Separator />

        <div className="space-y-3">
          <h4 className="text-sm font-medium">数据操作</h4>
          <div className="flex flex-col gap-2">
            <Button variant="outline" className="justify-start">
              <RefreshCw className="h-4 w-4 mr-2" />
              导出所有对话
            </Button>
            <Button variant="outline" className="justify-start">
              <Database className="h-4 w-4 mr-2" />
              备份设置
            </Button>
            <Button variant="outline" className="justify-start text-destructive hover:text-destructive">
              <RefreshCw className="h-4 w-4 mr-2" />
              清除所有数据
            </Button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderContent = () => {
    switch (activeCategory) {
      case "model":
        return renderModelSettings();
      case "permissions":
        return renderPermissionSettings();
      case "appearance":
        return renderAppearanceSettings();
      case "general":
        return renderGeneralSettings();
      case "shortcuts":
        return renderShortcutsSettings();
      case "data":
        return renderDataSettings();
      default:
        return null;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-background rounded-xl shadow-2xl w-full max-w-4xl h-[80vh] flex overflow-hidden">
        {/* Sidebar */}
        <div className="w-56 border-r border-border bg-muted/30 flex flex-col">
          <div className="p-4 border-b border-border">
            <h2 className="font-semibold">设置</h2>
          </div>
          <ScrollArea className="flex-1">
            <div className="p-2 space-y-1">
              {categories.map((category) => (
                <button
                  key={category.id}
                  onClick={() => setActiveCategory(category.id)}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                    activeCategory === category.id
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:bg-background/50"
                  )}
                >
                  <category.icon className="h-4 w-4" />
                  {category.name}
                </button>
              ))}
            </div>
          </ScrollArea>
        </div>

        {/* Content */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center justify-between p-4 border-b border-border">
            <h3 className="font-medium">
              {categories.find((c) => c.id === activeCategory)?.name}
            </h3>
            <div className="flex items-center gap-2">
              {saveStatus === "success" && (
                <span className="text-xs text-green-500 flex items-center gap-1">
                  <Check className="h-3 w-3" />
                  已保存
                </span>
              )}
              {saveStatus === "error" && (
                <span className="text-xs text-destructive">保存失败</span>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleSave}
                disabled={isSaving}
                className="gap-1.5"
              >
                {isSaving ? (
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Save className="h-3.5 w-3.5" />
                )}
                保存
              </Button>
              <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <ScrollArea className="flex-1 p-6">
            <div className="max-w-2xl">{renderContent()}</div>
          </ScrollArea>
        </div>
      </div>
    </div>
  );
}
