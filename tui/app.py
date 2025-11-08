"""Main Textual application for Graph TUI."""

# === app.py ===

from textual.app import App
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Footer, Static
from textual.containers import Container, Vertical
from textual import events
from rich.text import Text

from graph_tui.config import settings
from graph_tui.api.client import client
from graph_tui.models import Graph
from graph_tui.screens.main_screen import MainScreen


class GraphTUIApp(App):
    """Graph TUI Application."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    """
    
    TITLE = "Graph TUI - DAG Graph Editor"
    SUB_TITLE = "Terminal-based graph editing and execution"
    
    def __init__(self):
        """Initialize app."""
        super().__init__()
        self.current_graph = None
    
    async def on_mount(self) -> None:
        """Handle app mount."""
        # Connect to API
        await client.connect()
        
        # Show graph selection or load default
        await self._load_graph_selection()
    
    async def _load_graph_selection(self) -> None:
        """Load graph selection screen."""
        try:
            graphs = await client.list_graphs()
            
            if not graphs:
                # Create a demo graph
                self.notify("No graphs found. Creating demo graph...")
                graph = await client.create_graph(
                    name="Demo Graph",
                    description="A demo graph for testing"
                )
                self.current_graph = graph
            else:
                # Load first graph for now
                # TODO: Implement graph selection screen
                graph = await client.get_graph(graphs[0].id)
                self.current_graph = graph
            
            # Push main screen
            if self.current_graph:
                await self.push_screen(MainScreen(self.current_graph))
        except Exception as e:
            self.notify(f"Error loading graphs: {e}", severity="error")
    
    async def on_unmount(self) -> None:
        """Handle app unmount."""
        await client.disconnect()

