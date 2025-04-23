from flask import Flask, request, jsonify
import logging
import json
import os # Needed for checking file existence

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- Data Persistence Setup ---
DATA_FILE = "reputation_data.json"

# Initialize reputations dictionary (will be populated by load_data)
reputations = {}

def load_data():
    """Loads reputation data from the JSON file."""
    global reputations
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                # Handle empty file case
                content = f.read()
                if not content:
                    app.logger.info(f"Data file '{DATA_FILE}' is empty. Starting fresh.")
                    reputations = {}
                    return # Exit function after setting to empty dict

                # If content exists, try to load JSON
                reputations = json.loads(content) # Use loads for string content
                app.logger.info(f"Loaded data from {DATA_FILE}")

        except json.JSONDecodeError:
            app.logger.error(f"Error decoding JSON from {DATA_FILE}. Starting with empty data.")
            reputations = {} # Start fresh if file is corrupt
        except IOError as e:
            app.logger.error(f"Could not read file {DATA_FILE}: {e}. Starting with empty data.")
            reputations = {} # Start fresh if file is unreadable
        except Exception as e:
            app.logger.error(f"An unexpected error occurred loading data: {e}. Starting with empty data.")
            reputations = {} # Catch-all for safety
    else:
        app.logger.info(f"{DATA_FILE} not found. Starting with empty data.")
        reputations = {} # Start fresh if file doesn't exist


def save_data():
    """Saves the current reputation data to the JSON file."""
    global reputations
    try:
        with open(DATA_FILE, 'w') as f:
            # Use indent for readability in the JSON file
            json.dump(reputations, f, indent=4)
        app.logger.debug(f"Data successfully saved to {DATA_FILE}") # Use debug level for frequent saves
    except IOError as e:
        app.logger.error(f"Could not write data to file {DATA_FILE}: {e}")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred saving data: {e}")

# --- Load data when the application starts ---
# Do this *before* defining routes that might depend on the data
load_data()
# -----------------------------

@app.route('/')
def home():
    """Basic welcome message."""
    return "Reputation Server is running!"

@app.route('/reputation/<string:name>', methods=['POST'])
def update_reputation(name):
    """
    Updates the reputation for a given name and saves the data.
    Expects JSON data like: {"update": 5, "motivation": "Helped debug issue"}
    """
    global reputations # Ensure we're modifying the global dict

    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    update_value = data.get('update')
    motivation = data.get('motivation')

    # --- Validation ---
    if update_value is None:
        return jsonify({"error": "Missing 'update' key in JSON data"}), 400
    try:
        update_value = int(update_value)
    except (ValueError, TypeError):
         return jsonify({"error": "'update' value must be a number"}), 400
    if motivation is not None and not isinstance(motivation, str):
        return jsonify({"error": "'motivation' value must be a string"}), 400

    name = name.strip().lower()
    if not name:
         return jsonify({"error": "Name cannot be empty"}), 400

    # --- Get current state or initialize ---
    # Use .copy() to avoid modifying the original during calculation if needed,
    # although here we overwrite it anyway. It's good practice for complex dicts.
    user_data = reputations.get(name, {"score": 0, "last_motivation": None}).copy()
    current_score = user_data["score"]

    # --- Calculate and Update ---
    new_score = current_score + update_value
    user_data["score"] = new_score
    # Only update motivation if it was provided in this request
    if motivation is not None:
        user_data["last_motivation"] = motivation
    # If motivation was not provided, keep the existing user_data["last_motivation"]

    reputations[name] = user_data # Put the updated/new user data back into the main dict

    # --- Save data ---
    save_data() # Save the entire reputations dict after modification

    # --- Logging ---
    log_message = f"Updated reputation for '{name}': {current_score} + {update_value} = {new_score}."
    if motivation:
        log_message += f" Motivation: '{motivation}'"
    app.logger.info(log_message)

    # --- Response ---
    response_data = {
        "message": f"Reputation updated for '{name}'",
        "name": name,
        "new_reputation": new_score,
    }
    if motivation is not None:
         response_data["motivation_received"] = motivation

    return jsonify(response_data), 200


@app.route('/reputation/<string:name>', methods=['GET'])
def get_reputation(name):
    """Gets the current reputation details for a specific name."""
    name = name.strip().lower()
    # Data is already loaded into the global 'reputations' dict
    user_data = reputations.get(name)

    if user_data is None:
        return jsonify({"error": f"Name '{name}' not found"}), 404
    else:
        return jsonify({
            "name": name,
            "reputation": user_data.get("score", 0), # Use .get for safety
            "last_motivation": user_data.get("last_motivation") # Use .get for safety
        }), 200


@app.route('/ranking', methods=['GET'])
def get_ranking():
    """
    Returns a list of all users ranked by reputation (highest first).
    """
    # Data is already loaded into the global 'reputations' dict
    try:
        # Ensure item[1] exists and has a 'score' key before sorting
        valid_items = [(name, data) for name, data in reputations.items() if isinstance(data, dict) and 'score' in data]

        sorted_reputations = sorted(
            valid_items,
            # Use .get with a default of 0 in case 'score' is missing somehow (though load/save should prevent this)
            key=lambda item: item[1].get('score', 0),
            reverse=True
        )

        ranking = [{"name": name, "reputation": data["score"]}
                   for name, data in sorted_reputations]

        return jsonify(ranking), 200
    except Exception as e:
        app.logger.error(f"Error generating ranking: {e}")
        return jsonify({"error": "Could not generate ranking"}), 500


@app.route('/clear', methods=['POST'])
def clear_data():
    """ Clears all reputation data and saves the empty state. """
    global reputations
    count = len(reputations)
    reputations = {}
    save_data() # Save the cleared state to the file
    app.logger.warning("Cleared all reputation data and saved empty state.")
    return jsonify({"message": f"Cleared {count} reputation entries."}), 200


if __name__ == '__main__':
    # Load data is called globally before app runs
    app.run(host="0.0.0.0",debug=True, port=5000)
    # Note: In debug mode with auto-reload, the script might run twice,
    # potentially causing double loading/logging on startup.
    # This is usually fine for development but something to be aware of.
    # Run with debug=False for production or testing persistence behavior reliably.