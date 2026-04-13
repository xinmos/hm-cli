from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from hermes.app.ports import SchedulerDriver


class APSchedulerDriver:
    def __init__(self):
        self._scheduler = BackgroundScheduler()
        self._running = False

    def start(self) -> None:
        if not self._running:
            self._scheduler.start()
            self._running = True

    def shutdown(self) -> None:
        if self._running:
            self._scheduler.shutdown()
            self._running = False

    def add_job(
        self,
        job_id: str,
        trigger_type: str,
        trigger_expr: str,
        callback: Callable[[], None],
    ) -> None:
        trigger = self._parse_trigger(trigger_type, trigger_expr)
        if trigger:
            self._scheduler.add_job(
                callback,
                trigger=trigger,
                id=job_id,
                replace_existing=True,
            )

    def remove_job(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    def pause_job(self, job_id: str) -> None:
        try:
            self._scheduler.pause_job(job_id)
        except Exception:
            pass

    def resume_job(self, job_id: str) -> None:
        try:
            self._scheduler.resume_job(job_id)
        except Exception:
            pass

    def _parse_trigger(self, trigger_type: str, expr: str):
        from datetime import datetime

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
