import fitz

def needs_ocr(pdf_path):

    doc = fitz.open(pdf_path)

    characters = 0

    for page in doc:

        text = page.get_text()

        characters += len(text.strip())

    doc.close()

    return characters < 500