from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from datetime import timezone

from db.database import Base

class Artifact(Base):
    __tablename__ = "artifacts"
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    type = Column(String, nullable=False)  # table, image, attachment
    module = Column(String, nullable=False)  # which module generated this artifact
    data = Column(JSON, nullable=True)  # For storing structured data (like tables)
    file_path = Column(String, nullable=True)  # For storing file paths to images or attachments
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationship to document sections that use this artifact
    sections = relationship("DocumentSection", back_populates="artifact")