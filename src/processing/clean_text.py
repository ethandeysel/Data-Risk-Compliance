import re


def clean_page(text: str) -> str:
    """
    Basic cleaning of extracted PDF text.
    """

    # Remove carriage returns
    text = text.replace("\r", "")

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove multiple spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Remove page numbers that appear alone
    text = re.sub(r"\n\s*\d+\s*\n", "\n", text)

    return text.strip()