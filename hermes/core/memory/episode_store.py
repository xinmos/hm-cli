from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import orjson

from hermes.core.memory.models import Episode


class EpisodeStore:
    """JSON file-backed episode storage."""

    def __init__(
        self,
        file_path: Path,
        max_episodes: int = 2000,
        decay_rate: float = 0.01,
        min_retention_score: float = 0.1,
    ) -> None:
        self._path = file_path
        self._max_episodes = max_episodes
        self._decay_rate = decay_rate
        self._min_retention_score = min_retention_score
        self._episodes: dict[str, Episode] = {}
        self._load()

    def _load(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        if self._path.exists():
            try:
                data = orjson.loads(self._path.read_bytes())
                episodes = [Episode.from_dict(item) for item in data]
                # Keep most recent episodes within limit
                episodes.sort(key=lambda ep: ep.timestamp, reverse=True)
                for ep in episodes[:self._max_episodes]:
                    self._episodes[ep.id] = ep
            except Exception:
                self._episodes = {}
        else:
            self._try_migrate_from_sqlite()

    def _try_migrate_from_sqlite(self) -> None:
        """Migrate episodes from old SQLite memory.db if it exists."""
        db_path = self._path.parent / "memory.db"
        if not db_path.exists():
            return

        try:
            with sqlite3.connect(str(db_path)) as conn:
                rows = conn.execute(
                    "SELECT id, timestamp, event_type, session_id, summary, "
                    "raw_data, entities, importance, retention_score, tags "
                    "FROM episodes ORDER BY timestamp DESC"
                ).fetchall()

            for row in rows:
                raw_data = orjson.loads(row[5]) if isinstance(row[5], str) else {}
                entities_raw = orjson.loads(row[6]) if isinstance(row[6], str) else []
                tags_raw = orjson.loads(row[9]) if isinstance(row[9], str) else []
                ep_data = {
                    "id": row[0],
                    "timestamp": row[1],
                    "event_type": row[2],
                    "session_id": row[3],
                    "summary": row[4],
                    "raw_data": raw_data,
                    "entities": entities_raw,
                    "importance": row[7],
                    "retention_score": row[8],
                    "tags": tags_raw,
                }
                ep = Episode.from_dict(ep_data)
                self._episodes[ep.id] = ep

            # Trim to max
            sorted_eps = sorted(
                self._episodes.values(), key=lambda ep: ep.timestamp, reverse=True
            )
            self._episodes = {ep.id: ep for ep in sorted_eps[:self._max_episodes]}

            self._save()

            # Rename old DB after successful migration
            db_path.rename(db_path.with_suffix(".db.migrated"))
        except Exception:
            pass

    def _save(self) -> None:
        data = [ep.to_dict() for ep in self._episodes.values()]
        data.sort(key=lambda x: x["timestamp"], reverse=True)
        self._path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    def append(self, episode: Episode) -> None:
        self._episodes[episode.id] = episode
        # Trim if over limit
        if len(self._episodes) > self._max_episodes:
            sorted_eps = sorted(
                self._episodes.values(), key=lambda ep: ep.timestamp, reverse=True
            )
            self._episodes = {ep.id: ep for ep in sorted_eps[:self._max_episodes]}
        self._save()

    def query_by_time(
        self, start: datetime, end: datetime, session_id: str | None = None
    ) -> list[Episode]:
        result = []
        for ep in self._episodes.values():
            if start <= ep.timestamp <= end:
                if session_id is None or ep.session_id == session_id:
                    result.append(ep)
        result.sort(key=lambda ep: ep.timestamp, reverse=True)
        return result

    def get_all(self) -> list[Episode]:
        """Return all episodes as a list."""
        return list(self._episodes.values())

    def record_access(self, episode_id: str, now: datetime) -> None:
        """Apply exponential decay and access boost to an episode."""
        ep = self._episodes.get(episode_id)
        if ep is None:
            return

        last_time = ep.last_accessed or ep.timestamp
        days_since = (now - last_time).total_seconds() / 86400.0
        # Apply decay since last access
        decayed = ep.retention_score * (1 - self._decay_rate) ** days_since
        # Boost on access (capped at 1.0)
        ep.retention_score = min(1.0, decayed + 0.02)
        ep.last_accessed = now
        ep.access_count += 1

    def prune_decayed(self, now: datetime) -> int:
        """Remove episodes whose current decayed score falls below threshold."""
        to_delete: list[str] = []
        for ep in self._episodes.values():
            last_time = ep.last_accessed or ep.timestamp
            days_since = (now - last_time).total_seconds() / 86400.0
            current_score = ep.retention_score * (1 - self._decay_rate) ** days_since
            if current_score < self._min_retention_score:
                to_delete.append(ep.id)

        for eid in to_delete:
            del self._episodes[eid]

        if to_delete:
            self._save()
        return len(to_delete)

    def delete_old(self, before: datetime) -> int:
        removed = 0
        to_delete = [
            eid
            for eid, ep in self._episodes.items()
            if ep.timestamp < before
        ]
        for eid in to_delete:
            del self._episodes[eid]
            removed += 1
        if removed:
            self._save()
        return removed

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_episodes": len(self._episodes),
            "oldest": min(
                (ep.timestamp for ep in self._episodes.values()), default=None
            ),
            "newest": max(
                (ep.timestamp for ep in self._episodes.values()), default=None
            ),
        }
