import { NextResponse } from "next/server";

const models = [
  {
    id: "doubao-seed-2.0",
    name: "Doubao-Seed-2.0",
    provider: "bytedance",
    context_size: 128000,
    is_available: true,
  },
  {
    id: "gpt-4",
    name: "GPT-4",
    provider: "openai",
    context_size: 128000,
    is_available: true,
  },
  {
    id: "gpt-3.5-turbo",
    name: "GPT-3.5 Turbo",
    provider: "openai",
    context_size: 16384,
    is_available: true,
  },
];

export async function GET() {
  return NextResponse.json(models);
}
