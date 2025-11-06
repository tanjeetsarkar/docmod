import strawberry
from typing import List, Optional
from datetime import datetime
from sqlalchemy import func

from graphql_types import (
    Graph, Node, Edge, Execution, NodeExecution,
    GraphStatistics, NodeStatistics, ExecutionStatus
)
from graphql_inputs import GraphFilterInput, ExecutionFilterInput
from database import get_db_context
from models import (
    Graph as GraphModel,
    Node as NodeModel,
    Edge as EdgeModel,
    Execution as ExecutionModel,
    NodeExecution as NodeExecutionModel,
    ExecutionStatus as ExecutionStatusModel
)


@strawberry.type
class Query:
    
    @strawberry.field(description="Get a graph by ID")
    def graph(self, id: int) -> Optional[Graph]:
        with get_db_context() as db:
            graph = db.query(GraphModel).filter(GraphModel.id == id).first()
            if graph:
                return Graph.from_orm(graph)
            return None
    
    @strawberry.field(description="List all graphs with optional filtering")
    def graphs(
        self,
        filter: Optional[GraphFilterInput] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Graph]:
        with get_db_context() as db:
            query = db.query(GraphModel)
            
            if filter:
                if filter.name_contains:
                    query = query.filter(
                        GraphModel.name.ilike(f"%{filter.name_contains}%")
                    )
                if filter.is_active is not None:
                    query = query.filter(GraphModel.is_active == filter.is_active)
            
            graphs = query.order_by(GraphModel.created_at.desc()).offset(offset).limit(limit).all()
            return [Graph.from_orm(g) for g in graphs]
    
    @strawberry.field(description="Get a node by ID")
    def node(self, id: int) -> Optional[Node]:
        with get_db_context() as db:
            node = db.query(NodeModel).filter(NodeModel.id == id).first()
            if node:
                return Node.from_orm(node)
            return None
    
    @strawberry.field(description="Get nodes by graph ID")
    def nodes_by_graph(self, graph_id: int) -> List[Node]:
        with get_db_context() as db:
            nodes = db.query(NodeModel).filter(NodeModel.graph_id == graph_id).all()
            return [Node.from_orm(n) for n in nodes]
    
    @strawberry.field(description="Get an edge by ID")
    def edge(self, id: int) -> Optional[Edge]:
        with get_db_context() as db:
            edge = db.query(EdgeModel).filter(EdgeModel.id == id).first()
            if edge:
                return Edge.from_orm(edge)
            return None
    
    @strawberry.field(description="Get edges by graph ID")
    def edges_by_graph(self, graph_id: int) -> List[Edge]:
        with get_db_context() as db:
            edges = db.query(EdgeModel).filter(EdgeModel.graph_id == graph_id).all()
            return [Edge.from_orm(e) for e in edges]
    
    @strawberry.field(description="Get an execution by ID")
    def execution(self, id: int) -> Optional[Execution]:
        with get_db_context() as db:
            execution = db.query(ExecutionModel).filter(ExecutionModel.id == id).first()
            if execution:
                return Execution.from_orm(execution)
            return None
    
    @strawberry.field(description="List executions with optional filtering")
    def executions(
        self,
        filter: Optional[ExecutionFilterInput] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Execution]:
        with get_db_context() as db:
            query = db.query(ExecutionModel)
            
            if filter:
                if filter.graph_id:
                    query = query.filter(ExecutionModel.graph_id == filter.graph_id)
                if filter.status:
                    try:
                        status_enum = ExecutionStatusModel[filter.status.upper()]
                        query = query.filter(ExecutionModel.status == status_enum)
                    except KeyError:
                        pass  # Invalid status, ignore filter
            
            executions = query.order_by(
                ExecutionModel.started_at.desc()
            ).offset(offset).limit(limit).all()
            
            return [Execution.from_orm(e) for e in executions]
    
    @strawberry.field(description="Get a node execution by ID")
    def node_execution(self, id: int) -> Optional[NodeExecution]:
        with get_db_context() as db:
            node_exec = db.query(NodeExecutionModel).filter(
                NodeExecutionModel.id == id
            ).first()
            if node_exec:
                return NodeExecution.from_orm(node_exec)
            return None
    
    @strawberry.field(description="Get all node executions for a specific execution")
    def node_executions_by_execution(
        self,
        execution_id: int,
        status: Optional[ExecutionStatus] = None
    ) -> List[NodeExecution]:
        with get_db_context() as db:
            query = db.query(NodeExecutionModel).filter(
                NodeExecutionModel.execution_id == execution_id
            )
            
            if status:
                query = query.filter(
                    NodeExecutionModel.status == ExecutionStatusModel[status.name]
                )
            
            node_execs = query.all()
            return [NodeExecution.from_orm(ne) for ne in node_execs]
    
    @strawberry.field(description="Get statistics for a graph")
    def graph_statistics(self, graph_id: int) -> Optional[GraphStatistics]:
        with get_db_context() as db:
            # Check if graph exists
            graph = db.query(GraphModel).filter(GraphModel.id == graph_id).first()
            if not graph:
                return None
            
            # Get execution statistics
            total_executions = db.query(ExecutionModel).filter(
                ExecutionModel.graph_id == graph_id
            ).count()
            
            successful = db.query(ExecutionModel).filter(
                ExecutionModel.graph_id == graph_id,
                ExecutionModel.status == ExecutionStatusModel.SUCCESS
            ).count()
            
            failed = db.query(ExecutionModel).filter(
                ExecutionModel.graph_id == graph_id,
                ExecutionModel.status == ExecutionStatusModel.FAILED
            ).count()
            
            # Calculate average duration
            avg_duration = db.query(
                func.avg(
                    func.extract('epoch', ExecutionModel.completed_at - ExecutionModel.started_at)
                )
            ).filter(
                ExecutionModel.graph_id == graph_id,
                ExecutionModel.started_at.isnot(None),
                ExecutionModel.completed_at.isnot(None)
            ).scalar()
            
            # Get last execution
            last_exec = db.query(ExecutionModel).filter(
                ExecutionModel.graph_id == graph_id
            ).order_by(ExecutionModel.started_at.desc()).first()
            
            return GraphStatistics(
                graph_id=graph_id,
                total_executions=total_executions,
                successful_executions=successful,
                failed_executions=failed,
                average_duration_seconds=float(avg_duration) if avg_duration else None,
                last_execution=Execution.from_orm(last_exec) if last_exec else None
            )
    
    @strawberry.field(description="Get statistics for a node")
    def node_statistics(self, node_id: int) -> Optional[NodeStatistics]:
        with get_db_context() as db:
            # Check if node exists
            node = db.query(NodeModel).filter(NodeModel.id == node_id).first()
            if not node:
                return None
            
            # Get node execution statistics
            total_execs = db.query(NodeExecutionModel).filter(
                NodeExecutionModel.node_id == node_id
            ).count()
            
            successful = db.query(NodeExecutionModel).filter(
                NodeExecutionModel.node_id == node_id,
                NodeExecutionModel.status == ExecutionStatusModel.SUCCESS
            ).count()
            
            failed = db.query(NodeExecutionModel).filter(
                NodeExecutionModel.node_id == node_id,
                NodeExecutionModel.status == ExecutionStatusModel.FAILED
            ).count()
            
            # Calculate average duration
            avg_duration = db.query(
                func.avg(
                    func.extract('epoch', NodeExecutionModel.completed_at - NodeExecutionModel.started_at)
                )
            ).filter(
                NodeExecutionModel.node_id == node_id,
                NodeExecutionModel.started_at.isnot(None),
                NodeExecutionModel.completed_at.isnot(None)
            ).scalar()
            
            # Calculate success rate
            success_rate = (successful / total_execs * 100.0) if total_execs > 0 else 0.0
            
            return NodeStatistics(
                node_id=node_id,
                total_executions=total_execs,
                successful_executions=successful,
                failed_executions=failed,
                average_duration_seconds=float(avg_duration) if avg_duration else None,
                success_rate=success_rate
            )
    
    @strawberry.field(description="Search graphs by name")
    def search_graphs(self, query: str, limit: int = 10) -> List[Graph]:
        with get_db_context() as db:
            graphs = db.query(GraphModel).filter(
                GraphModel.name.ilike(f"%{query}%"),
                GraphModel.is_active == True
            ).limit(limit).all()
            return [Graph.from_orm(g) for g in graphs]
    
    @strawberry.field(description="Get currently running executions")
    def running_executions(self, limit: int = 50) -> List[Execution]:
        with get_db_context() as db:
            executions = db.query(ExecutionModel).filter(
                ExecutionModel.status == ExecutionStatusModel.RUNNING
            ).order_by(ExecutionModel.started_at.desc()).limit(limit).all()
            return [Execution.from_orm(e) for e in executions]
    
    @strawberry.field(description="Get recent executions")
    def recent_executions(
        self,
        limit: int = 50,
        hours: int = 24
    ) -> List[Execution]:
        with get_db_context() as db:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            executions = db.query(ExecutionModel).filter(
                ExecutionModel.started_at >= cutoff
            ).order_by(ExecutionModel.started_at.desc()).limit(limit).all()
            return [Execution.from_orm(e) for e in executions]


from datetime import timedelta  # Import for recent_executions
