from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable
from uuid import uuid4

from hermes.app.ports import SchedulerDriver, TaskInfo, TaskStore


@dataclass
class ScheduledTask:
    info: TaskInfo
    callback: Callable[[], None] = field(default=lambda: None)
    last_run: str | None = None


class TaskService:
    def __init__(self, store: TaskStore, scheduler: SchedulerDriver):
        self._store = store
        self._scheduler = scheduler
        self._tasks: dict[str, ScheduledTask] = {}

    def add_task(
        self,
        name: str,
        trigger_type: str,
        trigger_expr: str,
        action_callback: Callable[[], None],
    ) -> TaskInfo:
        task_id = str(uuid4())[:8]
        task_info = TaskInfo(
            id=task_id,
            name=name,
            trigger_type=trigger_type,
            trigger_expr=trigger_expr,
            action="custom",
            enabled=True,
        )

        self._scheduler.add_job(task_id, trigger_type, trigger_expr, action_callback)

        scheduled = ScheduledTask(info=task_info, callback=action_callback)
        self._tasks[task_id] = scheduled
        self._save_tasks()

        return task_info

    def remove_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._scheduler.remove_job(task_id)
            del self._tasks[task_id]
            self._save_tasks()
            return True
        return False

    def pause_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._scheduler.pause_job(task_id)
            self._tasks[task_id].info.enabled = False
            self._save_tasks()
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._scheduler.resume_job(task_id)
            self._tasks[task_id].info.enabled = True
            self._save_tasks()
            return True
        return False

    def list_tasks(self) -> list[TaskInfo]:
        return [t.info for t in self._tasks.values()]

    def get_task(self, task_id: str) -> TaskInfo | None:
        scheduled = self._tasks.get(task_id)
        return scheduled.info if scheduled else None

    def load_persistent_tasks(self) -> None:
        tasks = self._store.load_all()
        for task_info in tasks:
            if task_info.enabled:
                self._scheduler.add_job(
                    task_info.id,
                    task_info.trigger_type,
                    task_info.trigger_expr,
                    lambda tid=task_info.id: self._execute_task(tid),
                )
                scheduled = ScheduledTask(
                    info=task_info,
                    callback=lambda: None,
                )
                self._tasks[task_info.id] = scheduled

    def _save_tasks(self) -> None:
        tasks = [t.info for t in self._tasks.values()]
        self._store.save_all(tasks)

    def _execute_task(self, task_id: str) -> None:
        scheduled = self._tasks.get(task_id)
        if not scheduled or not scheduled.info.enabled:
            return

        scheduled.last_run = datetime.now().isoformat()
        try:
            scheduled.callback()
        except Exception as e:
            print(f"Task {task_id} failed: {e}")

        self._save_tasks()
