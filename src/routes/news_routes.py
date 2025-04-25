# src/routes/news_routes.py

import logging
import requests
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, session, request, jsonify, current_app)
from datetime import datetime, timedelta

# --- Relative Imports ---
# --- DO NOT import specific collections or initialized models here ---

# --- Import Utils ---
from ..utils.auth_utils import is_logged_in
from ..utils.api_utils import log_gemini_response_details

# Create Blueprint
bp = Blueprint('news', __name__)


# --- Routes ---

@bp.route('/agent')
def news_agent_page():
    """Renders the News Agent page."""
    # No db/model access needed here, just config check
    key_available = bool(current_app.config.get('WORLD_NEWS_API_KEY'))
    logging.info(f"Rendering news agent page. Key available status from config: {key_available}")
    # Add login check if needed: if not is_logged_in(): ...
    return render_template('news_agent.html',
                           news_api_available=key_available,
                           now=datetime.utcnow())


@bp.route('/fetch')
def fetch_live_news():
    """Fetches news using the World News API."""
    # --- Access extensions INSIDE function (only if needed, e.g., for DB storage) ---
    # Import db and collection only if you implement the optional storage part
    # from ..extensions import db, news_articles_collection

    logging.info("--- Enter /news/fetch (World News API) ---")
    # Add login check if needed: if not is_logged_in(): ...

    # Get API config from Flask app config
    api_key = current_app.config.get('WORLD_NEWS_API_KEY')
    api_endpoint = current_app.config.get('WORLD_NEWS_API_ENDPOINT')

    if not api_key or not api_endpoint:
        logging.error("News fetch failed: API key/endpoint not configured.")
        return jsonify({"error": "News API not configured on server."}), 503

    # --- Parameters ---
    try:
        params = { # Default parameters
            'text': request.args.get('text', 'latest technology'),
            'source-countries': request.args.get('source-countries', 'us,gb,ca'),
            'language': request.args.get('language', 'en'),
            'number': max(1, min(request.args.get('number', 20, type=int), 100)), # Clamp number
            'sort': request.args.get('sort', 'publish-time'),
            'sort-direction': request.args.get('sort-direction', 'DESC'),
            'earliest-publish-date': (datetime.utcnow() - timedelta(days=3)).strftime('%Y-%m-%d')
        }
    except Exception as e:
        logging.error(f"Error parsing news fetch arguments: {e}")
        return jsonify({"error": "Invalid request parameters."}), 400

    headers = {'x-api-key': api_key}
    logging.info(f"Fetching World News API. Endpoint: {api_endpoint}, Params: {params}")

    try:
        response = requests.get(api_endpoint, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        news_data = response.json()
        articles = news_data.get('news', [])
        total_results_reported = news_data.get('number', len(articles))

        # --- Map fields ---
        mapped_articles = []
        for article in articles:
            if not article.get('title') or not article.get('url'): continue # Skip incomplete
            mapped_articles.append({ # ... mapping logic ...
                "title": article.get('title'), "description": article.get('text'),
                "content": article.get('text'), "url": article.get('url'),
                "urlToImage": article.get('image'), "publishedAt": article.get('publish_date'),
                "source": { "id": None, "name": article.get('source_country', '').upper() or 'Unknown' }
            })

        # --- Optional: Store fetched articles in MongoDB ---
        # if db is not None and news_articles_collection is not None and mapped_articles:
            # logging.info(f"Attempting to store {len(mapped_articles)} fetched news articles...")
            # ... (DB insertion logic using news_articles_collection) ...
            # pass # Placeholder

        logging.info(f"Fetched {len(mapped_articles)} articles via World News API.")
        return jsonify({ "articles": mapped_articles, "status": "ok", "totalResults": total_results_reported })

    # ... (keep specific requests exception handling: Timeout, HTTPError, RequestException) ...
    except requests.exceptions.Timeout:
         logging.error("World News API request timed out."); return jsonify({"error": "Request to news source timed out."}), 504
    except requests.exceptions.HTTPError as http_err:
         # ... (detailed HTTPError handling) ...
         status_code = http_err.response.status_code; error_detail = f"HTTP error {status_code}"; return jsonify({"error": error_detail}), status_code
    except requests.exceptions.RequestException as req_err:
         logging.error(f"World News API connection error: {req_err}"); return jsonify({"error": "Could not connect to news source."}), 503
    except Exception as e:
        logging.error(f"Unexpected error fetching World News API: {e}", exc_info=True)
        return jsonify({"error": "Unexpected server error fetching news."}), 500
    finally:
        logging.info("--- Exiting /news/fetch (World News API) ---")


@bp.route('/summarize', methods=['POST'])
def summarize_news():
    """Summarizes news content using Gemini."""
    # --- Access extensions INSIDE function ---
    from ..extensions import genai_model # Only need genai_model here

    # Auth & Service Checks
    if not is_logged_in(): return jsonify({"error": "Authentication required"}), 401
    if genai_model is None: return jsonify({"error": "AI Summarizer service unavailable."}), 503

    # Get Data
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid request: No JSON data."}), 400
    content_to_summarize = data.get('content', '').strip()
    title = data.get('title', 'this news article')
    if not content_to_summarize: return jsonify({"error": "No content provided."}), 400
    if len(content_to_summarize) < 100: logging.warning(f"Content possibly too short for summary."); # Proceed anyway

    # Prepare Prompt
    prompt = f"""Provide a concise summary (2-4 sentences) of the news article text below. Focus on main points. Article Title: "{title}"\n\nText:\n---\n{content_to_summarize}\n---\n\nConcise Summary:"""

    logging.info(f"Sending content (length: {len(content_to_summarize)}) to Gemini for summarization...")
    summary = "[AI Error: Failed summary]" # Default

    try:
        # Use locally accessed genai_model
        response = genai_model.generate_content(prompt)
        log_gemini_response_details(response, f"summarize_{session.get('user_id')}")
        # ... (process response as before) ...
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
             summary = f"[AI summary blocked: {response.prompt_feedback.block_reason.name}]"
        elif response.candidates and response.text: summary = response.text.strip()
        elif response.candidates: summary = "[AI returned empty summary]"
        else: summary = "[AI returned no candidates]"

    except Exception as e:
        logging.error(f"Error during Gemini summarization call: {e}", exc_info=True)
        # Keep default error message

    logging.info("Summary processing complete.")
    return jsonify({"summary": summary})