from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter()


class ModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    context_size: int
    is_available: bool


@router.get("", response_model=List[ModelResponse])
async def list_models():
    return [
        {
            "id": "doubao-seed-2.0",
            "name": "Doubao-Seed-2.0",
            "provider": "bytedance",
            "context_size": 128000,
            "is_available": True,
        },
        {
            "id": "gpt-4",
            "name": "GPT-4",
            "provider": "openai",
            "context_size": 128000,
            "is_available": True,
        },
        {
            "id": "gpt-3.5-turbo",
            "name": "GPT-3.5 Turbo",
            "provider": "openai",
            "context_size": 16384,
            "is_available": True,
        },
    ]
