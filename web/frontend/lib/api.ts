import { Chat, Message } from "@/app/page";

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
