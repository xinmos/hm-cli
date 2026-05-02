from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProjectResponse(BaseModel):
    id: str
    name: str
    path: str
    created_at: datetime
    chat_count: int
