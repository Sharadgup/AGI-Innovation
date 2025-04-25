import logging
import traceback
import fitz  # PyMuPDF library

def extract_text_from_pdf(filepath):
    """
    Extracts all text from a PDF file using PyMuPDF.
    Returns tuple (full_text, num_pages) or (None, 0) on error.
    """
    full_text = None
    num_pages = 0
    doc = None  # Initialize doc to None
    try:
        doc = fitz.open(filepath)
        num_pages = len(doc)
        extracted_parts = []
        for page_num in range(num_pages):
            page = doc.load_page(page_num)
            extracted_parts.append(page.get_text("text")) # Use "text" for better text extraction
        full_text = "\n\n".join(extracted_parts) # Join pages with separator
        logging.info(f"Successfully extracted text from '{filepath}' (Pages: {num_pages}, Text Length: {len(full_text)})")
    except FileNotFoundError:
        logging.error(f"Error opening PDF: File not found at {filepath}")
    except fitz.fitz.FileDataError as e: # Catch specific PyMuPDF errors
         logging.error(f"Error opening PDF {filepath}: Invalid PDF data or format. {e}")
         logging.error(traceback.format_exc())
    except Exception as e:
        logging.error(f"Error processing PDF {filepath}: {e}")
        logging.error(traceback.format_exc())
        # full_text remains None, num_pages might be 0 or partially set
    finally:
        if doc:
            try:
                doc.close()
            except Exception as close_err:
                 logging.error(f"Error closing PDF document {filepath}: {close_err}")
    return full_text, num_pages