# src/sockets/pdf_chat_handlers.py

import logging
from flask import request, session
from flask_socketio import emit
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
import traceback

# --- Relative Imports ---
# --- DO NOT import specific collections or initialized models here ---
# from ..extensions import socketio # Only if needed for decorators

# --- Import Utils ---
from ..utils.auth_utils import is_logged_in
from ..utils.api_utils import log_gemini_response_details
from ..utils.db_utils import log_db_update_result


# Registration function - socketio instance is passed in
def register_pdf_chat_handlers(socketio_instance):

    # == PDF Chat Namespace (/pdf_chat) ==
    @socketio_instance.on('connect', namespace='/pdf_chat')
    def handle_pdf_chat_connect():
        if not is_logged_in(): return False # Reject unauthenticated
        username = session.get('username', 'Unknown'); user_id = session.get('user_id', 'N/A')
        logging.info(f"User '{username}' (ID: {user_id}) connected to /pdf_chat. SID: {request.sid}")

    @socketio_instance.on('disconnect', namespace='/pdf_chat')
    def handle_pdf_chat_disconnect():
        username = session.get('username', 'Unknown'); user_id = session.get('user_id', 'N/A')
        logging.info(f"User '{username}' (ID: {user_id}) disconnected from /pdf_chat. SID: {request.sid}")

    @socketio_instance.on('send_pdf_chat_message', namespace='/pdf_chat')
    def handle_pdf_chat_message(data):
        # --- Access extensions INSIDE handler ---
        from ..extensions import (db, genai_model, safety_settings,
                                 pdf_analysis_collection, pdf_chats_collection)

        sid = request.sid
        logging.debug(f"--- PDF Chat Msg START (SID:{sid}) ---")
        # Auth & Service Checks
        if not is_logged_in(): emit('error', {'message': 'Auth required.'}, room=sid, namespace='/pdf_chat'); return
        if db is None or pdf_analysis_collection is None or pdf_chats_collection is None:
            emit('error', {'message': 'Chat DB service unavailable.'}, room=sid, namespace='/pdf_chat'); return
        if genai_model is None:
            emit('error', {'message': 'AI service unavailable.'}, room=sid, namespace='/pdf_chat'); return

        # Validate data and IDs
        username = session.get('username','Unknown_PDFUser'); user_id_str = session.get('user_id')
        if not isinstance(data, dict): logging.warning(f"PDF Chat invalid data format"); return
        user_message = data.get('text', '').strip(); analysis_id_str = data.get('analysis_id')
        if not user_message or not analysis_id_str: emit('error', {'message': 'Missing text or analysis ID.'}, room=sid, namespace='/pdf_chat'); return
        try: analysis_id = ObjectId(analysis_id_str); user_id = ObjectId(user_id_str)
        except Exception as e: logging.error(f"Invalid ID format: {e}"); emit('error', {'message': 'Invalid context ID.'}, room=sid, namespace='/pdf_chat'); return

        logging.info(f"(PDF Chat SID:{sid}) Msg for analysis {analysis_id} from '{username}': '{user_message[:50]}...'")

        # --- Verify User Access & Get Context ---
        try:
             # Use locally accessed collection
             pdf_doc = pdf_analysis_collection.find_one(
                 {"_id": analysis_id, "user_id": user_id}, {"extracted_text_preview": 1}
             )
             if not pdf_doc:
                  logging.error(f"PDF doc {analysis_id} not found/access denied for user {user_id}.")
                  emit('error', {'message': 'PDF context error.'}, room=sid, namespace='/pdf_chat'); return
             pdf_text_context = pdf_doc.get("extracted_text_preview", "")
        except Exception as e:
             logging.error(f"Error fetching PDF doc {analysis_id}: {e}", exc_info=True)
             emit('error', {'message': 'Error retrieving PDF context.'}, room=sid, namespace='/pdf_chat'); return

        # --- Save User Message ---
        try:
            user_msg_doc = {"role": "user", "text": user_message, "timestamp": datetime.utcnow()}
            # Use locally accessed collection
            update_result_user = pdf_chats_collection.update_one(
                {"pdf_analysis_id": analysis_id},
                {"$push": {"messages": user_msg_doc},
                 "$setOnInsert": {"pdf_analysis_id": analysis_id, "user_id": user_id, "username": username, "start_timestamp": datetime.utcnow()}},
                upsert=True)
            log_db_update_result(update_result_user, username, f"pdf_chat_{sid}_{analysis_id}")
        except Exception as e: logging.error(f"DB save PDF user msg err (Analysis {analysis_id}): {e}", exc_info=True)

        # --- Process with AI ---
        ai_response_text = "[AI Error]"
        try:
            emit('typing_indicator', {'isTyping': True}, room=sid, namespace='/pdf_chat')
            # Build History (using locally accessed collection)
            history = []
            chat_doc = pdf_chats_collection.find_one({"pdf_analysis_id": analysis_id}, {"messages": {"$slice": -6}})
            if chat_doc and "messages" in chat_doc:
                 for msg in chat_doc["messages"]: history.append({'role': ('model' if msg.get('role')=='AI' else 'user'), 'parts': [msg.get('text', '')]})

            history_string = "\n".join([f"{m['role']}: {m['parts'][0]}" for m in history]) if history else "No previous messages."
            pdf_chat_prompt = f"""Context from PDF:\n---\n{pdf_text_context or "No text."}\n---\nChat History:\n---\n{history_string}\n---\nUser Question: {user_message}\n\nAnswer based ONLY on context/history:"""

            logging.info(f"(PDF Chat SID:{sid}) Sending query for analysis {analysis_id} to Gemini...")
            # Use locally accessed model and settings
            # Assuming safety_settings applied globally during model init
            response = genai_model.generate_content(pdf_chat_prompt, safety_settings=safety_settings)
            log_gemini_response_details(response, f"pdf_chat_{sid}_{analysis_id}")

            # Process response
            if response.candidates: ai_response_text = response.text or "[AI empty]"
            elif hasattr(response, 'prompt_feedback'): ai_response_text = f"[AI blocked: {response.prompt_feedback.block_reason.name}]"
            else: ai_response_text = "[AI blocked/empty]"

            # Save AI Response (using locally accessed collection)
            if not ai_response_text.startswith("[AI"):
                try:
                    ai_msg_doc = {"role": "AI", "text": ai_response_text, "timestamp": datetime.utcnow()}
                    update_result_ai = pdf_chats_collection.update_one({"pdf_analysis_id": analysis_id}, {"$push": {"messages": ai_msg_doc}})
                    log_db_update_result(update_result_ai, f"AI_PDFChat_{username}", f"pdf_chat_{sid}_{analysis_id}")
                except Exception as e: logging.error(f"DB save PDF AI msg err (Analysis {analysis_id}): {e}", exc_info=True)

        except Exception as e: # Catch AI processing errors
            logging.error(f"(PDF Chat SID:{sid}) AI processing error for analysis {analysis_id}: {e}", exc_info=True)
            emit('error', {'message': 'Server error during PDF chat.'}, room=sid, namespace='/pdf_chat')
        finally:
            emit('typing_indicator', {'isTyping': False}, room=sid, namespace='/pdf_chat')
            logging.info(f"(PDF Chat SID:{sid}) Emitting 'receive_pdf_chat_message' for analysis {analysis_id}...")
            emit('receive_pdf_chat_message', {'user': 'AI', 'text': ai_response_text}, room=sid, namespace='/pdf_chat')
            logging.debug(f"--- PDF Chat Msg END (SID:{sid}) ---")

    logging.info("PDF chat handlers registered.")