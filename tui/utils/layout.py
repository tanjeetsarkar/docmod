"""Graph layout algorithms for positioning nodes."""

from typing import Dict, List, Tuple
import networkx as nx

from graph_tui.models import Graph, Node, NodePosition
from graph_tui.config import settings


def calculate_hierarchical_layout(graph: Graph) -> Dict[str, NodePosition]:
    """
    Calculate hierarchical layout for DAG.
    
    Returns dict mapping node_id to NodePosition.
    """
    if not graph.nodes:
        return {}
    
    # Create NetworkX graph
    G = nx.DiGraph()
    
    # Add nodes
    for node in graph.nodes:
        G.add_node(node.id)
    
    # Add edges
    for edge in graph.edges:
        G.add_edge(edge.source_id, edge.target_id)
    
    # Calculate layers (topological sort with depth)
    try:
        layers = _calculate_layers(G)
    except nx.NetworkXError:
        # Graph has cycles, fall back to simple layout
        return _calculate_simple_layout(graph)
    
    # Position nodes by layer
    positions = {}
    layer_counts = {}
    
    for node_id, layer in layers.items():
        if layer not in layer_counts:
            layer_counts[layer] = 0
        
        x = layer * settings.node_spacing_x
        y = layer_counts[layer] * settings.node_spacing_y
        
        positions[node_id] = NodePosition(x=x, y=y)
        layer_counts[layer] += 1
    
    return positions


def _calculate_layers(G: nx.DiGraph) -> Dict[str, int]:
    """Calculate layer for each node (longest path from root)."""
    layers = {}
    
    # Get topological order
    topo_order = list(nx.topological_sort(G))
    
    # Calculate longest path to each node
    for node in topo_order:
        predecessors = list(G.predecessors(node))
        if not predecessors:
            layers[node] = 0
        else:
            layers[node] = max(layers[p] for p in predecessors) + 1
    
    return layers


def _calculate_simple_layout(graph: Graph) -> Dict[str, NodePosition]:
    """Simple grid layout as fallback."""
    positions = {}
    nodes_per_row = 5
    
    for i, node in enumerate(graph.nodes):
        row = i // nodes_per_row
        col = i % nodes_per_row
        
        x = col * settings.node_spacing_x
        y = row * settings.node_spacing_y
        
        positions[node.id] = NodePosition(x=x, y=y)
    
    return positions


def calculate_force_directed_layout(
    graph: Graph,
    iterations: int = 50
) -> Dict[str, NodePosition]:
    """
    Calculate force-directed layout using Fruchterman-Reingold.
    
    Good for non-hierarchical graphs or when you want organic layouts.
    """
    if not graph.nodes:
        return {}
    
    # Create NetworkX graph
    G = nx.DiGraph()
    for node in graph.nodes:
        G.add_node(node.id)
    for edge in graph.edges:
        G.add_edge(edge.source_id, edge.target_id)
    
    # Calculate layout
    pos = nx.spring_layout(G, iterations=iterations, seed=42)
    
    # Convert to our position format (scale up for terminal)
    positions = {}
    scale = 50  # Scale factor for terminal
    
    for node_id, (x, y) in pos.items():
        # Normalize to positive coordinates
        positions[node_id] = NodePosition(
            x=int((x + 1) * scale),
            y=int((y + 1) * scale)
        )
    
    return positions


def auto_layout_graph(graph: Graph, layout_type: str = "hierarchical") -> Graph:
    """
    Apply automatic layout to graph.
    
    Args:
        graph: Graph to layout
        layout_type: Type of layout ("hierarchical", "force", "simple")
    
    Returns:
        Graph with updated node positions
    """
    if layout_type == "hierarchical":
        positions = calculate_hierarchical_layout(graph)
    elif layout_type == "force":
        positions = calculate_force_directed_layout(graph)
    else:
        positions = _calculate_simple_layout(graph)
    
    # Update node positions
    for node in graph.nodes:
        if node.id in positions:
            node.position = positions[node.id]
    
    return graph


def optimize_node_spacing(graph: Graph, min_spacing: int = 5) -> Graph:
    """
    Optimize node spacing to avoid overlaps.
    
    Ensures nodes don't overlap by adjusting positions.
    """
    if len(graph.nodes) < 2:
        return graph
    
    # Sort nodes by position
    nodes_sorted = sorted(graph.nodes, key=lambda n: (n.position.y, n.position.x))
    
    # Adjust positions to avoid overlaps
    adjusted = []
    for node in nodes_sorted:
        # Check for overlaps with already adjusted nodes
        while any(
            abs(node.position.x - other.position.x) < settings.node_spacing_x and
            abs(node.position.y - other.position.y) < min_spacing
            for other in adjusted
        ):
            node.position.y += min_spacing
        
        adjusted.append(node)
    
    return graph