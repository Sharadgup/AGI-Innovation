import logging
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId # Keep ObjectId here if used for session ID conversion maybe?

# --- Authentication Helpers ---
def is_logged_in():
    """Checks if a user_id exists in the session."""
    return 'user_id' in session

def login_user(user_doc):
    """Logs in a user by setting session variables."""
    session.clear()
    user_id = str(user_doc['_id'])
    username = user_doc.get('username') or user_doc.get('name') or f"User_{user_id[:6]}"
    login_method = user_doc.get('login_method', 'password')

    session['user_id'] = user_id
    session['username'] = username
    session['login_method'] = login_method
    logging.info(f"User '{session['username']}' (ID: {user_id}) logged in via {login_method}.")

def hash_password(password):
    """Generates a secure hash for a password."""
    return generate_password_hash(password)

def verify_password(stored_hash, provided_password):
    """Verifies a provided password against a stored hash."""
    if not stored_hash or not provided_password:
        return False
    return check_password_hash(stored_hash, provided_password)

# You might add decorators here later, e.g., @login_required
# from functools import wraps
# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if not is_logged_in():
#             flash("Please log in to access this page.", "warning")
#             return redirect(url_for('auth.login')) # Assuming 'auth' is the blueprint name for auth_routes
#         return f(*args, **kwargs)
#     return decorated_function