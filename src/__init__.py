# src/__init__.py

import os
import sys
import logging
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from .routes import agent_routes

# --- Path Setup & Environment Loading ---
# Get the directory containing this __init__.py file (src/)
src_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (the project root)
project_root = os.path.dirname(src_dir)

# Load environment variables from .env file located in the project root
env_path = os.path.join(project_root, '.env')
if os.path.exists(env_path):
    # Use load_dotenv correctly - it loads into os.environ
    load_dotenv(dotenv_path=env_path, override=True) # override=True ensures .env takes precedence
    logging.debug(f"Loaded environment variables from: {env_path}")
else:
     logging.warning(f".env file not found at {env_path}. Environment variables might be missing.")

# --- Initial Imports (Relative within src) ---
# These imports happen when 'src' is first imported
try:
    logging.debug("Importing config, extensions, routes, sockets within src/__init__.py...")
    # Import configuration first, as extensions might depend on it implicitly via os.environ
    from .config import Config

    # Import the extensions module (this initializes placeholder variables)
    from . import extensions

    # Import route modules (containing blueprint definitions)
    from .routes import (auth_routes, core_routes, agent_routes,
                         data_analyzer_routes, pdf_routes, news_routes,
                         voice_routes)

    # Import socket handler registration modules
    from .sockets import chat_handlers, pdf_chat_handlers, voice_handlers
    logging.debug("Successfully imported local modules in src/__init__.py.")
except ImportError as e:
    # Log critical import errors during package initialization
    logging.critical(f"Failed to import local modules within src/__init__.py: {e}", exc_info=True)
    # Log sys.path for debugging import resolution issues
    logging.critical(f"sys.path at time of error: {sys.path}")
    raise # Re-raise the error to stop execution if essential imports fail
# --- End Initial Imports ---


# --- Application Factory Function ---
def create_app(config_class=Config):
    """
    Factory function to create and configure the Flask application instance.
    Handles app creation, configuration loading, extension initialization,
    blueprint registration, and SocketIO handler registration.
    """
    logging.debug("Executing create_app factory function...")

    # Create Flask app instance
    # template_folder and static_folder paths are relative to the 'src' directory
    app = Flask(__name__,
                instance_relative_config=False, # Config is loaded from object/file, not instance folder
                template_folder='templates',
                static_folder='static')

    # Load configuration from the specified config class (defaults to Config)
    app.config.from_object(config_class)
    logging.debug(f"App created, configuration loaded from {config_class.__name__}.")

    # Apply ProxyFix Middleware FIRST if configured (essential for deployments behind proxies)
    if app.config.get('USE_PROXYFIX', True): # Default to True unless explicitly disabled
        # Configure the number of proxies expected (adjust x_for, x_proto etc. as needed)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
        logging.info("ProxyFix middleware applied.")
    else:
        logging.info("ProxyFix middleware is disabled via configuration.")

    # Initialize Flask extensions with the app instance
    # This call runs extensions.init_app(app), connecting DB, creating models, etc.
    logging.debug("Initializing Flask extensions via extensions.init_app(app)...")
    try:
        extensions.init_app(app)
        logging.info("Flask extensions initialized successfully.")
    except Exception as ext_err:
        logging.critical(f"CRITICAL ERROR during extension initialization: {ext_err}", exc_info=True)
        # Depending on the severity, you might want to exit or prevent app run
        # For now, we continue, but services depending on failed extensions won't work.
        pass

    # Ensure Upload Folders Exist (using paths from app config)
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        analysis_folder = app.config['ANALYSIS_UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            logging.info(f"Created upload directory: {upload_folder}")
        if not os.path.exists(analysis_folder):
            os.makedirs(analysis_folder)
            logging.info(f"Created analysis upload directory: {analysis_folder}")
    except KeyError as key_err:
         logging.error(f"Upload folder configuration key missing: {key_err}")
    except Exception as folder_err:
         logging.error(f"Error creating upload folders: {folder_err}", exc_info=True)


    # Register Blueprints (Modular route definitions)
    logging.debug("Registering application blueprints...")
    try:
        # Register core blueprints
        app.register_blueprint(auth_routes.bp) # Handles basic auth (login/register/logout)
        app.register_blueprint(core_routes.bp) # Handles dashboard, landing page, etc.

        # Register feature-specific blueprints with URL prefixes
        app.register_blueprint(agent_routes.bp, url_prefix='/agent')
        app.register_blueprint(data_analyzer_routes.bp, url_prefix='/data')
        app.register_blueprint(pdf_routes.bp, url_prefix='/pdf')
        app.register_blueprint(news_routes.bp, url_prefix='/news')
        app.register_blueprint(voice_routes.bp, url_prefix='/voice')
        app.register_blueprint(agent_routes.bp, url_prefix='/agent')

        # --- Conditionally register Google OAuth Blueprint ---
        # Check if the blueprint object exists in extensions (was created successfully)
        # and if google integration is marked as enabled
        if extensions.google_bp is not None and extensions.google_enabled:
            # Register the blueprint created by Flask-Dance
            # The url_prefix here combines with the internal routes of the google_bp
            # (e.g., /login/google, /login/google/authorized defined by Flask-Dance)
            app.register_blueprint(extensions.google_bp, url_prefix="/login")
            logging.info(f"Registered Google OAuth blueprint at prefix '/login'.")
        else:
            logging.warning("Google OAuth blueprint not registered (check configuration/credentials in extensions.init_app).")
        # --- End Conditional Registration ---

        logging.info("Flask Blueprints registered successfully.")
    except Exception as bp_err:
         logging.error(f"Error occurred during Blueprint registration: {bp_err}", exc_info=True)


    # Register SocketIO Event Handlers
    logging.debug("Registering SocketIO event handlers...")
    try:
        # Pass the initialized socketio instance from extensions to the registration functions
        chat_handlers.register_chat_handlers(extensions.socketio)
        pdf_chat_handlers.register_pdf_chat_handlers(extensions.socketio)
        voice_handlers.register_voice_handlers(extensions.socketio)
        logging.info("SocketIO event handlers registered successfully.")
    except Exception as sock_err:
        logging.error(f"Error occurred during SocketIO handler registration: {sock_err}", exc_info=True)


    # Optional: Add a simple health check endpoint
    @app.route('/health')
    def health_check():
        # Could add checks here, e.g., db.command('ping')
        # For now, just indicates the app is running
        return "Application Alive", 200


    # Final log message before returning the app instance
    logging.info("Flask application factory setup complete.")
    return app

# --- Optional: Clean up sys.path modification if it was done here ---
# If the temporary path modification at the top was needed and uncommented:
# try:
#     sys.path = original_sys_path
#     logging.debug("Restored original sys.path after src/__init__.py execution.")
# except NameError:
#      pass # In case original_sys_path wasn't defined due to errors
# --- Usually safer to let run.py manage the initial path setup ---