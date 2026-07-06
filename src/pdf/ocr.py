import fitz
import pytesseract

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Users\ethan\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
)

from PIL import Image


def ocr_pdf(pdf_path):

    doc = fitz.open(pdf_path)

    pages = []

    for page_number, page in enumerate(doc):

        pix = page.get_pixmap(dpi=300)

        img = Image.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples
        )

        text = pytesseract.image_to_string(img)

        pages.append({
            "page": page_number + 1,
            "text": text
        })

    doc.close()

    return pages