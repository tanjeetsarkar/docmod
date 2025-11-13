import hashlib
import difflib
from pathlib import Path
from datetime import datetime
from typing import Optional
import asyncio
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
from fastapi import FastAPI, Depends, HTTPException
import uuid

# Database Models
class Node(Base):
    __tablename__ = "nodes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    current_hash = Column(String)  # SHA256 hash of current content
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    versions = relationship("CodeVersion", back_populates="node")


class CodeVersion(Base):
    __tablename__ = "code_versions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id = Column(String, ForeignKey("nodes.id"))
    content_hash = Column(String, nullable=False)  # SHA256 hash of this version
    diff = Column(Text)  # Unified diff from previous version
    content = Column(Text)  # Full file content at this version
    created_at = Column(DateTime, default=datetime.utcnow)
    
    node = relationship("Node", back_populates="versions")


# Version Control Service (Git-like using difflib)
class VersionControlService:
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
        """
        Generate unified diff between two versions
        Returns empty string if contents are identical
        """
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
    
    def generate_context_diff(
        self, 
        old_content: str, 
        new_content: str
    ) -> str:
        """
        Generate context diff (alternative format)
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.context_diff(
            old_lines,
            new_lines,
            fromfile='previous',
            tofile='current'
        )
        
        return ''.join(diff)
    
    def generate_html_diff(
        self,
        old_content: str,
        new_content: str
    ) -> str:
        """
        Generate HTML diff for nice visualization
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        
        html_diff = difflib.HtmlDiff()
        return html_diff.make_file(
            old_lines,
            new_lines,
            fromdesc='Previous Version',
            todesc='Current Version'
        )
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        return (self.base_path / file_path).exists()
    
    def get_diff_stats(self, diff: str) -> dict:
        """
        Parse diff and return statistics
        """
        lines = diff.split('\n')
        additions = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
        
        return {
            'additions': additions,
            'deletions': deletions,
            'total_changes': additions + deletions
        }


# Node Service
class NodeService:
    def __init__(self, vc_service: VersionControlService, db: AsyncSession):
        self.vc = vc_service
        self.db = db
    
    async def create_node(self, name: str, file_path: str) -> Node:
        """Create a new node and track its initial version"""
        if not self.vc.file_exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read initial content
        content = self.vc.get_file_content(file_path)
        content_hash = self.vc.compute_file_hash(content)
        
        # Create node
        node = Node(
            name=name,
            file_path=file_path,
            current_hash=content_hash
        )
        self.db.add(node)
        await self.db.flush()
        
        # Track initial version
        # For initial version, diff shows entire content as additions
        initial_diff = self.vc.generate_unified_diff("", content, "empty", "initial")
        
        version = CodeVersion(
            node_id=node.id,
            content_hash=content_hash,
            diff=initial_diff,
            content=content
        )
        self.db.add(version)
        
        await self.db.commit()
        return node
    
    async def check_and_update_node(self, node_id: str) -> Optional[CodeVersion]:
        """Check if node file changed and update if necessary"""
        node = await self.db.get(Node, node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        
        if not self.vc.file_exists(node.file_path):
            raise FileNotFoundError(f"Node file not found: {node.file_path}")
        
        # Read current content and compute hash
        current_content = self.vc.get_file_content(node.file_path)
        current_hash = self.vc.compute_file_hash(current_content)
        
        # Check if file content changed
        if node.current_hash == current_hash:
            return None  # No changes
        
        # File changed - track new version
        version = await self._track_version(node, current_content, current_hash)
        await self.db.commit()
        
        return version
    
    async def _track_version(
        self, 
        node: Node, 
        new_content: str, 
        new_hash: str
    ) -> CodeVersion:
        """Track a new version of the node's code"""
        # Get previous version for diff
        prev_version = await self._get_latest_version(node.id)
        prev_content = prev_version.content if prev_version else ""
        
        # Generate diff
        diff = self.vc.generate_unified_diff(
            prev_content,
            new_content,
            f"version-{prev_version.id[:8]}" if prev_version else "empty",
            "current"
        )
        
        # Create version record
        version = CodeVersion(
            node_id=node.id,
            content_hash=new_hash,
            diff=diff,
            content=new_content
        )
        self.db.add(version)
        
        # Update node's current hash
        node.current_hash = new_hash
        node.last_updated = datetime.utcnow()
        
        return version
    
    async def _get_latest_version(self, node_id: str) -> Optional[CodeVersion]:
        """Get the most recent version of a node"""
        from sqlalchemy import select
        stmt = select(CodeVersion).where(
            CodeVersion.node_id == node_id
        ).order_by(CodeVersion.created_at.desc()).limit(1)
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_node_history(self, node_id: str) -> list[CodeVersion]:
        """Get all versions of a node"""
        from sqlalchemy import select
        stmt = select(CodeVersion).where(
            CodeVersion.node_id == node_id
        ).order_by(CodeVersion.created_at.desc())
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def compare_versions(
        self, 
        node_id: str, 
        version_id_1: str, 
        version_id_2: str,
        format: str = "unified"
    ) -> str:
        """Compare two specific versions"""
        v1 = await self.db.get(CodeVersion, version_id_1)
        v2 = await self.db.get(CodeVersion, version_id_2)
        
        if not v1 or not v2:
            raise ValueError("One or both versions not found")
        
        if v1.node_id != node_id or v2.node_id != node_id:
            raise ValueError("Versions do not belong to this node")
        
        if format == "unified":
            return self.vc.generate_unified_diff(v1.content, v2.content)
        elif format == "context":
            return self.vc.generate_context_diff(v1.content, v2.content)
        elif format == "html":
            return self.vc.generate_html_diff(v1.content, v2.content)
        else:
            raise ValueError(f"Unknown diff format: {format}")
    
    async def rollback_to_version(self, node_id: str, version_id: str) -> None:
        """
        Rollback node to a specific version by writing content to file
        and creating a new version entry
        """
        node = await self.db.get(Node, node_id)
        version = await self.db.get(CodeVersion, version_id)
        
        if not node or not version:
            raise ValueError("Node or version not found")
        
        if version.node_id != node_id:
            raise ValueError("Version does not belong to this node")
        
        # Write old content to file
        full_path = self.vc.base_path / node.file_path
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(version.content)
        
        # Create new version entry for the rollback
        await self.check_and_update_node(node_id)


# FastAPI Application
app = FastAPI()

# Initialize Version Control service (configure your base path)
vc_service = VersionControlService(base_path="/path/to/your/dag/files")

@app.post("/nodes")
async def create_node(
    name: str,
    file_path: str,
    db: AsyncSession = Depends(get_db)
):
    """Create a new node and track its initial version"""
    node_service = NodeService(vc_service, db)
    try:
        node = await node_service.create_node(name, file_path)
        return {
            "id": node.id,
            "name": node.name,
            "file_path": node.file_path,
            "current_hash": node.current_hash,
            "message": "Node created and initial version tracked"
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/nodes/{node_id}/check-update")
async def check_node_update(
    node_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Check if node file changed and update version if necessary"""
    node_service = NodeService(vc_service, db)
    try:
        version = await node_service.check_and_update_node(node_id)
        
        if version:
            diff_stats = vc_service.get_diff_stats(version.diff)
            return {
                "updated": True,
                "version_id": version.id,
                "content_hash": version.content_hash,
                "stats": diff_stats,
                "message": "New version tracked"
            }
        else:
            return {
                "updated": False,
                "message": "No changes detected"
            }
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/nodes/{node_id}/history")
async def get_node_history(
    node_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get version history of a node"""
    node_service = NodeService(vc_service, db)
    versions = await node_service.get_node_history(node_id)
    
    return [
        {
            "id": v.id,
            "content_hash": v.content_hash,
            "created_at": v.created_at,
            "stats": vc_service.get_diff_stats(v.diff) if v.diff else None
        }
        for v in versions
    ]


@app.get("/nodes/{node_id}/versions/{version_id}/diff")
async def get_version_diff(
    node_id: str,
    version_id: str,
    format: str = "unified",
    db: AsyncSession = Depends(get_db)
):
    """Get the diff for a specific version"""
    version = await db.get(CodeVersion, version_id)
    if not version or version.node_id != node_id:
        raise HTTPException(status_code=404, detail="Version not found")
    
    diff_content = version.diff
    
    # If HTML format requested, regenerate from content
    if format == "html":
        node_service = NodeService(vc_service, db)
        prev_version = await node_service._get_latest_version(node_id)
        if prev_version and prev_version.id != version_id:
            # Find the version before this one
            from sqlalchemy import select
            stmt = select(CodeVersion).where(
                CodeVersion.node_id == node_id,
                CodeVersion.created_at < version.created_at
            ).order_by(CodeVersion.created_at.desc()).limit(1)
            result = await db.execute(stmt)
            prev = result.scalar_one_or_none()
            
            if prev:
                diff_content = vc_service.generate_html_diff(prev.content, version.content)
    
    return {
        "version_id": version.id,
        "content_hash": version.content_hash,
        "diff": diff_content,
        "stats": vc_service.get_diff_stats(version.diff),
        "created_at": version.created_at
    }


@app.get("/nodes/{node_id}/versions/{version_id}/content")
async def get_version_content(
    node_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get the full content of a specific version"""
    version = await db.get(CodeVersion, version_id)
    if not version or version.node_id != node_id:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return {
        "version_id": version.id,
        "content": version.content,
        "content_hash": version.content_hash,
        "created_at": version.created_at
    }


@app.post("/nodes/{node_id}/compare")
async def compare_versions(
    node_id: str,
    version_id_1: str,
    version_id_2: str,
    format: str = "unified",
    db: AsyncSession = Depends(get_db)
):
    """Compare two specific versions"""
    node_service = NodeService(vc_service, db)
    try:
        diff = await node_service.compare_versions(
            node_id, version_id_1, version_id_2, format
        )
        return {
            "version_id_1": version_id_1,
            "version_id_2": version_id_2,
            "diff": diff,
            "format": format
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/nodes/{node_id}/rollback/{version_id}")
async def rollback_node(
    node_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Rollback node to a specific version"""
    node_service = NodeService(vc_service, db)
    try:
        await node_service.rollback_to_version(node_id, version_id)
        return {
            "message": f"Node rolled back to version {version_id}",
            "node_id": node_id
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Background task to periodically check all nodes
async def periodic_node_check():
    """Background task to check all nodes for changes"""
    while True:
        try:
            async with AsyncSession(engine) as db:
                from sqlalchemy import select
                stmt = select(Node)
                result = await db.execute(stmt)
                nodes = result.scalars().all()
                
                node_service = NodeService(vc_service, db)
                
                for node in nodes:
                    try:
                        version = await node_service.check_and_update_node(node.id)
                        if version:
                            print(f"Node {node.name} updated: new version {version.id}")
                    except Exception as e:
                        print(f"Error checking node {node.id}: {e}")
        except Exception as e:
            print(f"Error in periodic check: {e}")
        
        # Check every 5 minutes
        await asyncio.sleep(300)


@app.on_event("startup")
async def startup_event():
    """Start background task on startup"""
    asyncio.create_task(periodic_node_check())