from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

router = APIRouter()


class ProjectResponse(BaseModel):
    id: str
    name: str
    path: str
    created_at: datetime
    chat_count: int


projects_db = []


@router.get("", response_model=List[ProjectResponse])
async def list_projects():
    return [
        {
            "id": "hm-cli",
            "name": "hm-cli",
            "path": "/Users/xinqiangxiong/codes/hm-cli",
            "created_at": datetime.now(),
            "chat_count": 2,
        }
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    return {
        "id": project_id,
        "name": project_id,
        "path": f"/path/to/{project_id}",
        "created_at": datetime.now(),
        "chat_count": 0,
    }
