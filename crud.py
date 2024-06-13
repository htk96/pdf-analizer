from sqlalchemy.orm import Session
from models import PDFData

def create_pdf_data(db: Session, file_name: str, page_number: int, text: str, image_data: str):
    db_pdf_data = PDFData(file_name=file_name, page_number=page_number, text=text, image_data=image_data)
    db.add(db_pdf_data)
    db.commit()
    db.refresh(db_pdf_data)
    return db_pdf_data

def get_pdf_data(db: Session):
    return db.query(PDFData).all()
