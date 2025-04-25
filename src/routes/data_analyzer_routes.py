# src/routes/data_analyzer_routes.py

from flask import (Blueprint, render_template, request, jsonify,
                   redirect, url_for, flash, session, current_app,
                   send_file, make_response)
import logging
import os
import json
import io
from datetime import datetime # Ensure datetime is imported
from bson import ObjectId, json_util # json_util might not be needed here anymore
from bson.errors import InvalidId
import pandas as pd
import plotly.express as px
import plotly.io as pio

# --- Relative Imports ---
# --- DO NOT import specific collections or initialized models at the top level ---

# --- Import Utils ---
from ..utils.auth_utils import is_logged_in
from ..utils.file_utils import allowed_analysis_file, get_secure_filename
from ..utils.data_analyzer_utils import (get_dataframe, generate_data_profile,
                                           generate_cleaning_recommendations,
                                           generate_gemini_insight_prompt,
                                           PDFReport) # Import the PDFReport class
from ..utils.db_utils import log_db_update_result
from ..utils.api_utils import log_gemini_response_details

# Create Blueprint
bp = Blueprint('data', __name__)


# --- Route Definitions ---

@bp.route('/analyzer')
def data_analyzer_page():
    """Renders the main page for the Data Analyzer tool."""
    if not is_logged_in():
        flash("Please log in to use the Data Analyzer.", "warning")
        return redirect(url_for('auth.login'))
    allowed_ext_str = ",".join([f".{ext}" for ext in current_app.config.get('ALLOWED_ANALYSIS_EXTENSIONS', set())])
    return render_template('data_analyzer.html',
                           now=datetime.utcnow(),
                           allowed_extensions=allowed_ext_str)


@bp.route('/analyzer/upload', methods=['POST'])
def upload_analysis_data():
    """Handles the upload of data files (CSV, XLSX) for analysis."""
    # --- Access extensions INSIDE function ---
    from ..extensions import db, analysis_uploads_collection

    # ... (rest of upload_analysis_data logic as corrected previously) ...
    logging.info("--- Enter /data/analyzer/upload ---")
    if not is_logged_in(): return jsonify({"error": "Authentication required."}), 401
    if db is None or analysis_uploads_collection is None: logging.error("Data upload failed: DB unavailable."); return jsonify({"error": "Database service unavailable."}), 503
    if 'analysisFile' not in request.files: return jsonify({"error": "No file part named 'analysisFile'."}), 400
    file = request.files['analysisFile']
    if file.filename == '': return jsonify({"error": "No file selected."}), 400
    if not allowed_analysis_file(file.filename): return jsonify({"error": f"Invalid file type..."}), 400
    try: user_id = ObjectId(session['user_id']); username = session.get('username', 'Unknown')
    except Exception as e: logging.error(f"Session error: {e}"); return jsonify({"error": "Invalid session."}), 401
    original_filename = get_secure_filename(file.filename); _, f_ext = os.path.splitext(original_filename)
    ts = datetime.utcnow().strftime('%Y%m%d%H%M%S%f'); stored_filename = f"{user_id}_{ts}{f_ext}"
    upload_dir = current_app.config['ANALYSIS_UPLOAD_FOLDER']; filepath = os.path.join(upload_dir, stored_filename)
    try:
        file.save(filepath); df = get_dataframe(filepath)
        if df is None:
            if os.path.exists(filepath): os.remove(filepath)
            return jsonify({"error": "Failed to read or unsupported file format."}), 400
        profile = generate_data_profile(df); now = datetime.utcnow()
        doc = { "user_id": user_id, "username": username, "original_filename": original_filename, "stored_filename": stored_filename, "filepath": filepath, "upload_timestamp": now, "row_count": profile.get('row_count', 0), "col_count": profile.get('col_count', 0), "column_info": profile.get('column_info', []), "memory_usage": profile.get('memory_usage'), "cleaning_steps": [], "analysis_results": {}, "generated_insights": [], "status": "uploaded", "last_modified": now }
        insert_result = analysis_uploads_collection.insert_one(doc); upload_id = insert_result.inserted_id
        logging.info(f"DB insert successful. Upload ID: {upload_id}")
        response_payload = { "message": "File uploaded and profiled successfully.", "upload_id": str(upload_id), "filename": original_filename, "rows": profile.get('row_count', 0), "columns": profile.get('col_count', 0), "column_info": profile.get('column_info', []) }
        return jsonify(response_payload), 200
    except Exception as e:
        logging.error(f"Unhandled exception during analysis file upload: {e}", exc_info=True)
        if 'filepath' in locals() and os.path.exists(filepath):
            try: os.remove(filepath)
            except OSError as rm_err: logging.error(f"Failed cleanup {filepath}: {rm_err}")
        return jsonify({"error": "Server error processing file."}), 500


@bp.route('/cleaner/<upload_id>')
def data_cleaner_page(upload_id):
    """Renders the data cleaning interface for a specific upload."""
    # --- Access extensions INSIDE function ---
    from ..extensions import db, analysis_uploads_collection

    logging.info(f"--- ENTER data_cleaner_page for upload_id: {upload_id} ---")
    if not is_logged_in():
        flash("Please log in.", "warning"); logging.warning("data_cleaner_page: Not logged in."); return redirect(url_for('auth.login'))
    if db is None or analysis_uploads_collection is None:
        flash("Database service unavailable.", "danger"); logging.error("data_cleaner_page: DB unavailable."); return redirect(url_for('data.analysis_history'))

    try:
        oid = ObjectId(upload_id)
        user_id = ObjectId(session['user_id'])
    except InvalidId:
        logging.error(f"Invalid ObjectId format. UploadID='{upload_id}', UserSessionID='{session.get('user_id')}'")
        flash("Invalid analysis record identifier.", "danger")
        return redirect(url_for('data.analysis_history'))
    except Exception as e:
        logging.error(f"Session error validating ID for data cleaner {upload_id}: {e}")
        flash("Session error. Please log in again.", "warning")
        return redirect(url_for('auth.login'))

    try:
        # Find the document, keeping the original BSON document
        upload_doc = analysis_uploads_collection.find_one({"_id": oid, "user_id": user_id})
        if not upload_doc:
            logging.warning(f"Data cleaner: Record {upload_id} not found or access denied for user {user_id}.")
            flash("Analysis record not found or access denied.", "danger")
            return redirect(url_for('data.analysis_history'))

        # Check file path and load dataframe
        filepath = upload_doc.get('filepath')
        if not filepath or not os.path.exists(filepath):
             logging.error(f"Data cleaner: Filepath missing for {upload_id}. Path: {filepath}")
             flash("Data file missing for this analysis.", "danger")
             return redirect(url_for('data.analysis_history'))
        df = get_dataframe(filepath)
        if df is None:
             logging.error(f"Data cleaner: Failed to load dataframe from {filepath}")
             flash("Error loading data file for cleaning.", "danger")
             return redirect(url_for('data.analysis_history'))

        # Get profile info from DB doc & generate recommendations from current DF state
        profile = { "row_count": upload_doc.get('row_count'), "col_count": upload_doc.get('col_count'), "column_info": upload_doc.get('column_info', []) }
        recommendations = generate_cleaning_recommendations(df)

        # --- Format dates for template ---
        upload_timestamp_str = "N/A"
        last_modified_str = "N/A"
        date_format = '%Y-%m-%d %H:%M:%S' # Desired format

        # Check if the field exists AND is a datetime object before formatting
        upload_dt = upload_doc.get('upload_timestamp')
        if isinstance(upload_dt, datetime):
            upload_timestamp_str = upload_dt.strftime(date_format)

        last_mod_dt = upload_doc.get('last_modified')
        if isinstance(last_mod_dt, datetime):
            # Show last modified only if different from upload time
            if last_mod_dt != upload_dt:
                 last_modified_str = last_mod_dt.strftime(date_format)
            else:
                 last_modified_str = "-" # Indicate same as upload

        # Generate preview data from the current DataFrame
        preview_data = df.head(100).to_dict(orient='records')

        logging.info(f"Rendering data_cleaner.html template for upload_id: {upload_id}")
        # Pass the original BSON doc AND the formatted date strings
        return render_template('data_cleaner.html',
                               upload_data=upload_doc, # Pass original document
                               upload_timestamp_str=upload_timestamp_str, # Pass formatted string
                               last_modified_str=last_modified_str,     # Pass formatted string
                               preview_data=preview_data,
                               column_info=profile['column_info'],
                               recommendations=recommendations,
                               now=datetime.utcnow())

    except Exception as e:
        logging.error(f"Unexpected error loading data cleaner page for {upload_id}: {e}", exc_info=True)
        flash("An unexpected error occurred loading the data cleaner.", "danger")
        return redirect(url_for('data.analysis_history'))
    finally:
        logging.info(f"--- EXIT data_cleaner_page for upload_id: {upload_id} ---")


# --- Other Routes (/cleaner/apply, /analysis/run, /plot/generate, etc.) ---
# Keep the rest of the routes as they were in the previous corrected versions,
# ensuring they use the pattern of importing extensions INSIDE the function.

# Example structure for apply_cleaning_action:
@bp.route('/cleaner/apply/<upload_id>', methods=['POST'])
def apply_cleaning_action(upload_id):
    # --- Access extensions INSIDE function ---
    from ..extensions import db, analysis_uploads_collection
    # --- Auth & Service Checks ---
    if not is_logged_in(): return jsonify({"error": "Authentication required."}), 401
    if db is None or analysis_uploads_collection is None: return jsonify({"error": "Database unavailable."}), 503
    # --- ID Validation ---
    try: oid = ObjectId(upload_id); user_id = ObjectId(session['user_id'])
    except Exception as e: return jsonify({"error": f"Invalid ID: {e}"}), 400
    # --- Find Doc ---
    upload_doc = analysis_uploads_collection.find_one({"_id": oid, "user_id": user_id})
    if not upload_doc: return jsonify({"error": "Record not found."}), 404
    # --- Get Request Data ---
    data = request.get_json(); # ... get action, column, params ...
    if not data or not data.get('action'): return jsonify({"error": "Missing action."}), 400
    # --- Load DataFrame ---
    filepath = upload_doc.get('filepath'); # ... check exists ...
    df = get_dataframe(filepath); # ... check df is not None ...
    # --- Apply Cleaning Logic ---
    df_modified = df.copy(); # ... your detailed cleaning logic ...
    # --- Save DataFrame ---
    # ... df_modified.to_csv/xlsx ...
    # --- Update DB ---
    new_profile = generate_data_profile(df_modified); # ... update analysis_uploads_collection ...
    # --- Prepare & Return Response ---
    preview_data = df_modified.head(100).to_dict(orient='records'); # ... etc ...
    # ... return jsonify(...) ...
    # --- Error Handling ---
    # ... try/except ValueError ...
    # ... try/except Exception ...


# --- Stubs for other routes (replace with your full corrected logic) ---

@bp.route('/analysis/run/<upload_id>/<analysis_type>', methods=['POST'])
def run_analysis(upload_id, analysis_type):
    from ..extensions import db, analysis_uploads_collection
    # ... (Full logic: auth, db check, find doc, load df, run analysis type, update db, return results) ...
    return jsonify({"message": f"Analysis '{analysis_type}' placeholder executed."})

@bp.route('/plot/generate/<upload_id>', methods=['POST'])
def generate_plot(upload_id):
    from ..extensions import db, analysis_uploads_collection
    # ... (Full logic: auth, db check, find doc, load df, get plot config, generate plotly fig, return JSON) ...
    return jsonify({"message": "Plot generation placeholder executed."})

@bp.route('/insights/generate/<upload_id>', methods=['POST'])
def generate_insights(upload_id):
    from ..extensions import db, analysis_uploads_collection, genai_model
    # ... (Full logic: auth, service checks, find doc, generate prompt, call gemini, update db, return insights) ...
    return jsonify({"message": "Insight generation placeholder executed."})

@bp.route('/download/<upload_id>/cleaned_data/<fileformat>')
def download_cleaned_data(upload_id, fileformat):
    """Allows downloading the current state of the data file as CSV or XLSX."""
    # --- Access extensions INSIDE function ---
    from ..extensions import db, analysis_uploads_collection

    # Auth & Service Checks...
    if not is_logged_in(): flash("Please log in.", "warning"); return redirect(url_for('auth.login'))
    if db is None or analysis_uploads_collection is None: flash("DB unavailable.", "danger"); return redirect(url_for('data.data_analyzer_page'))

    # ID Validation & Doc Retrieval...
    try:
        oid = ObjectId(upload_id)
        user_id = ObjectId(session['user_id'])
        upload_doc = analysis_uploads_collection.find_one({"_id": oid, "user_id": user_id})
        if not upload_doc: flash("Record not found.", "danger"); return redirect(url_for('data.analysis_history'))
    except InvalidId: flash("Invalid identifier.", "danger"); return redirect(url_for('data.analysis_history'))
    except Exception as e: flash("Session/DB error finding record.", "warning"); logging.error(f"Error finding doc for download {upload_id}: {e}"); return redirect(url_for('data.analysis_history'))

    # Check filepath
    filepath = upload_doc.get('filepath')
    if not filepath or not os.path.exists(filepath):
        flash("Data file missing on server.", "danger")
        logging.error(f"Missing file for download: {filepath}")
        return redirect(url_for('data.data_cleaner_page', upload_id=upload_id))

    # Validate fileformat parameter
    fileformat_lower = fileformat.lower()
    if fileformat_lower not in ['csv', 'xlsx']:
        flash(f"Invalid download format requested: '{fileformat}'.", "warning")
        return redirect(url_for('data.data_cleaner_page', upload_id=upload_id))

    original_filename_base, _ = os.path.splitext(upload_doc.get('original_filename', f'analysis_{upload_id}'))
    download_filename = f"{original_filename_base}_cleaned.{fileformat_lower}"
    mimetype = 'text/csv' if fileformat_lower == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    # --- Generate File Content ---
    try:
        # Load the current dataframe state from the file specified in the DB doc
        logging.info(f"Loading dataframe {filepath} for download as {fileformat_lower}")
        df = get_dataframe(filepath) # Use your utility function
        if df is None:
            flash("Failed to load data file for download.", "danger")
            logging.error(f"get_dataframe returned None for {filepath} during download.")
            return redirect(url_for('data.data_cleaner_page', upload_id=upload_id))

        # Prepare buffer in memory
        buffer = io.BytesIO()
        logging.info(f"Writing dataframe (Shape: {df.shape}) to {fileformat_lower} buffer...")

        if fileformat_lower == 'csv':
            # Use utf-8-sig for better Excel compatibility with CSVs
            df.to_csv(buffer, index=False, encoding='utf-8-sig')
            logging.info("CSV buffer created.")
        elif fileformat_lower == 'xlsx':
            # --- XLSX Specific Logic ---
            # Ensure 'openpyxl' engine is installed: pip install openpyxl
            try:
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Cleaned_Data')
                # Buffer is populated after 'with' block exits
                logging.info("XLSX buffer created successfully using openpyxl.")
            except ImportError:
                 logging.error("Excel generation failed: 'openpyxl' library not found. Please install it (`pip install openpyxl`).")
                 flash("Server configuration error: Cannot generate Excel file.", "danger")
                 return redirect(url_for('data.data_cleaner_page', upload_id=upload_id))
            except Exception as excel_err:
                 # Catch other potential errors during Excel writing
                 logging.error(f"Error writing XLSX buffer for {upload_id}: {excel_err}", exc_info=True)
                 flash("An error occurred while generating the Excel file.", "danger")
                 return redirect(url_for('data.data_cleaner_page', upload_id=upload_id))
            # --- End XLSX Logic ---

        buffer.seek(0) # IMPORTANT: Rewind buffer to the beginning before sending

        logging.info(f"Initiating download '{download_filename}' for {session.get('username')}")
        # Use make_response to set headers correctly
        response = make_response(send_file(
            buffer,
            mimetype=mimetype,
            download_name=download_filename, # Suggest filename to browser
            as_attachment=True # Force download dialog
        ))
        # Ensure Content-Disposition is set robustly
        response.headers["Content-Disposition"] = f"attachment; filename=\"{download_filename}\""
        return response

    except Exception as e:
        # Catch errors during dataframe loading or file writing
        logging.error(f"Error preparing/sending cleaned data download for {upload_id} as {fileformat}: {e}", exc_info=True)
        flash("An error occurred while preparing the file for download.", "danger")
        return redirect(url_for('data.data_cleaner_page', upload_id=upload_id))

@bp.route('/download/<upload_id>/pdf_report')
def download_pdf_report(upload_id):
    """Generates and downloads a PDF summary report of the analysis."""
    # --- Access extensions INSIDE function ---
    from ..extensions import db, analysis_uploads_collection

    # Auth & Service Checks...
    if not is_logged_in(): flash("Please log in.", "warning"); return redirect(url_for('auth.login'))
    if db is None or analysis_uploads_collection is None: flash("DB unavailable.", "danger"); return redirect(url_for('data.data_analyzer_page'))

    # ID Validation & Doc Retrieval...
    try:
        oid = ObjectId(upload_id)
        user_id = ObjectId(session['user_id'])
        upload_doc = analysis_uploads_collection.find_one({"_id": oid, "user_id": user_id})
        if not upload_doc:
            flash("Record not found or access denied.", "danger")
            return redirect(url_for('data.analysis_history'))
    except InvalidId:
        flash("Invalid record identifier.", "danger")
        return redirect(url_for('data.analysis_history'))
    except Exception as e:
        flash("Session or database error finding record.", "warning")
        logging.error(f"Error finding doc for PDF report {upload_id}: {e}")
        return redirect(url_for('data.analysis_history'))

    # --- Generate PDF ---
    try:
        logging.info(f"Generating PDF report for {upload_id} by {session.get('username')}")
        pdf = PDFReport(orientation='P', unit='mm', format='A4') # Use the helper class
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # --- Populate PDF Content ---
        # Ensure all data access uses .get() with defaults for safety

        # Section 1: Summary
        pdf.chapter_title('1. Data Summary')
        upload_time = upload_doc.get('upload_timestamp') # Get raw datetime
        last_mod = upload_doc.get('last_modified')
        upload_time_str = upload_time.strftime('%Y-%m-%d %H:%M:%S') if isinstance(upload_time, datetime) else 'N/A'
        last_mod_str = last_mod.strftime('%Y-%m-%d %H:%M:%S') if isinstance(last_mod, datetime) and last_mod != upload_time else '-'

        summary_text = (
            f"Original Filename: {upload_doc.get('original_filename', 'N/A')}\n"
            f"Upload Time: {upload_time_str} UTC\n"
            f"Last Modified: {last_mod_str} UTC\n"
            f"Status: {upload_doc.get('status', 'N/A')}\n"
            f"Dimensions: {upload_doc.get('row_count', 'N/A')} Rows x {upload_doc.get('col_count', 'N/A')} Columns"
        )
        pdf.chapter_body(summary_text)

        col_info = upload_doc.get('column_info', [])
        if col_info:
            col_header = ["Name", "Data Type", "Null Count"]
            col_data = [[c.get('name',''), c.get('dtype',''), c.get('null_count','N/A')] for c in col_info]
            col_widths = [pdf.w * 0.45 - pdf.l_margin, pdf.w * 0.25 - pdf.l_margin, pdf.w * 0.20 - pdf.l_margin]
            pdf.add_table(col_header, col_data, col_widths=col_widths)
        else: pdf.chapter_body("Initial column info not available.")

        # Section 2: Cleaning Steps
        pdf.chapter_title('2. Cleaning Steps Applied')
        steps = upload_doc.get('cleaning_steps', [])
        if steps:
            step_text_lines = []
            for i, step in enumerate(steps):
                 step_time_obj = step.get('timestamp')
                 step_time = step_time_obj.strftime('%Y-%m-%d %H:%M') if isinstance(step_time_obj, datetime) else '?' # Format time
                 action = step.get('action', '?')
                 column = step.get('column', '')
                 # Safely format params using json.dumps with default=str
                 params_str = json.dumps(step.get('params', {}), default=str, separators=(',', ':'))
                 line = f"[{step_time}] {i+1}: {action}"
                 if column: line += f" on '{column}'"
                 line += f" params: {params_str}"
                 step_text_lines.append(line)
            pdf.chapter_body("\n".join(step_text_lines))
        else: pdf.chapter_body("No cleaning steps recorded.")

        # Section 3: Analysis Results
        pdf.chapter_title('3. Analysis Results')
        analysis = upload_doc.get('analysis_results', {})
        if analysis:
            for name, data in analysis.items():
                 analysis_name_nice = name.replace('_',' ').title()
                 pdf.add_json_block(analysis_name_nice, data) # Use helper method
        else: pdf.chapter_body("No analysis results found.")

        # Section 4: Visualizations Placeholder
        pdf.chapter_title('4. Visualizations')
        pdf.chapter_body("(Visualizations generated interactively.)")

        # Section 5: AI Insights
        pdf.chapter_title('5. AI Generated Insights')
        insights = upload_doc.get('generated_insights', [])
        if insights:
             insights_text = "\n".join([f"- {insight}" for insight in insights])
             pdf.chapter_body(insights_text)
        else: pdf.chapter_body("No AI insights found.")

        # --- Generate PDF Output ---
        logging.info(f"Finalizing PDF output buffer for {upload_id}")
        # FPDF.output returns bytes when dest='S'
        pdf_output_bytes = pdf.output(dest='S')
        buffer = io.BytesIO(pdf_output_bytes)
        buffer.seek(0)

        original_filename_base, _ = os.path.splitext(upload_doc.get('original_filename', f'analysis_{upload_id}'))
        download_filename = f"{original_filename_base}_report.pdf"

        logging.info(f"Sending PDF report '{download_filename}' for {session.get('username')}")
        # Use make_response for better header control
        response = make_response(send_file(
            buffer,
            mimetype='application/pdf',
            download_name=download_filename,
            as_attachment=True # Force download dialog
        ))
        # Explicitly set Content-Disposition again for good measure
        response.headers["Content-Disposition"] = f"attachment; filename=\"{download_filename}\""
        return response

    except Exception as e:
        # Log the full error during PDF generation
        logging.error(f"Error generating PDF report for {upload_id}: {e}", exc_info=True)
        flash("An error occurred while generating the PDF report. Please check server logs.", "danger")
        # Redirect back to the cleaner page where the button was clicked
        return redirect(url_for('data.data_cleaner_page', upload_id=upload_id))

@bp.route('/history') # Route is '/data/history' due to blueprint prefix
def analysis_history():
    # --- Access extensions INSIDE function ---
    from ..extensions import db, analysis_uploads_collection
    # ... (Authentication check) ...
    if not is_logged_in(): flash("Please log in.", "warning"); return redirect(url_for('auth.login'))
    # ... (DB check) ...
    if db is None or analysis_uploads_collection is None: flash("DB unavailable.", "danger"); return redirect(url_for('core.dashboard'))
    # ... (Logic to fetch history from analysis_uploads_collection) ...
    history = []
    # ... (Try/except block to get user_id and fetch data) ...
    try:
        user_id = ObjectId(session['user_id'])
        history_cursor = analysis_uploads_collection.find(
            {"user_id": user_id},
            # ... projection ...
        ).sort([("last_modified", -1)]).limit(50)
        history = list(history_cursor)
        # ... (Format dates and _id for template) ...
        for item in history: # ... format item ...
            pass
    except Exception as e:
        # ... log error, flash error ...
        pass
    # Render the history template
    return render_template('analysis_history.html', history=history, now=datetime.utcnow())
