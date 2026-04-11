import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from hermes.config import Config


@dataclass
class ScheduledTask:
    id: str
    name: str
    trigger_type: str  # cron, interval, date
    trigger_expr: str
    action: str
    enabled: bool = True
    created_at: str = None
    last_run: Optional[str] = None
    next_run: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class TaskScheduler:
    def __init__(self, storage_path: Optional[Path] = None):
        self.scheduler = BackgroundScheduler()
        self._tasks: Dict[str, ScheduledTask] = {}
        self._actions: Dict[str, Callable] = {}
        self._storage = storage_path or (Config.WORKDIR / ".hermes" / "tasks.json")
        self._storage.parent.mkdir(parents=True, exist_ok=True)
        self._running = False

    def register_action(self, name: str, fn: Callable) -> None:
        self._actions[name] = fn

    def start(self) -> None:
        if not self._running:
            self.scheduler.start()
            self._running = True
            self._load_tasks()

    def shutdown(self) -> None:
        if self._running:
            self.scheduler.shutdown()
            self._running = False

    def add_task(
        self,
        name: str,
        trigger_type: str,
        trigger_expr: str,
        action: str,
        task_id: Optional[str] = None,
    ) -> ScheduledTask:
        task_id = task_id or str(uuid4())[:8]
        task = ScheduledTask(
            id=task_id,
            name=name,
            trigger_type=trigger_type,
            trigger_expr=trigger_expr,
            action=action,
        )

        trigger = self._parse_trigger(trigger_type, trigger_expr)
        if trigger is None:
            raise ValueError(f"Invalid trigger: {trigger_type} {trigger_expr}")

        def wrapper():
            self._execute_task(task_id)

        self.scheduler.add_job(
            wrapper,
            trigger=trigger,
            id=task_id,
            replace_existing=True,
        )

        self._tasks[task_id] = task
        self._save_tasks()
        return task

    def remove_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self.scheduler.remove_job(task_id)
            del self._tasks[task_id]
            self._save_tasks()
            return True
        return False

    def pause_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self.scheduler.pause_job(task_id)
            self._tasks[task_id].enabled = False
            self._save_tasks()
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self.scheduler.resume_job(task_id)
            self._tasks[task_id].enabled = True
            self._save_tasks()
            return True
        return False

    def list_tasks(self) -> List[ScheduledTask]:
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def _parse_trigger(self, trigger_type: str, expr: str):
        try:
            if trigger_type == "cron":
                parts = expr.split()
                if len(parts) == 5:
                    return CronTrigger(
                        minute=parts[0],
                        hour=parts[1],
                        day=parts[2],
                        month=parts[3],
                        day_of_week=parts[4],
                    )
                return CronTrigger.from_crontab(expr)
            elif trigger_type == "interval":
                kwargs = {}
                for part in expr.split():
                    if "=" in part:
                        k, v = part.split("=")
                        kwargs[k] = int(v)
                return IntervalTrigger(**kwargs)
            elif trigger_type == "date":
                return DateTrigger(run_date=datetime.fromisoformat(expr))
        except Exception:
            return None
        return None

    def _execute_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if not task or not task.enabled:
            return

        task.last_run = datetime.now().isoformat()

        action_fn = self._actions.get(task.action)
        if action_fn:
            try:
                action_fn()
            except Exception as e:
                print(f"Task {task_id} failed: {e}")

        self._save_tasks()

    def _save_tasks(self):
        data = [asdict(t) for t in self._tasks.values()]
        self._storage.write_text(json.dumps(data, indent=2))

    def _load_tasks(self):
        if not self._storage.exists():
            return
        try:
            data = json.loads(self._storage.read_text())
            for item in data:
                if item.get("enabled", True):
                    try:
                        self.add_task(
                            name=item["name"],
                            trigger_type=item["trigger_type"],
                            trigger_expr=item["trigger_expr"],
                            action=item["action"],
                            task_id=item["id"],
                        )
                    except Exception as e:
                        print(f"Failed to load task {item.get('id')}: {e}")
        except Exception as e:
            print(f"Failed to load tasks: {e}")

    def natural_language_schedule(self, description: str, action: str) -> Optional[ScheduledTask]:
        """Parse natural language like 'every day at 9am' into a scheduled task"""
        desc = description.lower().strip()

        # Simple patterns
        if "every day" in desc or "daily" in desc:
            time_match = None
            if "at " in desc:
                parts = desc.split("at ")
                if len(parts) > 1:
                    time_part = parts[1].split()[0]
                    if ":" in time_part:
                        hour, minute = time_part.split(":")
                        return self.add_task(
                            name=f"Daily task: {action}",
                            trigger_type="cron",
                            trigger_expr=f"{minute} {hour} * * *",
                            action=action,
                        )
                    else:
                        return self.add_task(
                            name=f"Daily task: {action}",
                            trigger_type="cron",
                            trigger_expr=f"0 {time_part} * * *",
                            action=action,
                        )

        if "every hour" in desc or "hourly" in desc:
            return self.add_task(
                name=f"Hourly task: {action}",
                trigger_type="cron",
                trigger_expr="0 * * * *",
                action=action,
            )

        if "every minute" in desc:
            return self.add_task(
                name=f"Minutely task: {action}",
                trigger_type="cron",
                trigger_expr="* * * * *",
                action=action,
            )

        return None
