"""
app_b/pipeline/registry.py
──────────────────────────
NodeRegistry maps NodeType → BaseNode subclass.

To add a completely new node type:
  1. Add a value to shared/contracts.py  NodeType enum
  2. Create a class in nodes/builtin.py (or a new file)
  3. Call  registry.register(NodeType.YOUR_TYPE, YourNodeClass)  below

Nothing else needs to change.
"""
from __future__ import annotations

import sys
import pathlib
from typing import Type

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from shared.contracts import NodeConfig, NodeType
from app_b.pipeline.nodes.base import BaseNode
from app_b.pipeline.nodes.builtin import (
    CommentaryNode,
    CritiqueNode,
    SummaryNode,
    ValidationNode,
)


class NodeRegistry:
    """Singleton registry — import the module-level `registry` instance."""

    def __init__(self) -> None:
        self._map: dict[NodeType, Type[BaseNode]] = {}

    def register(self, node_type: NodeType, cls: Type[BaseNode]) -> None:
        """Register a node class for a given NodeType."""
        self._map[node_type] = cls

    def create(self, config: NodeConfig) -> BaseNode:
        """
        Instantiate a node from its config.
        Raises KeyError if node_type is not registered.
        """
        cls = self._map.get(config.node_type)
        if cls is None:
            registered = [t.value for t in self._map]
            raise KeyError(
                f"No node registered for type '{config.node_type}'. "
                f"Registered types: {registered}"
            )
        return cls(config)

    def registered_types(self) -> list[str]:
        return [t.value for t in self._map]


# ── Module-level singleton ─────────────────────────────────────────────────

registry = NodeRegistry()

# Built-in registrations
registry.register(NodeType.COMMENTARY,  CommentaryNode)
registry.register(NodeType.VALIDATION,  ValidationNode)
registry.register(NodeType.SUMMARY,     SummaryNode)
registry.register(NodeType.CRITIQUE,    CritiqueNode)
