# GraphQL API Examples

This document provides example queries, mutations, and subscriptions for the DAG Executor GraphQL API.

Access the interactive GraphiQL interface at: `http://localhost:8000/graphql`

## Table of Contents
- [Queries](#queries)
- [Mutations](#mutations)
- [Subscriptions](#subscriptions)
- [Advanced Examples](#advanced-examples)

---

## Queries

### Get a Graph with Full Details

```graphql
query GetGraph($id: Int!) {
  graph(id: $id) {
    id
    name
    description
    createdAt
    updatedAt
    isActive
    nodes {
      id
      nodeKey
      name
      code
      constants
      timeoutSeconds
      outgoingEdges {
        id
        condition
        targetNode {
          nodeKey
          name
        }
      }
    }
    edges {
      id
      condition
      sourceNode {
        nodeKey
      }
      targetNode {
        nodeKey
      }
    }
    executionLevels
    topologicalOrder
  }
}
```

**Variables:**
```json
{
  "id": 1
}
```

### List All Graphs

```graphql
query ListGraphs {
  graphs(limit: 10, offset: 0) {
    id
    name
    description
    createdAt
    nodes {
      nodeKey
      name
    }
  }
}
```

### Get Execution Status

```graphql
query GetExecution($id: Int!) {
  execution(id: $id) {
    id
    status
    startedAt
    completedAt
    durationSeconds
    progress
    errorMessage
    context
    graph {
      name
    }
    nodeExecutions(status: SUCCESS) {
      id
      status
      durationSeconds
      node {
        nodeKey
        name
      }
      outputData
      errorMessage
    }
  }
}
```

**Variables:**
```json
{
  "id": 1
}
```

### Get Graph Statistics

```graphql
query GraphStats($graphId: Int!) {
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
      completedAt
    }
  }
}
```

### Get Node Statistics

```graphql
query NodeStats($nodeId: Int!) {
  nodeStatistics(nodeId: $nodeId) {
    nodeId
    totalExecutions
    successfulExecutions
    failedExecutions
    averageDurationSeconds
    successRate
  }
}
```

### Search Graphs

```graphql
query SearchGraphs($searchQuery: String!) {
  searchGraphs(query: $searchQuery, limit: 5) {
    id
    name
    description
    createdAt
  }
}
```

**Variables:**
```json
{
  "searchQuery": "data pipeline"
}
```

### Get Running Executions

```graphql
query RunningExecutions {
  runningExecutions(limit: 20) {
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
```

### Filter Executions

```graphql
query FilterExecutions($filter: ExecutionFilterInput!) {
  executions(filter: $filter, limit: 50) {
    id
    status
    startedAt
    completedAt
    graph {
      name
    }
  }
}
```

**Variables:**
```json
{
  "filter": {
    "graphId": 1,
    "status": "SUCCESS"
  }
}
```

---

## Mutations

### Create a Graph

```graphql
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
        condition
        sourceNode {
          nodeKey
        }
        targetNode {
          nodeKey
        }
      }
      executionLevels
    }
  }
}
```

**Variables:**
```json
{
  "input": {
    "name": "Simple Pipeline",
    "description": "A simple data processing pipeline",
    "nodes": [
      {
        "nodeKey": "fetch",
        "name": "Fetch Data",
        "code": "output = {'data': [1, 2, 3, 4, 5]}",
        "constants": {},
        "timeoutSeconds": 60
      },
      {
        "nodeKey": "process",
        "name": "Process Data",
        "code": "data = inputs['fetch']['data']\noutput = {'processed': [x * 2 for x in data]}",
        "constants": {},
        "timeoutSeconds": 60
      },
      {
        "nodeKey": "save",
        "name": "Save Results",
        "code": "result = inputs['process']['processed']\noutput = {'saved': True, 'count': len(result)}",
        "constants": {},
        "timeoutSeconds": 60
      }
    ],
    "edges": [
      {
        "sourceNodeKey": "fetch",
        "targetNodeKey": "process",
        "condition": "ON_SUCCESS"
      },
      {
        "sourceNodeKey": "process",
        "targetNodeKey": "save",
        "condition": "ON_SUCCESS"
      }
    ]
  }
}
```

### Update a Graph

```graphql
mutation UpdateGraph($id: Int!, $input: GraphUpdateInput!) {
  updateGraph(id: $id, input: $input) {
    success
    errors
    graph {
      id
      name
      description
      updatedAt
    }
  }
}
```

**Variables:**
```json
{
  "id": 1,
  "input": {
    "name": "Updated Pipeline Name",
    "description": "New description"
  }
}
```

### Delete a Graph

```graphql
mutation DeleteGraph($id: Int!) {
  deleteGraph(id: $id) {
    success
    message
  }
}
```

**Variables:**
```json
{
  "id": 1
}
```

### Execute a Graph

```graphql
mutation ExecuteGraph($graphId: Int!, $input: ExecutionInput) {
  executeGraph(graphId: $graphId, input: $input) {
    success
    errors
    execution {
      id
      status
      startedAt
      context
      graph {
        name
      }
    }
  }
}
```

**Variables:**
```json
{
  "graphId": 1,
  "input": {
    "context": {
      "environment": "production",
      "userId": "user123",
      "requestId": "req-456"
    }
  }
}
```

### Cancel Execution

```graphql
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
```

**Variables:**
```json
{
  "executionId": 1
}
```

### Retry Failed Execution

```graphql
mutation RetryExecution($executionId: Int!) {
  retryExecution(executionId: $executionId) {
    success
    errors
    execution {
      id
      status
      context
    }
  }
}
```

**Variables:**
```json
{
  "executionId": 1
}
```

---

## Subscriptions

### Subscribe to Execution Updates

```graphql
subscription ExecutionUpdates($executionId: Int!, $interval: Float) {
  executionUpdates(executionId: $executionId, interval: $interval) {
    id
    status
    progress
    startedAt
    completedAt
  }
}
```

**Variables:**
```json
{
  "executionId": 1,
  "interval": 1.0
}
```

### Subscribe to Node Execution Updates

```graphql
subscription NodeExecutionUpdates($executionId: Int!) {
  nodeExecutionUpdates(executionId: $executionId, interval: 1.0) {
    id
    status
    node {
      nodeKey
      name
    }
    outputData
    errorMessage
    completedAt
  }
}
```

### Subscribe to Execution Progress

```graphql
subscription ExecutionProgress($executionId: Int!) {
  executionProgress(executionId: $executionId, interval: 2.0)
}
```

**Note:** This returns a simple float (0-100) representing progress percentage.

### Subscribe to Running Executions

```graphql
subscription AllRunningExecutions {
  runningExecutions(interval: 5.0) {
    id
    status
    startedAt
    progress
    graph {
      name
    }
  }
}
```

### Subscribe to New Executions

```graphql
subscription NewExecutions($graphId: Int) {
  newExecutions(graphId: $graphId, interval: 2.0) {
    id
    status
    startedAt
    graph {
      name
    }
  }
}
```

---

## Advanced Examples

### Create Graph with Conditional Edges

```graphql
mutation CreateGraphWithConditionals {
  createGraph(input: {
    name: "Conditional Pipeline"
    nodes: [
      {
        nodeKey: "validate"
        name: "Validate Input"
        code: "import random\nif random.random() > 0.5:\n  output = {'valid': True}\nelse:\n  raise Exception('Validation failed')"
      }
      {
        nodeKey: "success_handler"
        name: "Success Handler"
        code: "output = {'message': 'Validation passed!'}"
      }
      {
        nodeKey: "error_handler"
        name: "Error Handler"
        code: "output = {'message': 'Validation failed, handling error'}"
      }
      {
        nodeKey: "cleanup"
        name: "Cleanup"
        code: "output = {'message': 'Cleanup complete'}"
      }
    ]
    edges: [
      {
        sourceNodeKey: "validate"
        targetNodeKey: "success_handler"
        condition: ON_SUCCESS
      }
      {
        sourceNodeKey: "validate"
        targetNodeKey: "error_handler"
        condition: ON_FAILURE
      }
      {
        sourceNodeKey: "success_handler"
        targetNodeKey: "cleanup"
        condition: ALWAYS
      }
      {
        sourceNodeKey: "error_handler"
        targetNodeKey: "cleanup"
        condition: ALWAYS
      }
    ]
  }) {
    success
    graph {
      id
      name
    }
  }
}
```

### Query Graph with Relationship Navigation

```graphql
query GraphWithRelationships($id: Int!) {
  graph(id: $id) {
    name
    nodes {
      nodeKey
      name
      # Navigate to outgoing edges
      outgoingEdges {
        condition
        # Navigate to target nodes
        targetNode {
          nodeKey
          name
        }
      }
      # Get execution history for this node
      executions(limit: 5) {
        status
        durationSeconds
        startedAt
      }
    }
    # Get all executions of this graph
    executions(status: SUCCESS, limit: 10) {
      id
      startedAt
      durationSeconds
    }
  }
}
```

### Complex Filtering and Statistics

```graphql
query ComplexAnalysis {
  # Get recent successful executions
  executions(
    filter: { status: "SUCCESS" }
    limit: 100
  ) {
    id
    durationSeconds
    graph {
      name
    }
    nodeExecutions {
      node {
        nodeKey
      }
      durationSeconds
    }
  }
  
  # Get statistics for multiple graphs
  graph1: graphStatistics(graphId: 1) {
    totalExecutions
    successfulExecutions
    averageDurationSeconds
  }
  
  graph2: graphStatistics(graphId: 2) {
    totalExecutions
    successfulExecutions
    averageDurationSeconds
  }
}
```

### Create and Execute in One Request

```graphql
mutation CreateAndExecute($input: GraphInput!) {
  createGraph(input: $input) {
    success
    errors
    graph {
      id
      name
    }
  }
}

# Then in a follow-up request:
mutation ExecuteNewGraph($graphId: Int!) {
  executeGraph(graphId: $graphId, input: {
    context: { immediate: true }
  }) {
    execution {
      id
      status
    }
  }
}
```

---

## Tips for Using GraphiQL

1. **Auto-completion**: Press `Ctrl+Space` to see available fields
2. **Documentation**: Click on types in the Documentation Explorer
3. **Query History**: Access previous queries from the history panel
4. **Prettify**: Click the prettify button to format your query
5. **Variables**: Use the Variables panel at the bottom for dynamic values

## WebSocket Connection (for Subscriptions)

When using subscriptions from a client:

```javascript
import { createClient } from 'graphql-ws';

const client = createClient({
  url: 'ws://localhost:8000/graphql',
});

const unsubscribe = client.subscribe(
  {
    query: `
      subscription {
        executionUpdates(executionId: 1) {
          id
          status
          progress
        }
      }
    `,
  },
  {
    next: (data) => console.log('Received:', data),
    error: (error) => console.error('Error:', error),
    complete: () => console.log('Completed'),
  }
);
```
