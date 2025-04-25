# src/sockets/chat_handlers.py

import logging
from flask import request, session
from flask_socketio import emit
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId

# --- Relative Imports ---
# --- Import only socketio placeholder if needed for decorators, otherwise none from extensions ---
# from ..extensions import socketio # Needed if using @socketio.on directly here

# --- Import Utils ---
from ..utils.auth_utils import is_logged_in
from ..utils.api_utils import log_gemini_response_details
from ..utils.db_utils import log_db_update_result

# Central registration function - socketio is passed in
def register_chat_handlers(socketio_instance):

    # == Default Namespace (Report Chat) ==
    @socketio_instance.on('connect')
    def handle_connect():
        logging.info(f"(Report Chat) Client connected: {request.sid}")
        # Add auth check here if needed for this namespace

    @socketio_instance.on('disconnect')
    def handle_disconnect():
        logging.info(f"(Report Chat) Client disconnected: {request.sid}")

    @socketio_instance.on('send_message') # Report chat message
    def handle_send_message(data):
        # --- Access extensions INSIDE handler ---
        from ..extensions import (db, genai_model, safety_settings,
                                 chats_collection, documentation_collection)

        sid = request.sid
        logging.info(f"--- Report Chat Msg START (SID:{sid}) ---")
        # Add auth check if needed

        # Check Services
        if db is None or chats_collection is None or documentation_collection is None:
            logging.error(f"(Report Chat SID:{sid}) DB service/collections unavailable.")
            emit('error', {'message': 'Chat database service unavailable.'}, room=sid)
            return
        if genai_model is None: # Check AI model
             logging.error(f"(Report Chat SID:{sid}) AI service unavailable.")
             emit('error', {'message': 'AI service unavailable.'}, room=sid)
             return

        # Validate data
        if not isinstance(data, dict): emit('error', {'message': 'Invalid format.'}, room=sid); return
        user_msg = data.get('text', '').strip()
        doc_id_str = data.get('documentation_id')
        if not user_msg or not doc_id_str: emit('error', {'message': 'Missing text or context ID.'}, room=sid); return
        try: doc_id = ObjectId(doc_id_str)
        except InvalidId: emit('error', {'message': 'Invalid context ID.'}, room=sid); return

        # --- Save User Message ---
        try:
            user_msg_doc = {"role": "user", "text": user_msg, "timestamp": datetime.utcnow()}
            # Use locally accessed chats_collection
            update_result_user = chats_collection.update_one(
                {"documentation_id": doc_id},
                {"$push": {"messages": user_msg_doc}, "$setOnInsert": {"documentation_id": doc_id, "start_timestamp": datetime.utcnow()}},
                upsert=True)
            log_db_update_result(update_result_user, f"User_ReportChat_{doc_id}", sid)
        except Exception as e: logging.error(f"DB save user msg err (Doc {doc_id}): {e}", exc_info=True)

        # --- Process with AI ---
        ai_resp = "[AI Error]"
        try:
            emit('typing_indicator', {'isTyping': True}, room=sid)
            # Build History (using locally accessed collections)
            history = []
            doc_data = documentation_collection.find_one({"_id": doc_id}, {"report_html": 1})
            if doc_data and "report_html" in doc_data: report_context = doc_data['report_html'][:3000]
            else: report_context = ""
            chat_doc = chats_collection.find_one({"documentation_id": doc_id}, {"messages": {"$slice": -6}})
            if chat_doc and "messages" in chat_doc:
                 for msg in chat_doc["messages"]: history.append({'role': ('model' if msg.get('role') == 'AI' else 'user'), 'parts': [msg.get('text', '')]})
            elif report_context: # Inject context if no history
                 history.extend([{'role':'user', 'parts': [f"Report context:\n{report_context}"]}, {'role':'model', 'parts': ["OK. Ask your question."]}])

            # Call Gemini (using locally accessed model and settings)
            logging.info(f"(Report Chat SID:{sid}) Sending query for doc {doc_id} to Gemini...")
            chat_session = genai_model.start_chat(history=history)
            # Note: safety_settings are often applied globally at model creation,
            # but can sometimes be passed to generate_content/send_message if the API supports it.
            # Assuming they are applied globally for now based on extensions.py init.
            # If needed per-call: response = chat_session.send_message(user_msg, safety_settings=safety_settings)
            response = chat_session.send_message(user_msg)
            log_gemini_response_details(response, f"report_chat_{sid}_{doc_id}")

            # Process response
            if response.candidates: ai_resp = response.text or "[AI empty]"
            elif hasattr(response, 'prompt_feedback'): ai_resp = f"[AI blocked: {response.prompt_feedback.block_reason.name}]"
            else: ai_resp = "[AI blocked/empty]"

            # Save AI Response
            if not ai_resp.startswith("[AI"):
                 try:
                     ai_msg_doc = {"role": "AI", "text": ai_resp, "timestamp": datetime.utcnow()}
                     update_result_ai = chats_collection.update_one({"documentation_id": doc_id},{"$push": {"messages": ai_msg_doc}})
                     log_db_update_result(update_result_ai, f"AI_ReportChat_{doc_id}", sid)
                 except Exception as e: logging.error(f"DB save AI msg err (Doc {doc_id}): {e}", exc_info=True)

        except Exception as e: # Catch errors during AI processing
            logging.error(f"(Report Chat SID:{sid}) AI processing error for doc {doc_id}: {e}", exc_info=True)
            emit('error', {'message': 'Error processing AI request.'}, room=sid) # Keep ai_resp as default error
        finally:
            emit('typing_indicator', {'isTyping': False}, room=sid)
            logging.info(f"(Report Chat SID:{sid}) Emitting AI response for doc {doc_id}.")
            emit('receive_message', {'user': 'AI', 'text': ai_resp}, room=sid)
            logging.info(f"--- Report Chat Msg END (SID:{sid}) ---")


    # == Dashboard Namespace (/dashboard_chat) ==
    @socketio_instance.on('connect', namespace='/dashboard_chat')
    def handle_dashboard_connect():
        # Auth check is primary here
        if not is_logged_in(): return False
        username = session.get('username', 'Unknown'); user_id = session.get('user_id', 'N/A')
        logging.info(f"User '{username}' (ID: {user_id}) connected to /dashboard_chat. SID: {request.sid}")

    @socketio_instance.on('disconnect', namespace='/dashboard_chat')
    def handle_dashboard_disconnect():
        username = session.get('username', 'Unknown'); user_id = session.get('user_id', 'N/A')
        logging.info(f"User '{username}' (ID: {user_id}) disconnected from /dashboard_chat. SID: {request.sid}")

    @socketio_instance.on('send_dashboard_message', namespace='/dashboard_chat')
    def handle_dashboard_chat(data):
        # --- Access extensions INSIDE handler ---
        from ..extensions import db, genai_model, safety_settings, general_chats_collection

        sid = request.sid
        logging.debug(f"--- Dash Chat START (SID:{sid}) ---")
        # Auth & Service Checks
        if not is_logged_in(): emit('error',{'message':'Auth required.'},room=sid,namespace='/dashboard_chat'); return
        if db is None or general_chats_collection is None: emit('error',{'message':'Chat DB unavailable.'},room=sid,namespace='/dashboard_chat'); return
        if genai_model is None: emit('error', {'message': 'AI service unavailable.'}, room=sid, namespace='/dashboard_chat'); return

        # Get user info/message
        username = session.get('username', 'Unknown_DashUser'); user_id_str = session.get('user_id')
        if not user_id_str: emit('error', {'message': 'Session error.'}, room=sid, namespace='/dashboard_chat'); return
        try: user_id = ObjectId(user_id_str)
        except Exception as e: logging.error(f"Invalid user_id: {e}"); emit('error', {'message': 'Session error.'}, room=sid, namespace='/dashboard_chat'); return
        if not isinstance(data, dict): logging.warning(f"Dash Chat Invalid data format from {username}"); return
        user_msg = data.get('text', '').strip()
        if not user_msg: logging.debug(f"Dash Chat empty message from {username}"); return

        logging.info(f"(Dash Chat SID:{sid}) Msg from {username}: '{user_msg[:50]}...'")

        # --- Save User Message ---
        try:
            user_msg_doc = {"role": "user", "text": user_msg, "timestamp": datetime.utcnow()}
            # Use locally accessed collection
            update_res = general_chats_collection.update_one(
                 {"user_id": user_id},
                 {"$push": {"messages": user_msg_doc},
                  "$setOnInsert": {"user_id": user_id, "username": username, "start_timestamp": datetime.utcnow()}}, # Upsert in case it's the first message
                  upsert=True)
            log_db_update_result(update_res, username, f"dash_chat_{sid}")
        except Exception as e: logging.error(f"DB save dash user msg err ({username}): {e}", exc_info=True)

        # --- Process with AI ---
        ai_resp="[AI Error]"
        try:
            emit('typing_indicator',{'isTyping':True},room=sid,namespace='/dashboard_chat')
            # Build History (using locally accessed collection)
            history=[];
            chat_doc = general_chats_collection.find_one({"user_id":user_id}, {"messages": {"$slice": -8}})
            if chat_doc and "messages" in chat_doc:
                for msg in chat_doc["messages"]: history.append({'role':('model' if msg.get('role')=='AI'else 'user'),'parts':[msg.get('text', '')]})

            # Call Gemini (using locally accessed model and settings)
            logging.info(f"(Dash Chat SID:{sid}) Sending query for {username} to Gemini...")
            chat_session = genai_model.start_chat(history=history)
            # Assuming safety settings applied globally
            response = chat_session.send_message(user_msg)
            log_gemini_response_details(response, f"dash_chat_{sid}")

            # Process response
            if response.candidates: ai_resp=response.text or "[AI empty]"
            elif hasattr(response, 'prompt_feedback'): ai_resp = f"[AI blocked: {response.prompt_feedback.block_reason.name}]"
            else: ai_resp="[AI blocked/empty]"

            # Save AI Response (using locally accessed collection)
            if not ai_resp.startswith("[AI"):
                 try:
                     ai_msg_doc = {"role": "AI", "text": ai_resp, "timestamp": datetime.utcnow()}
                     update_res_ai = general_chats_collection.update_one( {"user_id":user_id}, {"$push":{"messages":ai_msg_doc}})
                     log_db_update_result(update_res_ai, f"AI_DashChat_{username}", sid)
                 except Exception as e: logging.error(f"DB save dash AI resp err ({username}): {e}", exc_info=True)

        except Exception as e: # Catch errors during AI processing
            logging.error(f"Dash Chat AI processing error ({username}): {e}", exc_info=True)
            emit('error',{'message':'Server error.'},room=sid,namespace='/dashboard_chat')
        finally:
            emit('typing_indicator',{'isTyping':False},room=sid,namespace='/dashboard_chat')
            logging.info(f"(Dash Chat SID:{sid}) Emitting AI response to {username}.")
            emit('receive_dashboard_message',{'user':'AI','text':ai_resp},room=sid,namespace='/dashboard_chat')
            logging.debug(f"--- Dash Chat END (SID:{sid}) ---")

    logging.info("Default and Dashboard chat handlers registered.")