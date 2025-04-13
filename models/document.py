from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from db.database import Base

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    has_table_of_contents = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationship to document sections
    sections = relationship("DocumentSection", back_populates="document", order_by="DocumentSection.position")

class DocumentSection(Base):
    __tablename__ = "document_sections"
    
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)  # paragraph, table, image, attachment, tableOfContents
    position = Column(Integer, nullable=False)  # Order within document
    content = Column(Text, nullable=True)  # For paragraph content
    artifact_id = Column(String, ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    document = relationship("Document", back_populates="sections")
    artifact = relationship("Artifact", back_populates="sections")