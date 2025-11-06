import strawberry
from typing import Optional
from datetime import datetime

from graphql_types import Graph, Execution, ExecutionStatus
from graphql_inputs import GraphInput, GraphUpdateInput, ExecutionInput
from database import get_db_context
from models import (
    Graph as GraphModel,
    Node as NodeModel,
    Edge as EdgeModel,
    Execution as ExecutionModel,
    NodeExecution as NodeExecutionModel,
    ExecutionStatus as ExecutionStatusModel,
    EdgeCondition as EdgeConditionModel
)
from graph_validator import GraphValidator
from celery_tasks import execute_graph as execute_graph_task, cancel_execution as cancel_execution_task


@strawberry.type
class CreateGraphPayload:
    """Response payload for graph creation"""
    graph: Optional[Graph]
    errors: Optional[list[str]]
    success: bool


@strawberry.type
class UpdateGraphPayload:
    """Response payload for graph update"""
    graph: Optional[Graph]
    errors: Optional[list[str]]
    success: bool


@strawberry.type
class DeleteGraphPayload:
    """Response payload for graph deletion"""
    success: bool
    message: str


@strawberry.type
class ExecuteGraphPayload:
    """Response payload for graph execution"""
    execution: Optional[Execution]
    errors: Optional[list[str]]
    success: bool


@strawberry.type
class CancelExecutionPayload:
    """Response payload for execution cancellation"""
    execution: Optional[Execution]
    success: bool
    message: str


@strawberry.type
class Mutation:
    
    @strawberry.mutation(description="Create a new graph with nodes and edges")
    def create_graph(self, input: GraphInput) -> CreateGraphPayload:
        errors = []
        
        # Validate graph structure
        validator = GraphValidator(
            [{'node_key': n.node_key} for n in input.nodes],
            [
                {
                    'source_node_key': e.source_node_key,
                    'target_node_key': e.target_node_key,
                    'condition': e.condition.value
                }
                for e in input.edges
            ]
        )
        
        is_valid, error_msg = validator.validate()
        if not is_valid:
            return CreateGraphPayload(
                graph=None,
                errors=[error_msg],
                success=False
            )
        
        # Validate node keys are unique
        node_keys = [n.node_key for n in input.nodes]
        if len(node_keys) != len(set(node_keys)):
            return CreateGraphPayload(
                graph=None,
                errors=["Duplicate node_key found in nodes"],
                success=False
            )
        
        try:
            with get_db_context() as db:
                # Create graph
                graph = GraphModel(
                    name=input.name,
                    description=input.description
                )
                db.add(graph)
                db.flush()
                
                # Create nodes
                node_map = {}  # node_key -> Node object
                for node_data in input.nodes:
                    node = NodeModel(
                        graph_id=graph.id,
                        node_key=node_data.node_key,
                        name=node_data.name,
                        code=node_data.code,
                        constants=node_data.constants,
                        timeout_seconds=node_data.timeout_seconds
                    )
                    db.add(node)
                    db.flush()
                    node_map[node_data.node_key] = node
                
                # Create edges
                for edge_data in input.edges:
                    edge = EdgeModel(
                        graph_id=graph.id,
                        source_node_id=node_map[edge_data.source_node_key].id,
                        target_node_id=node_map[edge_data.target_node_key].id,
                        condition=EdgeConditionModel[edge_data.condition.name]
                    )
                    db.add(edge)
                
                db.commit()
                db.refresh(graph)
                
                return CreateGraphPayload(
                    graph=Graph.from_orm(graph),
                    errors=None,
                    success=True
                )
                
        except Exception as e:
            return CreateGraphPayload(
                graph=None,
                errors=[f"Failed to create graph: {str(e)}"],
                success=False
            )
    
    @strawberry.mutation(description="Update an existing graph")
    def update_graph(
        self,
        id: int,
        input: GraphUpdateInput
    ) -> UpdateGraphPayload:
        try:
            with get_db_context() as db:
                graph = db.query(GraphModel).filter(GraphModel.id == id).first()
                
                if not graph:
                    return UpdateGraphPayload(
                        graph=None,
                        errors=[f"Graph with id {id} not found"],
                        success=False
                    )
                
                # Update fields
                if input.name is not None:
                    graph.name = input.name
                if input.description is not None:
                    graph.description = input.description
                
                graph.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(graph)
                
                return UpdateGraphPayload(
                    graph=Graph.from_orm(graph),
                    errors=None,
                    success=True
                )
                
        except Exception as e:
            return UpdateGraphPayload(
                graph=None,
                errors=[f"Failed to update graph: {str(e)}"],
                success=False
            )
    
    @strawberry.mutation(description="Delete a graph (soft delete)")
    def delete_graph(self, id: int) -> DeleteGraphPayload:
        try:
            with get_db_context() as db:
                graph = db.query(GraphModel).filter(GraphModel.id == id).first()
                
                if not graph:
                    return DeleteGraphPayload(
                        success=False,
                        message=f"Graph with id {id} not found"
                    )
                
                # Soft delete
                graph.is_active = False
                db.commit()
                
                return DeleteGraphPayload(
                    success=True,
                    message=f"Graph {id} successfully deleted"
                )
                
        except Exception as e:
            return DeleteGraphPayload(
                success=False,
                message=f"Failed to delete graph: {str(e)}"
            )
    
    @strawberry.mutation(description="Execute a graph")
    def execute_graph(
        self,
        graph_id: int,
        input: Optional[ExecutionInput] = None
    ) -> ExecuteGraphPayload:
        try:
            with get_db_context() as db:
                # Check if graph exists
                graph = db.query(GraphModel).filter(
                    GraphModel.id == graph_id,
                    GraphModel.is_active == True
                ).first()
                
                if not graph:
                    return ExecuteGraphPayload(
                        execution=None,
                        errors=[f"Graph with id {graph_id} not found or inactive"],
                        success=False
                    )
                
                # Create execution record
                execution = ExecutionModel(
                    graph_id=graph_id,
                    status=ExecutionStatusModel.PENDING,
                    context=input.context if input else {}
                )
                db.add(execution)
                db.commit()
                db.refresh(execution)
                
                # Trigger Celery task
                execute_graph_task.apply_async(
                    args=[execution.id],
                    task_id=f"graph_exec_{execution.id}"
                )
                
                return ExecuteGraphPayload(
                    execution=Execution.from_orm(execution),
                    errors=None,
                    success=True
                )
                
        except Exception as e:
            return ExecuteGraphPayload(
                execution=None,
                errors=[f"Failed to execute graph: {str(e)}"],
                success=False
            )
    
    @strawberry.mutation(description="Cancel a running execution")
    def cancel_execution(self, execution_id: int) -> CancelExecutionPayload:
        try:
            with get_db_context() as db:
                execution = db.query(ExecutionModel).filter(
                    ExecutionModel.id == execution_id
                ).first()
                
                if not execution:
                    return CancelExecutionPayload(
                        execution=None,
                        success=False,
                        message=f"Execution with id {execution_id} not found"
                    )
                
                if execution.status not in [
                    ExecutionStatusModel.PENDING,
                    ExecutionStatusModel.RUNNING
                ]:
                    return CancelExecutionPayload(
                        execution=Execution.from_orm(execution),
                        success=False,
                        message=f"Cannot cancel execution with status {execution.status.value}"
                    )
                
                # Trigger cancellation
                cancel_execution_task.apply_async(args=[execution_id])
                
                return CancelExecutionPayload(
                    execution=Execution.from_orm(execution),
                    success=True,
                    message="Cancellation requested"
                )
                
        except Exception as e:
            return CancelExecutionPayload(
                execution=None,
                success=False,
                message=f"Failed to cancel execution: {str(e)}"
            )
    
    @strawberry.mutation(description="Retry a failed execution")
    def retry_execution(self, execution_id: int) -> ExecuteGraphPayload:
        try:
            with get_db_context() as db:
                old_execution = db.query(ExecutionModel).filter(
                    ExecutionModel.id == execution_id
                ).first()
                
                if not old_execution:
                    return ExecuteGraphPayload(
                        execution=None,
                        errors=[f"Execution with id {execution_id} not found"],
                        success=False
                    )
                
                # Create new execution with same context
                new_execution = ExecutionModel(
                    graph_id=old_execution.graph_id,
                    status=ExecutionStatusModel.PENDING,
                    context=old_execution.context
                )
                db.add(new_execution)
                db.commit()
                db.refresh(new_execution)
                
                # Trigger Celery task
                execute_graph_task.apply_async(
                    args=[new_execution.id],
                    task_id=f"graph_exec_{new_execution.id}"
                )
                
                return ExecuteGraphPayload(
                    execution=Execution.from_orm(new_execution),
                    errors=None,
                    success=True
                )
                
        except Exception as e:
            return ExecuteGraphPayload(
                execution=None,
                errors=[f"Failed to retry execution: {str(e)}"],
                success=False
            )
