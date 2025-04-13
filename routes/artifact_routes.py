# routes/artifact_routes.py
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import uuid
import os
from datetime import datetime
from sqlalchemy.orm import Session

from db.database import get_db
from models.artifacts import Artifact

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

# Constants for upload file size limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


class ArtifactBase(BaseModel):
    title: str
    type: str  # 'table', 'image', 'attachment'
    module: str  # e.g., 'EDA', 'pre-processing', etc.
    data: Optional[Dict[str, Any]] = None
    file_path: Optional[str] = None


class ArtifactResponse(BaseModel):
    id: str
    title: str
    type: str
    module: str
    created_at: datetime
    data: Optional[Dict[str, Any]] = None
    file_path: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/", response_model=ArtifactResponse)
async def create_artifact(
    artifact_data: ArtifactBase,
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    artifact_id = str(uuid.uuid4())

    # Handle file upload if provided
    file_path = None
    if file:
        # Create directory if it doesn't exist
        upload_dir = os.path.join("uploads", artifact_data.type)
        os.makedirs(upload_dir, exist_ok=True)

        # Save file
        file_path = os.path.join(upload_dir, f"{artifact_id}_{file.filename}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

    new_artifact = Artifact(
        id=artifact_id,
        title=artifact_data.title,
        type=artifact_data.type,
        module=artifact_data.module,
        data=artifact_data.data,
        file_path=file_path or artifact_data.file_path,
    )

    db.add(new_artifact)
    db.commit()
    db.refresh(new_artifact)

    return new_artifact


@router.get("/", response_model=dict)
async def get_artifacts(
    artifact_type: Optional[str] = None,
    module: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Artifact)

    if artifact_type:
        query = query.filter(Artifact.type == artifact_type)

    if module:
        query = query.filter(Artifact.module == module)

    artifacts = query.order_by(Artifact.created_at.desc()).all()
    
    # Group artifacts by type for frontend convenience
    result: Dict[str, List[Dict[str, Any]]] = {"tables": [], "images": [], "attachments": []}

    for artifact in artifacts:
        if artifact.type == "table":
            result["tables"].append(
                {
                    "id": artifact.id,
                    "title": artifact.title,
                    "module": artifact.module,
                    "created_at": artifact.created_at,
                }
            )
        elif artifact.type == "image":
            result["images"].append(
                {
                    "id": artifact.id,
                    "title": artifact.title,
                    "module": artifact.module,
                    "created_at": artifact.created_at,
                }
            )
        elif artifact.type == "attachment":
            result["attachments"].append(
                {
                    "id": artifact.id,
                    "title": artifact.title,
                    "module": artifact.module,
                    "created_at": artifact.created_at,
                }
            )

    return result


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(artifact_id: str, db: Session = Depends(get_db)):
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return artifact


@router.put("/{artifact_id}", response_model=ArtifactResponse)
async def update_artifact(
    artifact_id: str,
    artifact_data: ArtifactBase,
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Update artifact properties
    artifact.title = artifact_data.title
    artifact.module = artifact_data.module

    if artifact_data.data is not None:
        artifact.data = artifact_data.data

    # Handle file upload if provided
    if file:
        # Remove old file if exists
        if artifact.file_path and os.path.exists(artifact.file_path):
            os.remove(artifact.file_path)

        # Create directory if it doesn't exist
        upload_dir = os.path.join("uploads", artifact.type)
        os.makedirs(upload_dir, exist_ok=True)

        # Save new file
        file_path = os.path.join(upload_dir, f"{artifact_id}_{file.filename}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        artifact.file_path = file_path
    elif artifact_data.file_path:
        artifact.file_path = artifact_data.file_path

    db.commit()
    db.refresh(artifact)

    return artifact


@router.delete("/{artifact_id}")
async def delete_artifact(artifact_id: str, db: Session = Depends(get_db)):
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Delete file if exists
    if artifact.file_path and os.path.exists(artifact.file_path):
        os.remove(artifact.file_path)

    db.delete(artifact)
    db.commit()

    return {"message": "Artifact deleted successfully"}
