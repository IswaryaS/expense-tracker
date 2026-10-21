import pymupdf

from typing import List

# Tuned heuristics for high-signal financial tables
TRANSACTION_KEYWORDS = ["ledger", "date", "description", "withdrawal", "deposit", "balance"]
LEGAL_EXCLUSIONS = ["terms and conditions", "error resolution", "disclosure statement", "fee schedule"]

class NoTransactionsFoundError(ValueError):
    """Custom exception raised when a PDF lacks matching transaction layout structures."""
    pass

def extract_transaction_pages(pdf_bytes: bytes) -> str:
    """
    Opens a raw PDF file from memory, extracts text using layout block sorting 
    to preserve tabular rows, and filters out legal boilerplate pages.
    """
    # Load the document dynamically from memory
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    compiled_text: List[str] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # 1. Row-Preserving Extraction: Sort text blocks top-to-bottom, left-to-right
        # This prevents multi-column layouts from overlapping columns during extraction
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (b[1], b[0])) # Sort by Y coordinate first, then X coordinate
        
        # Assemble string representation for page classification
        page_text = "\n".join([b[4] for b in blocks if b[4].strip()])
        page_text_lower = page_text.lower()

        # 2. Strict Filter Execution
        # If it looks like a boilerplate legal index page, bypass entirely
        if any(exclusion in page_text_lower for exclusion in LEGAL_EXCLUSIONS):
            continue

        # Check if the text matches target ledger indicators
        if any(keyword in page_text_lower for keyword in TRANSACTION_KEYWORDS):
            compiled_text.append(f"### START OF STATEMENT PAGE {page_num + 1} ###")
            compiled_text.append(page_text.strip())
            compiled_text.append(f"### END OF STATEMENT PAGE {page_num + 1} ###\n")

    doc.close()

    if not compiled_text:
        raise NoTransactionsFoundError(
            "No matching transaction ledger patterns were discovered in this document."
        )

    return "\n".join(compiled_text)
