import logging
from flask import Blueprint, render_template, redirect, url_for, flash, session
from datetime import datetime

# Import extensions and utils using RELATIVE imports
from ..utils.auth_utils import is_logged_in # Changed

bp = Blueprint('voice', __name__)

@bp.route('/agent')
def voice_agent_page():
    """Renders the dedicated page for the Voice AI Assistant."""
    if not is_logged_in():
        flash("Please log in to use the Voice AI agent.", "warning")
        return redirect(url_for('auth.login'))
    return render_template('voice_agent.html', now=datetime.utcnow())