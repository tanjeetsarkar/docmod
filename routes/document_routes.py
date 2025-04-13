# routes/document_routes.py
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from models.document import Document, DocumentSection
from services.docx_services import generate_docx_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

class SectionBase(BaseModel):
    type: str
    id: str
    
class ParagraphSection(SectionBase):
    content: str
    
class ArtifactSection(SectionBase):
    artifactId: str
    title: str
    
class TOCSection(SectionBase):
    pass
    
class DocumentCreate(BaseModel):
    title: str
    sections: List[Dict[str, Any]]
    hasTableOfContents: bool = False

class DocumentResponse(BaseModel):
    id: str
    title: str
    sections: List[Dict[str, Any]]
    hasTableOfContents: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

@router.post("/", response_model=DocumentResponse)
async def create_document(
    document_data: DocumentCreate,
    db: Session = Depends(get_db)
):
    # Create the document in database
    document_id = str(uuid.uuid4())
    new_document = Document(
        id=document_id,
        title=document_data.title,
        has_table_of_contents=document_data.hasTableOfContents
    )
    
    db.add(new_document)
    
    # Process and add sections
    for idx, section_data in enumerate(document_data.sections):
        section = DocumentSection(
            id=section_data["id"],
            document_id=document_id,
            type=section_data["type"],
            position=idx,
            content=section_data.get("content"),
            artifact_id=section_data.get("artifactId")
        )
        db.add(section)
    
    db.commit()
    db.refresh(new_document)
    
    # Format response
    return format_document_response(new_document, db)

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return format_document_response(document, db)

@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    document_data: DocumentCreate,
    db: Session = Depends(get_db)
):
    # Check if document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Update document
    document.title = document_data.title
    document.has_table_of_contents = document_data.hasTableOfContents
    document.updated_at = datetime.now(timezone.utc)
    
    # Delete existing sections
    db.query(DocumentSection).filter(DocumentSection.document_id == document_id).delete()
    
    # Add new sections
    for idx, section_data in enumerate(document_data.sections):
        section = DocumentSection(
            id=section_data["id"],
            document_id=document_id,
            type=section_data["type"],
            position=idx,
            content=section_data.get("content"),
            artifact_id=section_data.get("artifactId")
        )
        db.add(section)
    
    db.commit()
    db.refresh(document)
    
    return format_document_response(document, db)

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    # Check if document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete document sections first (cascade delete should handle this, but being explicit)
    db.query(DocumentSection).filter(DocumentSection.document_id == document_id).delete()
    
    # Delete document
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted successfully"}

@router.get("/")
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    documents = db.query(Document).order_by(Document.updated_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": doc.id,
            "title": doc.title,
            "hasTableOfContents": doc.has_table_of_contents,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at
        }
        for doc in documents
    ]

@router.get("/{document_id}/export")
async def export_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    # Check if document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Gather all data needed for document generation
    formatted_doc = format_document_response(document, db)
    
    # Generate the DOCX file
    file_path = await generate_docx_document(formatted_doc, db)
    
    # Return the file
    return FileResponse(
        path=file_path,
        filename=f"{document.title.replace(' ', '_')}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

def format_document_response(document: Document, db: Session) -> dict:
    """Format a document entity into the response format needed by the frontend."""
    # Query all sections for this document ordered by position
    print("CHECK -----", type(document), document)
    sections = (
        db.query(DocumentSection)
        .filter(DocumentSection.document_id == document.id)
        .order_by(DocumentSection.position)
        .all()
    )
    
    formatted_sections = []
    for section in sections:
        section_data = {
            "id": section.id,
            "type": section.type
        }
        
        if section.type == "paragraph":
            section_data["content"] = section.content
        elif section.type == "tableOfContents":
            pass  # No additional data needed
        else:
            # For table, image, attachment sections
            artifact = section.artifact
            if artifact:
                section_data["artifactId"] = artifact.id
                section_data["title"] = artifact.title
        
        formatted_sections.append(section_data)
    
    return {
        "id": document.id,
        "title": document.title,
        "sections": formatted_sections,
        "hasTableOfContents": document.has_table_of_contents,
        "created_at": document.created_at,
        "updated_at": document.updated_at
    }