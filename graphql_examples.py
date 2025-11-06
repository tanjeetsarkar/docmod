"""
Example script demonstrating GraphQL API usage
"""
import requests
import time
import json

GRAPHQL_URL = "http://localhost:8000/graphql"


def execute_graphql(query: str, variables: dict = None):
    """Execute a GraphQL query"""
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables or {}}
    )
    response.raise_for_status()
    data = response.json()
    
    if "errors" in data:
        print("GraphQL Errors:", json.dumps(data["errors"], indent=2))
        return None
    
    return data.get("data")


def create_example_graph():
    """Create a graph using GraphQL mutation"""
    
    mutation = """
    mutation CreateGraph($input: GraphInput!) {
        createGraph(input: $input) {
            success
            errors
            graph {
                id
                name
                nodes {
                    id
                    nodeKey
                    name
                }
                edges {
                    id
                    sourceNode {
                        nodeKey
                    }
                    targetNode {
                        nodeKey
                    }
                    condition
                }
                executionLevels
                topologicalOrder
            }
        }
    }
    """
    
    variables = {
        "input": {
            "name": "GraphQL Example DAG",
            "description": "A sample DAG created via GraphQL",
            "nodes": [
                {
                    "nodeKey": "node_1",
                    "name": "Initialize",
                    "code": "output = {'count': 10, 'message': 'Started'}",
                    "constants": {"initial_value": 100},
                    "timeoutSeconds": 60
                },
                {
                    "nodeKey": "node_2",
                    "name": "Process A",
                    "code": "input_data = inputs.get('node_1', {})\ncount = input_data.get('count', 0)\noutput = {'result': count * 2}",
                    "constants": {},
                    "timeoutSeconds": 60
                },
                {
                    "nodeKey": "node_3",
                    "name": "Process B",
                    "code": "input_data = inputs.get('node_1', {})\ncount = input_data.get('count', 0)\noutput = {'result': count + 5}",
                    "constants": {},
                    "timeoutSeconds": 60
                },
                {
                    "nodeKey": "node_4",
                    "name": "Transform A",
                    "code": "input_data = inputs.get('node_2', {})\nresult = input_data.get('result', 0)\noutput = {'final': result ** 2}",
                    "constants": {},
                    "timeoutSeconds": 60
                },
                {
                    "nodeKey": "node_5",
                    "name": "Transform B",
                    "code": "input_data = inputs.get('node_2', {})\nresult = input_data.get('result', 0)\noutput = {'final': result + 100}",
                    "constants": {},
                    "timeoutSeconds": 60
                },
                {
                    "nodeKey": "node_6",
                    "name": "Merge",
                    "code": "input_2 = inputs.get('node_2', {})\ninput_3 = inputs.get('node_3', {})\noutput = {'merged': input_2.get('result', 0) + input_3.get('result', 0)}",
                    "constants": {},
                    "timeoutSeconds": 60
                },
                {
                    "nodeKey": "node_7",
                    "name": "Alternative",
                    "code": "input_data = inputs.get('node_3', {})\noutput = {'alternative': input_data.get('result', 0) * 10}",
                    "constants": {},
                    "timeoutSeconds": 60
                },
                {
                    "nodeKey": "node_8",
                    "name": "Final",
                    "code": "input_data = inputs.get('node_6', {})\noutput = {'final_result': input_data.get('merged', 0), 'status': 'completed'}",
                    "constants": {},
                    "timeoutSeconds": 60
                }
            ],
            "edges": [
                {"sourceNodeKey": "node_1", "targetNodeKey": "node_2", "condition": "ON_SUCCESS"},
                {"sourceNodeKey": "node_1", "targetNodeKey": "node_3", "condition": "ON_SUCCESS"},
                {"sourceNodeKey": "node_2", "targetNodeKey": "node_4", "condition": "ON_SUCCESS"},
                {"sourceNodeKey": "node_2", "targetNodeKey": "node_5", "condition": "ON_SUCCESS"},
                {"sourceNodeKey": "node_2", "targetNodeKey": "node_6", "condition": "ON_SUCCESS"},
                {"sourceNodeKey": "node_3", "targetNodeKey": "node_6", "condition": "ON_SUCCESS"},
                {"sourceNodeKey": "node_3", "targetNodeKey": "node_7", "condition": "ON_SUCCESS"},
                {"sourceNodeKey": "node_6", "targetNodeKey": "node_8", "condition": "ON_SUCCESS"}
            ]
        }
    }
    
    data = execute_graphql(mutation, variables)
    return data["createGraph"] if data else None


def execute_graph(graph_id: int, context: dict = None):
    """Execute a graph using GraphQL mutation"""
    
    mutation = """
    mutation ExecuteGraph($graphId: Int!, $input: ExecutionInput) {
        executeGraph(graphId: $graphId, input: $input) {
            success
            errors
            execution {
                id
                status
                context
                startedAt
                graph {
                    name
                }
            }
        }
    }
    """
    
    variables = {
        "graphId": graph_id,
        "input": {
            "context": context or {"environment": "test", "user": "graphql_user"}
        }
    }
    
    data = execute_graphql(mutation, variables)
    return data["executeGraph"] if data else None


def get_execution_status(execution_id: int):
    """Get execution status with detailed information"""
    
    query = """
    query GetExecution($id: Int!) {
        execution(id: $id) {
            id
            status
            startedAt
            completedAt
            durationSeconds
            progress
            errorMessage
            graph {
                name
            }
            nodeExecutions {
                id
                status
                durationSeconds
                node {
                    nodeKey
                    name
                }
                inputData
                outputData
                errorMessage
            }
        }
    }
    """
    
    variables = {"id": execution_id}
    data = execute_graphql(query, variables)
    return data["execution"] if data else None


def get_graph_statistics(graph_id: int):
    """Get statistics for a graph"""
    
    query = """
    query GetGraphStats($graphId: Int!) {
        graphStatistics(graphId: $graphId) {
            graphId
            totalExecutions
            successfulExecutions
            failedExecutions
            averageDurationSeconds
            lastExecution {
                id
                status
                startedAt
            }
        }
    }
    """
    
    variables = {"graphId": graph_id}
    data = execute_graphql(query, variables)
    return data["graphStatistics"] if data else None


def search_graphs(query: str):
    """Search graphs by name"""
    
    graphql_query = """
    query SearchGraphs($query: String!) {
        searchGraphs(query: $query) {
            id
            name
            description
            createdAt
        }
    }
    """
    
    variables = {"query": query}
    data = execute_graphql(graphql_query, variables)
    return data["searchGraphs"] if data else None


def list_running_executions():
    """Get all currently running executions"""
    
    query = """
    query RunningExecutions {
        runningExecutions {
            id
            status
            startedAt
            progress
            graph {
                id
                name
            }
        }
    }
    """
    
    data = execute_graphql(query)
    return data["runningExecutions"] if data else None


def cancel_execution(execution_id: int):
    """Cancel an execution"""
    
    mutation = """
    mutation CancelExecution($executionId: Int!) {
        cancelExecution(executionId: $executionId) {
            success
            message
            execution {
                id
                status
            }
        }
    }
    """
    
    variables = {"executionId": execution_id}
    data = execute_graphql(mutation, variables)
    return data["cancelExecution"] if data else None


def wait_for_completion(execution_id: int, timeout: int = 300):
    """Wait for execution to complete"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status_data = get_execution_status(execution_id)
        if not status_data:
            print("Failed to get execution status")
            return None
        
        status = status_data['status']
        progress = status_data.get('progress', 0)
        
        print(f"Status: {status} | Progress: {progress:.1f}%")
        
        if status in ['SUCCESS', 'FAILED', 'CANCELLED']:
            return status_data
        
        time.sleep(2)
    
    raise TimeoutError(f"Execution did not complete within {timeout} seconds")


def main():
    print("=" * 70)
    print("DAG Executor GraphQL API - Example Usage")
    print("=" * 70)
    
    # Step 1: Create graph
    print("\n1. Creating graph via GraphQL mutation...")
    result = create_example_graph()
    
    if not result or not result['success']:
        print(f"   ❌ Failed to create graph: {result.get('errors') if result else 'Unknown error'}")
        return
    
    graph = result['graph']
    graph_id = graph['id']
    print(f"   ✓ Graph created successfully")
    print(f"   ID: {graph_id}")
    print(f"   Name: {graph['name']}")
    print(f"   Nodes: {len(graph['nodes'])}")
    print(f"   Edges: {len(graph['edges'])}")
    print(f"   Execution Levels: {graph['executionLevels']}")
    print(f"   Topological Order: {graph['topologicalOrder']}")
    
    # Step 2: Execute graph
    print("\n2. Starting graph execution...")
    exec_result = execute_graph(graph_id, {
        "environment": "production",
        "user": "graphql_demo",
        "run_type": "test"
    })
    
    if not exec_result or not exec_result['success']:
        print(f"   ❌ Failed to execute: {exec_result.get('errors') if exec_result else 'Unknown error'}")
        return
    
    execution = exec_result['execution']
    execution_id = execution['id']
    print(f"   ✓ Execution started")
    print(f"   Execution ID: {execution_id}")
    print(f"   Status: {execution['status']}")
    
    # Step 3: Wait for completion
    print("\n3. Monitoring execution progress...")
    final_status = wait_for_completion(execution_id)
    
    if not final_status:
        print("   ❌ Failed to monitor execution")
        return
    
    print(f"\n   ✓ Execution completed")
    print(f"   Final Status: {final_status['status']}")
    print(f"   Duration: {final_status.get('durationSeconds', 0):.2f} seconds")
    
    # Step 4: Display results
    print("\n4. Node Execution Results:")
    print("   " + "-" * 66)
    
    for node_exec in final_status['nodeExecutions']:
        node = node_exec['node']
        print(f"\n   Node: {node['name']} ({node['nodeKey']})")
        print(f"   Status: {node_exec['status']}")
        
        if node_exec['durationSeconds']:
            print(f"   Duration: {node_exec['durationSeconds']:.2f}s")
        
        if node_exec['outputData']:
            print(f"   Output: {json.dumps(node_exec['outputData'], indent=10)}")
        
        if node_exec['errorMessage']:
            print(f"   Error: {node_exec['errorMessage']}")
        
        print("   " + "-" * 66)
    
    # Step 5: Get statistics
    print("\n5. Graph Statistics:")
    stats = get_graph_statistics(graph_id)
    
    if stats:
        print(f"   Total Executions: {stats['totalExecutions']}")
        print(f"   Successful: {stats['successfulExecutions']}")
        print(f"   Failed: {stats['failedExecutions']}")
        if stats['averageDurationSeconds']:
            print(f"   Average Duration: {stats['averageDurationSeconds']:.2f}s")
    
    # Step 6: Search functionality
    print("\n6. Testing search functionality...")
    search_results = search_graphs("GraphQL")
    print(f"   Found {len(search_results)} graph(s) matching 'GraphQL'")
    for g in search_results:
        print(f"   - {g['name']} (ID: {g['id']})")
    
    print("\n" + "=" * 70)
    print("✓ Example completed successfully!")
    print("=" * 70)
    print("\nYou can now:")
    print("• Visit http://localhost:8000/graphql to use GraphiQL")
    print("• Explore the schema and run custom queries")
    print("• Use subscriptions for real-time updates")


if __name__ == "__main__":
    main()
