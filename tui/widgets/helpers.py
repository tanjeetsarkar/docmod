"""Supporting widgets for Graph TUI."""

from typing import Optional
from textual.app import ComposeResult
from textual.widgets import Static, Tree, Label, Input, Button
from textual.containers import Container, Vertical, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from graph_tui.models import Graph, Node, Execution, NodeStatus


# === Node List Widget ===

class NodeList(Static):
    """Tree view of nodes."""
    
    DEFAULT_CSS = """
    NodeList {
        width: 30;
        height: 1fr;
        border: solid $primary;
    }
    """
    
    graph: reactive[Optional[Graph]] = reactive(None)
    selected_node_id: reactive[Optional[str]] = reactive(None)
    
    def compose(self) -> ComposeResult:
        """Compose widget."""
        yield Tree("Nodes")
    
    def watch_graph(self, graph: Optional[Graph]):
        """Update tree when graph changes."""
        tree = self.query_one(Tree)
        tree.clear()
        
        if not graph:
            return
        
        tree.root.expand()
        
        # Add root nodes
        for node in graph.get_root_nodes():
            self._add_node_tree(tree.root, node, graph)
    
    def _add_node_tree(self, parent, node: Node, graph: Graph):
        """Recursively add nodes to tree."""
        status_icon = self._get_status_icon(node.status)
        label = f"{status_icon} {node.name}"
        
        node_tree = parent.add(label, data=node.id)
        
        # Add children
        for child in graph.get_children(node.id):
            self._add_node_tree(node_tree, child, graph)
    
    def _get_status_icon(self, status: NodeStatus) -> str:
        """Get icon for status."""
        return {
            NodeStatus.PENDING: "○",
            NodeStatus.RUNNING: "◐",
            NodeStatus.SUCCESS: "●",
            NodeStatus.FAILURE: "✗",
            NodeStatus.SKIPPED: "⊘",
        }.get(status, "?")
    
    def set_graph(self, graph: Graph):
        """Set graph."""
        self.graph = graph


# === Property Panel ===

class PropertyPanel(Static):
    """Panel showing selected node properties."""
    
    DEFAULT_CSS = """
    PropertyPanel {
        width: 30;
        height: 1fr;
        border: solid $primary;
    }
    """
    
    node: reactive[Optional[Node]] = reactive(None)
    
    def render(self):
        """Render properties."""
        if not self.node:
            return Panel(
                Text("No node selected", style="dim"),
                title="Properties",
                border_style="blue"
            )
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="bold cyan")
        table.add_column("Value")
        
        table.add_row("ID", self.node.id)
        table.add_row("Name", self.node.name)
        table.add_row("Type", self.node.type)
        table.add_row("Status", self.node.status.value)
        
        if self.node.description:
            table.add_row("Description", self.node.description)
        
        table.add_row("Position", f"({self.node.position.x}, {self.node.position.y})")
        
        if self.node.parent_ids:
            table.add_row("Parents", str(len(self.node.parent_ids)))
        
        if self.node.child_ids:
            table.add_row("Children", str(len(self.node.child_ids)))
        
        if self.node.error_message:
            table.add_row("Error", Text(self.node.error_message, style="red"))
        
        return Panel(table, title="Properties", border_style="blue")
    
    def set_node(self, node: Optional[Node]):
        """Set node to display."""
        self.node = node


# === Execution Panel ===

class ExecutionPanel(Static):
    """Panel showing execution status and logs."""
    
    DEFAULT_CSS = """
    ExecutionPanel {
        width: 1fr;
        height: 15;
        border: solid $primary;
    }
    """
    
    execution: reactive[Optional[Execution]] = reactive(None)
    
    def render(self):
        """Render execution status."""
        if not self.execution:
            return Panel(
                Text("No execution running", style="dim"),
                title="Execution",
                border_style="blue"
            )
        
        # Status line
        status_text = Text()
        status_text.append("Status: ", style="bold")
        
        status_color = {
            "idle": "white",
            "running": "yellow",
            "completed": "green",
            "failed": "red",
            "cancelled": "orange"
        }.get(self.execution.status.value, "white")
        
        status_text.append(self.execution.status.value.upper(), style=f"bold {status_color}")
        
        # Progress
        if self.execution.progress > 0:
            status_text.append(f" ({self.execution.progress:.1f}%)", style="dim")
        
        # Duration
        if self.execution.duration:
            status_text.append(f" | Duration: {self.execution.duration:.1f}s", style="dim")
        
        # Logs
        log_lines = [status_text, Text("")]
        
        # Show last 10 logs
        for log in self.execution.logs[-10:]:
            log_text = Text()
            log_text.append(f"{log.timestamp.strftime('%H:%M:%S')} ", style="dim")
            
            level_style = {
                "info": "blue",
                "warning": "yellow",
                "error": "red"
            }.get(log.level, "white")
            
            log_text.append(f"[{log.level.upper()}] ", style=level_style)
            
            if log.node_id:
                log_text.append(f"({log.node_id[:8]}) ", style="dim")
            
            log_text.append(log.message)
            log_lines.append(log_text)
        
        from rich.console import Group
        content = Group(*log_lines)
        
        return Panel(content, title="Execution", border_style="blue")
    
    def set_execution(self, execution: Optional[Execution]):
        """Set execution."""
        self.execution = execution


# === Modal Dialogs ===

class CreateNodeModal(ModalScreen[Optional[dict]]):
    """Modal for creating a new node."""
    
    DEFAULT_CSS = """
    CreateNodeModal {
        align: center middle;
    }
    
    CreateNodeModal > Container {
        width: 60;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    
    CreateNodeModal Input {
        margin: 1 0;
    }
    
    CreateNodeModal Horizontal {
        height: auto;
        margin-top: 1;
    }
    
    CreateNodeModal Button {
        margin: 0 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Compose modal."""
        with Vertical():
            yield Label("Create New Node")
            yield Input(placeholder="Node name", id="name")
            yield Input(placeholder="Node type (e.g., task, transform)", id="type")
            yield Input(placeholder="Description (optional)", id="description")
            with Horizontal():
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "create":
            name = self.query_one("#name", Input).value
            node_type = self.query_one("#type", Input).value
            description = self.query_one("#description", Input).value
            
            if name and node_type:
                self.dismiss({
                    "name": name,
                    "type": node_type,
                    "description": description or None
                })
            else:
                # Show error - name and type required
                pass
        else:
            self.dismiss(None)


class EditNodeModal(ModalScreen[Optional[dict]]):
    """Modal for editing a node."""
    
    DEFAULT_CSS = """
    EditNodeModal {
        align: center middle;
    }
    
    EditNodeModal > Container {
        width: 60;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    
    EditNodeModal Input {
        margin: 1 0;
    }
    
    EditNodeModal Horizontal {
        height: auto;
        margin-top: 1;
    }
    
    EditNodeModal Button {
        margin: 0 1;
    }
    """
    
    def __init__(self, node: Node):
        """Initialize with node."""
        super().__init__()
        self.node = node
    
    def compose(self) -> ComposeResult:
        """Compose modal."""
        with Vertical():
            yield Label(f"Edit Node: {self.node.name}")
            yield Input(value=self.node.name, placeholder="Node name", id="name")
            yield Input(
                value=self.node.description or "", 
                placeholder="Description", 
                id="description"
            )
            with Horizontal():
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "save":
            name = self.query_one("#name", Input).value
            description = self.query_one("#description", Input).value
            
            if name:
                self.dismiss({
                    "name": name,
                    "description": description or None
                })
        else:
            self.dismiss(None)