# src/routes/agent_routes.py

import logging
from flask import Blueprint, render_template, redirect, url_for, flash, session, request, jsonify
from datetime import datetime
from bson import ObjectId
import json

# --- Relative Imports ---
# --- OK to import placeholder objects like db, genai_model if needed globally ---
# from ..extensions import db, genai_model
# --- DO NOT import safety_settings or specific collections here ---

# --- Import Utils ---
from ..utils.auth_utils import is_logged_in
# from ..utils.api_utils import log_gemini_response_details # Import if using the logger

bp = Blueprint('agent', __name__)


# --- Education Agent ---
@bp.route('/education')
def education_agent_page():
    if not is_logged_in():
        flash("Please log in.", "warning")
        return redirect(url_for('auth.login'))
    return render_template('education_agent.html', now=datetime.utcnow())

@bp.route('/education/query', methods=['POST'])
def education_agent_query():
    # --- Access extensions INSIDE function ---
    from ..extensions import db, genai_model, safety_settings, education_chats_collection

    if not is_logged_in(): return jsonify({"error": "Authentication required."}), 401
    if genai_model is None: return jsonify({"error": "AI service unavailable."}), 503
    # Check specific collection after db check
    if db is None or education_chats_collection is None:
         if db is None: logging.error("Edu query: DB service unavailable.")
         else: logging.error("Edu query: Edu collection unavailable.")
         return jsonify({"error": "Database service unavailable."}), 503

    if not request.is_json: return jsonify({"error": "Invalid request format. JSON required."}), 400

    data = request.get_json()
    user_query = data.get('query', '').strip()
    username = session.get('username', 'User')
    user_id_str = session.get('user_id')

    if not user_query or not user_id_str:
        return jsonify({"error": "Missing query or user session information."}), 400

    try: user_id = ObjectId(user_id_str)
    except Exception: logging.error(f"Invalid user_id format: {user_id_str}"); return jsonify({"error": 'Session error.'}), 500

    interaction_id = None
    try:
        # Access collection via db proxy or directly if imported locally
        # education_chats_collection = db.education_chats # Alternative access
        doc = { # ... doc data ...
            "user_id": user_id, "username": username, "query": user_query,
            "timestamp": datetime.utcnow(), "ai_answer": None, "answered_at": None
        }
        interaction_id = education_chats_collection.insert_one(doc).inserted_id
    except Exception as e: logging.error(f"Error saving education query: {e}")

    prompt = f"Educational Assistant...\nQuery: {user_query}\nAnswer:" # Your specific prompt
    ai_resp = "[AI Error]"
    try:
        logging.info(f"Sending education query to Gemini for user {username}...")
        # Use locally accessed genai_model and safety_settings
        response = genai_model.generate_content(prompt, safety_settings=safety_settings)
        # ... (process response as before) ...
        if response.candidates: ai_resp = response.text or "[AI empty]"
        elif hasattr(response, 'prompt_feedback'): ai_resp = f"[AI blocked: {response.prompt_feedback.block_reason.name}]"
        else: ai_resp = "[AI blocked/empty]"

        if interaction_id and not ai_resp.startswith("[AI"):
            try: education_chats_collection.update_one({"_id": interaction_id}, {"$set": {"ai_answer": ai_resp, "answered_at": datetime.utcnow()}})
            except Exception as e: logging.error(f"Error updating edu answer {interaction_id}: {e}")
        return jsonify({"answer": ai_resp})
    except Exception as e:
        logging.error(f"Error processing edu query via Gemini: {e}", exc_info=True)
        return jsonify({"error": "Server error processing AI request."}), 500


# --- Healthcare Agent ---
@bp.route('/healthcare')
def healthcare_agent_page():
    if not is_logged_in(): flash("Please log in.", "warning"); return redirect(url_for('auth.login'))
    return render_template('healthcare_agent.html', now=datetime.utcnow())

@bp.route('/healthcare/query', methods=['POST'])
def healthcare_agent_query():
    # --- Access extensions INSIDE function ---
    from ..extensions import db, genai_model, safety_settings, healthcare_chats_collection

    if not is_logged_in(): return jsonify({"error": "Authentication required."}), 401
    if genai_model is None: return jsonify({"error": "AI service unavailable."}), 503
    if db is None or healthcare_chats_collection is None: return jsonify({"error": "Database service unavailable."}), 503
    # ... (rest of the healthcare query logic, similar to education) ...
    # --- Make sure to use locally accessed `genai_model`, `safety_settings`, `healthcare_chats_collection` ---
    if not request.is_json: return jsonify({"error": "Invalid request format."}), 400
    data=request.get_json(); user_query=data.get('query','').strip()
    username=session.get('username','User'); user_id_str=session.get('user_id')
    if not user_query or not user_id_str: return jsonify({"error":"Missing query/session."}), 400
    try: user_id = ObjectId(user_id_str)
    except Exception as e: logging.error(f"Invalid user_id format: {e}"); return jsonify({"error": 'Session error.'}), 500

    interaction_id = None
    try:
        doc={"user_id":user_id,"username":username,"query":user_query,"timestamp":datetime.utcnow(),"ai_answer":None, "answered_at": None}
        interaction_id=healthcare_chats_collection.insert_one(doc).inserted_id
    except Exception as e: logging.error(f"Err save health query: {e}")

    prompt = f"""IMPORTANT: You are an AI providing general health information... User Query: {user_query}\n\nInformational Answer (Do NOT give advice):""" # Your prompt
    ai_resp = "[AI Error]"
    try:
        logging.info(f"Sending healthcare query to Gemini for user {username}...")
        response = genai_model.generate_content(prompt, safety_settings=safety_settings)
        # ... (process response) ...
        if response.candidates: ai_resp=response.text if response.text else "[AI empty]"
        elif hasattr(response, 'prompt_feedback'): ai_resp = f"[AI blocked: {response.prompt_feedback.block_reason.name}]"
        else: ai_resp="[AI blocked/empty]"

        if interaction_id and not ai_resp.startswith("[AI"):
            try: healthcare_chats_collection.update_one( {"_id":interaction_id}, {"$set":{"ai_answer":ai_resp,"answered_at":datetime.utcnow()}})
            except Exception as e: logging.error(f"Err update health answer {interaction_id}: {e}")
        return jsonify({"answer": ai_resp })
    except Exception as e:
        logging.error(f"Err proc health query: {e}", exc_info=True); return jsonify({"error": "Server error."}), 500


# --- Construction Agent ---
@bp.route('/construction')
def construction_agent_page():
    if not is_logged_in(): flash("Please log in.", "warning"); return redirect(url_for('auth.login'))
    return render_template('construction_agent.html', now=datetime.utcnow())

@bp.route('/construction/query', methods=['POST'])
def construction_agent_query():
    # --- Access extensions INSIDE function ---
    from ..extensions import db, genai_model, safety_settings, construction_agent_interactions_collection

    if not is_logged_in(): return jsonify({"error": "Authentication required."}), 401
    if genai_model is None: return jsonify({"error": "AI service unavailable."}), 503
    if db is None or construction_agent_interactions_collection is None: return jsonify({"error": "Database service unavailable."}), 503
    # ... (rest of the construction query logic, similar to others) ...
    # --- Make sure to use locally accessed `genai_model`, `safety_settings`, `construction_agent_interactions_collection` ---
    if not request.is_json: return jsonify({"error": "Invalid request format."}), 400
    data = request.get_json(); user_query = data.get('query', '').strip(); data_context = data.get('context', '')
    username = session.get('username', 'User'); user_id_str = session.get('user_id')
    if not user_query or not user_id_str: return jsonify({"error":"Missing query/session."}), 400
    try: user_id = ObjectId(user_id_str)
    except Exception as e: logging.error(f"Invalid user_id format: {e}"); return jsonify({"error": 'Session error.'}), 500

    interaction_id = None
    try:
        doc = { # ... doc data ...
            "user_id": user_id, "username": username, "query": user_query, "data_context": data_context,
            "timestamp": datetime.utcnow(), "ai_answer": None, "chart_data": None, "answered_at": None
        }
        interaction_id = construction_agent_interactions_collection.insert_one(doc).inserted_id
    except Exception as db_err: logging.error(f"Failed save construction query: {db_err}")

    prompt = f"""Construction Project AI Assistant... Context:\n{data_context if data_context else "N/A"}\nQuery:\n{user_query}\n```json_construction_chart_data...```\nAI Response:\n---""" # Your prompt
    ai_resp = "[AI Error]"; chart_data = {}
    try:
        logging.info(f"Sending construction query to Gemini for user {username}...")
        response = genai_model.generate_content(prompt, safety_settings=safety_settings)
        # ... (process response and chart parsing) ...
        raw_text = "";
        if response.candidates:
             raw_text = response.text; ai_resp = raw_text
             try: # Parse JSON
                 json_start_marker="```json_construction_chart_data"; json_end_marker="```"; start_index=raw_text.rfind(json_start_marker);
                 if start_index!=-1:
                     end_index=raw_text.find(json_end_marker, start_index+len(json_start_marker));
                     if end_index!=-1:
                         json_string=raw_text[start_index+len(json_start_marker):end_index].strip();
                         try: chart_data=json.loads(json_string); ai_resp=raw_text[:start_index].strip(); logging.info("Parsed construction chart data.");
                         except Exception as json_e: logging.error(f"Construction JSON Parse Err: {json_e}");
             except Exception as parse_e: logging.error(f"Construction Chart Parsing Err: {parse_e}");
        elif hasattr(response, 'prompt_feedback'): ai_resp = f"[AI blocked: {response.prompt_feedback.block_reason.name}]"
        else: ai_resp="[AI blocked/empty]"

        if interaction_id: # Update DB
            update_payload = {"$set": {"answered_at": datetime.utcnow(), "chart_data": chart_data}}
            if not ai_resp.startswith("[AI"): update_payload["$set"]["ai_answer"] = ai_resp
            try: construction_agent_interactions_collection.update_one({"_id":interaction_id}, update_payload)
            except Exception as e: logging.error(f"Err update construction answer {interaction_id}: {e}")
        return jsonify({"answer": ai_resp, "chart_data": chart_data })
    except Exception as e:
        logging.error(f"Err proc construction query: {e}", exc_info=True); return jsonify({"error": "Server error."}), 500