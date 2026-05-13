from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import orjson

from hermes.core.memory.models import EntityRef, KnowledgeEdge, KnowledgeNode


class KnowledgeGraph:
    """JSON-file backed co-occurrence knowledge graph for entity relationship tracing."""

    def __init__(self, file_path: Path) -> None:
        self._path = file_path
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: dict[str, KnowledgeEdge] = {}
        # Lookup index: entity_type:entity_id -> node id
        self._entity_index: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            return
        try:
            data = orjson.loads(self._path.read_bytes())
            for n in data.get("nodes", []):
                node = KnowledgeNode.from_dict(n)
                self._nodes[node.id] = node
                key = f"{node.entity_type}:{node.name}"
                self._entity_index[key] = node.id
            for e in data.get("edges", []):
                edge = KnowledgeEdge.from_dict(e)
                self._edges[edge.id] = edge
        except Exception:
            self._nodes = {}
            self._edges = {}
            self._entity_index = {}

    def _save(self) -> None:
        data: dict[str, Any] = {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
        }
        self._path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    def add_entities(self, entity_refs: list[EntityRef], episode_id: str) -> None:
        node_ids: list[str] = []
        for ref in entity_refs:
            key = f"{ref.entity_type}:{ref.name}"
            if key in self._entity_index:
                node = self._nodes[self._entity_index[key]]
                if episode_id not in node.source_episodes:
                    node.source_episodes.append(episode_id)
                node.confidence = min(1.0, node.confidence + 0.05)
                node.bump_version()
            else:
                node = KnowledgeNode(
                    id=str(uuid.uuid4()),
                    entity_type=ref.entity_type,
                    name=ref.name,
                    confidence=0.3,
                    source_episodes=[episode_id],
                )
                self._nodes[node.id] = node
                self._entity_index[key] = node.id
            node_ids.append(node.id)

        # Create co-occurrence edges between entity pairs in the same episode
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                source_id = node_ids[i]
                target_id = node_ids[j]
                edge_key = f"{source_id}::{target_id}"
                if edge_key in self._edges:
                    edge = self._edges[edge_key]
                    if episode_id not in edge.source_episodes:
                        edge.source_episodes.append(episode_id)
                    edge.confidence = min(1.0, edge.confidence + 0.05)
                else:
                    edge = KnowledgeEdge(
                        id=str(uuid.uuid4()),
                        source_id=source_id,
                        target_id=target_id,
                        relation_type="co_occurrence",
                        confidence=0.3,
                        source_episodes=[episode_id],
                    )
                    self._edges[edge.id] = edge

        if node_ids:
            self._save()

    def query_related_entities(self, entity_name: str) -> list[tuple[KnowledgeNode, KnowledgeEdge]]:
        """Return related nodes and their connecting edges (1-hop traversal)."""
        # Find matching nodes by name
        matched_ids: set[str] = set()
        for key, nid in self._entity_index.items():
            if entity_name.lower() in key.lower():
                matched_ids.add(nid)

        if not matched_ids:
            return []

        results: list[tuple[KnowledgeNode, KnowledgeEdge]] = []
        seen: set[str] = set()

        for eid, edge in self._edges.items():
            if edge.source_id in matched_ids and edge.target_id not in matched_ids:
                target = self._nodes.get(edge.target_id)
                if target and edge.id not in seen:
                    results.append((target, edge))
                    seen.add(edge.id)
            elif edge.target_id in matched_ids and edge.source_id not in matched_ids:
                source = self._nodes.get(edge.source_id)
                if source and edge.id not in seen:
                    results.append((source, edge))
                    seen.add(edge.id)

        results.sort(key=lambda x: x[1].confidence, reverse=True)
        return results

    def get_node(self, entity_type: str, entity_id: str) -> KnowledgeNode | None:
        key = f"{entity_type}:{entity_id}"
        nid = self._entity_index.get(key)
        return self._nodes.get(nid) if nid else None
