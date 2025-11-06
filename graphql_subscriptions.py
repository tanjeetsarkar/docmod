import strawberry
import asyncio
from typing import AsyncGenerator
from datetime import datetime

from graphql_types import Execution, NodeExecution, ExecutionStatus
from database import get_db_context
from models import (
    Execution as ExecutionModel,
    NodeExecution as NodeExecutionModel,
    ExecutionStatus as ExecutionStatusModel
)


@strawberry.type
class Subscription:
    
    @strawberry.subscription(description="Subscribe to execution status updates")
    async def execution_updates(
        self,
        execution_id: int,
        interval: float = 1.0
    ) -> AsyncGenerator[Execution, None]:
        """
        Stream execution status updates
        Polls database every `interval` seconds for changes
        Completes when execution reaches terminal state
        """
        terminal_states = {
            ExecutionStatusModel.SUCCESS,
            ExecutionStatusModel.FAILED,
            ExecutionStatusModel.CANCELLED,
            ExecutionStatusModel.TIMEOUT
        }
        
        last_status = None
        
        while True:
            with get_db_context() as db:
                execution = db.query(ExecutionModel).filter(
                    ExecutionModel.id == execution_id
                ).first()
                
                if not execution:
                    break
                
                # Only yield if status changed
                if execution.status != last_status:
                    last_status = execution.status
                    yield Execution.from_orm(execution)
                
                # Stop if terminal state reached
                if execution.status in terminal_states:
                    break
            
            await asyncio.sleep(interval)
    
    @strawberry.subscription(description="Subscribe to node execution updates")
    async def node_execution_updates(
        self,
        execution_id: int,
        interval: float = 1.0
    ) -> AsyncGenerator[list[NodeExecution], None]:
        """
        Stream all node execution updates for an execution
        Yields the complete list of node executions on each update
        """
        terminal_states = {
            ExecutionStatusModel.SUCCESS,
            ExecutionStatusModel.FAILED,
            ExecutionStatusModel.CANCELLED,
            ExecutionStatusModel.TIMEOUT
        }
        
        last_update = None
        
        while True:
            with get_db_context() as db:
                # Get execution status
                execution = db.query(ExecutionModel).filter(
                    ExecutionModel.id == execution_id
                ).first()
                
                if not execution:
                    break
                
                # Get all node executions
                node_execs = db.query(NodeExecutionModel).filter(
                    NodeExecutionModel.execution_id == execution_id
                ).all()
                
                # Create snapshot of current state
                current_update = {
                    ne.id: (ne.status, ne.completed_at)
                    for ne in node_execs
                }
                
                # Only yield if something changed
                if current_update != last_update:
                    last_update = current_update
                    yield [NodeExecution.from_orm(ne) for ne in node_execs]
                
                # Stop if execution complete
                if execution.status in terminal_states:
                    break
            
            await asyncio.sleep(interval)
    
    @strawberry.subscription(description="Subscribe to execution progress")
    async def execution_progress(
        self,
        execution_id: int,
        interval: float = 2.0
    ) -> AsyncGenerator[float, None]:
        """
        Stream execution progress percentage (0-100)
        Updates every `interval` seconds
        """
        terminal_states = {
            ExecutionStatusModel.SUCCESS,
            ExecutionStatusModel.FAILED,
            ExecutionStatusModel.CANCELLED,
            ExecutionStatusModel.TIMEOUT
        }
        
        while True:
            with get_db_context() as db:
                execution = db.query(ExecutionModel).filter(
                    ExecutionModel.id == execution_id
                ).first()
                
                if not execution:
                    break
                
                # Calculate progress
                total = db.query(NodeExecutionModel).filter(
                    NodeExecutionModel.execution_id == execution_id
                ).count()
                
                completed = db.query(NodeExecutionModel).filter(
                    NodeExecutionModel.execution_id == execution_id,
                    NodeExecutionModel.completed_at.isnot(None)
                ).count()
                
                progress = (completed / total * 100.0) if total > 0 else 0.0
                yield progress
                
                # Stop if execution complete
                if execution.status in terminal_states:
                    break
            
            await asyncio.sleep(interval)
    
    @strawberry.subscription(description="Subscribe to all running executions")
    async def running_executions(
        self,
        interval: float = 5.0
    ) -> AsyncGenerator[list[Execution], None]:
        """
        Stream all currently running executions
        Updates every `interval` seconds
        """
        while True:
            with get_db_context() as db:
                executions = db.query(ExecutionModel).filter(
                    ExecutionModel.status == ExecutionStatusModel.RUNNING
                ).order_by(ExecutionModel.started_at.desc()).all()
                
                yield [Execution.from_orm(e) for e in executions]
            
            await asyncio.sleep(interval)
    
    @strawberry.subscription(description="Subscribe to new executions")
    async def new_executions(
        self,
        graph_id: int = None,
        interval: float = 2.0
    ) -> AsyncGenerator[Execution, None]:
        """
        Stream newly created executions
        Optionally filter by graph_id
        """
        last_check = datetime.utcnow()
        
        while True:
            await asyncio.sleep(interval)
            
            with get_db_context() as db:
                query = db.query(ExecutionModel).filter(
                    ExecutionModel.started_at > last_check
                )
                
                if graph_id:
                    query = query.filter(ExecutionModel.graph_id == graph_id)
                
                new_executions = query.order_by(
                    ExecutionModel.started_at.asc()
                ).all()
                
                for execution in new_executions:
                    yield Execution.from_orm(execution)
                
                last_check = datetime.utcnow()
