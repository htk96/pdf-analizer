from pydantic import BaseModel

class PDFDataBase(BaseModel):
    file_name: str
    page_number: int
    text: str
    image_data: str

    class Config:
        orm_mode = True
