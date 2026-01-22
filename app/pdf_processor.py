import PyPDF2
import pdfplumber
from typing import Dict, List, Tuple, Any
import hashlib
import uuid
from datetime import datetime

def generate_document_id(filename: str, content: bytes) -> str:
    """Generate a unique document ID"""
    content_hash = hashlib.sha256(content).hexdigest()[:16]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{timestamp}_{content_hash}"

def extract_text_from_pdf(pdf_content: bytes) -> Tuple[str, int, Dict[str, Any]]:
    """Extract text and metadata from PDF"""
    import io
    
    text_parts = []
    page_count = 0
    metadata = {}
    
    # Try pdfplumber first (better text extraction)
    MAX_TEXT_PER_PAGE = 50000  # Limit text per page to prevent memory issues
    MAX_TOTAL_TEXT = 500000  # Max 500KB total text
    
    try:
        pdf_file = io.BytesIO(pdf_content)
        with pdfplumber.open(pdf_file) as pdf:
            page_count = len(pdf.pages)
            total_text_length = 0
            
            for i, page in enumerate(pdf.pages):
                if total_text_length >= MAX_TOTAL_TEXT:
                    break
                    
                page_text = page.extract_text() or ""
                # Limit text per page
                if len(page_text) > MAX_TEXT_PER_PAGE:
                    page_text = page_text[:MAX_TEXT_PER_PAGE] + "\n[... text truncated ...]"
                
                page_marker = f"--- Page {i+1} ---\n"
                page_content = page_marker + page_text + "\n"
                
                # Check if adding this page would exceed limit
                if total_text_length + len(page_content) > MAX_TOTAL_TEXT:
                    remaining = MAX_TOTAL_TEXT - total_text_length
                    if remaining > len(page_marker):
                        text_parts.append(page_marker + page_text[:remaining - len(page_marker)] + "\n[... document truncated ...]")
                    break
                
                text_parts.append(page_content)
                total_text_length += len(page_content)
            
            # Try to get metadata
            if pdf.metadata:
                metadata = {
                    "title": pdf.metadata.get("Title", ""),
                    "author": pdf.metadata.get("Author", ""),
                    "subject": pdf.metadata.get("Subject", ""),
                    "creator": pdf.metadata.get("Creator", ""),
                }
    except Exception as e:
        # Fallback to PyPDF2
        try:
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            page_count = len(pdf_reader.pages)
            total_text_length = 0
            
            for i, page in enumerate(pdf_reader.pages):
                if total_text_length >= MAX_TOTAL_TEXT:
                    break
                    
                page_text = page.extract_text() or ""
                # Limit text per page
                if len(page_text) > MAX_TEXT_PER_PAGE:
                    page_text = page_text[:MAX_TEXT_PER_PAGE] + "\n[... text truncated ...]"
                
                page_marker = f"--- Page {i+1} ---\n"
                page_content = page_marker + page_text + "\n"
                
                # Check if adding this page would exceed limit
                if total_text_length + len(page_content) > MAX_TOTAL_TEXT:
                    remaining = MAX_TOTAL_TEXT - total_text_length
                    if remaining > len(page_marker):
                        text_parts.append(page_marker + page_text[:remaining - len(page_marker)] + "\n[... document truncated ...]")
                    break
                
                text_parts.append(page_content)
                total_text_length += len(page_content)
            
            if pdf_reader.metadata:
                metadata = {
                    "title": pdf_reader.metadata.get("/Title", ""),
                    "author": pdf_reader.metadata.get("/Author", ""),
                    "subject": pdf_reader.metadata.get("/Subject", ""),
                }
        except Exception as e2:
            raise Exception(f"Failed to extract text from PDF: {str(e2)}")
    
    full_text = "\n".join(text_parts)
    return full_text, page_count, metadata

def find_text_positions(text: str, search_term: str) -> List[Tuple[int, int]]:
    """Find all positions of a search term in text"""
    positions = []
    start = 0
    search_lower = search_term.lower()
    text_lower = text.lower()
    
    while True:
        pos = text_lower.find(search_lower, start)
        if pos == -1:
            break
        positions.append((pos, pos + len(search_term)))
        start = pos + 1
    
    return positions

def get_page_from_position(text: str, char_pos: int) -> int:
    """Get page number from character position"""
    # Count page markers before this position
    page_marker = "--- Page "
    pos = 0
    page_num = 1
    
    while pos < char_pos and pos < len(text):
        next_marker = text.find(page_marker, pos)
        if next_marker == -1 or next_marker > char_pos:
            break
        page_num = int(text[next_marker + len(page_marker):text.find(" ---", next_marker)])
        pos = next_marker + 1
    
    return page_num


