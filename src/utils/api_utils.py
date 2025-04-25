# src/utils/api_utils.py

import logging

def log_gemini_response_details(response, identifier="N/A"):
    """Logs details of the Gemini response object for debugging."""
    # Add extra check if response itself is None
    if response is None:
        logging.debug(f"--- Gemini Response Details (ID:{identifier}) ---")
        logging.warning("Attempted to log details for a None response object.")
        logging.debug(f"--- End Gemini Response Details (ID:{identifier}) ---")
        return

    logging.debug(f"--- Gemini Response Details (ID:{identifier}) ---")
    try:
        logging.debug(f"Response Object Type: {type(response)}")

        # Candidates Check
        candidate_text = "Candidates: None or empty list."
        if hasattr(response, 'candidates') and response.candidates:
             candidate_text = f"Candidates Count: {len(response.candidates)}"
             logging.debug(candidate_text)
             for i, candidate in enumerate(response.candidates):
                 logging.debug(f"  Candidate[{i}]:")
                 # Content Parts Check
                 content_repr = "    Content: No parts or empty content"
                 if hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts'):
                      try:
                          # Log parts safely, convert non-string parts to string, limit length
                          parts_repr_list = [str(part)[:100] + ('...' if len(str(part)) > 100 else '') for part in candidate.content.parts] # Limit part length
                          content_repr = f"    Content Parts ({len(parts_repr_list)}): {parts_repr_list}"
                      except Exception as part_err:
                           content_repr = f"    Content Parts: Error getting parts representation - {part_err}"
                 logging.debug(content_repr)

                 # Finish Reason Check
                 finish_reason = "N/A"
                 if hasattr(candidate, 'finish_reason'):
                     try: finish_reason = candidate.finish_reason.name # Enum has .name
                     except AttributeError: finish_reason = str(candidate.finish_reason) # Fallback
                 logging.debug(f"    Finish Reason: {finish_reason}")

                 # Safety Ratings Check
                 if hasattr(candidate, 'safety_ratings'):
                     logging.debug(f"    Safety Ratings: {candidate.safety_ratings}")
                 else:
                     logging.debug("    Safety Ratings: N/A")
        else:
             logging.debug(candidate_text) # Log "None or empty list"

        # Prompt Feedback Check
        feedback_text = "Prompt Feedback: Not available or empty."
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
             feedback_text = f"Prompt Feedback: {response.prompt_feedback}"
             logging.debug(feedback_text)
             # Check for block reason specifically
             if hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
                 try: block_reason_str = response.prompt_feedback.block_reason.name
                 except AttributeError: block_reason_str = str(response.prompt_feedback.block_reason)
                 # Use WARNING level for blocked responses
                 logging.warning(f"*** PROMPT BLOCKED (in details)! Reason: {block_reason_str} ***")
        else:
             logging.debug(feedback_text)

        # Text Attribute Check (often resolves the response)
        text_attr_repr = "Text Attribute: Does not exist (might be chunked/non-text response?)."
        if hasattr(response, 'text'):
             try:
                 # Limit length of text logged
                 text_preview = str(response.text)[:200] + ('...' if len(str(response.text)) > 200 else '')
                 text_attr_repr = f"Text Attribute: '{text_preview}'"
             except Exception as text_err:
                 text_attr_repr = f"Text Attribute: Error accessing .text - {text_err}"
        logging.debug(text_attr_repr)

    except Exception as log_err:
        # Log errors occurring during the logging process itself
        logging.error(f"Error occurred while logging Gemini response details for ID {identifier}: {log_err}", exc_info=True)
    finally:
        # Ensure the end marker is always logged
        logging.debug(f"--- End Gemini Response Details (ID:{identifier}) ---")


# --- Add other API related utility functions here if needed ---
# Example: Function to handle News API requests might go here eventually

# def fetch_news_from_api(api_key, endpoint, params):
#     headers = {'x-api-key': api_key}
#     try:
#         response = requests.get(endpoint, headers=headers, params=params, timeout=15)
#         response.raise_for_status()
#         return response.json(), None # data, error
#     except requests.exceptions.Timeout:
#         logging.error("News API request timed out.")
#         return None, "Request to news source timed out."
#     except requests.exceptions.HTTPError as http_err:
#         # ... error handling logic ...
#         return None, error_detail
#     except requests.exceptions.RequestException as req_err:
#         logging.error(f"News API request connection error: {req_err}")
#         return None, "Could not connect to news source."
#     except Exception as e:
#         logging.error(f"Unexpected error fetching News API: {e}", exc_info=True)
#         return None, "An unexpected server error occurred."