# src/sockets/voice_handlers.py

import logging
from flask import request, session
from flask_socketio import emit
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
import traceback
import re # Import regular expressions for keyword checking

# --- Relative Imports ---
from ..utils.auth_utils import is_logged_in
from ..utils.api_utils import log_gemini_response_details
from ..utils.db_utils import log_db_update_result

# Helper function specific to voice handlers for emitting errors
# ... (_log_and_emit_voice_error function remains the same) ...
def _log_and_emit_voice_error(message, sid):
    logging.error(f"(Voice Chat SID:{sid}) Error: {message}")
    try: emit('error', {'message': message}, room=sid, namespace='/voice_chat')
    except Exception as e: logging.error(f"(Voice Chat SID:{sid}) Failed emit error '{message}': {e}", exc_info=True)


# Registration function
def register_voice_handlers(socketio_instance):
    """Registers SocketIO event handlers for the /voice_chat namespace."""

    # ... (handle_voice_connect and handle_voice_disconnect remain the same) ...
    @socketio_instance.on('connect', namespace='/voice_chat')
    def handle_voice_connect():
        if not is_logged_in(): return False
        user_id_str = session.get('user_id'); username = session.get('username', 'Unknown')
        logging.info(f"User '{username}' (ID: {user_id_str}) connected to '/voice_chat'. SID: {request.sid}")
        try: emit('connection_ack', {'message': 'Connected.'}, room=request.sid, namespace='/voice_chat')
        except Exception as e: logging.error(f"Error emitting ack to SID {request.sid}: {e}")

    @socketio_instance.on('disconnect', namespace='/voice_chat')
    def handle_voice_disconnect():
        username = session.get('username', 'Unknown_User'); user_id = session.get('user_id', 'N/A_ID')
        logging.info(f"User '{username}' (ID: {user_id}) disconnected from '/voice_chat'. SID: {request.sid}")

    @socketio_instance.on('send_voice_text', namespace='/voice_chat')
    def handle_send_voice_text(data):
        """Handles transcribed text, attempts multilingual response, falls back to English if needed."""
        # --- Access extensions INSIDE handler ---
        from ..extensions import (db, genai_model, safety_settings,
                                 voice_conversations_collection)

        sid = request.sid
        user_lang_from_payload = 'en-US'
        if isinstance(data, dict) and data.get('lang'): user_lang_from_payload = data.get('lang')
        logging.info(f"--- Received 'send_voice_text' (SID:{sid}, Client Lang:{user_lang_from_payload}) ---")

        # 1. --- Validation and Setup ---
        if not is_logged_in(): _log_and_emit_voice_error('Auth required.', sid); return
        if db is None or voice_conversations_collection is None: _log_and_emit_voice_error('DB unavailable.', sid); return
        if genai_model is None: _log_and_emit_voice_error('AI unavailable.', sid); return

        username = session.get('username','Unknown_VoiceUser'); user_id_str = session.get('user_id')
        if not isinstance(data, dict): logging.warning(f"Voice Chat invalid data format SID:{sid}"); return
        user_transcript = data.get('text', '').strip()
        user_lang = user_lang_from_payload
        if not user_transcript: logging.debug(f"Voice Chat empty transcript SID:{sid}"); return
        try: user_id = ObjectId(user_id_str)
        except Exception as e: _log_and_emit_voice_error(f"Invalid session ID.", sid); return

        logging.info(f"(Voice Chat SID:{sid}) Processing from '{username}' (Lang:{user_lang}): '{user_transcript[:70]}...'")

        now = datetime.utcnow()
        user_msg_doc = {"role": "user", "text": user_transcript, "lang": user_lang, "timestamp": now}
        ai_response_text = "[AI Processing Error]"
        ai_lang = user_lang # Assume success initially

        # 2. --- Call Gemini API (Attempt 1: Target Language) ---
        try:
            logging.debug(f"(Voice Chat SID:{sid}) Attempt 1: Gemini call (Target Lang: {user_lang})...")
            history = [] # Build history as before...
            try:
                convo_doc = voice_conversations_collection.find_one({"user_id": user_id}, {"messages": {"$slice": -4}})
                if convo_doc and "messages" in convo_doc:
                     for msg in convo_doc.get("messages", []):
                         if isinstance(msg, dict) and "role" in msg and "text" in msg:
                              history.append({'role': ('model' if msg['role']=='AI' else 'user'), 'parts': [msg['text']]})
            except Exception as hist_err: logging.error(f"Voice Chat history build error SID:{sid}: {hist_err}")

            language_map = { 'en-US': 'English', 'hi-IN': 'Hindi', 'de-DE': 'German', 'fr-FR': 'French', 'es-ES': 'Spanish', } # Add more
            language_name = language_map.get(user_lang, user_lang)
            prompt_attempt_1 = f"""**Role:** Multilingual voice assistant.\n**Task:** Respond conversationally IN '{language_name}' to the input. Be concise.\n**Input Language:** '{language_name}'\n**User Input:** "{user_transcript}"\n**Your Direct Response (in '{language_name}'):**"""

            chat_session = genai_model.start_chat(history=history)
            response = chat_session.send_message(prompt_attempt_1)
            log_gemini_response_details(response, f"voice_chat_{sid}_lang_attempt")

            # --- Process Response (Attempt 1) ---
            temp_ai_response = None
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                 ai_response_text = f"[AI blocked: {response.prompt_feedback.block_reason.name}]"
            elif response.candidates:
                try: temp_ai_response = response.text.strip()
                except Exception: pass # Ignore text extraction error for now
            else: ai_response_text = "[AI no candidates]" # No candidates from first attempt

            # --- Check if AI failed to respond in target language (Heuristic) ---
            # This check is basic - look for keywords indicating inability. Improve as needed.
            fallback_needed = False
            keywords_inability = ['cannot', 'unable', 'only speak english', 'don\'t speak', 'can\'t generate']
            if temp_ai_response:
                # Check if the successful response contains keywords suggesting it failed the language task
                if any(keyword in temp_ai_response.lower() for keyword in keywords_inability) and 'english' in temp_ai_response.lower():
                     logging.warning(f"(Voice Chat SID:{sid}) AI responded but indicated inability for lang {user_lang}. Response: '{temp_ai_response[:100]}...'")
                     fallback_needed = True
                else:
                    # Assume success if response exists and doesn't contain inability keywords
                    ai_response_text = temp_ai_response
                    ai_lang = user_lang # Language matches request
            elif ai_response_text.startswith("[AI"): # If first attempt already failed (blocked/no candidates)
                 pass # Keep the existing error message, fallback not needed for this specific error
            else: # Catch case where temp_ai_response is None or empty after check
                 ai_response_text = "[AI returned empty/invalid response]"
                 fallback_needed = True # Treat empty response as a failure for language task

            # --- Fallback Logic (Attempt 2: English Explanation) ---
            if fallback_needed and user_lang != 'en-US' and user_lang != 'en-GB': # Only fallback if user wasn't speaking English
                logging.info(f"(Voice Chat SID:{sid}) Fallback needed. Generating English explanation...")
                ai_lang = 'en-US' # SET LANGUAGE TO ENGLISH FOR FALLBACK MESSAGE
                # Ask Gemini for a polite English explanation
                # We don't necessarily need history for this fixed explanation
                prompt_fallback = f"""The user asked a question in '{language_name}'. You were unable to answer in that language.
                Respond politely IN ENGLISH explaining this limitation. Briefly apologize and offer to answer in English if they ask again in English.
                Keep it concise for voice output. Start directly with the explanation. Example: "I apologize, I currently can't provide detailed explanations in {language_name}. Would you like me to try answering in English?" """

                try:
                    # Use generate_content for a one-off response, no history needed for this fixed msg
                    fallback_response = genai_model.generate_content(prompt_fallback)
                    log_gemini_response_details(fallback_response, f"voice_chat_{sid}_fallback_eng")
                    if fallback_response.candidates:
                         ai_response_text = fallback_response.text.strip() or "I cannot answer in that language. Please try asking in English."
                    else: # Fallback prompt itself failed/blocked
                         ai_response_text = "I'm currently unable to respond in that language. Please try asking your question in English."
                except Exception as fallback_err:
                     logging.error(f"(Voice Chat SID:{sid}) Error generating English fallback message: {fallback_err}")
                     ai_response_text = "I experienced an issue trying to explain. Please try asking in English."
            # --- End Fallback Logic ---

        except Exception as e_gemini: # Catch broader errors during the AI calls
            logging.error(f"(Voice Chat SID:{sid}) Gemini API error (Lang: {user_lang}): {e_gemini}", exc_info=True)
            ai_response_text = "[Server AI error]"
            ai_lang = user_lang # Keep original lang for generic server error message


        # --- Update AI message doc with final results ---
        # Use the final ai_response_text and ai_lang (which might be en-US if fallback occurred)
        ai_msg_doc = {"role": "AI", "text": ai_response_text, "lang": ai_lang, "timestamp": datetime.utcnow()}

        # 3. --- Save Conversation Turn to MongoDB ---
        # (Save logic remains the same, using the final user_msg_doc and ai_msg_doc)
        try:
            logging.debug(f"(Voice Chat SID:{sid}) Saving turn (User Lang: {user_lang}, AI Lang: {ai_lang})")
            update_result = voice_conversations_collection.update_one(
                 {"user_id": user_id},
                 {"$push": {"messages": {"$each": [user_msg_doc, ai_msg_doc]}},
                  "$setOnInsert": {"user_id": user_id, "username": username, "start_timestamp": now}},
                 upsert=True)
            log_db_update_result(update_result, username, f"voice_chat_{sid}")
        except Exception as e_db:
             logging.error(f"(Voice Chat SID:{sid}) DB save error for user {user_id}: {e_db}", exc_info=True)

        # 4. --- Emit AI Response back to Client ---
        # Payload now includes the final AI text AND the correct language code for TTS
        response_payload = {'user': 'AI', 'text': ai_response_text, 'lang': ai_lang}
        try:
            logging.info(f"(Voice Chat SID:{sid}) Emitting 'receive_ai_voice_text' (Payload Lang: {ai_lang}) Text: '{ai_response_text[:50]}...'")
            emit('receive_ai_voice_text', response_payload, room=sid, namespace='/voice_chat')
            logging.debug(f"(Voice Chat SID:{sid}) Successfully called emit.")
        except Exception as e_emit:
             logging.error(f"(Voice Chat SID:{sid}) CRITICAL ERROR emitting response (Lang: {ai_lang}): {e_emit}", exc_info=True)

        logging.info(f"--- Finished handling 'send_voice_text' (User Lang: {user_lang}) SID:{sid} ---")
    # --- End handle_send_voice_text ---

    logging.info("Voice chat SocketIO handlers registered successfully.")
# --- End register_voice_handlers ---