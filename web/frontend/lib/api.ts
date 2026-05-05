import { Chat, Message } from "@/app/page";

export interface WorkspaceInfo {
  project_name: string;
  project_path: string;
  branch: string;
  model: string;
  context_window: number;
}

export interface WorkspaceFileItem {
  name: string;
  path: string;
  type: "file" | "directory";
  size?: number | null;
}

export interface WorkspaceFileContent {
  path: string;
  content: string;
  size: number;
}

export interface SkillSummary {
  path: string;
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  enabled: boolean;
  slash_command: string;
  allowed_tools: string;
  capabilities: string[];
  size: number;
  updated_at: string;
}

export interface SkillFile {
  skill: SkillSummary;
  content: string;
}

export interface MarketSkill {
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  capabilities: string[];
  allowed_tools: string;
  source_id: string;
  content?: string;
  source_url?: string;
}

export interface SkillMarketSource {
  id: string;
  name: string;
  url: string;
}

export interface ModelConfig {
  provider: string;
  api_key: string | null;
  base_url: string | null;
  model: string;
  temperature: number;
  max_tokens: number;
  timeout: number;
  max_retries: number;
  top_p: number;
  streaming: boolean;
  custom_models: string[];
}

export interface ModelConfigResponse {
  config: ModelConfig;
  saved: Record<string, unknown>;
  env: Partial<ModelConfig>;
  env_masked: Partial<ModelConfig>;
}

export interface WikiConfig {
  path: string;
  effective_path: string;
  default_path: string;
  saved_path?: string | null;
  env_path?: string | null;
  exists: boolean;
  is_directory: boolean;
  is_initialized: boolean;
  missing_items: string[];
  status_message: string;
  init_result?: {
    path: string;
    created_dirs: string[];
    created_files: string[];
    skipped_files: string[];
    status: {
      exists: boolean;
      is_directory: boolean;
      is_initialized: boolean;
      missing_items: string[];
      message: string;
    };
  } | null;
}

export interface QQBotConfig {
  app_id: string | null;
  secret: string | null;
  sandbox: boolean;
  timeout: number;
  enable_guild: boolean;
  enable_direct: boolean;
  enable_group: boolean;
  enable_c2c: boolean;
  enable_markdown: boolean;
}

export interface QQBotConfigResponse {
  config: QQBotConfig;
  saved: Record<string, unknown>;
  env: Partial<QQBotConfig>;
  env_masked: Partial<QQBotConfig>;
}

export interface FeishuBotConfig {
  app_id: string | null;
  app_secret: string | null;
  verification_token: string | null;
  encrypt_key: string | null;
  domain: string;
  auto_reconnect: boolean;
}

export interface FeishuBotConfigResponse {
  config: FeishuBotConfig;
  saved: Record<string, unknown>;
  env: Partial<FeishuBotConfig>;
  env_masked: Partial<FeishuBotConfig>;
}

export interface ModelSummary {
  id: string;
  name: string;
  provider: string;
  context_size: number;
  is_available: boolean;
}

function normalizeSkillList(data: unknown): SkillSummary[] {
  if (Array.isArray(data)) {
    return data as SkillSummary[];
  }
  if (
    data &&
    typeof data === "object" &&
    "skills" in data &&
    Array.isArray((data as { skills?: unknown }).skills)
  ) {
    return (data as { skills: SkillSummary[] }).skills;
  }
  throw new Error("Invalid skills response");
}

// 根据环境确定 API 基础 URL
// 开发环境：前端在 3000，后端在 8000
// 生产环境：使用相对路径（同源）
const getApiBase = () => {
  if (typeof window !== "undefined") {
    // 开发环境
    if (window.location.port === "3000" || window.location.hostname === "localhost") {
      return "http://localhost:8000";
    }
  }
  // 生产环境使用相对路径
  return "";
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || getApiBase();

export interface ChatStreamPayload {
  message: string;
  permissions: string;
  model: string;
  message_id: string;
  attachments?: ChatAttachment[];
}

export interface ChatAttachment {
  name: string;
  type: "file" | "image";
  content: string;
  mime_type?: string;
}

export interface StreamChatOptions {
  onEvent: (data: any) => void;
  signal?: AbortSignal;
}

function parseSseEvent(chunk: string): { event: string; data: any } | null {
  const lines = chunk
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line) => line !== "");

  if (lines.length === 0) {
    return null;
  }

  let event = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim() || "message";
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  const data = JSON.parse(dataLines.join("\n"));
  if (data && typeof data === "object" && !("type" in data)) {
    data.type = event;
  }

  return { event, data };
}

export async function fetchChats(): Promise<Chat[]> {
  const res = await fetch(`${API_BASE}/api/chats`);
  if (!res.ok) throw new Error("Failed to fetch chats");
  return res.json();
}

export async function createChat(title?: string): Promise<Chat> {
  const res = await fetch(`${API_BASE}/api/chats`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error("Failed to create chat");
  return res.json();
}

export async function fetchMessages(chatId: string): Promise<Message[]> {
  const res = await fetch(`${API_BASE}/api/chats/${chatId}/messages`);
  if (!res.ok) throw new Error("Failed to fetch messages");
  const data = await res.json();
  // 转换日期格式
  return data.map((m: any) => ({
    ...m,
    created_at: m.created_at || new Date().toISOString(),
  }));
}

export async function deleteChat(chatId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chats/${chatId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete chat");
}

export async function renameChat(chatId: string, title: string): Promise<Chat> {
  const res = await fetch(`${API_BASE}/api/chats/${chatId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error("Failed to rename chat");
  return res.json();
}

export async function fetchWorkspaceInfo(): Promise<WorkspaceInfo> {
  const res = await fetch(`${API_BASE}/api/workspace`);
  if (!res.ok) throw new Error("Failed to fetch workspace info");
  return res.json();
}

export async function fetchWorkspaceFiles(path = ""): Promise<WorkspaceFileItem[]> {
  const params = new URLSearchParams({ path });
  const res = await fetch(`${API_BASE}/api/workspace/files?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch workspace files");
  return res.json();
}

export async function fetchWorkspaceFile(path: string): Promise<WorkspaceFileContent> {
  const params = new URLSearchParams({ path });
  const res = await fetch(`${API_BASE}/api/workspace/file?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch workspace file");
  return res.json();
}

export async function saveWorkspaceFile(path: string, content: string): Promise<WorkspaceFileContent> {
  const params = new URLSearchParams({ path });
  const res = await fetch(`${API_BASE}/api/workspace/file?${params.toString()}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error("Failed to save workspace file");
  return res.json();
}

export async function fetchLocalSkills(): Promise<SkillSummary[]> {
  const res = await fetch(`${API_BASE}/api/skills`);
  if (!res.ok) throw new Error("Failed to fetch skills");
  return normalizeSkillList(await res.json());
}

export async function fetchSkillMarketSources(): Promise<SkillMarketSource[]> {
  const res = await fetch(`${API_BASE}/api/skills/sources`);
  if (!res.ok) throw new Error("Failed to fetch skill sources");
  const data = await res.json();
  if (!Array.isArray(data)) throw new Error("Invalid skill sources response");
  return data;
}

export async function fetchMarketSkills(sourceId: string): Promise<MarketSkill[]> {
  const params = new URLSearchParams({ source_id: sourceId });
  const res = await fetch(`${API_BASE}/api/skills/market?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch market skills");
  const data = await res.json();
  if (!Array.isArray(data)) throw new Error("Invalid market response");
  return data;
}

export async function installMarketSkill(id: string, sourceId: string): Promise<SkillFile> {
  const res = await fetch(`${API_BASE}/api/skills/install`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, source_id: sourceId }),
  });
  if (!res.ok) throw new Error("Failed to install skill");
  return res.json();
}

export async function setLocalSkillEnabled(path: string, enabled: boolean): Promise<SkillSummary> {
  const params = new URLSearchParams({ path });
  const res = await fetch(`${API_BASE}/api/skills/file/enabled?${params.toString()}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error("Failed to update skill state");
  return res.json();
}

export async function fetchModelConfig(): Promise<ModelConfigResponse> {
  const res = await fetch(`${API_BASE}/api/models/config`);
  if (!res.ok) throw new Error("Failed to fetch model config");
  return res.json();
}

export async function fetchWikiConfig(): Promise<WikiConfig> {
  const res = await fetch(`${API_BASE}/api/models/wiki-config`);
  if (!res.ok) throw new Error("Failed to fetch wiki config");
  return res.json();
}

export async function fetchQQConfig(): Promise<QQBotConfigResponse> {
  const res = await fetch(`${API_BASE}/api/models/qq-config`);
  if (!res.ok) throw new Error("Failed to fetch QQ config");
  return res.json();
}

export async function fetchFeishuConfig(): Promise<FeishuBotConfigResponse> {
  const res = await fetch(`${API_BASE}/api/models/feishu-config`);
  if (!res.ok) throw new Error("Failed to fetch Feishu config");
  return res.json();
}

export async function fetchModels(): Promise<ModelSummary[]> {
  const res = await fetch(`${API_BASE}/api/models`);
  if (!res.ok) throw new Error("Failed to fetch models");
  return res.json();
}

export async function saveModelConfig(config: ModelConfig): Promise<ModelConfigResponse> {
  const res = await fetch(`${API_BASE}/api/models/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Failed to save model config");
  return res.json();
}

export async function saveWikiConfig(path: string): Promise<WikiConfig> {
  const res = await fetch(`${API_BASE}/api/models/wiki-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) throw new Error("Failed to save wiki config");
  return res.json();
}

export async function saveQQConfig(config: QQBotConfig): Promise<QQBotConfigResponse> {
  const res = await fetch(`${API_BASE}/api/models/qq-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Failed to save QQ config");
  return res.json();
}

export async function saveFeishuConfig(config: FeishuBotConfig): Promise<FeishuBotConfigResponse> {
  const res = await fetch(`${API_BASE}/api/models/feishu-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Failed to save Feishu config");
  return res.json();
}

export async function initializeWiki(path: string): Promise<WikiConfig> {
  const res = await fetch(`${API_BASE}/api/models/wiki-config/init`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Failed to initialize wiki");
  }
  return data;
}

export async function testModelConfig(config: ModelConfig): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/models/config/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Failed to test model config");
  }
  return data;
}

export async function exportModelEnv(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/models/config/export-env`);
  if (!res.ok) throw new Error("Failed to export model env");
  const data = await res.json();
  return data.content;
}

export async function importModelEnv(content: string): Promise<ModelConfigResponse> {
  const res = await fetch(`${API_BASE}/api/models/config/import-env`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error("Failed to import model env");
  return res.json();
}

export async function deleteLocalSkill(path: string): Promise<void> {
  const params = new URLSearchParams({ path });
  const res = await fetch(`${API_BASE}/api/skills/file?${params.toString()}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete skill");
}

export async function streamChatMessage(
  chatId: string,
  payload: ChatStreamPayload,
  options: StreamChatOptions,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chats/${chatId}/messages/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  if (!res.ok) {
    throw new Error(`Failed to stream message (${res.status})`);
  }
  if (!res.body) {
    throw new Error("Streaming response body is not available");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    buffer = buffer.replace(/\r\n/g, "\n");

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const parsed = parseSseEvent(rawEvent);
      if (parsed) {
        options.onEvent(parsed.data);
      }

      boundary = buffer.indexOf("\n\n");
    }

    if (done) {
      break;
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseEvent(buffer);
    if (parsed) {
      options.onEvent(parsed.data);
    }
  }
}
