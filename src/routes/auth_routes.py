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

# --- Import only the main db/extensions object if needed for setup, OR import nothing from extensions here ---
from ..extensions import db, google_bp, google_enabled # OK to import placeholders needed globally
# --- DO NOT import specific collections like input_prompts_collection here ---

# --- Import Utils ---
from ..utils.auth_utils import is_logged_in, login_user, hash_password, verify_password
from ..utils.file_utils import get_secure_filename # We might need a specific allowed list for images

# --- Allowed image extensions (Define globally for this module) ---
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_profile_image(filename):
    """Checks if the filename has an allowed image extension."""
    # Ensure filename is not None and is a string before processing
    if not filename or not isinstance(filename, str):
        return False
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

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

# --- Profile Routes ---
# --- Profile Routes ---
@bp.route('/profile', methods=['GET'])
def view_profile():
    """Displays the user's profile page."""
    from ..extensions import db # Need DB inside
    if not is_logged_in(): flash("Please log in.", "warning"); return redirect(url_for('auth.login'))
    if db is None: flash("Database unavailable.", "danger"); return redirect(url_for('core.dashboard'))
    registrations_collection = db.registrations

    try:
        user_id = ObjectId(session['user_id'])
        user_data = registrations_collection.find_one({"_id": user_id})
        if not user_data: flash("User not found.", "danger"); session.clear(); return redirect(url_for('auth.login'))

        # Prepare profile data safely
        profile_data = { "_id": str(user_data["_id"]), "username": user_data.get("username"), "email": user_data.get("email"), "name": user_data.get("name", ""), "age": user_data.get("age", ""), "profile_picture_url": None, "login_method": user_data.get("login_method", "password") }
        db_path = user_data.get("profile_picture_path")
        if db_path:
            try:
                # This relies on static file serving for 'uploads' or a dedicated route
                profile_data["profile_picture_url"] = url_for('static', filename=db_path)
            except Exception as url_err: logging.error(f"Could not build profile pic URL for path '{db_path}': {url_err}")

        logging.debug(f"Rendering profile page for: {profile_data.get('username')}")
        return render_template('auth/profile.html', user=profile_data, now=datetime.utcnow())

    except InvalidId:
         flash("Invalid user session.", "danger"); session.clear(); return redirect(url_for('auth.login'))
    except PyMongoError as db_err:
         logging.error(f"View Profile DB Error for {session.get('user_id')}: {db_err}", exc_info=True)
         flash("Database error fetching profile.", "danger"); return redirect(url_for('core.dashboard'))
    except Exception as e:
        logging.error(f"Error fetching profile for {session.get('user_id')}: {e}", exc_info=True)
        flash("Error retrieving profile.", "danger"); return redirect(url_for('core.dashboard'))

@bp.route('/profile/update', methods=['POST'])
def update_profile():
    from ..extensions import db
    # ... (login check, db check) ...
    if not is_logged_in(): flash("Please log in.", "warning"); return redirect(url_for('auth.login'))
    if db is None: flash("Database unavailable.", "danger"); return redirect(url_for('auth.view_profile'))
    registrations_collection = db.registrations
    user_id_str = session['user_id']

    try:
        user_id = ObjectId(user_id_str)
        username_session = session.get('username', 'Unknown')

        name = request.form.get('name', '').strip()
        age_str = request.form.get('age', '').strip()
        profile_image_file = request.files.get('profile_picture')

        update_data = {"$set": {"last_modified": datetime.utcnow()}}
        unset_data = {}
        # ... (process name, age) ...

        # --- Handle Image Upload ---
        if profile_image_file and profile_image_file.filename != '':
            logging.debug(f"Processing profile picture upload: {profile_image_file.filename}, type: {profile_image_file.content_type}") # Log file info
            if allowed_profile_image(profile_image_file.filename):
                try:
                    # --- Log paths being used ---
                    upload_folder_base = current_app.config.get('UPLOAD_FOLDER')
                    if not upload_folder_base: raise ValueError("UPLOAD_FOLDER not configured.")
                    logging.debug(f"Base Upload Folder: {upload_folder_base}")

                    profile_pics_rel_path = os.path.join('profile_pics', user_id_str)
                    user_pic_dir_abs = os.path.join(upload_folder_base, profile_pics_rel_path)
                    logging.debug(f"Absolute directory path for saving: {user_pic_dir_abs}")

                    # --- Log before creating directory ---
                    logging.debug(f"Attempting os.makedirs on: {user_pic_dir_abs}")
                    os.makedirs(user_pic_dir_abs, exist_ok=True)
                    logging.debug(f"Directory ensured/created: {user_pic_dir_abs}")

                    original_filename = secure_filename(profile_image_file.filename)
                    if not original_filename: # Check if secure_filename resulted in empty string
                         raise ValueError("Could not secure the original filename.")
                    _, f_ext = os.path.splitext(original_filename)
                    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                    stored_filename = f"{timestamp}{f_ext}"
                    save_path_abs = os.path.join(user_pic_dir_abs, stored_filename)
                    logging.debug(f"Absolute save path for file: {save_path_abs}")

                    # Determine DB path based on serving strategy (adjust if needed)
                    image_db_path_to_store = os.path.join('uploads', 'profile_pics', user_id_str, stored_filename).replace("\\", "/")
                    logging.debug(f"Path to store in DB: {image_db_path_to_store}")

                    # (Optional delete old file logic...)

                    # --- Log before saving file ---
                    logging.info(f"Attempting to save profile picture to: {save_path_abs}")
                    profile_image_file.save(save_path_abs) # <<< THE ACTUAL SAVE OPERATION
                    logging.info(f"Profile picture saved successfully to absolute path.")
                    update_data["$set"]["profile_picture_path"] = image_db_path_to_store

                except PermissionError as pe:
                    # <<< LOOK FOR THIS LOG >>>
                    logging.error(f"PERMISSION DENIED saving profile picture to '{user_pic_dir_abs}' or '{save_path_abs}': {pe}", exc_info=True)
                    flash(f"Error: Permission denied to save image. Server configuration issue.", "danger")
                except OSError as oe:
                    # <<< OR THIS LOG >>>
                    logging.error(f"OS error saving profile picture (Disk full? Invalid path?): {oe}", exc_info=True)
                    flash(f"Server OS error saving image: {oe.strerror}. Please try again later.", "danger")
                except ValueError as ve: # Catch config or filename errors
                    # <<< OR THIS LOG >>>
                     logging.error(f"Configuration or value error during image upload: {ve}", exc_info=True)
                     flash("Server configuration error preventing image upload.", "danger")
                except Exception as upload_err: # Catch any other errors during the save process
                    # <<< OR THIS LOG >>>
                    logging.error(f"Unexpected error saving profile picture: {upload_err}", exc_info=True)
                    flash("An unexpected error occurred during picture upload.", "danger")

                # --- End Specific Exception Handling ---

            else:
                flash("Invalid image file type selected. Allowed: png, jpg, jpeg, gif, webp.", "warning")
                # Decide if invalid type should stop the whole update or just skip image part
                # return redirect(url_for('auth.view_profile')) # Uncomment to stop update on bad type

        # --- Update Database (only if changes exist) ---
        # ... (The rest of the update logic as before) ...
        final_update_op = {}; # ... construct final_update_op ...
        if final_update_op:
            # ... (log update, perform update_one, flash success/fail) ...
            try:
                update_result = registrations_collection.update_one({"_id": user_id}, final_update_op)
                # ... check update_result.acknowledged, flash ...
            except PyMongoError as db_err: # Catch DB error during final update
                 logging.error(f"Update Profile DB Error (final update): {db_err}", exc_info=True)
                 flash("Database error saving profile changes.", "danger")
                 # Fall through to redirect below, error is flashed
            except Exception as final_e: # Catch any other error during final update
                logging.error(f"Unexpected error during final profile update: {final_e}", exc_info=True)
                flash("Unexpected error saving profile changes.", "danger")
        else:
             flash("No changes submitted.", "info")

        return redirect(url_for('auth.view_profile')) # Redirect back

    # --- Outer Exception Handling ---
    except InvalidId:
         # Indent the block
         logging.warning(f"Invalid ObjectId format in session user_id: {session.get('user_id')}")
         flash("Invalid user session identifier. Please log in again.", "danger")
         session.clear()
         return redirect(url_for('auth.login'))

    except KeyError as e_key:
         # Indent the block
         logging.error(f"Session key missing during profile update: {e_key}", exc_info=True)
         flash("Your session is invalid or has expired. Please log in again.", "warning")
         session.clear()
         return redirect(url_for('auth.login'))

    except PyMongoError as db_err:
         # Indent the block (This one was likely okay already, but ensure consistency)
         logging.error(f"Update Profile DB Error for {user_id_str if 'user_id_str' in locals() else 'UNKNOWN'}: {db_err}", exc_info=True)
         flash("A database error occurred updating profile.", "danger")
         return redirect(url_for('auth.view_profile')) # Redirect back to profile page

    except Exception as e:
        # Indent the block (This one was likely okay already)
        logging.error(f"Unexpected error updating profile for {user_id_str if 'user_id_str' in locals() else 'UNKNOWN'}: {e}", exc_info=True)
        flash("An unexpected error occurred while updating profile.", "danger")
        return redirect(url_for('auth.view_profile')) # Redirect back to profile page

# ... (rest of file) ...

# --- End auth_routes.py ---
