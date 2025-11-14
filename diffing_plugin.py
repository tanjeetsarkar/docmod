"""
FastAPI Plugin System Implementation
"""
import hashlib
import difflib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Protocol
from abc import ABC, abstractmethod
import asyncio
import importlib
import inspect
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
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


class PluginManager:
    """Manages plugin lifecycle and hooks"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.plugins: Dict[str, Plugin] = {}
        self._hooks: Dict[str, List[Plugin]] = {
            'on_node_created': [],
            'on_node_updated': [],
            'on_node_deleted': [],
            'on_dag_executed': []
        }
    
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
        
        # Register hooks
        for hook_name in self._hooks.keys():
            if hasattr(plugin, hook_name):
                self._hooks[hook_name].append(plugin)
        
        print(f"✓ Plugin '{plugin.name}' v{plugin.version} registered at {plugin_prefix}")
    
    async def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister a plugin"""
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin '{plugin_name}' is not registered")
        
        plugin = self.plugins[plugin_name]
        
        # Shutdown plugin
        await plugin.shutdown()
        
        # Remove from hooks
        for hook_list in self._hooks.values():
            if plugin in hook_list:
                hook_list.remove(plugin)
        
        # Remove plugin
        del self.plugins[plugin_name]
        
        print(f"✓ Plugin '{plugin_name}' unregistered")
    
    async def trigger_hook(self, hook_name: str, **kwargs) -> None:
        """Trigger a hook for all registered plugins"""
        if hook_name not in self._hooks:
            raise ValueError(f"Unknown hook: {hook_name}")
        
        for plugin in self._hooks[hook_name]:
            try:
                hook_method = getattr(plugin, hook_name)
                await hook_method(**kwargs)
            except Exception as e:
                print(f"Error in plugin '{plugin.name}' hook '{hook_name}': {e}")
    
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
# CODE VERSIONING PLUGIN
# ============================================================================

# Database Models for Code Versioning Plugin
class CodeVersionNode(Base):
    __tablename__ = "plugin_code_version_nodes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id = Column(String, nullable=False, unique=True, index=True)  # Reference to main node
    file_path = Column(String, nullable=False)
    current_hash = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    versions = relationship("CodeVersion", back_populates="tracking_node")


class CodeVersion(Base):
    __tablename__ = "plugin_code_versions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tracking_node_id = Column(String, ForeignKey("plugin_code_version_nodes.id"))
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
        
        # Setup routes
        self._setup_routes()
        
        # Start background task if enabled
        if self.config.get('auto_check_enabled', True):
            interval = self.config.get('check_interval', 300)
            asyncio.create_task(self._periodic_check(interval))
        
        print(f"Code Versioning Plugin initialized with base_path: {base_path}")
    
    async def shutdown(self) -> None:
        """Cleanup on shutdown"""
        print("Code Versioning Plugin shutting down")
    
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
    
    async def on_node_created(self, node_id: str, file_path: str, **kwargs) -> None:
        """Hook: Track initial version when node is created"""
        async with AsyncSession(engine) as db:
            await self._track_initial_version(node_id, file_path, db)
            await db.commit()
    
    async def on_node_updated(self, node_id: str, **kwargs) -> None:
        """Hook: Check for code changes when node is updated"""
        async with AsyncSession(engine) as db:
            await self._check_and_track(node_id, db)
            await db.commit()
    
    async def on_dag_executed(self, dag_id: str, node_ids: List[str], **kwargs) -> None:
        """Hook: Check all nodes in executed DAG for changes"""
        async with AsyncSession(engine) as db:
            for node_id in node_ids:
                try:
                    await self._check_and_track(node_id, db)
                except Exception as e:
                    print(f"Error checking node {node_id}: {e}")
            await db.commit()
    
    async def _track_initial_version(
        self, 
        node_id: str, 
        file_path: str, 
        db: AsyncSession
    ) -> None:
        """Track initial version of a node"""
        if not self.vc_service.file_exists(file_path):
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
        db.add(version)
    
    async def _check_and_track(
        self, 
        node_id: str, 
        db: AsyncSession
    ) -> Optional[CodeVersion]:
        """Check if node changed and track new version"""
        from sqlalchemy import select
        
        # Get tracking node
        stmt = select(CodeVersionNode).where(CodeVersionNode.node_id == node_id)
        result = await db.execute(stmt)
        tracking_node = result.scalar_one_or_none()
        
        if not tracking_node:
            return None
        
        if not self.vc_service.file_exists(tracking_node.file_path):
            return None
        
        # Check if changed
        current_content = self.vc_service.get_file_content(tracking_node.file_path)
        current_hash = self.vc_service.compute_file_hash(current_content)
        
        if tracking_node.current_hash == current_hash:
            return None
        
        # Get previous version
        prev_version = await self._get_latest_version(tracking_node.id, db)
        prev_content = prev_version.content if prev_version else ""
        
        # Generate diff and create new version
        diff = self.vc_service.generate_unified_diff(prev_content, current_content)
        version = CodeVersion(
            tracking_node_id=tracking_node.id,
            content_hash=current_hash,
            diff=diff,
            content=current_content
        )
        db.add(version)
        
        # Update tracking node
        tracking_node.current_hash = current_hash
        tracking_node.last_updated = datetime.utcnow()
        
        return version
    
    async def _get_latest_version(
        self, 
        tracking_node_id: str, 
        db: AsyncSession
    ) -> Optional[CodeVersion]:
        """Get latest version for a tracking node"""
        from sqlalchemy import select
        stmt = select(CodeVersion).where(
            CodeVersion.tracking_node_id == tracking_node_id
        ).order_by(CodeVersion.created_at.desc()).limit(1)
        
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _get_node_history(
        self, 
        node_id: str, 
        db: AsyncSession
    ) -> List[CodeVersion]:
        """Get all versions for a node"""
        from sqlalchemy import select
        
        stmt = select(CodeVersionNode).where(CodeVersionNode.node_id == node_id)
        result = await db.execute(stmt)
        tracking_node = result.scalar_one_or_none()
        
        if not tracking_node:
            return []
        
        stmt = select(CodeVersion).where(
            CodeVersion.tracking_node_id == tracking_node.id
        ).order_by(CodeVersion.created_at.desc())
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def _get_version_by_id(
        self, 
        version_id: str, 
        db: AsyncSession
    ) -> Optional[CodeVersion]:
        """Get version by ID"""
        return await db.get(CodeVersion, version_id)
    
    async def _periodic_check(self, interval: int):
        """Background task to periodically check all nodes"""
        while True:
            try:
                async with AsyncSession(engine) as db:
                    from sqlalchemy import select
                    stmt = select(CodeVersionNode)
                    result = await db.execute(stmt)
                    tracking_nodes = result.scalars().all()
                    
                    for tracking_node in tracking_nodes:
                        try:
                            await self._check_and_track(tracking_node.node_id, db)
                        except Exception as e:
                            print(f"Error checking node {tracking_node.node_id}: {e}")
                    
                    await db.commit()
            except Exception as e:
                print(f"Error in periodic check: {e}")
            
            await asyncio.sleep(interval)


# ============================================================================
# MAIN APPLICATION WITH PLUGIN SYSTEM
# ============================================================================

app = FastAPI(title="DAG Execution System with Plugins")

# Initialize plugin manager
plugin_manager = PluginManager(app)

@app.on_event("startup")
async def startup():
    """Register plugins on startup"""
    # Register Code Versioning Plugin
    code_versioning_config = {
        'base_path': '/app/dag_files',
        'auto_check_enabled': True,
        'check_interval': 300  # 5 minutes
    }
    code_versioning_plugin = CodeVersioningPlugin(app, code_versioning_config)
    await plugin_manager.register_plugin(
        code_versioning_plugin,
        prefix="/api/v1/code-versioning"
    )

@app.on_event("shutdown")
async def shutdown():
    """Unregister all plugins on shutdown"""
    for plugin_name in list(plugin_manager.plugins.keys()):
        await plugin_manager.unregister_plugin(plugin_name)

# Plugin management endpoints
@app.get("/plugins")
async def list_plugins():
    """List all registered plugins"""
    return plugin_manager.list_plugins()

@app.get("/plugins/{plugin_name}")
async def get_plugin_info(plugin_name: str):
    """Get information about a specific plugin"""
    plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {
        "name": plugin.name,
        "version": plugin.version,
        "config": plugin.config
    }

# Example: Your existing DAG endpoints with plugin hooks
@app.post("/nodes")
async def create_node(name: str, file_path: str):
    """Create a node and trigger plugin hooks"""
    # Your existing node creation logic
    node_id = str(uuid.uuid4())
    
    # ... save node to database ...
    
    # Trigger plugin hooks
    await plugin_manager.trigger_hook(
        'on_node_created',
        node_id=node_id,
        file_path=file_path,
        name=name
    )
    
    return {"id": node_id, "name": name, "file_path": file_path}

@app.put("/nodes/{node_id}")
async def