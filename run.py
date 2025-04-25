# run.py
import eventlet
eventlet.monkey_patch()
import logging
import traceback
import os
# import sys # Not needed if editable install works

# Configure logging early
# ... (logging config as before) ...
logging.basicConfig( level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] [%(funcName)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S' )
logging.getLogger("engineio.server").setLevel(logging.WARNING) # etc.

# --- Pre-load config check (Optional but recommended) ---
try:
    from src.config import Config
    MONGODB_URI_CHECK = Config.MONGODB_URI
    MONGODB_DB_NAME_CHECK = Config.MONGODB_DB_NAME
    if not MONGODB_URI_CHECK or not MONGODB_DB_NAME_CHECK:
         logging.critical("PRE-CHECK FAILED: MONGODB_URI or MONGODB_DB_NAME missing in environment/.env.")
         # Keep exit(1) here, as missing config is different from connection failure
         exit(1)
    logging.info("Pre-check passed: MONGODB_URI and MONGODB_DB_NAME seem to be loaded.")
except Exception as e_pre:
     logging.critical(f"Error during configuration pre-check: {e_pre}", exc_info=True)
     exit(1)
# --- --------------------------------------------------- ---

# Import Application Factory and Core Extensions
logging.debug("Attempting to import create_app from src package...")
try:
    from src import create_app
    from src.extensions import socketio, db_client, db # Import db_client and db
    logging.info("Successfully imported create_app and core extensions.")
except ImportError as e:
    logging.critical(f"!!! Failed to import from src package: {e}", exc_info=True)
    exit(1)
except Exception as e_other:
    logging.critical(f"!!! An unexpected error occurred during initial imports: {e_other}", exc_info=True)
    exit(1)

# Create the Flask App Instance
logging.debug("Attempting to create Flask app instance via create_app()...")
try:
    app = create_app()
    logging.info("Flask app instance created successfully.")
except Exception as e_create:
    logging.critical(f"!!! Failed during Flask app creation process: {e_create}", exc_info=True)
    exit(1)

# Main Execution Block
if __name__ == '__main__':
    logging.debug("Running main execution block (__name__ == '__main__')...")

    # --- Sanity Checks Before Running Server ---
    logging.debug("Performing pre-run sanity checks...")

    # --- MODIFIED MONGODB CHECK ---
    if db_client is None or db is None:
        # Log the critical failure, but DO NOT exit.
        logging.critical("="*60)
        logging.critical("CRITICAL WARNING: MongoDB connection FAILED during startup.")
        logging.critical("  Check previous logs from 'src/extensions.py' for specific")
        logging.critical("  ConnectionFailure, OperationFailure, or ConfigurationError details.")
        logging.critical("  Verify MONGODB_URI, credentials, network access, firewall, and DB server status.")
        logging.critical("  DATABASE FEATURES WILL NOT WORK.")
        logging.critical("="*60)
        # exit(1) # <<<<<<<<<<<<<<< COMMENTED OUT THIS LINE
    else:
        logging.info("MongoDB connection check passed post-app creation (db_client/db objects exist).")
    # --- END MODIFIED CHECK ---

    # ... (Secret Key Check, Gemini Check as before) ...
    secret = app.config.get('SECRET_KEY') # etc...
    from src.extensions import genai_model # Check model
    if genai_model is None: logging.warning("Gemini AI Model check: Model is None.")
    else: logging.info("Gemini AI Model check passed.")


    # --- Get Server Run Configuration ---
    # ... (Get host, port, debug_mode as before) ...
    host = app.config.get('HOST', '127.0.0.1'); port = app.config.get('PORT', 5000); debug_mode = app.config.get('DEBUG', False); use_reloader_config = False;
    logging.info(f"Server Run Configuration - Host: {host}, Port: {port}, Debug: {debug_mode}, Reloader: {use_reloader_config}")


    # --- Start the Development Server ---
    logging.info(f"Attempting to start Flask-SocketIO server via socketio.run() on http://{host}:{port}...")
    # ... (try/except block for socketio.run as before) ...
    try:
        socketio.run( app, host=host, port=port, debug=debug_mode, use_reloader=use_reloader_config )
    except KeyboardInterrupt: logging.info("Server stopped via KeyboardInterrupt.")
    except OSError as os_err: logging.critical(f"Server startup failed (OS error): {os_err}", exc_info=True); exit(1)
    except Exception as e_run: logging.critical(f"Unexpected server error: {e_run}", exc_info=True); exit(1)


    logging.info("Server execution finished.")
# --- End Main Execution Guard ---