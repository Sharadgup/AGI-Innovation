# src/routes/core_routes.py

import logging
import json
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, session, current_app, request, jsonify)
from bson import ObjectId
from bson.errors import InvalidId

# --- Relative Imports ---
# --- Import Utility functions at the top level ---
from ..utils.auth_utils import is_logged_in # Import the login check function
from ..utils.api_utils import log_gemini_response_details # Import logging helper

# --- DO NOT import initialized extensions like db, genai_model, or collections here ---

# --- Create the Blueprint ---
bp = Blueprint('core', __name__)


# --- Route Definitions ---

@bp.route('/')
def landing_page():
    """Renders the landing page. Redirects to dashboard if logged in."""
    # --- Import extensions needed INSIDE function ---
    from ..extensions import google_enabled # Needed for template context

    # Use the is_logged_in function imported at the top
    if is_logged_in():
         return redirect(url_for('core.dashboard'))
    # Pass google_enabled status for the login button conditional display
    return render_template('landing.html', now=datetime.utcnow(), google_login_enabled=google_enabled)


@bp.route('/dashboard')
def dashboard():
    """Renders the main user dashboard after login."""
    # Use the is_logged_in function imported at the top
    if not is_logged_in():
        flash("Please log in to access the dashboard.", "warning")
        return redirect(url_for('auth.login')) # Redirect to auth blueprint's login

    username = session.get('username', 'User')

    # Prepare data for the dashboard template
    # Get necessary info from config or extensions INSIDE function if needed
    usable_models = [current_app.config.get("GEMINI_MODEL_NAME", "N/A")]

    # Static data examples
    available_models = ["G 1.5 Flash", "G Pro"]
    sectors = ["Healthcare", "Finance", "Tech", "Edu", "Retail", "General"]
    apps = [{"id": "tts", "name": "Text-to-Speech"}, {"id": "ttv", "name": "Text-to-Video (Future)"}]
    services = ["Analysis", "Visualization", "Chat", "PDF", "News", "Voice"]

    dashboard_data = {
        "username": username,
        "services": services,
        "available_models": available_models,
        "usable_models": usable_models,
        "sectors": sectors,
        "apps": apps
    }
    return render_template('dashboard.html', data=dashboard_data, now=datetime.utcnow())


@bp.route('/index') # Original route for the 'report' page template
def report_page():
     """Renders the page that likely contains the initial report generation form."""
     # Decide if this page requires login using the imported function
     # if not is_logged_in():
     #    flash("Please log in to generate reports.", "warning")
     #    return redirect(url_for('auth.login'))
     return render_template('index.html', now=datetime.utcnow())


@bp.route('/generate_report', methods=['POST'])
def generate_report_route():
    """Handles the POST request to generate a report from text input."""
    logging.info("Request received at /generate_report")
    # --- Import extensions needed INSIDE function ---
    from ..extensions import db, genai_model, input_prompts_collection, documentation_collection

    # Check dependencies
    if genai_model is None:
        logging.error("/generate_report: AI model unavailable.")
        return jsonify({"error": "AI service is currently unavailable."}), 503
    # Check DB and specific collections
    if db is None:
         logging.error("/generate_report: Database service unavailable (db object is None).")
         return jsonify({"error": "Database service is currently unavailable."}), 503
    # Re-access collections via db proxy just in case initial assignment failed but db connected
    input_prompts_collection_local = db.input_prompts # Use local var names to avoid shadowing
    documentation_collection_local = db.documentation
    if input_prompts_collection_local is None or documentation_collection_local is None:
         logging.error("/generate_report: Required database collections unavailable.")
         return jsonify({"error": "Database service collections unavailable."}), 503

    # Validate request format
    if not request.is_json:
        logging.warning("/generate_report: Received non-JSON request.")
        return jsonify({"error": "Invalid request format. JSON required."}), 400

    data = request.get_json()
    input_text = data.get('text')

    if not input_text:
        logging.warning("/generate_report: No 'text' provided in request.")
        return jsonify({"error": "No input text provided."}), 400

    prompt_doc_id = None
    user_id = None
    username = session.get('username', 'Anonymous')

    # Use the is_logged_in function imported at the top
    if is_logged_in():
        try:
            user_id = ObjectId(session['user_id'])
        except (InvalidId, KeyError):
            logging.warning("Could not get valid user_id for report generation.")
            user_id = None

    # --- Save Input Prompt ---
    try:
        prompt_doc = {
             "original_text": input_text, "timestamp": datetime.utcnow(),
             "user_id": user_id, "username": username if user_id else "Anonymous"
        }
        prompt_insert_result = input_prompts_collection_local.insert_one(prompt_doc)
        prompt_doc_id = prompt_insert_result.inserted_id
        logging.info(f"Saved input prompt ID: {prompt_doc_id} (User: {username})")
    except Exception as e:
        logging.error(f"Error saving input prompt to DB: {e}", exc_info=True)
        prompt_doc_id = None

    # --- Prepare Prompt for Gemini ---
    prompt_for_ai = f"Analyze the following text...\nInput Text:\n```\n{input_text}\n```\n\nReport:\n---\n```json_chart_data\n{{ ... }}\n```" # Your prompt structure

    report_content = None; chart_data = {}; doc_id = None

    try:
        # --- Call Gemini ---
        logging.info(f"Sending prompt (User: {username}, PromptID: {prompt_doc_id}) to Gemini...")
        # Use the genai_model accessed inside the function
        response = genai_model.generate_content(prompt_for_ai)
        # Use the log function imported at the top
        log_gemini_response_details(response, f"report_{prompt_doc_id or 'no_prompt_id'}")

        # --- Process Gemini Response ---
        if not response or not response.candidates:
             raise ValueError("AI response was empty or blocked.")
        gen_text = response.text
        report_content = gen_text
        # Chart parsing logic...
        try:
             json_start_marker="```json_chart_data"; json_end_marker="```"; start_index=gen_text.rfind(json_start_marker)
             if start_index!=-1:
                 end_index=gen_text.find(json_end_marker, start_index+len(json_start_marker));
                 if end_index!=-1:
                     json_string=gen_text[start_index+len(json_start_marker):end_index].strip();
                     try: chart_data=json.loads(json_string); report_content=gen_text[:start_index].strip(); logging.info("Parsed chart data.");
                     except Exception as json_e: logging.error(f"Chart JSON parse error: {json_e}");
        except Exception as parse_e: logging.error(f"Chart marker parse error: {parse_e}");


        # --- Save Documentation ---
        try:
            finish_reason = response.candidates[0].finish_reason.name if response.candidates else 'UNKNOWN'
            doc_save = {
                "input_prompt_id": prompt_doc_id, "user_id": user_id, "username": username if user_id else "Anonymous",
                "report_html": report_content, "chart_data": chart_data, "timestamp": datetime.utcnow(),
                "model_used": current_app.config.get("GEMINI_MODEL_NAME", "N/A"), "finish_reason": finish_reason
            }
            doc_insert_result = documentation_collection_local.insert_one(doc_save)
            doc_id = doc_insert_result.inserted_id
            logging.info(f"Saved documentation to DB. Doc ID: {doc_id}")

            # Link back from prompt doc
            if prompt_doc_id:
                try: input_prompts_collection_local.update_one({"_id": prompt_doc_id}, {"$set": {"related_documentation_id": doc_id}})
                except Exception as link_err: logging.error(f"Failed link prompt {prompt_doc_id} to doc {doc_id}: {link_err}")

            # --- SUCCESS RETURN ---
            return jsonify({
                 "report_html": report_content, "chart_data": chart_data,
                 "report_context_for_chat": report_content[:3000], "documentation_id": str(doc_id)
            }), 200

        except Exception as db_save_err: # Error saving documentation
            logging.error(f"Error saving documentation to DB: {db_save_err}", exc_info=True)
            return jsonify({ # Still return generated content, but flag DB error
                "error": "Report generated but failed to save to database.", "report_html": report_content,
                "chart_data": chart_data, "report_context_for_chat": report_content[:3000], "documentation_id": None
            }), 200

    except ValueError as ve: # Error during AI call (e.g., blocked)
         logging.error(f"Value error during report generation: {ve}")
         return jsonify({"error": f"Failed to generate report: {ve}"}), 500
    except Exception as e: # Other unexpected errors
        logging.error(f"Unexpected error during AI processing or report parsing: {e}", exc_info=True)
        return jsonify({"error": "A server error occurred during AI processing or report parsing."}), 500