from sqlalchemy import Column, Integer, String, Text
from database import Base

class PDFData(Base):
    __tablename__ = "pdf_data"
    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, index=True)
    page_number = Column(Integer)
    text = Column(Text)
    image_data = Column(Text)
