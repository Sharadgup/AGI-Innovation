# src/routes/pdf_routes.py

import logging
import os
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, session, request, jsonify, current_app)
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId

# --- Relative Imports ---
# --- DO NOT import specific collections or initialized models here ---

# --- Import Utils ---
from ..utils.auth_utils import is_logged_in
from ..utils.file_utils import allowed_file, get_secure_filename
from ..utils.pdf_utils import extract_text_from_pdf

# Create Blueprint
bp = Blueprint('pdf', __name__)


# --- Routes ---

@bp.route('/analyzer')
def pdf_analyzer_page():
    """Renders the PDF Analyzer page, showing recent uploads."""
    # --- Access extensions INSIDE function ---
    from ..extensions import db, pdf_analysis_collection

    if not is_logged_in():
        flash("Please log in to use the PDF Analyzer.", "warning")
        return redirect(url_for('auth.login'))

    user_pdfs = []
    username = session.get('username', 'Unknown')
    try:
        user_id_obj = ObjectId(session['user_id'])
        # Check DB and collection availability
        if db is not None and pdf_analysis_collection is not None:
            cursor = pdf_analysis_collection.find(
                {"user_id": user_id_obj},
                {"original_filename": 1, "upload_timestamp": 1, "_id": 1, "page_count": 1}
            ).sort("upload_timestamp", -1).limit(10)
            user_pdfs = list(cursor)
            # Convert ID for template
            for pdf in user_pdfs: pdf['_id'] = str(pdf['_id'])
            logging.info(f"Fetched {len(user_pdfs)} recent PDFs for user {username}")
        else:
            logging.warning("pdf_analysis_collection or DB is None, cannot fetch user PDFs.")
            flash("Database service may be unavailable.", "warning") # Inform user subtly

    except InvalidId:
        logging.error(f"Invalid user ID in session for PDF analyzer: {session.get('user_id')}")
        flash("Session error. Please log in again.", "warning")
        return redirect(url_for('auth.login'))
    except Exception as e:
        logging.error(f"Error fetching user PDFs for {username}: {e}", exc_info=True)
        flash("An error occurred while retrieving your recent PDFs.", "danger")

    return render_template('pdf_analyzer.html', now=datetime.utcnow(), user_pdfs=user_pdfs)


@bp.route('/upload', methods=['POST'])
def upload_pdf():
    """Handles PDF file uploads, extracts text, and saves metadata."""
    # --- Access extensions INSIDE function ---
    from ..extensions import db, pdf_analysis_collection

    # Auth & Service Checks
    if not is_logged_in(): return jsonify({"error": "Authentication required."}), 401
    if db is None or pdf_analysis_collection is None:
        logging.error("PDF upload failed: DB service/collection unavailable.")
        return jsonify({"error": "Database service unavailable."}), 503

    # File Checks
    if 'pdfFile' not in request.files: return jsonify({"error": "No file part named 'pdfFile'."}), 400
    file = request.files['pdfFile']
    if file.filename == '': return jsonify({"error": "No file selected."}), 400
    if not allowed_file(file.filename):
         allowed_str = ', '.join(current_app.config.get('ALLOWED_EXTENSIONS', set()))
         return jsonify({"error": f"Invalid file type. Allowed: {allowed_str}"}), 400

    # --- Process File ---
    filepath = None # Define for potential cleanup
    try:
        user_id = ObjectId(session['user_id'])
        username = session.get('username', 'Unknown')
    except (InvalidId, KeyError, Exception) as e:
        logging.error(f"Invalid session during PDF upload: {e}")
        return jsonify({"error": "Invalid session. Please log in again."}), 401

    original_filename = get_secure_filename(file.filename)
    ts = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    stored_filename = f"{user_id}_{ts}_{original_filename}"
    upload_dir = current_app.config['UPLOAD_FOLDER']
    filepath = os.path.join(upload_dir, stored_filename)
    logging.info(f"Attempting to save PDF upload to: {filepath}")

    try:
        # Save file
        file.save(filepath)
        logging.info(f"PDF saved successfully: {filepath}")

        # Extract text
        logging.info(f"Extracting text from PDF: {filepath}")
        extracted_text, page_count = extract_text_from_pdf(filepath) # Use util function

        if extracted_text is None: # Check if extraction failed
            # pdf_utils already logged the specific error
            raise ValueError("Failed to extract text from the uploaded PDF.")

        # Prepare DB document
        now = datetime.utcnow()
        doc = {
            "user_id": user_id, "username": username,
            "original_filename": original_filename, "stored_filename": stored_filename,
            "filepath": filepath, "page_count": page_count, "upload_timestamp": now,
            "extracted_text_preview": extracted_text[:2000], # Store preview
            "full_text_extracted": True, # Mark as extracted
            "analysis_status": "extracted", "last_modified": now
        }

        logging.info(f"Inserting PDF analysis record into DB for {username}")
        # Use locally accessed collection
        analysis_insert_result = pdf_analysis_collection.insert_one(doc)
        analysis_id = analysis_insert_result.inserted_id
        logging.info(f"PDF record created successfully. ID: {analysis_id}")

        # Return success response for frontend
        return jsonify({
            "message": "PDF uploaded and text extracted successfully.",
            "analysis_id": str(analysis_id),
            "filename": original_filename,
            "text_preview": extracted_text[:3000] # Send preview for context
            }), 200

    except ValueError as ve: # Catch specific errors like text extraction failure
         logging.error(f"Value error during PDF upload/processing for {username}: {ve}")
         if filepath and os.path.exists(filepath): # Cleanup
             try: os.remove(filepath); logging.info(f"Cleaned up failed PDF upload: {filepath}")
             except OSError as rm_err: logging.error(f"Failed to cleanup file: {filepath}. Error: {rm_err}")
         return jsonify({"error": str(ve)}), 500 # Return 500 for server-side processing issues

    except Exception as e: # Catch general errors
        logging.error(f"Unexpected error during PDF upload for {username}: {e}", exc_info=True)
        if filepath and os.path.exists(filepath): # Cleanup
            try: os.remove(filepath); logging.info(f"Cleaned up failed PDF upload: {filepath}")
            except OSError as rm_err: logging.error(f"Failed to cleanup file: {filepath}. Error: {rm_err}")
        return jsonify({"error": "An unexpected server error occurred processing the PDF."}), 500