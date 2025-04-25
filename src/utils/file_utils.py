import os
from werkzeug.utils import secure_filename
from flask import current_app # Use current_app to access config

def allowed_file(filename):
    """Checks if the filename has an allowed extension for general uploads."""
    allowed_ext = current_app.config.get('ALLOWED_EXTENSIONS', set())
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_ext

def allowed_analysis_file(filename):
    """Checks if the filename has an allowed extension for data analysis uploads."""
    allowed_ext = current_app.config.get('ALLOWED_ANALYSIS_EXTENSIONS', set())
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_ext

def get_secure_filename(filename):
    """Wrapper for werkzeug's secure_filename."""
    return secure_filename(filename)

# Could add functions for creating unique filenames, etc.