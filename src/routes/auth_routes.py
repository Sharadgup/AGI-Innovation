# src/routes/auth_routes.py
import logging
from datetime import datetime
# --- Keep standard imports ---
from flask import (Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify)
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError, PyMongoError
from flask_dance.contrib.google import google
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature # For tokens
from datetime import timedelta # For token expiry

# --- Import only the main db/extensions object if needed for setup, OR import nothing from extensions here ---
from ..extensions import db, google_bp, google_enabled # OK to import placeholders needed globally
# --- DO NOT import specific collections like input_prompts_collection here ---

# --- Import Utils ---
from ..utils.auth_utils import is_logged_in, login_user, hash_password, verify_password
from ..utils.file_utils import get_secure_filename # We might need a specific allowed list for images

import pdb

# --- Allowed image extensions (Define globally for this module) ---
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_profile_image(filename):
    """Checks if the filename has an allowed image extension."""
    # Ensure filename is not None and is a string before processing
    if not filename or not isinstance(filename, str):
        return False
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


# These imports might fail if the modules don't exist or have errors
try:
    from ..agent_core import gmail_api_handler, ai_response, scheduler
    from ..database import mongo_handler # Import the MODULE
    AGENT_CORE_LOADED = True
    # --- Connect DB on module load ---
    mongo_handler.connect_db() # Ensures DB connection attempt on startup
except ImportError as e:
    logging.critical(f"Failed import agent/db modules: {e}. Routes will fail.")
    AGENT_CORE_LOADED = False


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



# --- NEW: Route to Display Change Password Form ---
@bp.route('/change-password', methods=['GET'])
# @login_required # Use decorator if available and preferred
def change_password_form():
    """Displays the form for the user to change their password."""
    # Manual check if decorator not used
    if not is_logged_in():
        flash("Please log in to change your password.", "warning")
        return redirect(url_for('auth.login'))
    # Check login method from session
    if session.get('login_method') != 'password':
         flash("Password change is only available for accounts created with a password.", "warning")
         return redirect(url_for('core.dashboard')) # Redirect if logged in via Google

    logging.debug("Rendering change password form.")
    # Render template from auth subdirectory
    return render_template('auth/change_password.html', now=datetime.utcnow())


# --- NEW: Route to Process Change Password Form ---
@bp.route('/change-password', methods=['POST'])
# @login_required # Use decorator if available and preferred
def change_password_submit():
    """Handles the submission of the change password form."""
    # --- Access extensions INSIDE function ---
    from ..extensions import db # Only need db here

    # Manual checks if decorator not used
    if not is_logged_in():
        flash("Session expired. Please log in again.", "warning")
        return redirect(url_for('auth.login'))
    if session.get('login_method') != 'password':
         # This check prevents direct POST access for non-password users
         flash("Password change is not available for this account type.", "warning")
         return redirect(url_for('core.dashboard'))

    # Check DB connection
    if db is None:
        flash("Database service unavailable. Please try again later.", "danger")
        return redirect(url_for('auth.change_password_form'))

    registrations_collection = db.registrations # Access collection via db proxy

    # Get form data
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # --- Validation ---
    if not all([current_password, new_password, confirm_password]):
        flash("All password fields are required.", "warning")
        return redirect(url_for('auth.change_password_form'))
    if new_password != confirm_password:
        flash("New passwords do not match.", "warning")
        return redirect(url_for('auth.change_password_form'))
    if len(new_password) < 6:
        flash("New password must be at least 6 characters long.", "warning")
        return redirect(url_for('auth.change_password_form'))
    if new_password == current_password:
         flash("New password cannot be the same as the current password.", "warning")
         return redirect(url_for('auth.change_password_form'))
    # --- End Validation ---

    try:
        # Get user ID from secure session
        user_id = ObjectId(session['user_id'])
        username = session.get('username', 'Unknown') # For logging

        # Fetch current user document
        user = registrations_collection.find_one({"_id": user_id})
        if not user:
            flash("User session invalid. Please log in again.", "danger")
            session.clear(); return redirect(url_for('auth.login'))

        # Verify the CURRENT password using util function
        if not verify_password(user.get('password_hash'), current_password):
            flash("Incorrect current password.", "danger")
            return redirect(url_for('auth.change_password_form'))

        # --- Hash the NEW password ---
        new_hashed_password = hash_password(new_password) # Use util function

        # --- Update the user document in MongoDB ---
        update_result = registrations_collection.update_one(
            {"_id": user_id},
            {"$set": {"password_hash": new_hashed_password, "last_modified": datetime.utcnow()}}
        )

        if update_result.modified_count == 1:
            flash("Password updated successfully!", "success")
            logging.info(f"Password updated for user '{username}' (ID: {user_id})")
            return redirect(url_for('core.dashboard')) # Or profile page
        else:
            # Should ideally not happen if password verification passed and ID is correct
            flash("Password could not be updated due to an internal issue. Please try again.", "danger")
            logging.warning(f"Password update DB modify count was {update_result.modified_count} for user '{username}' (ID: {user_id}).")
            return redirect(url_for('auth.change_password_form'))

    except InvalidId:
         flash("Invalid user session identifier.", "danger")
         session.clear(); return redirect(url_for('auth.login'))
    except Exception as e:
        logging.error(f"Error changing password for user '{session.get('username', 'Unknown')}': {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again later.", "danger")
        return redirect(url_for('auth.change_password_form'))

# --- Forgot Password Routes ---

def get_reset_token_serializer(secret_key=None, salt='password-reset-salt'):
    """Creates a configured serializer for generating/verifying tokens."""
    if secret_key is None:
        secret_key = current_app.config['SECRET_KEY'] # Use app's main secret key
    return URLSafeTimedSerializer(secret_key, salt=salt)

# --- Route to Display Forgot Password Form ---
@bp.route('/forgot-password', methods=['GET'])
def forgot_password_request_form():
    """Displays the form asking for the user's email to send a reset link."""
    if is_logged_in(): return redirect(url_for('core.dashboard')) # Redirect if already logged in
    return render_template('auth/forgot_password_request.html', now=datetime.utcnow())

# --- Route to Handle Forgot Password Email Submission ---
@bp.route('/forgot-password', methods=['POST'])
def forgot_password_request_submit():
    """Processes the email submission, generates token, and sends reset email."""
    # --- Access extensions INSIDE function ---
    from ..extensions import db, mail # Need db and mail
    from flask_mail import Message # Need Message class

    if is_logged_in(): return redirect(url_for('core.dashboard'))
    if db is None: flash("Database unavailable.", "danger"); return redirect(url_for('auth.forgot_password_request_form'))
    if mail is None or not current_app.config.get('MAIL_USERNAME'):
         flash("Email service is not configured on the server.", "danger")
         logging.error("Forgot Password attempt failed: Flask-Mail not configured/initialized.")
         return redirect(url_for('auth.forgot_password_request_form'))

    registrations_collection = db.registrations
    email = request.form.get('email', '').strip().lower()

    if not email:
        flash("Please enter your email address.", "warning")
        return redirect(url_for('auth.forgot_password_request_form'))

    try:
        user = registrations_collection.find_one({"email": email})

        # IMPORTANT: Only allow reset for password-based accounts if desired
        if user and user.get('login_method', 'password') == 'password':
            # --- Generate Token ---
            s = get_reset_token_serializer()
            # Include user ID in the token data, set expiry (e.g., 1 hour)
            expires_in_seconds = 3600
            token = s.dumps({'user_id': str(user['_id'])}) # expiry handled by serializer max_age

            # --- Create Reset Link ---
            # Use _external=True to get the full URL including domain
            reset_url = url_for('auth.reset_password_form', token=token, _external=True)

            # --- Send Email (Placeholder - Requires Flask-Mail Setup) ---
            subject = "Password Reset Request - Vision AI Studio"
            # Create HTML body (consider using render_template for a nice email template)
            html_body = f"""
            <p>Hello {user.get('name') or user.get('username', 'User')},</p>
            <p>You requested a password reset for your Vision AI Studio account associated with this email address.</p>
            <p>Click the link below to set a new password. This link is valid for 1 hour:</p>
            <p><a href="{reset_url}">{reset_url}</a></p>
            <p>If you did not request this reset, please ignore this email.</p>
            <p>Thanks,<br>The Vision AI Studio Team</p>
            """
            msg = Message(subject=subject,
                          recipients=[email], # Send to user's email
                          html=html_body,
                          sender=current_app.config.get('MAIL_DEFAULT_SENDER')) # Use configured sender

            try:
                logging.info(f"Attempting to send password reset email to {email} for user {user.get('username')}")
                # mail.send(msg) # <<< UNCOMMENT THIS LINE WHEN MAIL IS CONFIGURED
                logging.info("Password reset email send command issued (actual sending depends on Flask-Mail config).")
                # --- --- --- --- ---

                # !! TEMPORARY: For testing without email, log the link !!
                print("-" * 20)
                print(f"PASSWORD RESET LINK (for testing - normally emailed): {reset_url}")
                print("-" * 20)
                # !! END TEMPORARY !!

                flash("If an account exists for that email, a password reset link has been sent. Please check your inbox (and spam folder).", "info")
                return redirect(url_for('auth.login'))

            except Exception as mail_err:
                 logging.error(f"Failed to send password reset email to {email}: {mail_err}", exc_info=True)
                 flash("Could not send reset email due to a server error. Please contact support.", "danger")
                 return redirect(url_for('auth.forgot_password_request_form'))

        elif user and user.get('login_method') != 'password':
             # User exists but uses OAuth - don't send reset link
             flash(f"This account uses {user.get('login_method', 'an external provider')} for login. Please manage your password through that service.", "warning")
             return redirect(url_for('auth.login'))
        else:
            # Email not found - show generic success message for security (don't reveal if email exists)
            logging.info(f"Password reset requested for non-existent or non-password email: {email}")
            flash("If an account exists for that email, a password reset link has been sent.", "info")
            return redirect(url_for('auth.login'))

    except PyMongoError as db_err:
        logging.error(f"Forgot Password DB Error for {email}: {db_err}", exc_info=True)
        flash("A database error occurred. Please try again.", "danger")
        return redirect(url_for('auth.forgot_password_request_form'))
    except Exception as e:
        logging.error(f"Unexpected error during password reset request for {email}: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
        return redirect(url_for('auth.forgot_password_form')) # Redirect back to forgot form

# --- Route to Display Reset Password Form (from email link) ---
@bp.route('/reset-password/<token>', methods=['GET'])
def reset_password_form(token):
    """Verifies the token and displays the form to enter a new password."""
    if is_logged_in(): return redirect(url_for('core.dashboard')) # Don't allow logged-in users here

    s = get_reset_token_serializer()
    try:
        # Verify token signature and expiry (default max_age is 3600s/1hr for loads)
        data = s.loads(token, max_age=3600)
        user_id_str = data.get('user_id')
        if not user_id_str: raise Exception("Token missing user ID")
        # Optional: Could check here if user still exists, but POST handles final check
        logging.info(f"Password reset token validated for user ID: {user_id_str}")
        # Render the form, passing the valid token
        return render_template('auth/reset_password_form.html', token=token, now=datetime.utcnow())

    except SignatureExpired:
        flash("The password reset link has expired. Please request a new one.", "danger")
        return redirect(url_for('auth.forgot_password_request_form'))
    except BadTimeSignature:
        flash("The password reset link is invalid or has been tampered with.", "danger")
        return redirect(url_for('auth.forgot_password_request_form'))
    except Exception as e:
        logging.error(f"Error validating reset token '{token[:10]}...': {e}")
        flash("Invalid password reset link.", "danger")
        return redirect(url_for('auth.forgot_password_request_form'))

# --- Route to Handle Reset Password Submission ---
@bp.route('/reset-password/<token>', methods=['POST'])
def reset_password_submit(token):
    """Processes the new password submission after validating the token."""
    # --- Access extensions INSIDE function ---
    from ..extensions import db

    if is_logged_in(): return redirect(url_for('core.dashboard'))
    if db is None: flash("Database unavailable.", "danger"); return redirect(url_for('auth.login')) # Redirect to login on DB error here
    registrations_collection = db.registrations

    # Re-verify the token
    s = get_reset_token_serializer()
    user_id_str = None
    try:
        data = s.loads(token, max_age=3600) # Check expiry again
        user_id_str = data.get('user_id')
        if not user_id_str: raise Exception("Invalid token data")
        user_id = ObjectId(user_id_str) # Convert to ObjectId for DB query
    except (SignatureExpired, BadTimeSignature, InvalidId, Exception) as e:
        logging.warning(f"Invalid or expired token used on POST: {token[:10]}... Error: {e}")
        flash("Invalid or expired password reset link. Please request a new one.", "danger")
        return redirect(url_for('auth.forgot_password_request_form'))

    # Get new passwords from form
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # Validation
    if not new_password or not confirm_password:
        flash("Both password fields are required.", "warning")
        return render_template('auth/reset_password_form.html', token=token, now=datetime.utcnow()) # Re-render form with token
    if new_password != confirm_password:
        flash("Passwords do not match.", "warning")
        return render_template('auth/reset_password_form.html', token=token, now=datetime.utcnow())
    if len(new_password) < 6:
        flash("Password must be at least 6 characters long.", "warning")
        return render_template('auth/reset_password_form.html', token=token, now=datetime.utcnow())

    try:
        # Find the user again to ensure they still exist and haven't changed login method
        user = registrations_collection.find_one({"_id": user_id, "login_method": "password"})
        if not user:
            flash("Password reset failed: User account not found or cannot be reset.", "danger")
            return redirect(url_for('auth.forgot_password_request_form'))

        # Hash the new password
        new_hashed_password = hash_password(new_password)

        # Update the password in the database
        update_result = registrations_collection.update_one(
            {"_id": user_id},
            # Also update last_modified timestamp
            {"$set": {"password_hash": new_hashed_password, "last_modified": datetime.utcnow()}}
            # Consider invalidating other sessions here if needed
        )

        if update_result.acknowledged:
            flash("Your password has been successfully reset! Please log in with your new password.", "success")
            logging.info(f"Password successfully reset for user ID {user_id_str}")
            return redirect(url_for('auth.login')) # Redirect to login page
        else:
            flash("Password reset failed due to a database issue.", "danger")
            return render_template('auth/reset_password_form.html', token=token, now=datetime.utcnow())

    except PyMongoError as db_err:
         logging.error(f"Reset Password DB Error for {user_id_str}: {db_err}", exc_info=True)
         flash("Database error resetting password.", "danger")
         return render_template('auth/reset_password_form.html', token=token, now=datetime.utcnow())
    except Exception as e:
        logging.error(f"Unexpected error resetting password for {user_id_str}: {e}", exc_info=True)
        flash("An unexpected error occurred.", "danger")
        return render_template('auth/reset_password_form.html', token=token, now=datetime.utcnow())

# --- Profile Routes ---
@bp.route('/profile', methods=['GET'])
def view_profile():
    """Displays the user's profile page."""
    from ..extensions import db
    if not is_logged_in(): flash("Please log in.", "warning"); return redirect(url_for('auth.login'))
    if db is None: flash("Database unavailable.", "danger"); return redirect(url_for('core.dashboard'))
    registrations_collection = db.registrations
    try:
        user_id = ObjectId(session['user_id'])
        user_data = registrations_collection.find_one({"_id": user_id})
        if not user_data: flash("User not found.", "danger"); session.clear(); return redirect(url_for('auth.login'))

        profile_data = { "_id": str(user_data["_id"]), "username": user_data.get("username"), "email": user_data.get("email", ""), "name": user_data.get("name", ""), "age": user_data.get("age", ""), "profile_picture_url": None, "login_method": user_data.get("login_method", "password") }
        db_path = user_data.get("profile_picture_path")
        if db_path:
            try:
                # --- IMPORTANT: Serving Strategy ---
                # This assumes 'uploads' (or at least 'profile_pics') is accessible via the static route.
                # If UPLOAD_FOLDER is outside static, you need a different url_for pointing
                # to a dedicated file serving route.
                # Example if uploads is under static: filename='uploads/' + db_path
                # Example if profile_pics is under static: filename='profile_pics/' + os.path.basename(db_path) # Might need more parts
                # Using the currently stored path, assuming it's relative to static root:
                profile_data["profile_picture_url"] = url_for('static', filename=db_path)
                logging.debug(f"Generated profile picture URL: {profile_data['profile_picture_url']}")
            except Exception as url_err:
                 logging.error(f"Could not build profile pic URL for DB path '{db_path}': {url_err}")

        logging.debug(f"Rendering profile for: {profile_data.get('username')}")
        return render_template('auth/profile.html', user=profile_data, now=datetime.utcnow())

    except InvalidId: flash("Invalid session.", "danger"); session.clear(); return redirect(url_for('auth.login'))
    except PyMongoError as db_err: logging.error(f"View Profile DB Error: {db_err}"); flash("DB error.", "danger"); return redirect(url_for('core.dashboard'))
    except Exception as e: logging.error(f"Error fetching profile: {e}", exc_info=True); flash("Error retrieving profile.", "danger"); return redirect(url_for('core.dashboard'))

@bp.route('/profile/update', methods=['POST'])
def update_profile():
    from ..extensions import db
    # Check 1
    if not is_logged_in(): flash("Please log in.", "warning"); return redirect(url_for('auth.login'))
    # Check 2
    if db is None: flash("Database unavailable.", "danger"); return redirect(url_for('auth.view_profile'))
    registrations_collection = db.registrations
    user_id_str = session['user_id']
    logging.info(f"--- ENTERING /profile/update for user ID {user_id_str} ---")

    # Outer Try Block
    try:
        user_id = ObjectId(user_id_str)
        username_session = session.get('username', 'Unknown')
        user = registrations_collection.find_one({"_id": user_id})
        # Check 3
        if not user: flash("User session invalid.", "danger"); session.clear(); return redirect(url_for('auth.login'))

        # Get form data
        name = request.form.get('name', '').strip()
        age_str = request.form.get('age', '').strip()
        profile_image_file = request.files.get('profile_picture')
        email = request.form.get('email', '').strip().lower()

        update_set = {"last_modified": datetime.utcnow()}
        update_unset = {}
        changes_intended = False
        image_save_failed = False
        flash_messages = []

        # Process Name
        if name and name != user.get("name"): update_set["name"] = name; changes_intended = True; # ... update session ...

        # Process Age
        if 'age' in request.form:
            # ... (age validation logic) ...
            if age_str:
                try: # ... int conversion ...
                    if not (0 < age < 130): flash("Valid age...", "warning"); return redirect(url_for('auth.view_profile')) # <<< Path A returns
                    # ... set update_set, changes_intended ...
                except ValueError: flash("Age must be number.", "warning"); return redirect(url_for('auth.view_profile')) # <<< Path B returns
            elif user.get("age") is not None: update_unset["age"] = ""; changes_intended = True

        # Process Email
        if user.get("login_method") == "password" and 'email' in request.form:
            # ... (email validation logic) ...
            if email and email != user.get('email'):
                if '@' not in email or '.' not in email.split('@')[-1]: flash("Valid email...", "warning"); return redirect(url_for('auth.view_profile')) # <<< Path C returns
                else: # Check uniqueness
                    try: # ... find_one check ...
                        if existing: flash("Email exists...", "danger"); return redirect(url_for('auth.view_profile')) # <<< Path D returns
                        else: update_set["email"] = email; changes_intended = True
                    except PyMongoError: flash("DB error...", "danger"); return redirect(url_for('auth.view_profile')) # <<< Path E returns
            elif not email and user.get('email') is not None: update_unset["email"] = ""; changes_intended = True

        # Process Image Upload
        if profile_image_file and profile_image_file.filename != '':
            changes_intended = True
            if allowed_profile_image(profile_image_file.filename):
                try: # Image save logic
                    # ... (paths, makedirs, save, set update_set) ...
                    update_set["profile_picture_path"] = image_db_path_to_store # Example
                except Exception as upload_err: # Catches save errors
                    logging.error(f"IMAGE SAVE FAILED : {upload_err}", exc_info=True)
                    flash_messages.append(("Error uploading profile picture.", "warning"))
                    image_save_failed = True
            else: # Invalid image type
                flash_messages.append(("Invalid image file type.", "warning"))
                image_save_failed = True # Treat as failure

        # --- Perform Database Update ---
        final_update_op = {}
        if len(update_set) > 1: final_update_op["$set"] = update_set
        if update_unset: final_update_op["$unset"] = update_unset

        if changes_intended and final_update_op: # Case 1: Changes intended, operations exist
             try: # DB Update logic
                 update_result = registrations_collection.update_one({"_id": user_id}, final_update_op)
                 if update_result.acknowledged: # Subcase 1a: Update successful
                     if not image_save_failed: flash_messages.append(("Profile updated!", "success"))
                 else: # Subcase 1b: Update not acknowledged
                      flash_messages.append(("Profile DB update failed.", "danger"))
             except DuplicateKeyError: # Subcase 1c: Duplicate key during update
                 flash_messages.append((f"Update failed: Email exists.", "danger"))
             except PyMongoError as db_err: # Subcase 1d: Other DB error during update
                 flash_messages.append(("DB error saving changes.", "danger"))
        elif not changes_intended and not image_save_failed: # Case 2: No changes, no image fail
            flash_messages.append(("No changes detected.", "info"))
        # Case 3: (Implicit else) changes_intended was True (e.g., image attempt)
        #         BUT final_update_op is empty (e.g., only image changed but save failed)
        #         OR image_save_failed is True.
        #         In this case, the image error message is already in flash_messages.

        # --- Flash Messages ---
        for msg, cat in flash_messages:
            flash(msg, cat)
         # --- SET BREAKPOINT HERE ---
        logging.debug(">>> Reached end of TRY block. About to redirect. <<<")
        pdb.set_trace()
         # --- --------------------- ---

        # --- !!! PROBLEM AREA !!! ---
        # If execution reaches here after any of the DB update try/except paths (1a, 1b, 1c, 1d)
        # OR after the implicit Case 3, there is NO return statement UNTIL the end of the outer try block.
        # It needs to return *immediately* after flashing messages related to the update attempt.

        


        # --- Corrected Final Redirect ---
        # This should be the LAST line within the main 'try' block
        return redirect(url_for('auth.view_profile'))


    # --- Outer Exception Handling ---
    except InvalidId: flash("Invalid session.", "danger"); session.clear(); return redirect(url_for('auth.login'))
    except KeyError as e_key: logging.error(f"Session key missing: {e_key}"); flash("Session invalid.", "warning"); session.clear(); return redirect(url_for('auth.login'))
    except PyMongoError as db_err: logging.error(f"Outer Update DB Error: {db_err}"); flash("DB Error.", "danger"); return redirect(url_for('auth.view_profile'))
    except Exception as e: logging.error(f"Error updating profile: {e}", exc_info=True); flash("Unexpected error.", "danger"); return redirect(url_for('auth.view_profile'))
# ... (rest of file) ...

def check_agent_core():
    if not AGENT_CORE_LOADED: return jsonify({"error": "Agent core components failed."}), 503
    # Check DB connection via mongo_handler's db attribute
    if not mongo_handler.db:
         mongo_handler.connect_db() # Attempt reconnect
         if not mongo_handler.db: return jsonify({"error": "DB connection unavailable."}), 503
    return None

# --- Email Agent Routes ---

# ... (email_agent_page route remains the same) ...
@bp.route('/email')
def email_agent_page():
     if not is_logged_in(): flash("Log in required."); return redirect(url_for('auth.login'))
     return render_template('agents/email_agent.html', now=datetime.utcnow())

# --- Route to get current agent status ---
@bp.route('/email/status', methods=['GET'])
def get_email_agent_status():
    if not is_logged_in(): return jsonify({"error": "Auth required."}), 401
    core_error = check_agent_core();
    if core_error: return core_error

    # --- Get state from DB ---
    current_state = mongo_handler.get_agent_state()
    if not current_state: # Handle case where state couldn't be retrieved
        return jsonify({"error": "Could not retrieve agent state from database."}), 500

    # --- Check live Gmail connection (if implemented) ---
    is_connected_live = False
    try:
        # Assumes function exists and checks token validity/makes small API call
        # is_connected_live = gmail_api_handler.is_gmail_service_active()
        # If check passes, update the stored state (best effort)
        # if is_connected_live != current_state.get("gmail_connected"):
        #      mongo_handler.update_agent_state({"gmail_connected": is_connected_live})
        # For now, rely on stored state primarily
        is_connected_live = current_state.get("gmail_connected", False)
        pass # Remove this line if implementing live check
    except Exception as e:
        logging.warning(f"Could not perform live Gmail connection check: {e}")
        is_connected_live = current_state.get("gmail_connected", False) # Use stored value on error


    response_data = {
        "gmail_connected": is_connected_live, # Reflect live check if possible
        "is_monitoring": current_state.get("is_monitoring", False),
        "status_message": current_state.get("last_status_message", "Unknown")
    }
    return jsonify(response_data), 200

# --- Route to initiate Google OAuth for Gmail ---
@bp.route('/email/authorize')
def email_agent_authorize():
    # ... (Keep logic as before, relies on gmail_api_handler) ...
    if not is_logged_in(): flash("Log in required."); return redirect(url_for('auth.login'))
    core_error = check_agent_core(); 
    if core_error: return redirect(url_for('.email_agent_page')) # etc.
    try: auth_url = gmail_api_handler.get_authorization_url(...); return redirect(auth_url)
    except Exception as e: logging.error(...); flash(...); return redirect(url_for('.email_agent_page'))

# --- Route to handle Google OAuth callback ---
@bp.route('/email/callback')
def email_agent_oauth_callback():
    # ... (Keep logic as before to exchange code, save credentials via gmail_api_handler) ...
    if not is_logged_in(): flash("Log in required."); return redirect(url_for('auth.login'))
    core_error = check_agent_core(); 
    if core_error: return redirect(url_for('.email_agent_page'))
    try:
        auth_code = request.args.get('code') # etc...
        success = gmail_api_handler.exchange_code_for_credentials(...)
        if success:
            flash("Gmail connected!", "success")
            # --- Update state in DB ---
            mongo_handler.update_agent_state({
                "gmail_connected": True,
                "last_status_message": "Idle (Connected)"
            })
        else: raise Exception("Failed credential exchange.")
        return redirect(url_for('.email_agent_page'))
    except Exception as e:
        logging.error(f"OAuth Callback Error: {e}", exc_info=True)
        flash(f"Failed connection: {e}", "danger")
        # --- Update state in DB ---
        mongo_handler.update_agent_state({"gmail_connected": False, "last_status_message": "Connection Failed"})
        return redirect(url_for('.email_agent_page'))


# --- Route to start the monitoring process ---
@bp.route('/email/start', methods=['POST'])
def start_email_agent_monitoring():
    if not is_logged_in(): return jsonify({"error": "Auth required."}), 401
    core_error = check_agent_core(); 
    if core_error: return core_error

    try:
        # --- Update state in DB ---
        updated_state = mongo_handler.update_agent_state({
            "is_monitoring": True,
            "last_status_message": "Monitoring Inbox"
        })
        if not updated_state:
            raise Exception("Failed to update agent state in database.")

        # --- Trigger actual scheduler job (if applicable) ---
        # Example: scheduler.resume_email_job() or scheduler.ensure_email_job_running()
        # This logic depends heavily on your scheduler implementation.
        logging.info("Agent state set to monitoring. Actual start depends on scheduler.")
        message = "Agent monitoring initiated."

        return jsonify({"message": message}), 200
    except Exception as e:
        logging.error(f"Error starting monitoring: {e}", exc_info=True)
        # Optionally try to revert state if possible
        mongo_handler.update_agent_state({"is_monitoring": False, "last_status_message": "Error starting"})
        return jsonify({"error": f"Failed to start monitoring: {e}"}), 500

# --- Route to stop the monitoring process ---
@bp.route('/email/stop', methods=['POST'])
def stop_email_agent_monitoring():
    if not is_logged_in(): return jsonify({"error": "Auth required."}), 401
    core_error = check_agent_core(); 
    if core_error: return core_error

    try:
        # --- Update state in DB ---
        updated_state = mongo_handler.update_agent_state({
            "is_monitoring": False,
            "last_status_message": "Idle (Stopped by user)"
        })
        if not updated_state:
            raise Exception("Failed to update agent state in database.")

        # --- Trigger actual scheduler job pause (if applicable) ---
        # Example: scheduler.pause_email_job()
        logging.info("Agent state set to stopped. Actual stop depends on scheduler.")
        message = "Agent monitoring stopped."

        return jsonify({"message": message}), 200
    except Exception as e:
        logging.error(f"Error stopping monitoring: {e}", exc_info=True)
        # State might be inconsistent if DB update succeeded but scheduler pause failed
        return jsonify({"error": f"Failed to stop monitoring: {e}"}), 500

# --- Keep other routes (config, logs, drafts, draft action) ---
# Make sure they use mongo_handler appropriately to get/set data.
# Example for /email/config:
@bp.route('/email/config', methods=['POST'])
def save_email_agent_config():
     if not is_logged_in(): return jsonify({"error": "Auth required."}), 401
     core_error = check_agent_core(); 
     if core_error: return core_error
     if not request.is_json: return jsonify({"error": "JSON required"}), 400
     config_data = request.json; user_id = ObjectId(session['user_id'])
     try:
         db = mongo_handler.db; 
         if not db: raise ConnectionError("DB error")
         update_payload = { "$set": { f"email_agent_config.{k}": v for k, v in config_data.items() } }
         update_payload["$set"]["email_agent_config.updated_at"] = datetime.utcnow()
         db.registrations.update_one({"_id": user_id}, update_payload, upsert=True) # Save config in user doc
         logging.info(f"Saved email agent config for user {user_id}")
         return jsonify({"message": "Config saved."}), 200
     except Exception as e: logging.error(f"Error saving config: {e}"); return jsonify({"error": f"Failed: {e}"}), 500

# --- End agent_routes.py (or email_agent_routes.py) ---


# --- End auth_routes.py ---
