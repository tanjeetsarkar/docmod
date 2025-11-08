"""GraphQL API client."""

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional
from contextlib import asynccontextmanager

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport

from graph_tui.config import settings
from graph_tui.models import Graph, Node, Execution, ExecutionLog, NodeStatus, GraphStatus


class GraphQLClient:
    """GraphQL client wrapper."""
    
    def __init__(self):
        """Initialize client."""
        self._http_client: Optional[Client] = None
        self._ws_client: Optional[Client] = None
    
    async def connect(self):
        """Connect to GraphQL endpoint."""
        # HTTP transport for queries and mutations
        http_transport = AIOHTTPTransport(
            url=settings.graphql_url,
            timeout=settings.timeout,
        )
        self._http_client = Client(
            transport=http_transport,
            fetch_schema_from_transport=True,
        )
        
        # WebSocket transport for subscriptions
        ws_transport = WebsocketsTransport(url=settings.graphql_ws_url)
        self._ws_client = Client(transport=ws_transport)
    
    async def disconnect(self):
        """Disconnect from GraphQL endpoint."""
        if self._http_client:
            await self._http_client.close_async()
        if self._ws_client:
            await self._ws_client.close_async()
    
    @asynccontextmanager
    async def session(self):
        """Context manager for client session."""
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()
    
    # === Queries ===
    
    async def list_graphs(self) -> List[Graph]:
        """List all graphs."""
        query = gql("""
            query ListGraphs {
                graphs {
                    id
                    name
                    description
                    status
                    createdAt
                    updatedAt
                }
            }
        """)
        
        result = await self._http_client.execute_async(query)
        return [self._parse_graph(g) for g in result.get("graphs", [])]
    
    async def get_graph(self, graph_id: str) -> Optional[Graph]:
        """Get graph by ID with all nodes and edges."""
        query = gql("""
            query GetGraph($id: ID!) {
                graph(id: $id) {
                    id
                    name
                    description
                    status
                    createdAt
                    updatedAt
                    nodes {
                        id
                        name
                        type
                        description
                        position { x, y }
                        config
                        status
                        parentIds
                        childIds
                        startedAt
                        completedAt
                        errorMessage
                        result
                    }
                    edges {
                        id
                        sourceId
                        targetId
                        label
                    }
                }
            }
        """)
        
        result = await self._http_client.execute_async(query, variable_values={"id": graph_id})
        graph_data = result.get("graph")
        return self._parse_graph(graph_data) if graph_data else None
    
    async def get_execution_status(self, graph_id: str) -> Optional[Execution]:
        """Get current execution status."""
        query = gql("""
            query GetExecution($graphId: ID!) {
                execution(graphId: $graphId) {
                    id
                    graphId
                    status
                    startedAt
                    completedAt
                    progress
                    logs {
                        timestamp
                        nodeId
                        level
                        message
                    }
                }
            }
        """)
        
        result = await self._http_client.execute_async(
            query, 
            variable_values={"graphId": graph_id}
        )
        exec_data = result.get("execution")
        return self._parse_execution(exec_data) if exec_data else None
    
    # === Mutations ===
    
    async def create_graph(self, name: str, description: Optional[str] = None) -> Graph:
        """Create new graph."""
        mutation = gql("""
            mutation CreateGraph($input: CreateGraphInput!) {
                createGraph(input: $input) {
                    id
                    name
                    description
                    status
                }
            }
        """)
        
        result = await self._http_client.execute_async(
            mutation,
            variable_values={
                "input": {"name": name, "description": description}
            }
        )
        return self._parse_graph(result["createGraph"])
    
    async def create_node(
        self, 
        graph_id: str, 
        name: str, 
        node_type: str,
        position: Optional[Dict[str, int]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Node:
        """Create new node."""
        mutation = gql("""
            mutation CreateNode($input: CreateNodeInput!) {
                createNode(input: $input) {
                    id
                    name
                    type
                    position { x, y }
                    config
                    status
                }
            }
        """)
        
        result = await self._http_client.execute_async(
            mutation,
            variable_values={
                "input": {
                    "graphId": graph_id,
                    "name": name,
                    "type": node_type,
                    "position": position or {"x": 0, "y": 0},
                    "config": config or {}
                }
            }
        )
        return self._parse_node(result["createNode"])
    
    async def update_node(
        self, 
        node_id: str, 
        name: Optional[str] = None,
        position: Optional[Dict[str, int]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Node:
        """Update node."""
        mutation = gql("""
            mutation UpdateNode($id: ID!, $input: UpdateNodeInput!) {
                updateNode(id: $id, input: $input) {
                    id
                    name
                    type
                    position { x, y }
                    config
                }
            }
        """)
        
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if position is not None:
            update_data["position"] = position
        if config is not None:
            update_data["config"] = config
        
        result = await self._http_client.execute_async(
            mutation,
            variable_values={"id": node_id, "input": update_data}
        )
        return self._parse_node(result["updateNode"])
    
    async def delete_node(self, node_id: str) -> bool:
        """Delete node."""
        mutation = gql("""
            mutation DeleteNode($id: ID!) {
                deleteNode(id: $id)
            }
        """)
        
        result = await self._http_client.execute_async(
            mutation,
            variable_values={"id": node_id}
        )
        return result.get("deleteNode", False)
    
    async def connect_nodes(self, source_id: str, target_id: str) -> str:
        """Connect two nodes."""
        mutation = gql("""
            mutation ConnectNodes($input: ConnectNodesInput!) {
                connectNodes(input: $input) {
                    id
                }
            }
        """)
        
        result = await self._http_client.execute_async(
            mutation,
            variable_values={
                "input": {"sourceId": source_id, "targetId": target_id}
            }
        )
        return result["connectNodes"]["id"]
    
    async def execute_graph(self, graph_id: str) -> str:
        """Execute graph."""
        mutation = gql("""
            mutation ExecuteGraph($graphId: ID!) {
                executeGraph(graphId: $graphId) {
                    id
                }
            }
        """)
        
        result = await self._http_client.execute_async(
            mutation,
            variable_values={"graphId": graph_id}
        )
        return result["executeGraph"]["id"]
    
    # === Subscriptions ===
    
    async def subscribe_execution_updates(
        self, 
        graph_id: str
    ) -> AsyncIterator[Execution]:
        """Subscribe to execution updates."""
        subscription = gql("""
            subscription ExecutionUpdates($graphId: ID!) {
                executionUpdates(graphId: $graphId) {
                    id
                    graphId
                    status
                    startedAt
                    completedAt
                    progress
                    logs {
                        timestamp
                        nodeId
                        level
                        message
                    }
                }
            }
        """)
        
        async for result in self._ws_client.subscribe_async(
            subscription,
            variable_values={"graphId": graph_id}
        ):
            yield self._parse_execution(result["executionUpdates"])
    
    # === Parsing helpers ===
    
    def _parse_graph(self, data: Dict[str, Any]) -> Graph:
        """Parse graph data."""
        return Graph(**self._camel_to_snake(data))
    
    def _parse_node(self, data: Dict[str, Any]) -> Node:
        """Parse node data."""
        return Node(**self._camel_to_snake(data))
    
    def _parse_execution(self, data: Dict[str, Any]) -> Execution:
        """Parse execution data."""
        return Execution(**self._camel_to_snake(data))
    
    def _camel_to_snake(self, data: Any) -> Any:
        """Convert camelCase keys to snake_case recursively."""
        if isinstance(data, dict):
            return {
                self._to_snake(k): self._camel_to_snake(v) 
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._camel_to_snake(item) for item in data]
        return data
    
    @staticmethod
    def _to_snake(name: str) -> str:
        """Convert camelCase to snake_case."""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


# Global client instance
client = GraphQLClient()