import strawberry
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# Enums
@strawberry.enum
class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@strawberry.enum
class EdgeCondition(Enum):
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    ALWAYS = "always"


# Scalar types
JSON = strawberry.scalar(
    Dict[str, Any],
    serialize=lambda v: v,
    parse_value=lambda v: v,
    description="JSON scalar type"
)


# GraphQL Types
@strawberry.type
class Node:
    id: int
    graph_id: int
    node_key: str
    name: str
    code: str
    constants: JSON
    timeout_seconds: int
    
    @strawberry.field
    def outgoing_edges(self, info) -> List['Edge']:
        """Get all edges originating from this node"""
        from database import get_db_context
        from models import Edge as EdgeModel
        
        with get_db_context() as db:
            edges = db.query(EdgeModel).filter(
                EdgeModel.source_node_id == self.id
            ).all()
            return [Edge.from_orm(e) for e in edges]
    
    @strawberry.field
    def incoming_edges(self, info) -> List['Edge']:
        """Get all edges pointing to this node"""
        from database import get_db_context
        from models import Edge as EdgeModel
        
        with get_db_context() as db:
            edges = db.query(EdgeModel).filter(
                EdgeModel.target_node_id == self.id
            ).all()
            return [Edge.from_orm(e) for e in edges]
    
    @strawberry.field
    def executions(self, info, limit: int = 10) -> List['NodeExecution']:
        """Get recent executions of this node"""
        from database import get_db_context
        from models import NodeExecution as NodeExecutionModel
        
        with get_db_context() as db:
            node_execs = db.query(NodeExecutionModel).filter(
                NodeExecutionModel.node_id == self.id
            ).order_by(NodeExecutionModel.started_at.desc()).limit(limit).all()
            return [NodeExecution.from_orm(ne) for ne in node_execs]
    
    @classmethod
    def from_orm(cls, node_model) -> 'Node':
        return cls(
            id=node_model.id,
            graph_id=node_model.graph_id,
            node_key=node_model.node_key,
            name=node_model.name,
            code=node_model.code,
            constants=node_model.constants,
            timeout_seconds=node_model.timeout_seconds
        )


@strawberry.type
class Edge:
    id: int
    graph_id: int
    source_node_id: int
    target_node_id: int
    condition: EdgeCondition
    
    @strawberry.field
    def source_node(self, info) -> Node:
        """Get the source node of this edge"""
        from database import get_db_context
        from models import Node as NodeModel
        
        with get_db_context() as db:
            node = db.query(NodeModel).filter(NodeModel.id == self.source_node_id).first()
            return Node.from_orm(node)
    
    @strawberry.field
    def target_node(self, info) -> Node:
        """Get the target node of this edge"""
        from database import get_db_context
        from models import Node as NodeModel
        
        with get_db_context() as db:
            node = db.query(NodeModel).filter(NodeModel.id == self.target_node_id).first()
            return Node.from_orm(node)
    
    @classmethod
    def from_orm(cls, edge_model) -> 'Edge':
        from models import EdgeCondition as EdgeConditionModel
        return cls(
            id=edge_model.id,
            graph_id=edge_model.graph_id,
            source_node_id=edge_model.source_node_id,
            target_node_id=edge_model.target_node_id,
            condition=EdgeCondition[edge_model.condition.name]
        )


@strawberry.type
class Graph:
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    @strawberry.field
    def nodes(self, info) -> List[Node]:
        """Get all nodes in this graph"""
        from database import get_db_context
        from models import Node as NodeModel
        
        with get_db_context() as db:
            nodes = db.query(NodeModel).filter(NodeModel.graph_id == self.id).all()
            return [Node.from_orm(n) for n in nodes]
    
    @strawberry.field
    def edges(self, info) -> List[Edge]:
        """Get all edges in this graph"""
        from database import get_db_context
        from models import Edge as EdgeModel
        
        with get_db_context() as db:
            edges = db.query(EdgeModel).filter(EdgeModel.graph_id == self.id).all()
            return [Edge.from_orm(e) for e in edges]
    
    @strawberry.field
    def executions(
        self,
        info,
        status: Optional[ExecutionStatus] = None,
        limit: int = 50
    ) -> List['Execution']:
        """Get executions of this graph"""
        from database import get_db_context
        from models import Execution as ExecutionModel, ExecutionStatus as ExecutionStatusModel
        
        with get_db_context() as db:
            query = db.query(ExecutionModel).filter(ExecutionModel.graph_id == self.id)
            
            if status:
                query = query.filter(
                    ExecutionModel.status == ExecutionStatusModel[status.name]
                )
            
            executions = query.order_by(
                ExecutionModel.started_at.desc()
            ).limit(limit).all()
            
            return [Execution.from_orm(e) for e in executions]
    
    @strawberry.field
    def execution_levels(self, info) -> List[List[str]]:
        """Get execution levels for parallel processing"""
        from graph_validator import GraphValidator
        
        nodes = [{'node_key': n.node_key} for n in self.nodes(info)]
        edges = [
            {
                'source_node_key': e.source_node(info).node_key,
                'target_node_key': e.target_node(info).node_key,
                'condition': e.condition.value
            }
            for e in self.edges(info)
        ]
        
        validator = GraphValidator(nodes, edges)
        return validator.get_execution_levels()
    
    @strawberry.field
    def topological_order(self, info) -> List[str]:
        """Get topological sort of nodes"""
        from graph_validator import GraphValidator
        
        nodes = [{'node_key': n.node_key} for n in self.nodes(info)]
        edges = [
            {
                'source_node_key': e.source_node(info).node_key,
                'target_node_key': e.target_node(info).node_key,
                'condition': e.condition.value
            }
            for e in self.edges(info)
        ]
        
        validator = GraphValidator(nodes, edges)
        return validator.topological_sort()
    
    @classmethod
    def from_orm(cls, graph_model) -> 'Graph':
        return cls(
            id=graph_model.id,
            name=graph_model.name,
            description=graph_model.description,
            created_at=graph_model.created_at,
            updated_at=graph_model.updated_at,
            is_active=graph_model.is_active
        )


@strawberry.type
class NodeExecution:
    id: int
    execution_id: int
    node_id: int
    status: ExecutionStatus
    input_data: JSON
    output_data: Optional[JSON]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    celery_task_id: Optional[str]
    
    @strawberry.field
    def node(self, info) -> Node:
        """Get the node that was executed"""
        from database import get_db_context
        from models import Node as NodeModel
        
        with get_db_context() as db:
            node = db.query(NodeModel).filter(NodeModel.id == self.node_id).first()
            return Node.from_orm(node)
    
    @strawberry.field
    def execution(self, info) -> 'Execution':
        """Get the parent execution"""
        from database import get_db_context
        from models import Execution as ExecutionModel
        
        with get_db_context() as db:
            execution = db.query(ExecutionModel).filter(
                ExecutionModel.id == self.execution_id
            ).first()
            return Execution.from_orm(execution)
    
    @strawberry.field
    def duration_seconds(self, info) -> Optional[float]:
        """Calculate execution duration in seconds"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None
    
    @classmethod
    def from_orm(cls, node_exec_model) -> 'NodeExecution':
        from models import ExecutionStatus as ExecutionStatusModel
        return cls(
            id=node_exec_model.id,
            execution_id=node_exec_model.execution_id,
            node_id=node_exec_model.node_id,
            status=ExecutionStatus[node_exec_model.status.name],
            input_data=node_exec_model.input_data,
            output_data=node_exec_model.output_data,
            error_message=node_exec_model.error_message,
            started_at=node_exec_model.started_at,
            completed_at=node_exec_model.completed_at,
            celery_task_id=node_exec_model.celery_task_id
        )


@strawberry.type
class Execution:
    id: int
    graph_id: int
    status: ExecutionStatus
    context: JSON
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    
    @strawberry.field
    def graph(self, info) -> Graph:
        """Get the graph that was executed"""
        from database import get_db_context
        from models import Graph as GraphModel
        
        with get_db_context() as db:
            graph = db.query(GraphModel).filter(GraphModel.id == self.graph_id).first()
            return Graph.from_orm(graph)
    
    @strawberry.field
    def node_executions(
        self,
        info,
        status: Optional[ExecutionStatus] = None
    ) -> List[NodeExecution]:
        """Get all node executions for this execution"""
        from database import get_db_context
        from models import NodeExecution as NodeExecutionModel, ExecutionStatus as ExecutionStatusModel
        
        with get_db_context() as db:
            query = db.query(NodeExecutionModel).filter(
                NodeExecutionModel.execution_id == self.id
            )
            
            if status:
                query = query.filter(
                    NodeExecutionModel.status == ExecutionStatusModel[status.name]
                )
            
            node_execs = query.all()
            return [NodeExecution.from_orm(ne) for ne in node_execs]
    
    @strawberry.field
    def duration_seconds(self, info) -> Optional[float]:
        """Calculate total execution duration in seconds"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None
    
    @strawberry.field
    def progress(self, info) -> float:
        """Calculate execution progress percentage (0-100)"""
        from database import get_db_context
        from models import NodeExecution as NodeExecutionModel
        
        with get_db_context() as db:
            total = db.query(NodeExecutionModel).filter(
                NodeExecutionModel.execution_id == self.id
            ).count()
            
            completed = db.query(NodeExecutionModel).filter(
                NodeExecutionModel.execution_id == self.id,
                NodeExecutionModel.completed_at.isnot(None)
            ).count()
            
            if total == 0:
                return 0.0
            return (completed / total) * 100.0
    
    @classmethod
    def from_orm(cls, execution_model) -> 'Execution':
        from models import ExecutionStatus as ExecutionStatusModel
        return cls(
            id=execution_model.id,
            graph_id=execution_model.graph_id,
            status=ExecutionStatus[execution_model.status.name],
            context=execution_model.context,
            started_at=execution_model.started_at,
            completed_at=execution_model.completed_at,
            error_message=execution_model.error_message
        )


# Statistics and aggregations
@strawberry.type
class GraphStatistics:
    graph_id: int
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration_seconds: Optional[float]
    last_execution: Optional[Execution]


@strawberry.type
class NodeStatistics:
    node_id: int
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration_seconds: Optional[float]
    success_rate: float
