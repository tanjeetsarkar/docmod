from celery import group, chord
from celery_app import celery_app
from database import get_db_context
from models import Execution, NodeExecution, Node, ExecutionStatus, EdgeCondition
from code_executor import CodeExecutor
from graph_validator import GraphValidator
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import redis

# Redis client for state management
REDIS_CLIENT = redis.from_url(celery_app.conf.broker_url, decode_responses=True)


@celery_app.task(bind=True, name="execute_graph")
def execute_graph(self, execution_id: int):
    """
    Main entry point for graph execution
    Orchestrates the entire DAG execution
    """
    with get_db_context() as db:
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        # Update execution status
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.utcnow()
        db.commit()
        
        # Get graph structure
        graph = execution.graph
        nodes = {n.node_key: n for n in graph.nodes}
        edges = [
            {
                'source_node_key': e.source_node.node_key,
                'target_node_key': e.target_node.node_key,
                'condition': e.condition
            }
            for e in graph.edges
        ]
        
        # Validate and get execution levels
        validator = GraphValidator(
            [{'node_key': k} for k in nodes.keys()],
            edges
        )
        
        try:
            levels = validator.get_execution_levels()
        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = f"Graph validation failed: {str(e)}"
            execution.completed_at = datetime.utcnow()
            db.commit()
            return
        
        # Initialize Redis state for tracking
        state_key = f"execution:{execution_id}:state"
        REDIS_CLIENT.hset(state_key, mapping={
            'status': ExecutionStatus.RUNNING.value,
            'completed_nodes': json.dumps([]),
            'failed_nodes': json.dumps([])
        })
        REDIS_CLIENT.expire(state_key, 86400)  # 24 hours
        
        # Create node executions
        node_executions = {}
        for node_key, node in nodes.items():
            node_exec = NodeExecution(
                execution_id=execution_id,
                node_id=node.id,
                status=ExecutionStatus.PENDING
            )
            db.add(node_exec)
            db.flush()
            node_executions[node_key] = node_exec.id
        db.commit()
    
    # Execute level 0 (nodes with no dependencies)
    if levels:
        execute_level.apply_async(
            args=[execution_id, 0, levels, node_executions],
            task_id=f"exec_{execution_id}_level_0"
        )


@celery_app.task(bind=True, name="execute_level")
def execute_level(self, execution_id: int, level_idx: int, levels: List[List[str]], node_exec_map: Dict[str, int]):
    """
    Execute all nodes at a specific level in parallel
    """
    if level_idx >= len(levels):
        # All levels completed, finalize execution
        finalize_execution.apply_async(args=[execution_id])
        return
    
    current_level_nodes = levels[level_idx]
    
    # Check if execution was cancelled
    state_key = f"execution:{execution_id}:state"
    status = REDIS_CLIENT.hget(state_key, 'status')
    if status == ExecutionStatus.CANCELLED.value:
        return
    
    # Create tasks for all nodes in this level
    tasks = []
    for node_key in current_level_nodes:
        node_exec_id = node_exec_map[node_key]
        task = execute_node.s(execution_id, node_exec_id, node_key, node_exec_map)
        tasks.append(task)
    
    # Execute nodes in parallel and wait for completion before next level
    if tasks:
        callback = execute_level.s(execution_id, level_idx + 1, levels, node_exec_map)
        chord(tasks)(callback)
    else:
        # No tasks at this level, move to next
        execute_level.apply_async(args=[execution_id, level_idx + 1, levels, node_exec_map])


@celery_app.task(bind=True, name="execute_node")
def execute_node(self, execution_id: int, node_execution_id: int, node_key: str, node_exec_map: Dict[str, int]):
    """
    Execute a single node
    """
    with get_db_context() as db:
        node_exec = db.query(NodeExecution).filter(NodeExecution.id == node_execution_id).first()
        if not node_exec:
            raise ValueError(f"NodeExecution {node_execution_id} not found")
        
        node = node_exec.node
        execution = node_exec.execution
        
        # Check if we should execute based on predecessor results
        graph = node.graph
        validator = GraphValidator(
            [{'node_key': n.node_key} for n in graph.nodes],
            [
                {
                    'source_node_key': e.source_node.node_key,
                    'target_node_key': e.target_node.node_key,
                    'condition': e.condition
                }
                for e in graph.edges
            ]
        )
        
        dependencies = validator.get_dependencies(node_key)
        
        # Check if dependencies allow execution
        should_execute, inputs = check_dependencies(
            db, execution_id, node_key, dependencies, graph.edges, node_exec_map
        )
        
        if not should_execute:
            node_exec.status = ExecutionStatus.CANCELLED
            node_exec.completed_at = datetime.utcnow()
            db.commit()
            return {'status': 'skipped', 'node_key': node_key}
        
        # Update status
        node_exec.status = ExecutionStatus.RUNNING
        node_exec.started_at = datetime.utcnow()
        node_exec.celery_task_id = self.request.id
        node_exec.input_data = inputs
        db.commit()
        
        # Execute code
        success, output, error = CodeExecutor.execute(
            code=node.code,
            constants=node.constants,
            inputs=inputs,
            context=execution.context,
            timeout_seconds=node.timeout_seconds
        )
        
        # Update result
        node_exec.status = ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED
        node_exec.output_data = {'result': output} if success else None
        node_exec.error_message = error if not success else None
        node_exec.completed_at = datetime.utcnow()
        db.commit()
        
        # Update Redis state
        state_key = f"execution:{execution_id}:state"
        if success:
            completed = json.loads(REDIS_CLIENT.hget(state_key, 'completed_nodes') or '[]')
            completed.append(node_key)
            REDIS_CLIENT.hset(state_key, 'completed_nodes', json.dumps(completed))
        else:
            failed = json.loads(REDIS_CLIENT.hget(state_key, 'failed_nodes') or '[]')
            failed.append(node_key)
            REDIS_CLIENT.hset(state_key, 'failed_nodes', json.dumps(failed))
        
        return {
            'status': 'success' if success else 'failed',
            'node_key': node_key,
            'output': output
        }


def check_dependencies(
    db,
    execution_id: int,
    node_key: str,
    dependencies: List[str],
    edges,
    node_exec_map: Dict[str, int]
) -> tuple[bool, Dict[str, Any]]:
    """
    Check if all dependencies are satisfied for node execution
    Returns: (should_execute, inputs_from_predecessors)
    """
    if not dependencies:
        return True, {}
    
    inputs = {}
    
    for dep_key in dependencies:
        # Find the edge condition
        edge_condition = None
        for edge in edges:
            if edge.source_node.node_key == dep_key and edge.target_node.node_key == node_key:
                edge_condition = edge.condition
                break
        
        # Get dependency execution result
        dep_exec_id = node_exec_map[dep_key]
        dep_exec = db.query(NodeExecution).filter(NodeExecution.id == dep_exec_id).first()
        
        if not dep_exec or dep_exec.status not in [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED]:
            # Dependency not completed yet
            return False, {}
        
        # Check edge condition
        if edge_condition == EdgeCondition.ON_SUCCESS and dep_exec.status != ExecutionStatus.SUCCESS:
            return False, {}
        elif edge_condition == EdgeCondition.ON_FAILURE and dep_exec.status != ExecutionStatus.FAILED:
            return False, {}
        # ALWAYS condition passes regardless of status
        
        # Collect output
        if dep_exec.status == ExecutionStatus.SUCCESS and dep_exec.output_data:
            inputs[dep_key] = dep_exec.output_data.get('result')
    
    return True, inputs


@celery_app.task(name="finalize_execution")
def finalize_execution(execution_id: int):
    """
    Finalize execution after all nodes complete
    """
    with get_db_context() as db:
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            return
        
        # Check overall status
        node_statuses = [ne.status for ne in execution.node_executions]
        
        if all(s == ExecutionStatus.SUCCESS for s in node_statuses):
            execution.status = ExecutionStatus.SUCCESS
        elif any(s == ExecutionStatus.FAILED for s in node_statuses):
            execution.status = ExecutionStatus.FAILED
            failed_nodes = [
                ne.node.name for ne in execution.node_executions
                if ne.status == ExecutionStatus.FAILED
            ]
            execution.error_message = f"Failed nodes: {', '.join(failed_nodes)}"
        else:
            execution.status = ExecutionStatus.CANCELLED
        
        execution.completed_at = datetime.utcnow()
        db.commit()
        
        # Cleanup Redis state
        state_key = f"execution:{execution_id}:state"
        REDIS_CLIENT.delete(state_key)


@celery_app.task(name="cancel_execution")
def cancel_execution(execution_id: int):
    """
    Cancel an ongoing execution
    """
    # Update Redis state
    state_key = f"execution:{execution_id}:state"
    REDIS_CLIENT.hset(state_key, 'status', ExecutionStatus.CANCELLED.value)
    
    with get_db_context() as db:
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if execution:
            execution.status = ExecutionStatus.CANCELLED
            execution.completed_at = datetime.utcnow()
            
            # Cancel pending nodes
            for node_exec in execution.node_executions:
                if node_exec.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
                    node_exec.status = ExecutionStatus.CANCELLED
                    node_exec.completed_at = datetime.utcnow()
            
            db.commit()
