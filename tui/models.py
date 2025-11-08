"""Data models for Graph TUI."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# === Node Models ===

class NodeStatus(str, Enum):
    """Node execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


class NodePosition(BaseModel):
    """Node position on canvas."""
    x: int = 0
    y: int = 0


class Node(BaseModel):
    """Graph node model."""
    id: str
    name: str
    type: str
    description: Optional[str] = None
    position: NodePosition = Field(default_factory=NodePosition)
    config: Dict[str, Any] = Field(default_factory=dict)
    status: NodeStatus = NodeStatus.PENDING
    parent_ids: List[str] = Field(default_factory=list)
    child_ids: List[str] = Field(default_factory=list)
    
    # Execution metadata
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[Any] = None


# === Edge Models ===

class Edge(BaseModel):
    """Graph edge model."""
    id: str
    source_id: str
    target_id: str
    label: Optional[str] = None


# === Graph Models ===

class GraphStatus(str, Enum):
    """Graph execution status."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Graph(BaseModel):
    """Graph model."""
    id: str
    name: str
    description: Optional[str] = None
    nodes: List[Node] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
    status: GraphStatus = GraphStatus.IDLE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def get_root_nodes(self) -> List[Node]:
        """Get nodes with no parents."""
        return [node for node in self.nodes if not node.parent_ids]
    
    def get_children(self, node_id: str) -> List[Node]:
        """Get child nodes."""
        node = self.get_node(node_id)
        if not node:
            return []
        return [self.get_node(child_id) for child_id in node.child_ids if self.get_node(child_id)]
    
    def get_parents(self, node_id: str) -> List[Node]:
        """Get parent nodes."""
        node = self.get_node(node_id)
        if not node:
            return []
        return [self.get_node(parent_id) for parent_id in node.parent_ids if self.get_node(parent_id)]


# === Execution Models ===

class ExecutionLog(BaseModel):
    """Execution log entry."""
    timestamp: datetime
    node_id: Optional[str] = None
    level: str = "info"  # info, warning, error
    message: str


class Execution(BaseModel):
    """Graph execution model."""
    id: str
    graph_id: str
    status: GraphStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    logs: List[ExecutionLog] = Field(default_factory=list)
    progress: float = 0.0  # 0-100
    
    @property
    def duration(self) -> Optional[float]:
        """Get execution duration in seconds."""
        if not self.started_at:
            return None
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()