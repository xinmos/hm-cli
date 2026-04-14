from dataclasses import asdict
from pathlib import Path
from typing import Any

import orjson

from hermes.app.ports import TaskInfo


class JsonTaskStore:
    def __init__(self, storage_path: Path):
        self._storage = storage_path
        self._storage.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> list[TaskInfo]:
        if not self._storage.exists():
            return []

        try:
            data = orjson.loads(self._storage.read_bytes())
            return [self._dict_to_task(item) for item in data]
        except Exception:
            return []

    def save_all(self, tasks: list[TaskInfo]) -> None:
        data = [asdict(t) for t in tasks]
        self._storage.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    def _dict_to_task(self, item: dict[str, Any]) -> TaskInfo:
        return TaskInfo(
            id=item["id"],
            name=item["name"],
            trigger_type=item["trigger_type"],
            trigger_expr=item["trigger_expr"],
            action=item["action"],
            enabled=item.get("enabled", True),
        )
