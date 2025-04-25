# src/utils/db_utils.py

import logging
from pymongo import ASCENDING, DESCENDING # Import for index direction if needed

# --- Allowed Imports ---
# Standard libraries (logging, etc.) are fine.
# Other utilities from '.utils' might be okay if needed, e.g.:
# from .some_other_util import helper_func

# --- !!! Critical: Avoid Imports Leading to Circular Dependencies !!! ---
# DO NOT import directly from 'extensions.py', 'routes'/*, or 'sockets'/*
# Examples of imports to AVOID here:
# from ..extensions import db, socketio # WRONG - Circular
# from ..routes.auth_routes import bp # WRONG - Bad practice & potential circular
# ---

def log_db_update_result(update_result, username="N/A", identifier="N/A"):
    """Logs details of a MongoDB update_one or insert_one result."""
    if not update_result:
        logging.error(f"DB Result logging received None object for {username} (ID:{identifier})")
        return
    try:
        if hasattr(update_result, 'acknowledged'): # Standard UpdateResult/InsertOneResult
            if hasattr(update_result, 'inserted_id'): # InsertOneResult
                logging.debug(f"DB Insert Result for {username} (ID:{identifier}): New ObjectId: {update_result.inserted_id}, Ack={update_result.acknowledged}")
                if update_result.acknowledged:
                     logging.info(f"DB: INSERTED new doc for {username} (ID:{identifier}). New ObjectId: {update_result.inserted_id}")
                else:
                     logging.error(f"DB ERROR for {username} (ID:{identifier}): Insert command was NOT acknowledged.")
            elif hasattr(update_result, 'matched_count'): # UpdateResult
                logging.debug(f"DB Update Result for {username} (ID:{identifier}): Matched={update_result.matched_count}, Modified={update_result.modified_count}, UpsertedId={update_result.upserted_id}, Ack={update_result.acknowledged}")
                if update_result.acknowledged:
                    if update_result.upserted_id:
                        logging.info(f"DB: UPSERTED new doc for {username} (ID:{identifier}). ObjectId: {update_result.upserted_id}")
                    elif update_result.modified_count > 0:
                        logging.info(f"DB: UPDATED existing doc for {username} (ID:{identifier}). {update_result.modified_count} modified.")
                    elif update_result.matched_count >= 1 and update_result.modified_count == 0:
                        # This is normal if the update didn't change anything or $setOnInsert was used on existing doc
                        logging.debug(f"DB: Matched doc for {username} (ID:{identifier}) but modified 0.")
                    elif update_result.matched_count == 0 and not update_result.upserted_id:
                        logging.warning(f"DB Warning for {username} (ID:{identifier}): Matched 0 and no upsert ID. Document may not exist or filter is incorrect.")
                    else: # matched > 1 (unlikely with unique IDs) or other cases
                         logging.debug(f"DB: Update status for {username} (ID:{identifier}) - Matched:{update_result.matched_count}, Modified:{update_result.modified_count}, Upserted:{update_result.upserted_id}")
                else:
                    logging.error(f"DB ERROR for {username} (ID:{identifier}): Update command was NOT acknowledged by server.")
            else:
                 logging.warning(f"Received unknown DB result type (has 'acknowledged' but not insert/update structure) for {username} (ID:{identifier}): {type(update_result)}")
        else:
            # Handle other types of results if necessary, or log that it's unexpected
            logging.warning(f"Received unexpected DB result type for {username} (ID:{identifier}): {type(update_result)}")
            logging.debug(f"Unexpected DB Result content: {update_result}")

    except Exception as log_db_err:
        logging.error(f"Error logging DB update result for {username} (ID:{identifier}): {log_db_err}", exc_info=True)


def ensure_indexes(db):
    """
    Creates necessary indexes on the database collections if they don't exist.
    Takes the PyMongo Database object as input.
    """
    if not db:
        logging.error("Cannot ensure indexes: Database object provided is None.")
        return

    # Define indexes: { collection_name: [ (field_name, options_dict), ... ], ... }
    # Use pymongo constants like ASCENDING if needed, otherwise 1 for ascending is fine.
    collection_index_map = {
        "registrations": [
            ("username", {"unique": True, "sparse": True}),
            ("email", {"unique": True, "sparse": True}),
            ("google_id", {"unique": True, "sparse": True}),
        ],
        "general_chats": [
            # Unique index if only ONE general chat history per user is allowed
            ("user_id", {"unique": True})
            # Non-unique index if multiple general chats per user are possible (e.g., by session)
            # ("user_id", {}),
        ],
        "education_chats": [("user_id", {})], # Index for faster lookup by user
        "healthcare_chats": [("user_id", {})],
        "construction_agent_interactions": [("user_id", {})],
        "pdf_analysis": [
            ("user_id", {}), # Find analyses by user
            ("upload_timestamp", {}) # Sort by upload time
            ],
        "pdf_chats": [
            ("pdf_analysis_id", {}), # Find chats related to a specific PDF analysis
            ("user_id", {}) # Optionally index by user too if needed for direct query
            ],
        "voice_conversations": [
            ("user_id", {"unique": True}), # Assuming one voice convo history per user
            ],
        "analysis_uploads": [
            ("user_id", {}), # Find uploads by user
            ("upload_timestamp", {}), # Sort by upload time
            ("last_modified", {}) # Sort by last modified time
            ],
        "news_articles": [ # If storing articles
            ("url", {"unique": True, "sparse": True}), # Ensure unique URLs, allow docs without URL
            ("fetched_at", {}), # Query/sort by fetch time
            ("publish_date", {}) # Query/sort by publish time
        ],
        # Add other collections and their desired indexes here
        "input_prompts": [
             ("user_id", {}),
             ("timestamp", {})
             ],
        "documentation": [
             ("user_id", {}),
             ("timestamp", {}),
             ("input_prompt_id", {})
             ],
        "chats": [ # Original 'report' chat collection
            ("documentation_id", {}),
            # ("user_id", {}) # If user info is added
            ]
    }

    logging.info("Ensuring database indexes...")
    all_collections = []
    try:
        all_collections = db.list_collection_names()
        logging.debug(f"Found collections: {all_collections}")
    except Exception as list_coll_err:
        logging.error(f"Failed to list database collections: {list_coll_err}. Skipping index creation.")
        return

    for coll_name, indexes_to_create in collection_index_map.items():
        if coll_name not in all_collections:
            logging.warning(f"Collection '{coll_name}' configured for indexing not found in DB. Skipping.")
            continue

        collection = db[coll_name]
        logging.debug(f"Processing indexes for collection: '{coll_name}'")
        try:
            # Get existing index information
            existing_index_info = collection.index_information()
            existing_index_names = list(existing_index_info.keys())
            logging.debug(f"Existing indexes for '{coll_name}': {existing_index_names}")

            for field, options in indexes_to_create:
                # Generate a predictable index name (e.g., 'user_id_1', 'email_1_sparse_unique')
                # This helps check if an equivalent index already exists, even if MongoDB assigned a different name.
                index_key_tuple = tuple(sorted([(field, 1)])) # PyMongo uses 1 for ASCENDING direction
                index_name_parts = [f"{k}_{v}" for k, v in index_key_tuple]

                # Check if options make it unique or sparse etc. to add to name
                if options.get('unique'): index_name_parts.append("unique")
                if options.get('sparse'): index_name_parts.append("sparse")
                # Add other common options if needed (e.g., ttl)

                proposed_index_name = "_".join(index_name_parts)

                # Check if an index with the same key specification already exists
                index_exists = False
                for name, info in existing_index_info.items():
                    # Compare the 'key' part of the index info
                    if tuple(sorted(info.get('key', []))) == index_key_tuple:
                        # Basic check passed, could compare options more rigorously if needed
                        index_exists = True
                        logging.debug(f"Index on field '{field}' (Key: {index_key_tuple}) already exists as '{name}' in '{coll_name}'. Skipping creation.")
                        break # Found equivalent index

                if not index_exists:
                    try:
                        # Add the generated name to options if you want consistent naming
                        create_options = options.copy()
                        create_options['name'] = proposed_index_name
                        collection.create_index([(field, 1)], **create_options) # Pass options dict
                        logging.info(f"Successfully created index '{proposed_index_name}' on {coll_name}.{field} with options {create_options}")
                    except Exception as idx_err:
                        # Log specific error but continue trying other indexes/collections
                        logging.warning(f"Failed to create index '{proposed_index_name}' on {coll_name}.{field}: {idx_err}")
                # else: # Already logged existence above
                     # pass

        except Exception as list_idx_err:
            logging.error(f"Could not list or process indexes for collection '{coll_name}': {list_idx_err}")
            # Continue to the next collection

    logging.info("Finished checking/ensuring database indexes.")