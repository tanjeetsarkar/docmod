"""Graph canvas widget for visualizing and interacting with graphs."""

from typing import Optional, Set, Tuple
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static
from textual.reactive import reactive
from textual.message import Message
from rich.console import RenderableType
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from graph_tui.models import Graph, Node, NodeStatus


class GraphCanvas(Static):
    """Canvas for displaying and interacting with graph nodes."""
    
    DEFAULT_CSS = """
    GraphCanvas {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        overflow: auto;
    }
    """
    
    # Reactive attributes
    selected_node_id: reactive[Optional[str]] = reactive(None)
    graph: reactive[Optional[Graph]] = reactive(None)
    
    class NodeSelected(Message):
        """Posted when a node is selected."""
        def __init__(self, node_id: str) -> None:
            self.node_id = node_id
            super().__init__()
    
    class NodeMoved(Message):
        """Posted when a node is moved."""
        def __init__(self, node_id: str, x: int, y: int) -> None:
            self.node_id = node_id
            self.x = x
            self.y = y
            super().__init__()
    
    def __init__(self, *args, **kwargs):
        """Initialize canvas."""
        super().__init__(*args, **kwargs)
        self._offset_x = 0
        self._offset_y = 0
        self._connecting_mode = False
        self._connection_source: Optional[str] = None
    
    def render(self) -> RenderableType:
        """Render the canvas."""
        if not self.graph or not self.graph.nodes:
            return Panel(
                Text("No graph loaded. Press 'l' to load a graph.", style="dim"),
                title="Graph Canvas",
                border_style="blue"
            )
        
        # Create a text-based representation of the graph
        lines = self._render_graph()
        return Panel(
            "\n".join(lines),
            title=f"Graph: {self.graph.name}",
            border_style="blue"
        )
    
    def _render_graph(self) -> list[str]:
        """Render graph as ASCII art."""
        if not self.graph:
            return []
        
        # Calculate canvas size
        max_x = max((n.position.x for n in self.graph.nodes), default=0) + 30
        max_y = max((n.position.y for n in self.graph.nodes), default=0) + 10
        
        # Create empty canvas
        canvas = [[' ' for _ in range(max_x)] for _ in range(max_y)]
        
        # Draw edges first (so they appear behind nodes)
        for edge in self.graph.edges:
            source = self.graph.get_node(edge.source_id)
            target = self.graph.get_node(edge.target_id)
            if source and target:
                self._draw_edge(canvas, source, target)
        
        # Draw nodes
        for node in self.graph.nodes:
            self._draw_node(canvas, node, node.id == self.selected_node_id)
        
        # Convert canvas to strings
        return [''.join(row).rstrip() for row in canvas]
    
    def _draw_node(self, canvas: list[list[str]], node: Node, selected: bool):
        """Draw a node on the canvas."""
        x, y = node.position.x, node.position.y
        width = 20
        height = 3
        
        # Choose style based on status
        if selected:
            corners = ('╔', '╗', '╚', '╝')
            h_line, v_line = '═', '║'
            style = 'selected'
        else:
            corners = ('┌', '┐', '└', '┘')
            h_line, v_line = '─', '│'
            style = node.status.value
        
        # Draw box
        try:
            # Top
            canvas[y][x] = corners[0]
            for i in range(1, width - 1):
                canvas[y][x + i] = h_line
            canvas[y][x + width - 1] = corners[1]
            
            # Sides
            for i in range(1, height - 1):
                canvas[y + i][x] = v_line
                canvas[y + i][x + width - 1] = v_line
            
            # Bottom
            canvas[y + height - 1][x] = corners[2]
            for i in range(1, width - 1):
                canvas[y + height - 1][x + i] = h_line
            canvas[y + height - 1][x + width - 1] = corners[3]
            
            # Node name (truncated)
            name = node.name[:width - 4]
            name_x = x + (width - len(name)) // 2
            for i, char in enumerate(name):
                canvas[y + 1][name_x + i] = char
            
            # Status indicator
            status_char = self._get_status_char(node.status)
            canvas[y + 1][x + 1] = status_char
            
        except IndexError:
            pass  # Node is outside canvas bounds
    
    def _draw_edge(self, canvas: list[list[str]], source: Node, target: Node):
        """Draw an edge between two nodes."""
        # Simple line from source to target
        x1, y1 = source.position.x + 10, source.position.y + 1
        x2, y2 = target.position.x, target.position.y + 1
        
        try:
            # Vertical line
            if x1 == x2:
                for y in range(min(y1, y2), max(y1, y2) + 1):
                    if canvas[y][x1] == ' ':
                        canvas[y][x1] = '│'
            # Horizontal line
            elif y1 == y2:
                for x in range(min(x1, x2), max(x1, x2) + 1):
                    if canvas[y1][x] == ' ':
                        canvas[y1][x] = '─'
            # L-shaped connection
            else:
                # Horizontal part
                for x in range(x1, x2):
                    if canvas[y1][x] == ' ':
                        canvas[y1][x] = '─'
                # Vertical part
                for y in range(min(y1, y2), max(y1, y2) + 1):
                    if canvas[y][x2] == ' ':
                        canvas[y][x2] = '│'
                # Corner
                canvas[y1][x2] = '└' if y2 > y1 else '┘'
            
            # Arrow at target
            if x2 < len(canvas[y2]):
                canvas[y2][x2] = '►'
        except IndexError:
            pass
    
    def _get_status_char(self, status: NodeStatus) -> str:
        """Get character for node status."""
        return {
            NodeStatus.PENDING: '○',
            NodeStatus.RUNNING: '◐',
            NodeStatus.SUCCESS: '●',
            NodeStatus.FAILURE: '✗',
            NodeStatus.SKIPPED: '⊘',
        }.get(status, '?')
    
    def set_graph(self, graph: Graph):
        """Set the graph to display."""
        self.graph = graph
        if graph.nodes and not self.selected_node_id:
            self.selected_node_id = graph.nodes[0].id
        self.refresh()
    
    def select_node(self, node_id: str):
        """Select a node."""
        if self.graph and self.graph.get_node(node_id):
            self.selected_node_id = node_id
            self.post_message(self.NodeSelected(node_id))
            self.refresh()
    
    def select_next_node(self):
        """Select next node."""
        if not self.graph or not self.graph.nodes:
            return
        
        if not self.selected_node_id:
            self.select_node(self.graph.nodes[0].id)
            return
        
        current_idx = next(
            (i for i, n in enumerate(self.graph.nodes) if n.id == self.selected_node_id),
            -1
        )
        next_idx = (current_idx + 1) % len(self.graph.nodes)
        self.select_node(self.graph.nodes[next_idx].id)
    
    def select_prev_node(self):
        """Select previous node."""
        if not self.graph or not self.graph.nodes:
            return
        
        if not self.selected_node_id:
            self.select_node(self.graph.nodes[-1].id)
            return
        
        current_idx = next(
            (i for i, n in enumerate(self.graph.nodes) if n.id == self.selected_node_id),
            -1
        )
        prev_idx = (current_idx - 1) % len(self.graph.nodes)
        self.select_node(self.graph.nodes[prev_idx].id)
    
    def get_selected_node(self) -> Optional[Node]:
        """Get currently selected node."""
        if self.graph and self.selected_node_id:
            return self.graph.get_node(self.selected_node_id)
        return None
    
    def start_connection_mode(self):
        """Start connection mode."""
        if self.selected_node_id:
            self._connecting_mode = True
            self._connection_source = self.selected_node_id
    
    def complete_connection(self):
        """Complete connection to selected node."""
        if self._connecting_mode and self._connection_source and self.selected_node_id:
            if self._connection_source != self.selected_node_id:
                # Signal connection
                pass
            self._connecting_mode = False
            self._connection_source = None