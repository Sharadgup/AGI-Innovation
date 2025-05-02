# src/extensions.py
import logging
import google.generativeai as genai
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError, OperationFailure
from flask_socketio import SocketIO
from flask_dance.contrib.google import make_google_blueprint
import time # Import time for potential retry delay (optional)

# --- Relative Import for DB Utilities ---
try:
    from .utils.db_utils import ensure_indexes, log_db_update_result
    logging.debug("Successfully imported db_utils from .utils")
except ImportError as e:
    logging.critical(f"Failed relative import of db_utils in extensions.py: {e}", exc_info=True)
    # Define dummy functions if import fails to prevent later crashes, but log critically
    def ensure_indexes(db): logging.error("ensure_indexes function unavailable."); pass # type: ignore # noqa F811
    def log_db_update_result(update_result, username="N/A", identifier="N/A"): logging.error("log_db_update_result unavailable."); pass # type: ignore # noqa F811
# ---------------------------------------

# --- Initialize Extension Placeholders ---
# ... (keep all placeholder initializations as before: socketio, db_client=None, db=None, collections=None, etc.) ...
socketio = SocketIO(); logging.debug("SocketIO placeholder created.")
db_client = None; db = None; logging.debug("MongoDB placeholders set to None.")
registrations_collection = None; input_prompts_collection = None; documentation_collection = None; chats_collection = None; general_chats_collection = None; education_chats_collection = None; healthcare_chats_collection = None; construction_agent_interactions_collection = None; pdf_analysis_collection = None; pdf_chats_collection = None; voice_conversations_collection = None; analysis_uploads_collection = None; news_articles_collection = None; logging.debug("Collection placeholders set to None.")
genai_model = None; safety_settings = []; logging.debug("Gemini placeholders set.")
google_bp = None; google_enabled = False; logging.debug("Google OAuth placeholders set.")
# --- End Placeholders ---


# --- Main Initialization Function ---
def init_app(app):
    logging.debug("Executing extensions.init_app(app)...")
    global db_client, db, socketio, genai_model, google_bp, google_enabled, safety_settings
    global registrations_collection, input_prompts_collection, documentation_collection, chats_collection, general_chats_collection, education_chats_collection, healthcare_chats_collection, construction_agent_interactions_collection, pdf_analysis_collection, pdf_chats_collection, voice_conversations_collection, analysis_uploads_collection, news_articles_collection

    # --- Initialize SocketIO ---
    # ... (keep SocketIO init code as before) ...
    logging.debug("Initializing SocketIO...")
    try:
        socketio.init_app( app, async_mode=app.config.get('SOCKETIO_ASYNC_MODE', 'eventlet'), cors_allowed_origins=app.config.get('CORS_ALLOWED_ORIGINS', '*'), ping_timeout=app.config.get('SOCKETIO_PING_TIMEOUT', 20), ping_interval=app.config.get('SOCKETIO_PING_INTERVAL', 10) )
        logging.info(f"SocketIO initialized. Mode: {app.config.get('SOCKETIO_ASYNC_MODE', 'eventlet')}, Origins: {app.config.get('CORS_ALLOWED_ORIGINS', '*')}")
    except Exception as e_sock: logging.error(f"Failed to initialize SocketIO: {e_sock}", exc_info=True)


    # --- Initialize MongoDB ---
    logging.debug("Initializing MongoDB connection...")
    # --- Use values from config ---
    mongo_uri = app.config.get("MONGODB_URI")
    db_name = app.config.get("MONGODB_DB_NAME")
    # --- -------------------- ---

    # --- !!! REMOVE HARDCODED VALUES !!! ---
    # mongo_uri = "YOUR_ACTUAL_MONGODB_URI_STRING_HERE" # REMOVE OR COMMENT OUT
    # db_name = "YOUR_ACTUAL_DATABASE_NAME_HERE"       # REMOVE OR COMMENT OUT
    # --- ----------------------------- ---


    if not mongo_uri:
        logging.critical("MongoDB connection skipped: MONGODB_URI not found in config.")
        db_client = None; db = None
    elif not db_name:
        logging.critical("MongoDB connection skipped: MONGODB_DB_NAME not found in config.")
        db_client = None; db = None
    else:
        # --- Enhanced Connection Attempt ---
        max_retries = 1 # Number of retries (set to 0 to disable retry)
        retry_delay = 3 # Seconds between retries

        for attempt in range(max_retries + 1):
            try:
                masked_uri = mongo_uri.split('@')[-1] if '@' in mongo_uri else mongo_uri
                logging.info(f"[Attempt {attempt+1}/{max_retries+1}] Connecting to MongoDB (URI ends '...{masked_uri[-20:]}', DB: '{db_name}')...")

                # Add direct_connection=False if sometimes needed for specific proxies/setups, but usually not required.
                db_client = MongoClient(
                    mongo_uri,
                    serverSelectionTimeoutMS=10000, # Timeout for server selection
                    connectTimeoutMS=10000,         # Initial connection timeout
                    socketTimeoutMS=15000,          # Timeout for operations on socket
                    appname="VisionAIStudio"
                    # directConnection=False # Uncomment only if specific network issues suggest it
                )

                # Verify connection with a ping (more reliable than ismaster sometimes)
                logging.debug("Pinging MongoDB server (command: ping)...")
                db_client.admin.command('ping') # Requires auth if enforced
                logging.info("MongoDB server ping successful.")

                # Get DB object
                db = db_client[db_name]
                logging.info(f"MongoDB connected successfully. Database '{db_name}' object obtained.")

                # Assign Collections
                logging.debug("Assigning MongoDB collection objects...")
                registrations_collection = db["registrations"] # Add all collection assignments here...
                input_prompts_collection = db["input_prompts"]; documentation_collection = db["documentation"]; chats_collection = db["chats"]; general_chats_collection = db["general_chats"]; education_chats_collection = db["education_chats"]; healthcare_chats_collection = db["healthcare_chats"]; construction_agent_interactions_collection = db["construction_agent_interactions"]; pdf_analysis_collection = db["pdf_analysis"]; pdf_chats_collection = db["pdf_chats"]; voice_conversations_collection = db["voice_conversations"]; analysis_uploads_collection = db["analysis_uploads"]; news_articles_collection = db["news_articles"]; email_log_collection = db["email_logs"]; agent_state_collection = db["agent_state"]
                logging.info("MongoDB Collections assigned.")

                # Ensure Indexes
                logging.debug("Ensuring database indexes...")
                try: ensure_indexes(db)
                except Exception as index_err: logging.error(f"Error during index creation: {index_err}", exc_info=True)

                # If successful, break the retry loop
                break

            # --- Specific Error Handling with Clearer Messages ---
            except ConfigurationError as e_config:
                logging.critical(f"[Attempt {attempt+1}] MongoDB Configuration Error: {e_config}. Please check the MONGODB_URI format in your .env file.", exc_info=False)
                db_client = None; db = None; break # No point retrying config error
            except OperationFailure as e_auth:
                 logging.critical(f"[Attempt {attempt+1}] MongoDB Operation Failure: {e_auth}. Check DB credentials, permissions, and 'authSource' in URI.", exc_info=False)
                 db_client = None; db = None; break # No point retrying auth error
            except ConnectionFailure as e_conn:
                logging.error(f"[Attempt {attempt+1}] MongoDB Connection Failure: {e_conn}. Check host/port, network, firewall, server status, Atlas IP Whitelist. Retrying in {retry_delay}s..." if attempt < max_retries else "", exc_info=False)
                db_client = None; db = None
                if attempt >= max_retries:
                    logging.critical("MongoDB connection failed after all retries.")
                    break # Exit loop after final attempt
                else:
                    time.sleep(retry_delay) # Wait before retrying connection failure
            except Exception as e_mongo:
                logging.critical(f"[Attempt {attempt+1}] Unexpected MongoDB Error: {e_mongo}", exc_info=True)
                db_client = None; db = None; break # Exit loop on unexpected error
        # --- End Connection Attempt Loop ---
    # --- End MongoDB Initialization ---


    # --- Initialize Google Gemini ---
    # ... (keep Gemini init code as before) ...
    logging.debug("Initializing Google Gemini model...")
    api_key = app.config.get("GEMINI_API_KEY"); model_name = app.config.get("GEMINI_MODEL_NAME", "gemini-1.5-flash")
    if api_key:
        try:
            genai.configure(api_key=api_key); safety_settings = [ {"category": cat, "threshold": "BLOCK_MEDIUM_AND_ABOVE"} for cat in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"] ]; genai_model = genai.GenerativeModel(model_name, safety_settings=safety_settings); logging.info(f"Gemini model '{model_name}' initialized."); logging.debug(f"Safety settings: {safety_settings}")
        except Exception as e_gemini: logging.error(f"Error initializing Gemini: {e_gemini}", exc_info=True); genai_model = None; safety_settings = []
    else: logging.warning("GEMINI_API_KEY missing."); genai_model = None; safety_settings = []


    # --- Initialize Google OAuth ---
    # ... (keep Google OAuth init code as before) ...
    logging.debug("Initializing Google OAuth...")
    google_oauth_client_id = app.config.get("GOOGLE_OAUTH_CLIENT_ID"); google_oauth_client_secret = app.config.get("GOOGLE_OAUTH_CLIENT_SECRET"); google_redirect_uri = app.config.get("GOOGLE_REDIRECT_URI")
    google_enabled = bool(google_oauth_client_id and google_oauth_client_secret and google_redirect_uri)
    if google_enabled:
        try:
            logging.info(f"Creating Google OAuth Blueprint. Redirect URI: {google_redirect_uri}"); google_bp = make_google_blueprint( client_id=google_oauth_client_id, client_secret=google_oauth_client_secret, scope=["openid", "email", "profile"], redirect_to="auth.google_auth_callback", offline=False, redirect_uri=google_redirect_uri ); logging.info("Google OAuth Blueprint object created.")
        except Exception as bp_error: logging.error(f"Failed Google OAuth Blueprint: {bp_error}", exc_info=True); google_enabled = False; google_bp = None
    else: missing = [item for item, value in [("CLIENT_ID", google_oauth_client_id), ("CLIENT_SECRET", google_oauth_client_secret), ("REDIRECT_URI", google_redirect_uri)] if not value]; logging.warning(f"Google OAuth disabled - missing: {', '.join(missing)}"); google_bp = None


    logging.debug("extensions.init_app(app) finished.")
# --- End Initialization Function ---