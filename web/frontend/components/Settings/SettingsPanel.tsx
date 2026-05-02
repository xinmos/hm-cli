"use client";

import { useState, useEffect } from "react";
import {
  Archive,
  BookOpen,
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Eye,
  EyeOff,
  FileText,
  FolderOpen,
  Info,
  Key,
  ListTree,
  MessageSquare,
  Shield,
  Database,
  Download,
  Plus,
  RotateCcw,
  Save,
  Search,
  ShieldAlert,
  RefreshCw,
  Trash2,
  Upload,
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
import {
  deleteChat,
  fetchChats,
  fetchModelConfig,
  fetchWikiConfig,
  saveModelConfig,
  saveWikiConfig,
  type ModelConfig,
  type WikiConfig,
} from "@/lib/api";

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

type SettingsCategory =
  | "model"
  | "knowledge"
  | "permissions"
  | "data";

const defaultModelSettings: ModelConfig = {
  provider: "openai-compatible",
  api_key: "",
  base_url: "",
  model: "llama-model",
  temperature: 0.7,
  max_tokens: 2048,
  timeout: 60,
  max_retries: 2,
  top_p: 1.0,
  streaming: true,
  custom_models: ["gpt-4o", "doubao-seed-2.0", "deepseek-chat", "qwen-max"],
};

interface PermissionSettings {
  autoApprove: boolean;
  allowedTools: string[];
  blockedCommands: string[];
  sandboxMode: boolean;
}

type DataTab = "overview" | "conversations";
type ToastType = "success" | "error" | "info";
type ToastState = { type: ToastType; message: string } | null;
type HermesConversation = {
  id: string;
  title: string;
  updated_at: string;
  message_count: number;
};

const storageUsage = {
  used: 832,
  total: 1024,
  chatIndex: 4,
  messages: 612,
  memory: 216,
};

const backupHistory = [
  { id: "bk-1", name: "自动备份", time: "今天 09:20", size: "742 MB" },
  { id: "bk-2", name: "手动备份", time: "昨天 18:04", size: "735 MB" },
  { id: "bk-3", name: "恢复前临时备份", time: "4月24日 22:10", size: "728 MB" },
  { id: "bk-4", name: "自动备份", time: "4月23日 09:20", size: "721 MB" },
  { id: "bk-5", name: "自动备份", time: "4月22日 09:20", size: "718 MB" },
];

function normalizeModelSettings(settings: ModelConfig): ModelConfig {
  const customModels = Array.from(
    new Set(
      [settings.model, ...(settings.custom_models || [])]
        .map((model) => model.trim())
        .filter(Boolean)
    )
  );

  return {
    ...settings,
    api_key: settings.api_key?.trim() || null,
    base_url: settings.base_url?.trim() || null,
    model: settings.model.trim(),
    temperature: Number(settings.temperature),
    max_tokens: Number(settings.max_tokens),
    timeout: Number(settings.timeout),
    max_retries: Number(settings.max_retries),
    top_p: Number(settings.top_p),
    custom_models: customModels,
  };
}

function validateModelSettings(settings: ModelConfig): string | null {
  const normalized = normalizeModelSettings(settings);
  if (!normalized.model) return "模型名称不能为空";
  if (!Number.isFinite(normalized.temperature) || normalized.temperature < 0 || normalized.temperature > 2) {
    return "Temperature 必须在 0 到 2 之间";
  }
  if (!Number.isInteger(normalized.max_tokens) || normalized.max_tokens < 1) {
    return "Max Tokens 必须是正整数";
  }
  if (!Number.isInteger(normalized.timeout) || normalized.timeout < 1) {
    return "Timeout 必须是正整数";
  }
  if (!Number.isInteger(normalized.max_retries) || normalized.max_retries < 0) {
    return "Max Retries 必须是 0 或正整数";
  }
  if (!Number.isFinite(normalized.top_p) || normalized.top_p < 0 || normalized.top_p > 1) {
    return "Top P 必须在 0 到 1 之间";
  }
  return null;
}

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const [activeCategory, setActiveCategory] = useState<SettingsCategory>("model");
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");

  // Model settings
  const [modelSettings, setModelSettings] = useState<ModelConfig>(defaultModelSettings);
  const [envSettings, setEnvSettings] = useState<Partial<ModelConfig>>({});
  const [showApiKey, setShowApiKey] = useState(false);
  const [newModelName, setNewModelName] = useState("");
  const [toast, setToast] = useState<ToastState>(null);
  const [wikiConfig, setWikiConfig] = useState<WikiConfig | null>(null);
  const [wikiPathDraft, setWikiPathDraft] = useState(".hermes/llm-wiki");

  const [dataTab, setDataTab] = useState<DataTab>("overview");
  const [cleanupOpen, setCleanupOpen] = useState(false);
  const [autoCleanupEnabled, setAutoCleanupEnabled] = useState(false);
  const [cleanupDays, setCleanupDays] = useState(90);
  const [contextLimit, setContextLimit] = useState(256);
  const [importConflict, setImportConflict] = useState<"skip" | "overwrite">("skip");
  const [importFileName, setImportFileName] = useState("");
  const [exportFormat, setExportFormat] = useState<"json" | "markdown">("json");
  const [autoBackupEnabled, setAutoBackupEnabled] = useState(true);
  const [backupFrequency, setBackupFrequency] = useState<"daily" | "weekly">("daily");
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [conversationQuery, setConversationQuery] = useState("");
  const [conversationFilter, setConversationFilter] = useState<"all" | "active" | "archived">("all");
  const [selectedConversations, setSelectedConversations] = useState<string[]>([]);
  const [hermesConversations, setHermesConversations] = useState<HermesConversation[]>([]);

  // Permission settings
  const [permissionSettings, setPermissionSettings] = useState<PermissionSettings>({
    autoApprove: false,
    allowedTools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    blockedCommands: ["rm -rf", "sudo", "chmod", "chown"],
    sandboxMode: true,
  });

  useEffect(() => {
    let cancelled = false;
    fetchModelConfig()
      .then((response) => {
        if (cancelled) return;
        setModelSettings(response.config);
        setEnvSettings(response.env_masked);
      })
      .catch((error) => {
        console.error("Failed to load model config:", error);
        setSaveStatus("error");
      });

    fetchWikiConfig()
      .then((response) => {
        if (cancelled) return;
        setWikiConfig(response);
        setWikiPathDraft(response.path);
      })
      .catch((error) => {
        console.error("Failed to load llm-wiki config:", error);
      });

    fetchChats()
      .then((chats) => {
        if (cancelled) return;
        setHermesConversations(chats);
      })
      .catch((error) => {
        console.error("Failed to load .hermes sessions:", error);
      });

    const savedSettings = localStorage.getItem("hermes-settings");
    if (savedSettings) {
      try {
        const parsed = JSON.parse(savedSettings);
        if (parsed.permissions) setPermissionSettings(parsed.permissions);
      } catch (e) {
        console.error("Failed to parse settings:", e);
      }
    }

    return () => {
      cancelled = true;
    };
  }, []);

  // Save settings
  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus("idle");

    try {
      const validationError = validateModelSettings(modelSettings);
      if (activeCategory === "model" && validationError) {
        setSaveStatus("error");
        return;
      }

      if (activeCategory === "model") {
        const response = await saveModelConfig(normalizeModelSettings(modelSettings));
        setModelSettings(response.config);
        setEnvSettings(response.env_masked);
      } else if (activeCategory === "knowledge") {
        const path = wikiPathDraft.trim();
        if (!path) {
          setSaveStatus("error");
          return;
        }
        const response = await saveWikiConfig(path);
        setWikiConfig(response);
        setWikiPathDraft(response.path);
      } else {
        const settings = {
          permissions: permissionSettings,
        };
        localStorage.setItem("hermes-settings", JSON.stringify(settings));
      }
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
    { id: "knowledge" as const, name: "知识库", icon: FolderOpen },
    { id: "permissions" as const, name: "权限设置", icon: Shield },
    { id: "data" as const, name: "数据管理", icon: Database },
  ];

  const addCustomModel = (name: string) => {
    const model = name.trim();
    if (!model) return;
    setModelSettings((prev) => ({
      ...prev,
      model,
      custom_models: Array.from(new Set([model, ...prev.custom_models])),
    }));
    setNewModelName("");
  };

  const removeCustomModel = (name: string) => {
    setModelSettings((prev) => ({
      ...prev,
      custom_models: prev.custom_models.filter((model) => model !== name),
    }));
  };

  const fieldLabel = (label: string, tooltip: string) => (
    <div className="flex items-center gap-1.5">
      <label className="text-sm font-medium">{label}</label>
      <Tooltip>
        <TooltipTrigger asChild>
          <Info className="h-3.5 w-3.5 text-muted-foreground" />
        </TooltipTrigger>
        <TooltipContent className="max-w-[280px] text-xs">{tooltip}</TooltipContent>
      </Tooltip>
    </div>
  );

  const showToast = (message: string, type: ToastType = "success") => {
    setToast({ message, type });
    window.setTimeout(() => setToast(null), 2600);
  };

  const renderKnowledgeSettings = () => {
    const isDefaultPath = wikiConfig && wikiPathDraft.trim() === wikiConfig.default_path;
    const resolvedPath = wikiConfig?.effective_path || wikiPathDraft || ".hermes/llm-wiki";

    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-medium mb-1">知识库</h3>
          <p className="text-sm text-muted-foreground">配置 llm-wiki 工作区，用于 AI 知识管理和问答</p>
        </div>

        <Separator />

        <div className="space-y-5">
          {/* What is llm-wiki */}
          <div className="rounded-md border bg-muted/20 p-4 space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              <span>什么是 llm-wiki？</span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              llm-wiki 是一个基于 Obsidian 的 LLM 知识库系统。你可以将原始资料放入 raw/sources/，
              AI 会自动整理、归纳并生成结构化的 wiki 页面到 wiki/ 目录中，支持实体、概念、合成分类管理。
            </p>
          </div>

          {/* Directory config */}
          <div className="space-y-2">
            <label className="text-sm font-medium">工作区目录</label>
            <Input
              value={wikiPathDraft}
              placeholder=".hermes/llm-wiki"
              onChange={(event) => setWikiPathDraft(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              实际路径：<span className="font-mono text-foreground">{resolvedPath}</span>
            </p>
            {wikiConfig?.env_path && (
              <p className="text-xs text-amber-600">
                环境变量正在覆盖配置：{wikiConfig.env_path}
              </p>
            )}
          </div>

          {!isDefaultPath && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setWikiPathDraft(wikiConfig?.default_path || ".hermes/llm-wiki")}
            >
              恢复默认目录
            </Button>
          )}

          {/* Note */}
          <div className="rounded-md border-l-2 border-l-primary bg-muted/20 p-4 space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <FolderOpen className="h-4 w-4 text-muted-foreground" />
              <span>目录初始化</span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              这里只配置路径。如果该目录尚无 llm-wiki 结构，需要在与 AI 对话时通过技能指令进行初始化，
              系统会用内置模板创建 Obsidian vault、schema、raw/sources 和 wiki 子目录。
              初始化后可用 Obsidian 打开该目录进行可视化浏览。
            </p>
          </div>
        </div>
      </div>
    );
  };

  // Render model settings
  const renderModelSettings = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-1">模型配置</h3>
        <p className="text-sm text-muted-foreground">保存后会写入后端配置文件，并在下一次 LLM 调用时生效</p>
      </div>

      <Separator />

      <div className="space-y-5">
        <div className="space-y-2">
          {fieldLabel("API Key", "OpenAI 兼容 API 的密钥。默认从页面配置读取；为空时可回退到环境变量。")}
          <div className="relative">
            <Input
              type={showApiKey ? "text" : "password"}
              placeholder={String(envSettings.api_key || "sk-...")}
              value={modelSettings.api_key || ""}
              onChange={(e) =>
                setModelSettings((prev) => ({ ...prev, api_key: e.target.value }))
              }
              className="pr-10"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1 h-8 w-8"
              onClick={() => setShowApiKey((value) => !value)}
            >
              {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
          </div>
          {envSettings.api_key && (
            <p className="text-xs text-muted-foreground">环境变量回退值：{String(envSettings.api_key)}</p>
          )}
        </div>

        <div className="space-y-2">
          {fieldLabel("Base URL", "OpenAI 兼容端点地址，例如自部署、Azure、Ollama 或国产模型 Provider。")}
          <Input
            placeholder={String(envSettings.base_url || "https://api.openai.com/v1")}
            value={modelSettings.base_url || ""}
            onChange={(e) =>
              setModelSettings((prev) => ({ ...prev, base_url: e.target.value }))
            }
          />
          {envSettings.base_url && (
            <p className="text-xs text-muted-foreground">环境变量回退值：{String(envSettings.base_url)}</p>
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              {fieldLabel("常用模型列表", "点击模型标签即可设为当前默认模型；新增模型会随配置一起持久化。")}
              <p className="text-xs text-muted-foreground">
                当前模型：{modelSettings.model || String(envSettings.model || "未设置")}
                {envSettings.model && !modelSettings.model ? `；环境变量回退值：${String(envSettings.model)}` : ""}
              </p>
            </div>
            <div className="flex min-w-[260px] gap-2">
              <Input
                value={newModelName}
                placeholder="添加模型名"
                onChange={(e) => setNewModelName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCustomModel(newModelName);
                  }
                }}
              />
              <Button type="button" variant="outline" size="icon" onClick={() => addCustomModel(newModelName)}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {modelSettings.custom_models.map((model) => (
              <button
                key={model}
                type="button"
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors",
                  modelSettings.model === model
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background hover:bg-muted"
                )}
                onClick={() => setModelSettings((prev) => ({ ...prev, model }))}
              >
                <span>{model}</span>
                <X
                  className="h-3 w-3 opacity-70 hover:opacity-100"
                  onClick={(event) => {
                    event.stopPropagation();
                    removeCustomModel(model);
                  }}
                />
              </button>
            ))}
          </div>
        </div>

        <Separator />

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            {fieldLabel("Temperature", "控制输出随机性，LangChain ChatOpenAI 通用支持，范围 0 到 2。")}
            <Input
              type="number"
              min="0"
              max="2"
              step="0.1"
              value={modelSettings.temperature}
              onChange={(e) =>
                setModelSettings((prev) => ({
                  ...prev,
                  temperature: Number(e.target.value),
                }))
              }
            />
          </div>
          <div className="space-y-2">
            {fieldLabel("Max Tokens", "限制单次回复长度。部分模型或 Provider 可能忽略该参数，取决于 API 端点。")}
            <Input
              type="number"
              min="1"
              value={modelSettings.max_tokens}
              onChange={(e) =>
                setModelSettings((prev) => ({
                  ...prev,
                  max_tokens: Number(e.target.value),
                }))
              }
            />
          </div>
          <div className="space-y-2">
            {fieldLabel("Timeout", "请求超时时间，单位秒；会传给 ChatOpenAI 的 request_timeout。")}
            <Input
              type="number"
              min="1"
              value={modelSettings.timeout}
              onChange={(e) =>
                setModelSettings((prev) => ({
                  ...prev,
                  timeout: Number(e.target.value),
                }))
              }
            />
          </div>
          <div className="space-y-2">
            {fieldLabel("Max Retries", "请求失败后的重试次数。设置为 0 表示不重试。")}
            <Input
              type="number"
              min="0"
              value={modelSettings.max_retries}
              onChange={(e) =>
                setModelSettings((prev) => ({
                  ...prev,
                  max_retries: Number(e.target.value),
                }))
              }
            />
          </div>
          <div className="space-y-2">
            {fieldLabel("Top P", "核采样参数。多数 OpenAI 兼容接口支持，但个别 Provider 可能忽略。")}
            <Input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={modelSettings.top_p}
              onChange={(e) =>
                setModelSettings((prev) => ({
                  ...prev,
                  top_p: Number(e.target.value),
                }))
              }
            />
          </div>
          <div className="flex items-center justify-between rounded-md border px-3 py-2">
            <div className="space-y-0.5">
              {fieldLabel("Streaming", "开启后使用流式响应；关闭后测试连接仍会使用普通 invoke。")}
              <p className="text-xs text-muted-foreground">影响下一次模型调用</p>
            </div>
            <Switch
              checked={modelSettings.streaming}
              onCheckedChange={(checked) =>
                setModelSettings((prev) => ({ ...prev, streaming: checked }))
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

  // Render data settings
  const renderDataSettings = () => {
    const storagePercent = Math.round((storageUsage.used / storageUsage.total) * 100);
    const progressColor = storagePercent >= 90
      ? "bg-destructive"
      : storagePercent >= 75
        ? "bg-amber-500"
        : "bg-primary";
    const storageCards = [
      {
        id: "chat-index",
        title: "会话索引",
        path: ".hermes/web/chats.json",
        size: `${storageUsage.chatIndex} MB`,
        icon: MessageSquare,
        action: "重建索引",
      },
      {
        id: "messages",
        title: "会话消息",
        path: ".hermes/web/messages",
        size: `${storageUsage.messages} MB`,
        icon: ListTree,
        action: "清理旧会话",
      },
      {
        id: "memory",
        title: "记忆库",
        path: ".hermes/memory.db",
        size: `${storageUsage.memory} MB`,
        icon: Database,
        action: "压缩记忆",
      },
    ];
    const filteredConversations = hermesConversations.filter((conversation) => {
      const matchesQuery = conversation.title.toLowerCase().includes(conversationQuery.toLowerCase());
      const matchesFilter = conversationFilter === "all"
        || (conversationFilter === "active" && conversation.message_count > 0)
        || (conversationFilter === "archived" && conversation.message_count === 0);
      return matchesQuery && matchesFilter;
    });
    const allVisibleSelected = filteredConversations.length > 0
      && filteredConversations.every((conversation) => selectedConversations.includes(conversation.id));

    const handleImportFile = (file: File | undefined) => {
      if (!file) return;
      const isSupported = file.name.endsWith(".json") || file.name.endsWith(".md") || file.name.endsWith(".markdown");
      if (!isSupported) {
        showToast("只支持 JSON 或 Markdown 文件", "error");
        return;
      }
      setImportFileName(file.name);
      showToast(`已选择 ${file.name}，导入任务待确认`, "info");
    };

    const toggleConversation = (conversationId: string) => {
      setSelectedConversations((prev) =>
        prev.includes(conversationId)
          ? prev.filter((id) => id !== conversationId)
          : [...prev, conversationId]
      );
    };

    const toggleAllVisible = () => {
      setSelectedConversations((prev) => {
        const visibleIds = filteredConversations.map((conversation) => conversation.id);
        if (allVisibleSelected) {
          return prev.filter((id) => !visibleIds.includes(id));
        }
        return Array.from(new Set([...prev, ...visibleIds]));
      });
    };

    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-medium mb-1">数据管理</h3>
          <p className="text-sm text-muted-foreground">管理当前工作区 .hermes 目录下的 Hermes 会话与记忆数据</p>
        </div>

        <div className="inline-flex rounded-md border bg-muted/30 p-1">
          {[
            { id: "overview" as const, label: "存储与备份" },
            { id: "conversations" as const, label: "对话管理" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setDataTab(tab.id)}
              className={cn(
                "rounded px-3 py-1.5 text-sm transition-colors",
                dataTab === tab.id
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {dataTab === "overview" ? (
          <div className="space-y-6">
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-medium">存储概览</h4>
                  <p className="text-xs text-muted-foreground">
                    .hermes 已使用 {storageUsage.used} MB / {storageUsage.total} MB
                  </p>
                </div>
                <span className={cn(
                  "rounded px-2 py-1 text-xs font-medium",
                  storagePercent >= 90
                    ? "bg-destructive/10 text-destructive"
                    : storagePercent >= 75
                      ? "bg-amber-100 text-amber-700"
                      : "bg-muted text-muted-foreground"
                )}>
                  {storagePercent}% 已用
                </span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                <div className={cn("h-full rounded-full transition-all", progressColor)} style={{ width: `${storagePercent}%` }} />
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                {storageCards.map((item) => (
                  <div key={item.id} className="rounded-md border bg-background p-3">
                    <div className="mb-3 flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <item.icon className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <span className="text-sm font-medium">{item.title}</span>
                          <p className="mt-0.5 text-[11px] text-muted-foreground">{item.path}</p>
                        </div>
                      </div>
                      <span className="text-sm font-semibold">{item.size}</span>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-8 w-full"
                      onClick={() => showToast(`${item.action}任务已创建`, "info")}
                    >
                      {item.action}
                    </Button>
                  </div>
                ))}
              </div>

              <div className="rounded-md border">
                <button
                  type="button"
                  className="flex w-full items-center justify-between px-3 py-2 text-left"
                  onClick={() => setCleanupOpen((value) => !value)}
                >
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">自动清理策略</span>
                  </div>
                  {cleanupOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
                {cleanupOpen && (
                  <div className="space-y-4 border-t p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">自动删除旧会话</p>
                        <p className="text-xs text-muted-foreground">作用于 .hermes/web/chats.json 和 .hermes/web/messages</p>
                      </div>
                      <Switch checked={autoCleanupEnabled} onCheckedChange={setAutoCleanupEnabled} />
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1.5">
                        <label className="text-xs font-medium text-muted-foreground">删除 N 天前会话</label>
                        <Input
                          type="number"
                          min="1"
                          value={cleanupDays}
                          onChange={(event) => setCleanupDays(Number(event.target.value))}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-medium text-muted-foreground">上下文长度上限</label>
                        <Input
                          type="number"
                          min="16"
                          value={contextLimit}
                          onChange={(event) => setContextLimit(Number(event.target.value))}
                        />
                      </div>
                    </div>
                    <Button type="button" size="sm" onClick={() => showToast("自动清理策略已保存")}>
                      保存策略
                    </Button>
                  </div>
                )}
              </div>
            </section>

            <Separator />

            <section className="space-y-4">
              <div>
                <h4 className="text-sm font-medium">数据迁移</h4>
                <p className="text-xs text-muted-foreground">导入和导出 .hermes/web 会话数据，大文件会以后台任务处理</p>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div
                  className="rounded-md border border-dashed p-4"
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    handleImportFile(event.dataTransfer.files?.[0]);
                  }}
                >
                  <Upload className="mb-3 h-5 w-5 text-muted-foreground" />
                  <p className="text-sm font-medium">导入会话 JSON / Markdown</p>
                  <p className="mt-1 text-xs text-muted-foreground">导入到 .hermes/web，冲突时按所选策略处理</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <label className="inline-flex h-9 cursor-pointer items-center justify-center rounded-md border border-input bg-background px-3 text-sm hover:bg-accent">
                      选择文件
                      <input
                        type="file"
                        accept=".json,.md,.markdown"
                        className="hidden"
                        onChange={(event) => handleImportFile(event.target.files?.[0])}
                      />
                    </label>
                    <Select value={importConflict} onValueChange={(value) => setImportConflict(value as "skip" | "overwrite")}>
                      <SelectTrigger className="h-9 w-[120px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="skip">冲突跳过</SelectItem>
                        <SelectItem value="overwrite">冲突覆盖</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {importFileName && <p className="mt-2 text-xs text-muted-foreground">已选择：{importFileName}</p>}
                </div>

                <div className="rounded-md border p-4">
                  <Download className="mb-3 h-5 w-5 text-muted-foreground" />
                  <p className="text-sm font-medium">导出 .hermes 会话</p>
                  <p className="mt-1 text-xs text-muted-foreground">JSON 包含 chats.json 与 messages，Markdown 适合只读归档</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Select value={exportFormat} onValueChange={(value) => setExportFormat(value as "json" | "markdown")}>
                      <SelectTrigger className="h-9 w-[180px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="json">JSON 完整数据</SelectItem>
                        <SelectItem value="markdown">Markdown 只读</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button type="button" size="sm" onClick={() => showToast("导出任务已加入后台队列", "info")}>
                      开始导出
                    </Button>
                  </div>
                </div>
              </div>
            </section>

            <Separator />

            <section className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="text-sm font-medium">备份与恢复</h4>
                  <p className="text-xs text-muted-foreground">恢复前会自动备份当前 .hermes/web 会话状态</p>
                </div>
                <div className="flex items-center gap-3">
                  <Select value={backupFrequency} onValueChange={(value) => setBackupFrequency(value as "daily" | "weekly")}>
                    <SelectTrigger className="h-9 w-[96px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">每天</SelectItem>
                      <SelectItem value="weekly">每周</SelectItem>
                    </SelectContent>
                  </Select>
                  <Switch checked={autoBackupEnabled} onCheckedChange={setAutoBackupEnabled} />
                </div>
              </div>
              <div className="space-y-2">
                {backupHistory.map((backup) => (
                  <div key={backup.id} className="flex items-center justify-between rounded-md border px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Archive className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium">{backup.name}</p>
                        <p className="text-xs text-muted-foreground">{backup.time} · {backup.size}</p>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (window.confirm("恢复前会先创建当前状态的临时备份，确认继续？")) {
                          showToast(`正在从 ${backup.time} 的备份恢复`, "info");
                        }
                      }}
                    >
                      <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                      恢复
                    </Button>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-md border border-destructive/30 bg-destructive/5 p-4">
              <div className="mb-3 flex items-start gap-2">
                <ShieldAlert className="mt-0.5 h-5 w-5 text-destructive" />
                <div>
                  <h4 className="text-sm font-semibold text-destructive">危险区域</h4>
                  <p className="text-xs text-muted-foreground">
                    清除所有数据会影响 .hermes/web/chats.json、.hermes/web/messages 和会话备份索引。操作前建议先导出备份。
                  </p>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                <Input
                  value={deleteConfirmText}
                  onChange={(event) => setDeleteConfirmText(event.target.value)}
                  placeholder="输入 DELETE-HERMES-DATA 以确认"
                />
                <Button
                  type="button"
                  variant="destructive"
                  disabled={deleteConfirmText !== "DELETE-HERMES-DATA"}
                  onClick={() => {
	                    if (window.confirm("二次确认：这会清除 .hermes/web 下的会话数据。确认继续？")) {
                      setDeleteConfirmText("");
                      showToast("清除任务已创建", "info");
                    }
                  }}
                >
                  清除所有数据
                </Button>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3 border-destructive/30 text-destructive hover:text-destructive"
                onClick={() => showToast("备份导出任务已加入后台队列", "info")}
              >
                <Download className="mr-1.5 h-3.5 w-3.5" />
                先导出备份
              </Button>
            </section>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative min-w-[240px] flex-1">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  value={conversationQuery}
                  onChange={(event) => setConversationQuery(event.target.value)}
	                  placeholder="搜索 .hermes 会话"
                  className="pl-9"
                />
              </div>
              <Select value={conversationFilter} onValueChange={(value) => setConversationFilter(value as "all" | "active" | "archived")}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
	                  <SelectItem value="active">有消息</SelectItem>
	                  <SelectItem value="archived">空会话</SelectItem>
                </SelectContent>
              </Select>
              <Button
                type="button"
                variant="outline"
                disabled={selectedConversations.length === 0}
	                onClick={() => showToast(`已创建 ${selectedConversations.length} 个 .hermes 会话的导出任务`, "info")}
              >
                批量导出
              </Button>
              <Button
                type="button"
                variant="outline"
                className="text-destructive hover:text-destructive"
                disabled={selectedConversations.length === 0}
                onClick={() => {
	                  if (window.confirm(`确认删除选中的 ${selectedConversations.length} 个 .hermes 会话？`)) {
	                    const selectedIds = [...selectedConversations];
	                    Promise.all(selectedIds.map((chatId) => deleteChat(chatId)))
	                      .then(() => {
	                        setHermesConversations((prev) => prev.filter((conversation) => !selectedIds.includes(conversation.id)));
	                        setSelectedConversations([]);
	                        showToast("已从 .hermes/web 删除选中的会话", "success");
	                      })
	                      .catch(() => showToast("删除 .hermes 会话失败", "error"));
	                  }
                }}
              >
                批量删除
              </Button>
            </div>

            <div className="overflow-hidden rounded-md border">
              <table className="w-full table-fixed text-sm">
                <colgroup>
                  <col className="w-10" />
                  <col />
                  <col className="w-28" />
                  <col className="w-20" />
                  <col className="w-20" />
                </colgroup>
                <thead className="bg-muted/40 text-xs font-medium text-muted-foreground">
                  <tr className="border-b">
                    <th className="px-3 py-2 text-left align-middle">
                      <input type="checkbox" checked={allVisibleSelected} onChange={toggleAllVisible} />
                    </th>
	                    <th className="px-3 py-2 text-left align-middle">.hermes 会话</th>
                    <th className="px-3 py-2 text-left align-middle">更新时间</th>
	                    <th className="px-3 py-2 text-left align-middle">消息数</th>
	                    <th className="px-3 py-2 text-left align-middle">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredConversations.map((conversation) => (
                    <tr key={conversation.id} className="border-b last:border-b-0">
                      <td className="px-3 py-2 align-middle">
                        <input
                          type="checkbox"
                          checked={selectedConversations.includes(conversation.id)}
                          onChange={() => toggleConversation(conversation.id)}
                        />
                      </td>
                      <td className="px-3 py-2 align-middle">
                        <div className="flex min-w-0 items-center gap-2">
                          <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                          <span className="truncate font-medium">{conversation.title}</span>
                        </div>
                      </td>
	                      <td className="px-3 py-2 align-middle text-xs text-muted-foreground">
	                        {new Date(conversation.updated_at).toLocaleString()}
	                      </td>
	                      <td className="px-3 py-2 align-middle text-xs text-muted-foreground">{conversation.message_count}</td>
	                      <td className="px-3 py-2 align-middle">
	                        <span className="inline-flex min-w-12 justify-center rounded bg-muted px-2 py-1 text-xs text-muted-foreground">
	                          {conversation.message_count > 0 ? "有消息" : "空会话"}
	                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredConversations.length === 0 && (
                <div className="px-3 py-8 text-center text-sm text-muted-foreground">没有匹配的对话</div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderContent = () => {
    switch (activeCategory) {
      case "model":
        return renderModelSettings();
      case "knowledge":
        return renderKnowledgeSettings();
      case "permissions":
        return renderPermissionSettings();
      case "data":
        return renderDataSettings();
      default:
        return null;
    }
  };

  if (!isOpen) return null;

  return (
    <TooltipProvider delayDuration={120}>
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
            <div className="max-w-4xl">{renderContent()}</div>
          </ScrollArea>
        </div>
      </div>
      {toast && (
        <div
          className={cn(
            "fixed right-6 top-6 z-[60] rounded-md border bg-background px-4 py-3 text-sm shadow-lg",
            toast.type === "success" && "border-green-200 text-green-700",
            toast.type === "error" && "border-destructive/30 text-destructive",
            toast.type === "info" && "border-border text-foreground"
          )}
        >
          {toast.message}
        </div>
      )}
    </div>
    </TooltipProvider>
  );
}
