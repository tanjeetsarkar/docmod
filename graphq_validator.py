from typing import Dict, List, Set, Tuple
from collections import defaultdict, deque


class GraphValidator:
    """Validates graph structure and provides topological sorting"""
    
    def __init__(self, nodes: List[Dict], edges: List[Dict]):
        """
        Args:
            nodes: List of dicts with 'node_key' field
            edges: List of dicts with 'source_node_key' and 'target_node_key' fields
        """
        self.nodes = {n['node_key']: n for n in nodes}
        self.edges = edges
        self.adj_list = self._build_adjacency_list()
    
    def _build_adjacency_list(self) -> Dict[str, List[Tuple[str, str]]]:
        """Build adjacency list: node_key -> [(target_key, condition), ...]"""
        adj = defaultdict(list)
        for edge in self.edges:
            adj[edge['source_node_key']].append(
                (edge['target_node_key'], edge.get('condition', 'on_success'))
            )
        return adj
    
    def has_cycle(self) -> bool:
        """Check if graph has cycles using DFS"""
        visited = set()
        rec_stack = set()
        
        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor, _ in self.adj_list.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node_key in self.nodes:
            if node_key not in visited:
                if dfs(node_key):
                    return True
        
        return False
    
    def topological_sort(self) -> List[str]:
        """
        Perform topological sort using Kahn's algorithm
        Returns list of node_keys in execution order
        """
        in_degree = {node_key: 0 for node_key in self.nodes}
        
        # Calculate in-degrees
        for node_key in self.nodes:
            for neighbor, _ in self.adj_list.get(node_key, []):
                in_degree[neighbor] += 1
        
        # Queue with nodes having no incoming edges
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            
            for neighbor, _ in self.adj_list.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(result) != len(self.nodes):
            raise ValueError("Graph has a cycle")
        
        return result
    
    def get_execution_levels(self) -> List[List[str]]:
        """
        Group nodes into levels for parallel execution
        Level 0: nodes with no dependencies
        Level N: nodes depending only on nodes from levels 0 to N-1
        """
        in_degree = {node_key: 0 for node_key in self.nodes}
        
        for node_key in self.nodes:
            for neighbor, _ in self.adj_list.get(node_key, []):
                in_degree[neighbor] += 1
        
        levels = []
        current_level = [node for node, degree in in_degree.items() if degree == 0]
        
        while current_level:
            levels.append(current_level)
            next_level = []
            
            for node in current_level:
                for neighbor, _ in self.adj_list.get(node, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_level.append(neighbor)
            
            current_level = next_level
        
        return levels
    
    def get_dependencies(self, node_key: str) -> List[str]:
        """Get all nodes that must complete before this node can run"""
        dependencies = []
        for nk in self.nodes:
            for neighbor, _ in self.adj_list.get(nk, []):
                if neighbor == node_key:
                    dependencies.append(nk)
        return dependencies
    
    def get_children(self, node_key: str) -> List[Tuple[str, str]]:
        """Get children of a node with their edge conditions"""
        return self.adj_list.get(node_key, [])
    
    def validate(self) -> Tuple[bool, str]:
        """
        Validate the graph
        Returns: (is_valid, error_message)
        """
        if not self.nodes:
            return False, "Graph has no nodes"
        
        if self.has_cycle():
            return False, "Graph contains a cycle"
        
        # Check for orphaned nodes in edges
        node_keys = set(self.nodes.keys())
        for edge in self.edges:
            if edge['source_node_key'] not in node_keys:
                return False, f"Edge references non-existent source node: {edge['source_node_key']}"
            if edge['target_node_key'] not in node_keys:
                return False, f"Edge references non-existent target node: {edge['target_node_key']}"
        
        return True, ""
