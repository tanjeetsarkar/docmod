"""Configuration management for Graph TUI."""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    api_url: str = "http://localhost:8000"
    graphql_endpoint: str = "/graphql"
    graphql_ws_endpoint: str = "/graphql/ws"
    
    # API Timeouts
    timeout: int = 30
    
    # UI Configuration
    refresh_rate: int = 2  # seconds for polling execution status
    max_nodes_display: int = 1000  # limit for performance
    
    # Graph Layout
    default_node_width: int = 20
    default_node_height: int = 3
    node_spacing_x: int = 25
    node_spacing_y: int = 5
    
    # Keyboard shortcuts
    key_new_node: str = "n"
    key_edit_node: str = "e"
    key_delete_node: str = "d"
    key_connect_nodes: str = "c"
    key_execute_graph: str = "x"
    key_save: str = "s"
    key_help: str = "?"
    key_quit: str = "q"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GRAPH_TUI_",
        case_sensitive=False,
    )
    
    @property
    def graphql_url(self) -> str:
        """Get full GraphQL URL."""
        return f"{self.api_url}{self.graphql_endpoint}"
    
    @property
    def graphql_ws_url(self) -> str:
        """Get full GraphQL WebSocket URL."""
        base = self.api_url.replace("http://", "ws://").replace("https://", "wss://")
        return f"{base}{self.graphql_ws_endpoint}"


# Global settings instance
settings = Settings()