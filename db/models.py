from sqlalchemy import Column, String, Integer, Date
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector
from config import settings

Base = declarative_base()

class DocumentChunk(Base):
    __tablename__ = "chunks"

    chunk_id = Column(String, primary_key=True, index=True)
    document_id = Column(String, index=True)
    title = Column(String)
    category = Column(String, index=True)
    target_audience = Column(String, index=True)
    date_issued = Column(Date)

    page_number = Column(Integer)
    chunk_index = Column(Integer)
    
    content = Column(String)
    embedding = Column(Vector(settings.model_dim))