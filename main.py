from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
import fitz  # PyMuPDF
import svgwrite
import os
import io
import base64
from PIL import Image

from database import SessionLocal, init_db
from models import PDFData
from crud import create_pdf_data, get_pdf_data

app = FastAPI()

init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""
텍스트는 초록 박스
이미지는 빨간박스
"""
def save_to_svg(page_data, svg_name):
    dwg = svgwrite.Drawing(svg_name, profile='tiny')
    for word in page_data['words']:
        x0, y0, x1, y1, text = word[:5]         # 필요하지 않은 값을 무시
        font_size = y1 - y0                     # 글꼴 크기 설정(get_text(words) 사용 시 사용)
        # font_size = 12 * ((y1 - y0)/100 + 1)  # 글꼴 크기 설정(get_text(blocks) 사용 시 사용(words 옵션 사용하면 글자 크기가 너무 커짐))
        text_length = (x1 - x0) * 1.03          # 박스의 x축 길이
        adjusted_height = (y1 - y0) * 1.3       # 박스의 y축 길이를
        # 텍스트 추가
        dwg.add(dwg.text(text, insert=(x0, y1), fill='black', font_size=font_size))
        # 텍스트 주위에 박스 추가
        dwg.add(dwg.rect(insert=(x0, y0), size=(text_length, adjusted_height), fill='none', stroke='green'))

    # 이미지 처리
    for image_info in page_data['images']:
        image = image_info['image']
        coords = image_info['coords']
        if coords:
            x0, y0, x1, y1 = coords
            # 이미지를 SVG 포맷으로 변환하여 추가
            img_buff = io.BytesIO()
            image.save(img_buff, format='PNG')
            img_data = img_buff.getvalue()
            dwg.add(dwg.image(href="data:image/png;base64," + base64.b64encode(img_data).decode(), insert=(x0, y0), size=(x1 - x0, y1 - y0)))
            # 이미지 주위에 박스 추가
            dwg.add(dwg.rect(insert=(x0, y0), size=(x1 - x0, y1 - y0), fill='none', stroke='red'))
    dwg.save()


# extract_pdf의 텍스트 추출 메서드 설명
"""
page.get_text() [default: text]: 한 음절씩 추출
page.get_text("words"): 한 단어씩 추출(공백을 기준으로 함.)
page.get_text("blocks"): 한 단락씩 추출
PyMuPDF의 추출 순서: 1. 구조화되지 않은 텍스트(상단부터) / 2. 구조화된 텍스트(상단부터) / 3. 꼬리말
get_text(option, delimiters=None) // "delimiters=" 로 구분자 추가 가능.(ex. "example@alogo.grap"는 이메일 전체가 추출되지만 구분자를 @로 한다면 "example", "alogo", "grap" 으로 추출됨.)
PDF의 내용을 다양하게 수정할 수 있음. [참고페이지](https://pymupdf.readthedocs.io/en/latest/page.html)의 Modifying Pages 참고
"""


@app.post("/pdf-analyzer/")
async def pdf_analyzer(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDFs are accepted.")
    
    upload_folder_path = 'uploaded_files'
    analyzed_folder_path = 'analyzed_files'
    os.makedirs(upload_folder_path, exist_ok=True)
    os.makedirs(analyzed_folder_path, exist_ok=True)

    file_path = os.path.join(upload_folder_path, file.filename)

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    doc = fitz.open(file_path)
    svg_files = []
    all_text_content = ''
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        words = page.get_text("words")

        text_content = ' '.join([w[4] for w in words])
        all_text_content += text_content + '\n'

        images = []
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(io.BytesIO(image_bytes))
            img_rects = page.get_image_rects(xref)
            if img_rects:
                coords = (img_rects[0].x0, img_rects[0].y0, img_rects[0].x1, img_rects[0].y1)
            else:
                coords = None
            image_data = base64.b64encode(image_bytes).decode()
            images.append({'image': image, 'coords': coords})
            create_pdf_data(db, file.filename, page_num + 1, text_content, image_data)

        page_data = {'words': words, 'images': images}
        svg_filename = f'page_{page_num + 1}_combined.svg'
        svg_path = os.path.join(analyzed_folder_path, svg_filename)
        save_to_svg(page_data, svg_path)
        svg_files.append(svg_path)


    return {
        "status": {
            "code": 200,
            "message": "OK"
        },
        "result": {
            "files": svg_files,
            "text": all_text_content.strip()
        }
    }

@app.get("/get-svg/{file_name}")
async def get_svg(file_name: str):
    folder_path = 'uploaded_files'
    file_path = os.path.join(folder_path, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, media_type='image/svg+xml', filename=file_name)

@app.get("/data/")
def read_data(db: Session = Depends(get_db)):
    data = get_pdf_data(db)
    return data
