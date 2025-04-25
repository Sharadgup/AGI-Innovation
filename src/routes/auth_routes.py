# src/routes/auth_routes.py
import logging
from datetime import datetime
# --- Keep standard imports ---
from flask import (Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify)
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from flask_dance.contrib.google import google

# --- Import only the main db/extensions object if needed for setup, OR import nothing from extensions here ---
# from ..extensions import db, google_bp, google_enabled # OK to import placeholders needed globally
# --- DO NOT import specific collections like input_prompts_collection here ---

# --- Import Utils ---
from ..utils.auth_utils import is_logged_in, login_user, hash_password, verify_password

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    # --- Access collections INSIDE the function using current_app or imported db ---
    from ..extensions import db, google_enabled # Import status needed for template

    # --- Check login status ---
    if is_logged_in():
        return redirect(url_for('core.dashboard'))

    google_login_status = google_enabled # Use the imported status

    if request.method == 'POST':
        # --- Check DB connection ---
        if db is None: # Check if DB connection failed in init_app
            flash("Database service is currently unavailable. Please try again later.", "danger")
            return render_template('register.html', now=datetime.utcnow(), google_login_enabled=google_login_status)

        # --- Access Collection ---
        registrations_collection = db.registrations # Access collection via db proxy

        # --- Get Form Data ---
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '') # Get password here
        confirm = request.form.get('confirm_password', '')

        # --- Basic Validation --- # Added full validation checks back
        if not username or not password:
             flash("Username and password are required.", "warning")
             return render_template('register.html', username=username, now=datetime.utcnow(), google_login_enabled=google_login_status)
        if password != confirm:
             flash("Passwords do not match.", "warning")
             return render_template('register.html', username=username, now=datetime.utcnow(), google_login_enabled=google_login_status)
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "warning")
            return render_template('register.html', username=username, now=datetime.utcnow(), google_login_enabled=google_login_status)

        # --- Process Registration ---
        hashed_pw = hash_password(password)
        try:
            user_doc = {
               "username": username,
               "password_hash": hashed_pw,
               "created_at": datetime.utcnow(),
               "login_method": "password"
            }
            registrations_collection.insert_one(user_doc)
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('auth.login'))

        except DuplicateKeyError:
            flash("Username already exists. Please choose a different one or log in.", "danger")
            # Render template after DuplicateKeyError
            return render_template('register.html', username=username, now=datetime.utcnow(), google_login_enabled=google_login_status) # Added return

        except Exception as e:
            logging.error(f"Registration error for user '{username}': {e}", exc_info=True)
            flash("An unexpected error occurred during registration. Please try again.", "danger")
            # Render template after general Exception
            return render_template('register.html', username=username, now=datetime.utcnow(), google_login_enabled=google_login_status) # Added return

    # GET request
    return render_template('register.html', now=datetime.utcnow(), google_login_enabled=google_login_status)


@bp.route('/login', methods=['GET', 'POST'])
def login():
     # --- Access extensions INSIDE the function ---
     from ..extensions import db, google_enabled

     if is_logged_in():
        return redirect(url_for('core.dashboard'))

     google_login_status = google_enabled # Use imported status

     if request.method == 'POST':
         if db is None: # Check db connection
             flash("Database service is currently unavailable. Please try again later.", "danger") # Added flash
             return render_template('login.html', now=datetime.utcnow(), google_login_enabled=google_login_status)

         registrations_collection = db.registrations # Access via db proxy
         username = request.form.get('username', '').strip() # Get username from form
         password = request.form.get('password', '') # Get password from form

         # --- Added Validation ---
         if not username or not password:
            flash("Both username and password are required.", "warning")
            return render_template('login.html', username=username, now=datetime.utcnow(), google_login_enabled=google_login_status)

         try:
             user = registrations_collection.find_one({"username": username})
             # Verify user exists and password is correct
             if user and user.get('password_hash') and verify_password(user['password_hash'], password):
                 login_user(user) # Log the user in
                 # Redirect to dashboard after successful login
                 return redirect(url_for('core.dashboard')) # Redirect inside the if
             else:
                 flash("Invalid username or password.", "danger") # Flash error for invalid credentials
                 # Return template immediately after flash
                 return render_template('login.html', username=username, now=datetime.utcnow(), google_login_enabled=google_login_status)

         except Exception as e:
              logging.error(f"Login error for user '{username}': {e}", exc_info=True) # Log error
              flash("An unexpected error occurred during login.", "danger") # Flash generic error
              # Render template after Exception
              return render_template('login.html', username=username, now=datetime.utcnow(), google_login_enabled=google_login_status) # Added return

     # GET request - Render the login page
     return render_template('login.html', now=datetime.utcnow(), google_login_enabled=google_login_status)


@bp.route("/google/authorized")
def google_auth_callback():
     # --- Access extensions INSIDE the function ---
     from ..extensions import db, google_enabled, registrations_collection # Can access directly here if needed

     # --- Check if enabled/authorized ---
     if not google_enabled or not google.authorized:
          flash("Google login failed or is disabled.", "danger") # Added flash
          return redirect(url_for("auth.login"))

     # --- Check DB connection ---
     if db is None: # Check DB connection
         flash("Database service is currently unavailable.", "danger") # Added flash
         return redirect(url_for("auth.login"))

     # --- Access collection (already imported or use db.registrations) ---
     # registrations_collection = db.registrations # Access collection

     # --- Keep the Google auth logic (find/update/create user) ---
     # Ensure you add flash messages and redirects within the try/except blocks
     # where appropriate, similar to the password login/register.
     try:
        # Fetch user info from Google
        resp = google.get("/oauth2/v3/userinfo")
        if not resp.ok:
            logging.error(f"Failed to fetch user info from Google: {resp.status_code} - {resp.text}")
            flash("Could not retrieve your information from Google. Please try again.", "danger")
            return redirect(url_for("auth.login"))

        user_info = resp.json()
        google_id = user_info.get("sub")
        email = user_info.get("email")
        name = user_info.get("name")

        if not google_id:
            flash("Google ID not found in response. Cannot log in.", "danger")
            return redirect(url_for("auth.login"))

        # Check if user exists
        user_doc = registrations_collection.find_one({"google_id": google_id})
        if not user_doc and email:
            user_doc = registrations_collection.find_one({"email": email})

        now = datetime.utcnow()
        if user_doc: # User exists, update and login
            update_data = {"$set": {"last_login_at": now, "login_method": "google"}}
            if not user_doc.get("google_id"): update_data["$set"]["google_id"] = google_id
            if not user_doc.get("name") and name: update_data["$set"]["name"] = name
            try:
                registrations_collection.update_one({"_id": user_doc["_id"]}, update_data)
                updated_user_doc = registrations_collection.find_one({"_id": user_doc["_id"]})
                if updated_user_doc: login_user(updated_user_doc); return redirect(url_for("core.dashboard"))
                else: flash("Login failed after update.", "danger"); return redirect(url_for("auth.login"))
            except Exception as update_err:
                logging.error(f"Failed update during Google login for {email or google_id}: {update_err}")
                flash("Login failed due to DB error.", "danger"); return redirect(url_for("auth.login"))
        else: # New user, create and login
            new_user_data = { "google_id": google_id, "email": email, "name": name, "created_at": now, "last_login_at": now, "login_method": "google"}
            try:
                insert_result = registrations_collection.insert_one(new_user_data)
                created_user_doc = registrations_collection.find_one({"_id": insert_result.inserted_id})
                if created_user_doc: login_user(created_user_doc); return redirect(url_for("core.dashboard"))
                else: flash("Login failed after create.", "danger"); return redirect(url_for("auth.login"))
            except DuplicateKeyError:
                 logging.error(f"Duplicate key on Google create for {email or google_id}.")
                 flash("Account issue occurred. Try again.", "warning"); return redirect(url_for("auth.login"))
            except Exception as insert_err:
                 logging.error(f"Failed insert new Google user {email or google_id}: {insert_err}")
                 flash("Login failed due to DB error.", "danger"); return redirect(url_for("auth.login"))
     except Exception as e:
         logging.error(f"Error during Google OAuth callback: {e}", exc_info=True)
         flash("An unexpected error occurred during Google login.", "danger")
         return redirect(url_for("auth.login"))


# --- Logout Route ---
@bp.route('/logout')
def logout():
    username = session.get('username', 'Unknown')
    user_id = session.get('user_id', 'N/A')
    session.clear()
    flash("You have been logged out successfully.", "success")
    logging.info(f"User '{username}' (ID: {user_id}) logged out.")
    return redirect(url_for('auth.login')) # Redirect to login page