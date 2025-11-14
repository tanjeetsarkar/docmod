"""
Event-Driven FastAPI Plugin System Implementation
Uses SQLAlchemy events to listen to database changes
"""
import hashlib
import difflib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from abc import ABC, abstractmethod
import asyncio
import inspect
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, Session
from sqlalchemy.engine import Engine
from fastapi import FastAPI, Depends, HTTPException, APIRouter
import uuid


# ============================================================================
# PLUGIN SYSTEM CORE
# ============================================================================

class Plugin(ABC):
    """Base class for all plugins"""
    
    def __init__(self, app: FastAPI, config: Dict[str, Any]):
        self.app = app
        self.config = config
        self.router = APIRouter()
        self._event_listeners = []
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version"""
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize plugin (setup DB, services, etc.)"""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup on shutdown"""
        pass
    
    def get_router(self) -> APIRouter:
        """Return the plugin's router"""
        return self.router
    
    # Event handlers that plugins can override
    async def on_node_created(self, node_id: str, **kwargs) -> None:
        """Hook called when a node is created"""
        pass
    
    async def on_node_updated(self, node_id: str, **kwargs) -> None:
        """Hook called when a node is updated"""
        pass
    
    async def on_node_deleted(self, node_id: str, **kwargs) -> None:
        """Hook called when a node is deleted"""
        pass
    
    async def on_dag_executed(self, dag_id: str, **kwargs) -> None:
        """Hook called when a DAG is executed"""
        pass
    
    def register_model_listener(
        self, 
        model_class, 
        event_type: str, 
        callback: Callable
    ) -> None:
        """Register a SQLAlchemy model event listener"""
        listener = event.listen(model_class, event_type, callback)
        self._event_listeners.append((model_class, event_type, callback))
    
    def unregister_all_listeners(self) -> None:
        """Unregister all SQLAlchemy event listeners"""
        for model_class, event_type, callback in self._event_listeners:
            event.remove(model_class, event_type, callback)
        self._event_listeners.clear()


class PluginManager:
    """Manages plugin lifecycle and hooks"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.plugins: Dict[str, Plugin] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._event_processor_task = None
    
    async def start_event_processor(self):
        """Start background task to process events from queue"""
        self._event_processor_task = asyncio.create_task(self._process_events())
    
    async def stop_event_processor(self):
        """Stop the event processor"""
        if self._event_processor_task:
            self._event_processor_task.cancel()
            try:
                await self._event_processor_task
            except asyncio.CancelledError:
                pass
    
    async def _process_events(self):
        """Process events from the queue"""
        while True:
            try:
                event_data = await self._event_queue.get()
                hook_name = event_data.pop('hook_name')
                
                # Trigger hook for all registered plugins
                for plugin in self.plugins.values():
                    try:
                        if hasattr(plugin, hook_name):
                            hook_method = getattr(plugin, hook_name)
                            if asyncio.iscoroutinefunction(hook_method):
                                await hook_method(**event_data)
                            else:
                                hook_method(**event_data)
                    except Exception as e:
                        print(f"Error in plugin '{plugin.name}' hook '{hook_name}': {e}")
                
                self._event_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error processing event: {e}")
    
    def queue_event(self, hook_name: str, **kwargs):
        """Queue an event to be processed asynchronously"""
        event_data = {'hook_name': hook_name, **kwargs}
        self._event_queue.put_nowait(event_data)
    
    async def register_plugin(self, plugin: Plugin, prefix: str = None) -> None:
        """Register a plugin with the application"""
        if plugin.name in self.plugins:
            raise ValueError(f"Plugin '{plugin.name}' is already registered")
        
        # Initialize plugin
        await plugin.initialize()
        
        # Store plugin
        self.plugins[plugin.name] = plugin
        
        # Register router with optional prefix
        plugin_prefix = prefix or f"/plugins/{plugin.name}"
        self.app.include_router(
            plugin.get_router(),
            prefix=plugin_prefix,
            tags=[f"Plugin: {plugin.name}"]
        )
        
        print(f"✓ Plugin '{plugin.name}' v{plugin.version} registered at {plugin_prefix}")
    
    async def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister a plugin"""
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin '{plugin_name}' is not registered")
        
        plugin = self.plugins[plugin_name]
        
        # Unregister event listeners
        plugin.unregister_all_listeners()
        
        # Shutdown plugin
        await plugin.shutdown()
        
        # Remove plugin
        del self.plugins[plugin_name]
        
        print(f"✓ Plugin '{plugin_name}' unregistered")
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """Get a specific plugin"""
        return self.plugins.get(plugin_name)
    
    def list_plugins(self) -> List[Dict[str, str]]:
        """List all registered plugins"""
        return [
            {
                "name": plugin.name,
                "version": plugin.version,
                "config": plugin.config
            }
            for plugin in self.plugins.values()
        ]


# ============================================================================
# MAIN APPLICATION MODELS (Your existing Node model)
# ============================================================================

class Node(Base):
    """Main application Node model"""
    __tablename__ = "nodes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# CODE VERSIONING PLUGIN
# ============================================================================

# Database Models for Code Versioning Plugin
class CodeVersionNode(Base):
    __tablename__ = "plugin_code_version_nodes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id = Column(String, nullable=False, unique=True, index=True)
    file_path = Column(String, nullable=False)
    current_hash = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    versions = relationship("CodeVersion", back_populates="tracking_node", cascade="all, delete-orphan")


class CodeVersion(Base):
    __tablename__ = "plugin_code_versions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tracking_node_id = Column(String, ForeignKey("plugin_code_version_nodes.id", ondelete="CASCADE"))
    content_hash = Column(String, nullable=False)
    diff = Column(Text)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tracking_node = relationship("CodeVersionNode", back_populates="versions")


class VersionControlService:
    """Service for version control operations"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
    
    def get_file_content(self, file_path: str) -> str:
        """Read file content"""
        full_path = self.base_path / file_path
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def compute_file_hash(self, content: str) -> str:
        """Compute SHA256 hash of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def generate_unified_diff(
        self, 
        old_content: str, 
        new_content: str,
        old_label: str = "previous",
        new_label: str = "current"
    ) -> str:
        """Generate unified diff between two versions"""
        if old_content == new_content:
            return ""
        
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=old_label,
            tofile=new_label,
            lineterm=''
        )
        
        return ''.join(diff)
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        return (self.base_path / file_path).exists()
    
    def get_diff_stats(self, diff: str) -> dict:
        """Parse diff and return statistics"""
        lines = diff.split('\n')
        additions = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
        
        return {
            'additions': additions,
            'deletions': deletions,
            'total_changes': additions + deletions
        }


class CodeVersioningPlugin(Plugin):
    """Plugin for tracking code changes in DAG nodes"""
    
    @property
    def name(self) -> str:
        return "code_versioning"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def initialize(self) -> None:
        """Initialize the plugin"""
        # Initialize version control service
        base_path = self.config.get('base_path', '/app/dag_files')
        self.vc_service = VersionControlService(base_path)
        
        # Get plugin manager from app state
        self.plugin_manager: PluginManager = self.app.state.plugin_manager
        
        # Register SQLAlchemy event listeners
        self._setup_event_listeners()
        
        # Setup API routes
        self._setup_routes()
        
        print(f"Code Versioning Plugin initialized with base_path: {base_path}")
    
    async def shutdown(self) -> None:
        """Cleanup on shutdown"""
        self.unregister_all_listeners()
        print("Code Versioning Plugin shutting down")
    
    def _setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for Node model"""
        
        # Listen to INSERT events (node creation)
        def after_insert_listener(mapper, connection, target):
            """Called after a node is inserted"""
            self.plugin_manager.queue_event(
                'on_node_created',
                node_id=target.id,
                file_path=target.file_path,
                name=target.name
            )
        
        # Listen to UPDATE events (node updates)
        def after_update_listener(mapper, connection, target):
            """Called after a node is updated"""
            self.plugin_manager.queue_event(
                'on_node_updated',
                node_id=target.id,
                file_path=target.file_path,
                name=target.name
            )
        
        # Listen to DELETE events (node deletion)
        def after_delete_listener(mapper, connection, target):
            """Called after a node is deleted"""
            self.plugin_manager.queue_event(
                'on_node_deleted',
                node_id=target.id
            )
        
        # Register listeners
        self.register_model_listener(Node, 'after_insert', after_insert_listener)
        self.register_model_listener(Node, 'after_update', after_update_listener)
        self.register_model_listener(Node, 'after_delete', after_delete_listener)
    
    def _setup_routes(self):
        """Setup plugin routes"""
        
        @self.router.get("/history/{node_id}")
        async def get_version_history(
            node_id: str,
            db: AsyncSession = Depends(get_db)
        ):
            """Get version history for a node"""
            versions = await self._get_node_history(node_id, db)
            return [
                {
                    "id": v.id,
                    "content_hash": v.content_hash,
                    "created_at": v.created_at,
                    "stats": self.vc_service.get_diff_stats(v.diff) if v.diff else None
                }
                for v in versions
            ]
        
        @self.router.get("/diff/{node_id}/{version_id}")
        async def get_version_diff(
            node_id: str,
            version_id: str,
            db: AsyncSession = Depends(get_db)
        ):
            """Get diff for a specific version"""
            version = await self._get_version_by_id(version_id, db)
            if not version:
                raise HTTPException(status_code=404, detail="Version not found")
            
            return {
                "version_id": version.id,
                "content_hash": version.content_hash,
                "diff": version.diff,
                "stats": self.vc_service.get_diff_stats(version.diff),
                "created_at": version.created_at
            }
        
        @self.router.post("/check/{node_id}")
        async def check_for_updates(
            node_id: str,
            db: AsyncSession = Depends(get_db)
        ):
            """Manually check for updates on a node"""
            version = await self._check_and_track(node_id, db)
            await db.commit()
            
            if version:
                return {
                    "updated": True,
                    "version_id": version.id,
                    "stats": self.vc_service.get_diff_stats(version.diff)
                }
            return {"updated": False, "message": "No changes detected"}
        
        @self.router.get("/compare/{node_id}")
        async def compare_versions(
            node_id: str,
            version_id_1: str,
            version_id_2: str,
            db: AsyncSession = Depends(get_db)
        ):
            """Compare two versions"""
            v1 = await self._get_version_by_id(version_id_1, db)
            v2 = await self._get_version_by_id(version_id_2, db)
            
            if not v1 or not v2:
                raise HTTPException(status_code=404, detail="Version not found")
            
            diff = self.vc_service.generate_unified_diff(v1.content, v2.content)
            return {
                "version_id_1": version_id_1,
                "version_id_2": version_id_2,
                "diff": diff,
                "stats": self.vc_service.get_diff_stats(diff)
            }
        
        @self.router.get("/stats/{node_id}")
        async def get_node_stats(
            node_id: str,
            db: AsyncSession = Depends(get_db)
        ):
            """Get statistics for a node's version history"""
            versions = await self._get_node_history(node_id, db)
            
            total_additions = 0
            total_deletions = 0
            
            for v in versions:
                if v.diff:
                    stats = self.vc_service.get_diff_stats(v.diff)
                    total_additions += stats['additions']
                    total_deletions += stats['deletions']
            
            return {
                "node_id": node_id,
                "total_versions": len(versions),
                "total_additions": total_additions,
                "total_deletions": total_deletions,
                "total_changes": total_additions + total_deletions
            }
    
    async def on_node_created(self, node_id: str, file_path: str, **kwargs) -> None:
        """Hook: Track initial version when node is created"""
        # Create new session for async operation
        async with AsyncSession(engine) as db:
            try:
                await self._track_initial_version(node_id, file_path, db)
                await db.commit()
                print(f"✓ Tracked initial version for node {node_id}")
            except Exception as e:
                await db.rollback()
                print(f"✗ Error tracking initial version for node {node_id}: {e}")
    
    async def on_node_updated(self, node_id: str, file_path: str, **kwargs) -> None:
        """Hook: Check for code changes when node is updated"""
        async with AsyncSession(engine) as db:
            try:
                version = await self._check_and_track(node_id, db)
                await db.commit()
                
                if version:
                    print(f"✓ Tracked new version for node {node_id}")
                else:
                    print(f"ℹ No changes detected for node {node_id}")
            except Exception as e:
                await db.rollback()
                print(f"✗ Error checking node {node_id}: {e}")
    
    async def on_node_deleted(self, node_id: str, **kwargs) -> None:
        """Hook: Clean up tracking data when node is deleted"""
        async with AsyncSession(engine) as db:
            try:
                from sqlalchemy import select, delete
                
                # Find tracking node
                stmt = select(CodeVersionNode).where(CodeVersionNode.node_id == node_id)
                result = await db.execute(stmt)
                tracking_node = result.scalar_one_or_none()
                
                if tracking_node:
                    # Delete tracking node (cascade will handle versions)
                    await db.delete(tracking_node)
                    await db.commit()
                    print(f"✓ Cleaned up version history for deleted node {node_id}")
            except Exception as e:
                await db.rollback()
                print(f"✗ Error cleaning up node {node_id}: {e}")
    
    async def _track_initial_version(
        self, 
        node_id: str, 
        file_path: str, 
        db: AsyncSession
    ) -> None:
        """Track initial version of a node"""
        if not self.vc_service.file_exists(file_path):
            print(f"⚠ File not found: {file_path}")
            return
        
        content = self.vc_service.get_file_content(file_path)
        content_hash = self.vc_service.compute_file_hash(content)
        
        # Create tracking node
        tracking_node = CodeVersionNode(
            node_id=node_id,
            file_path=file_path,
            current_hash=content_hash
        )
        db.add(tracking_node)
        await db.flush()
        
        # Create initial version
        initial_diff = self.vc_service.generate_unified_diff("", content, "empty", "initial")
        version = CodeVersion(
            tracking_node_id=tracking_node.id,
            content_hash=content_hash,
            diff=initial_diff,
            content=content
        )
        db.add(v