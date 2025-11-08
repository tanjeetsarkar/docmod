"""Main graph editor screen."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer
from textual.binding import Binding

from graph_tui.models import Graph, Node
from graph_tui.widgets.graph_canvas import GraphCanvas
from graph_tui.widgets import NodeList, PropertyPanel, ExecutionPanel
from graph_tui.widgets import CreateNodeModal, EditNodeModal
from graph_tui.api.client import client


class MainScreen(Screen):
    """Main graph editor screen."""
    
    BINDINGS = [
        Binding("n", "new_node", "New Node"),
        Binding("e", "edit_node", "Edit Node"),
        Binding("d", "delete_node", "Delete Node"),
        Binding("c", "connect_nodes", "Connect Nodes"),
        Binding("x", "execute_graph", "Execute"),
        Binding("r", "refresh", "Refresh"),
        Binding("tab", "cycle_focus", "Switch Panel"),
        Binding("shift+tab", "cycle_focus_reverse", "Switch Panel (Rev)"),
        Binding("up,k", "navigate_up", "Up", show=False),
        Binding("down,j", "navigate_down", "Down", show=False),
        Binding("left,h", "navigate_left", "Left", show=False),
        Binding("right,l", "navigate_right", "Right", show=False),
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
    ]
    
    CSS = """
    MainScreen {
        layout: grid;
        grid-size: 3 3;
        grid-columns: 30 1fr 30;
        grid-rows: 1 1fr 15;
    }
    
    #header {
        column-span: 3;
    }
    
    #node-list {
        row-span: 2;
    }
    
    #graph-canvas {
        row-span: 2;
    }
    
    #property-panel {
        row-span: 2;
    }
    
    #execution-panel {
        column-span: 3;
    }
    """
    
    def __init__(self, graph: Graph):
        """Initialize screen."""
        super().__init__()
        self.graph = graph
        self._execution_task = None
        self._connecting_mode = False
        self._connection_source = None
    
    def compose(self) -> ComposeResult:
        """Compose screen."""
        yield Header(id="header")
        yield NodeList(id="node-list")
        yield GraphCanvas(id="graph-canvas")
        yield PropertyPanel(id="property-panel")
        yield ExecutionPanel(id="execution-panel")
        yield Footer()
    
    async def on_mount(self) -> None:
        """Handle mount."""
        # Set initial graph
        canvas = self.query_one(GraphCanvas)
        canvas.set_graph(self.graph)
        
        node_list = self.query_one(NodeList)
        node_list.set_graph(self.graph)
        
        # Start execution monitoring
        self._start_execution_monitoring()
    
    def on_graph_canvas_node_selected(self, event: GraphCanvas.NodeSelected) -> None:
        """Handle node selection."""
        node = self.graph.get_node(event.node_id)
        if node:
            prop_panel = self.query_one(PropertyPanel)
            prop_panel.set_node(node)
    
    async def action_new_node(self) -> None:
        """Create new node."""
        result = await self.app.push_screen_wait(CreateNodeModal())
        
        if result:
            try:
                # Calculate position (simple incremental)
                last_node = self.graph.nodes[-1] if self.graph.nodes else None
                x = last_node.position.x + 25 if last_node else 0
                y = last_node.position.y if last_node else 0
                
                # Create via API
                node = await client.create_node(
                    graph_id=self.graph.id,
                    name=result["name"],
                    node_type=result["type"],
                    position={"x": x, "y": y}
                )
                
                # Update local graph
                self.graph.nodes.append(node)
                await self._refresh_display()
                
                self.notify(f"Node '{node.name}' created")
            except Exception as e:
                self.notify(f"Error creating node: {e}", severity="error")
    
    async def action_edit_node(self) -> None:
        """Edit selected node."""
        canvas = self.query_one(GraphCanvas)
        node = canvas.get_selected_node()
        
        if not node:
            self.notify("No node selected", severity="warning")
            return
        
        result = await self.app.push_screen_wait(EditNodeModal(node))
        
        if result:
            try:
                # Update via API
                updated_node = await client.update_node(
                    node_id=node.id,
                    name=result.get("name"),
                    config=node.config  # Keep existing config
                )
                
                # Update local graph
                for i, n in enumerate(self.graph.nodes):
                    if n.id == node.id:
                        self.graph.nodes[i] = updated_node
                        break
                
                await self._refresh_display()
                self.notify(f"Node '{updated_node.name}' updated")
            except Exception as e:
                self.notify(f"Error updating node: {e}", severity="error")
    
    async def action_delete_node(self) -> None:
        """Delete selected node."""
        canvas = self.query_one(GraphCanvas)
        node = canvas.get_selected_node()
        
        if not node:
            self.notify("No node selected", severity="warning")
            return
        
        try:
            # Delete via API
            await client.delete_node(node.id)
            
            # Update local graph
            self.graph.nodes = [n for n in self.graph.nodes if n.id != node.id]
            self.graph.edges = [
                e for e in self.graph.edges 
                if e.source_id != node.id and e.target_id != node.id
            ]
            
            await self._refresh_display()
            self.notify(f"Node '{node.name}' deleted")
        except Exception as e:
            self.notify(f"Error deleting node: {e}", severity="error")
    
    async def action_connect_nodes(self) -> None:
        """Connect two nodes."""
        canvas = self.query_one(GraphCanvas)
        
        if not self._connecting_mode:
            # Start connection mode
            node = canvas.get_selected_node()
            if node:
                self._connecting_mode = True
                self._connection_source = node.id
                self.notify(f"Select target node for connection from '{node.name}'")
        else:
            # Complete connection
            target_node = canvas.get_selected_node()
            if target_node and self._connection_source:
                if target_node.id != self._connection_source:
                    try:
                        # Create connection via API
                        edge_id = await client.connect_nodes(
                            source_id=self._connection_source,
                            target_id=target_node.id
                        )
                        
                        # Reload graph to get updated edges
                        await self._reload_graph()
                        self.notify("Nodes connected")
                    except Exception as e:
                        self.notify(f"Error connecting nodes: {e}", severity="error")
                else:
                    self.notify("Cannot connect node to itself", severity="warning")
            
            # Reset connection mode
            self._connecting_mode = False
            self._connection_source = None
    
    async def action_execute_graph(self) -> None:
        """Execute the graph."""
        try:
            execution_id = await client.execute_graph(self.graph.id)
            self.notify(f"Graph execution started (ID: {execution_id})")
            
            # Start monitoring execution
            self._start_execution_monitoring()
        except Exception as e:
            self.notify(f"Error executing graph: {e}", severity="error")
    
    async def action_refresh(self) -> None:
        """Refresh graph from server."""
        await self._reload_graph()
        self.notify("Graph refreshed")
    
    async def action_navigate_up(self) -> None:
        """Navigate up."""
        canvas = self.query_one(GraphCanvas)
        canvas.select_prev_node()
    
    async def action_navigate_down(self) -> None:
        """Navigate down."""
        canvas = self.query_one(GraphCanvas)
        canvas.select_next_node()
    
    async def action_navigate_left(self) -> None:
        """Navigate left (to parent)."""
        canvas = self.query_one(GraphCanvas)
        node = canvas.get_selected_node()
        if node and node.parent_ids:
            canvas.select_node(node.parent_ids[0])
    
    async def action_navigate_right(self) -> None:
        """Navigate right (to child)."""
        canvas = self.query_one(GraphCanvas)
        node = canvas.get_selected_node()
        if node and node.child_ids:
            canvas.select_node(node.child_ids[0])
    
    async def action_cycle_focus(self) -> None:
        """Cycle focus to next panel."""
        self.screen.focus_next()
    
    async def action_cycle_focus_reverse(self) -> None:
        """Cycle focus to previous panel."""
        self.screen.focus_previous()
    
    async def action_help(self) -> None:
        """Show help."""
        # TODO: Implement help screen
        self.notify("Help: Use arrow keys to navigate, 'n' to create node, 'c' to connect")
    
    async def _reload_graph(self) -> None:
        """Reload graph from API."""
        try:
            updated_graph = await client.get_graph(self.graph.id)
            if updated_graph:
                self.graph = updated_graph
                await self._refresh_display()
        except Exception as e:
            self.notify(f"Error reloading graph: {e}", severity="error")
    
    async def _refresh_display(self) -> None:
        """Refresh all display widgets."""
        canvas = self.query_one(GraphCanvas)
        canvas.set_graph(self.graph)
        
        node_list = self.query_one(NodeList)
        node_list.set_graph(self.graph)
        
        # Update property panel with selected node
        selected = canvas.get_selected_node()
        if selected:
            prop_panel = self.query_one(PropertyPanel)
            prop_panel.set_node(selected)
    
    def _start_execution_monitoring(self) -> None:
        """Start monitoring execution status."""
        if self._execution_task:
            self._execution_task.cancel()
        
        self._execution_task = self.app.create_task(
            self._monitor_execution(),
            name="execution_monitor"
        )
    
    async def _monitor_execution(self) -> None:
        """Monitor execution via subscription."""
        try:
            async with client.session():
                async for execution in client.subscribe_execution_updates(self.graph.id):
                    # Update execution panel
                    exec_panel = self.query_one(ExecutionPanel)
                    exec_panel.set_execution(execution)
                    
                    # Update graph with node statuses
                    # (This would need the execution to include node statuses)
                    await self._reload_graph()
        except Exception as e:
            # Silently fail or log
            pass