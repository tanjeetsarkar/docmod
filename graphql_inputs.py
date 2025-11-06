import strawberry
from typing import Optional, List, Dict, Any
from graphql_types import EdgeCondition, JSON


@strawberry.input
class NodeInput:
    """Input type for creating a node"""
    node_key: str = strawberry.field(description="Unique identifier for the node within the graph")
    name: str = strawberry.field(description="Human-readable name for the node")
    code: str = strawberry.field(description="Python code to execute")
    constants: JSON = strawberry.field(
        default_factory=dict,
        description="Static values passed to the code"
    )
    timeout_seconds: int = strawberry.field(
        default=300,
        description="Maximum execution time in seconds"
    )


@strawberry.input
class EdgeInput:
    """Input type for creating an edge"""
    source_node_key: str = strawberry.field(description="Key of the source node")
    target_node_key: str = strawberry.field(description="Key of the target node")
    condition: EdgeCondition = strawberry.field(
        default=EdgeCondition.ON_SUCCESS,
        description="Condition for executing the target node"
    )


@strawberry.input
class GraphInput:
    """Input type for creating a graph"""
    name: str = strawberry.field(description="Name of the graph")
    description: Optional[str] = strawberry.field(
        default=None,
        description="Description of the graph"
    )
    nodes: List[NodeInput] = strawberry.field(description="List of nodes in the graph")
    edges: List[EdgeInput] = strawberry.field(description="List of edges connecting nodes")


@strawberry.input
class GraphUpdateInput:
    """Input type for updating a graph"""
    name: Optional[str] = None
    description: Optional[str] = None


@strawberry.input
class ExecutionInput:
    """Input type for starting an execution"""
    context: JSON = strawberry.field(
        default_factory=dict,
        description="Global context available to all nodes during execution"
    )


@strawberry.input
class GraphFilterInput:
    """Input type for filtering graphs"""
    name_contains: Optional[str] = None
    is_active: Optional[bool] = None


@strawberry.input
class ExecutionFilterInput:
    """Input type for filtering executions"""
    graph_id: Optional[int] = None
    status: Optional[str] = None
