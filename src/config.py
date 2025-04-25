# src/config.py

import os
import logging # Use logging instead of print for consistency
from datetime import timedelta
from dotenv import load_dotenv

# --- Load Environment Variables ---
# Calculate the path to the .env file expected in the project root directory
# os.path.dirname(__file__) gives the directory of config.py (src/)
# os.path.dirname(...) gives the parent directory (project root)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(project_root, '.env')

# Attempt to load the .env file
if os.path.exists(dotenv_path):
    # override=True ensures that variables in .env overwrite existing environment variables
    load_dotenv(dotenv_path=dotenv_path, override=True)
    # Use logging to indicate success
    logging.info(f"Configuration loaded from: {dotenv_path}")
else:
    # Warn if the .env file is missing
    logging.warning(f".env file not found at expected location: {dotenv_path}. Relying on environment variables.")
# --- End Environment Loading ---


# --- Configuration Class ---
class Config:
    """Base configuration settings for the Flask application."""

    # --- Flask Core Settings ---
    # WARNING: Set a strong, unique secret key in your .env file for production!
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-only-not-for-production!')

    # Debug Mode: Enable for development (detailed errors, auto-reload*), disable for production.
    # *Note: Auto-reload might conflict with async modes like eventlet. Controlled by use_reloader in run.py.
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    # Server Binding: Use 0.0.0.0 to listen on all interfaces (e.g., inside Docker), 127.0.0.1 for local only.
    HOST = os.environ.get('FLASK_HOST', '127.0.0.1')
    PORT = int(os.environ.get('FLASK_PORT', 5000))

    # ProxyFix: Enable if deploying behind a reverse proxy (Nginx, Apache, Load Balancer)
    # to correctly handle headers like X-Forwarded-For, X-Forwarded-Proto.
    USE_PROXYFIX = os.environ.get('USE_PROXYFIX', 'True').lower() in ('true', '1', 't')
    # --- End Flask Core ---


    # --- File Upload Settings ---
    # Absolute path ensures it works regardless of where the script is run from.
    UPLOAD_FOLDER = os.path.abspath(os.path.join(project_root, 'uploads'))
    ALLOWED_EXTENSIONS = {'pdf'} # For general PDF uploads
    # Subdirectory for data analysis uploads within the main upload folder.
    ANALYSIS_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'analysis_data')
    ALLOWED_ANALYSIS_EXTENSIONS = {'xlsx', 'csv'} # For data analysis files
    # Optional: Set a maximum file upload size (e.g., 100MB)
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_MB', 100)) * 1024 * 1024
    # --- End File Uploads ---


    # --- MongoDB Settings ---
    # CRITICAL: Ensure these match your .env file and MongoDB setup.
    MONGODB_URI = os.getenv("MONGODB_URI")
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME")
    # --- End MongoDB ---


    # --- Gemini API Settings ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash") # Allow override via env
    # --- End Gemini API ---


    # --- World News API Settings ---
    _fallback_news_key = "MTDrUuB40hsh8vr68q7KDqV9PysQ4czz" # Keep fallback local
    WORLD_NEWS_API_KEY = os.getenv("WORLD_NEWS_API_KEY")
    # Log if fallback is used (only logs once when config module is loaded)
    if not WORLD_NEWS_API_KEY and not os.getenv("CI"): # Avoid logging fallback in CI envs
        logging.warning("!!! WORLD_NEWS_API_KEY not set. Using internal fallback key for testing ONLY. !!!")
        WORLD_NEWS_API_KEY = _fallback_news_key
    # Define the endpoint here for consistency
    WORLD_NEWS_API_ENDPOINT = "https://api.worldnewsapi.com/search-news"
    # --- End World News API ---


    # --- Google OAuth Settings ---
    # Load credentials from environment
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

    # OAUTHLIB Handling for HTTP vs HTTPS during development/testing
    # Set based on FLASK_DEBUG usually. Allows OAuth flow over HTTP for local dev.
    # WARNING: MUST be '0' (or False) in production over HTTPS.
    OAUTHLIB_INSECURE_TRANSPORT = '1' if DEBUG else '0'
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = OAUTHLIB_INSECURE_TRANSPORT # Set env var used by oauthlib

    # Determine the correct Google Redirect URI based on environment
    # Set ENV_MODE=production in your production environment/.env
    ENV_MODE = os.getenv("ENV_MODE", "development").lower()
    # Define your specific URIs here
    _PROD_REDIRECT_URI = "https://5000-idx-ai-note-system-1744087101492.cluster-a3grjzek65cxex762e4mwrzl46.cloudworkstations.dev/login/google/authorized" # Example Production HTTPS URL
    _DEV_REDIRECT_URI_HTTP = "http://127.0.0.1:5000/login/google/authorized" # Local HTTP
    # _DEV_REDIRECT_URI_HTTPS = "https://127.0.0.1:5000/login/google/authorized" # Local HTTPS if using mkcert/etc

    if ENV_MODE == "production":
         GOOGLE_REDIRECT_URI = _PROD_REDIRECT_URI
         # Enforce secure session cookies in production
         SESSION_COOKIE_SECURE = True
         SESSION_COOKIE_HTTPONLY = True
         SESSION_COOKIE_SAMESITE = 'Lax'
    else: # Development mode
         GOOGLE_REDIRECT_URI = _DEV_REDIRECT_URI_HTTP # Default to HTTP for dev
         # Allow non-secure session cookies in development over HTTP
         SESSION_COOKIE_SECURE = False
         SESSION_COOKIE_HTTPONLY = True
         SESSION_COOKIE_SAMESITE = 'Lax' # Or 'None' if needed, but requires Secure=True

    # Log the determined redirect URI for verification
    logging.debug(f"Google OAuth Redirect URI determined ({ENV_MODE} mode): {GOOGLE_REDIRECT_URI}")
    # --- End Google OAuth ---


    # --- SocketIO Settings ---
    # Allowed origins for CORS. Use "*" for development ONLY. Be specific in production.
    # Example Production: CORS_ALLOWED_ORIGINS = ["https://your_frontend_domain.com", "https://www.your_frontend_domain.com"]
    CORS_ALLOWED_ORIGINS = "*" if DEBUG else os.getenv("CORS_ALLOWED_ORIGINS", None) # Require explicit setting in prod env
    if CORS_ALLOWED_ORIGINS == "*" and not DEBUG:
         logging.warning("SECURITY WARNING: CORS_ALLOWED_ORIGINS is '*' in non-DEBUG mode. Restrict allowed origins in production!")
    elif CORS_ALLOWED_ORIGINS is None and not DEBUG:
         logging.warning("CORS_ALLOWED_ORIGINS not set in production environment. SocketIO connections may fail.")

    SOCKETIO_PING_TIMEOUT = int(os.getenv("SOCKETIO_PING_TIMEOUT", 20))
    SOCKETIO_PING_INTERVAL = int(os.getenv("SOCKETIO_PING_INTERVAL", 10))
    SOCKETIO_ASYNC_MODE = os.getenv("SOCKETIO_ASYNC_MODE", 'eventlet') # Ensure consistency with run.py patching
    # --- End SocketIO ---


    # --- Flask Session Settings ---
    # Configure session lifetime
    PERMANENT_SESSION_LIFETIME = timedelta(days=int(os.getenv("SESSION_LIFETIME_DAYS", 7)))
    # --- End Session ---


# --- Optional: Environment-Specific Configurations ---
# You can create subclasses for different environments if needed

# class ProductionConfig(Config):
#     DEBUG = False
#     USE_PROXYFIX = True
#     SESSION_COOKIE_SECURE = True
#     # Explicitly set allowed origins if not using environment variable approach above
#     # CORS_ALLOWED_ORIGINS = ["https://your_domain.com"]

# class DevelopmentConfig(Config):
#     DEBUG = True
#     # SESSION_COOKIE_SECURE = False # Already handled by logic above based on DEBUG

# --- End Optional Configurations ---