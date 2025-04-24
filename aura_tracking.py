from flask import Flask, request, jsonify
import logging # Import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO) # Log INFO level messages and above

# In-memory storage for reputations: { name: {"score": value, "last_motivation": "some string or None"} }
# WARNING: Data is lost on server restart! Use a database for persistence.
reputations = {}

@app.route('/')
def home():
    """Basic welcome message."""
    return "Reputation Server is running!"

@app.route('/reputation/<string:name>', methods=['POST'])
def update_reputation(name):
    """
    Updates the reputation for a given name.
    Expects JSON data like: {"update": 5, "motivation": "Helped debug issue"}
    The "motivation" field is optional.
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    update_value = data.get('update')
    motivation = data.get('motivation') # Get the motivation string (optional)

    # --- Validation ---
    if update_value is None:
        return jsonify({"error": "Missing 'update' key in JSON data"}), 400

    if not isinstance(update_value, (int, float)):
        try:
            update_value = int(update_value) # Try converting numeric strings
        except (ValueError, TypeError):
             return jsonify({"error": "'update' value must be a number"}), 400

    if motivation is not None and not isinstance(motivation, str):
        return jsonify({"error": "'motivation' value must be a string"}), 400

    # Clean the name (optional, but good practice)
    name = name.strip().lower()
    if not name:
         return jsonify({"error": "Name cannot be empty"}), 400

    # --- Get current state or initialize ---
    user_data = reputations.get(name, {"score": 0, "last_motivation": None})
    current_score = user_data["score"]

    # --- Calculate and Update ---
    new_score = current_score + update_value

    # Store the updated score and the new motivation (overwriting the old one)
    reputations[name] = {
        "score": new_score,
        "last_motivation": motivation # Store the new motivation, even if it's None
    }

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
    # Include the motivation in the response if it was provided
    if motivation is not None: # Check for None explicitly, as empty string "" is valid
         response_data["motivation_received"] = motivation

    return jsonify(response_data), 200


@app.route('/reputation/<string:name>', methods=['GET'])
def get_reputation(name):
    """Gets the current reputation details for a specific name."""
    name = name.strip().lower()
    user_data = reputations.get(name) # Returns None if name not found

    if user_data is None:
        return jsonify({"error": f"Name '{name}' not found"}), 404
    else:
        return jsonify({
            "name": name,
            "reputation": user_data["score"],
            "last_motivation": user_data["last_motivation"] # Return the last motivation
        }), 200

@app.route('/ranking', methods=['GET'])
def get_ranking():
    """
    Returns a list of all users ranked by reputation (highest first).
    """
    # Sort items (name, data_dict pairs) by score (item[1]['score']) in descending order
    sorted_reputations = sorted(
        reputations.items(),
        key=lambda item: item[1]['score'], # Access score inside the dictionary value
        reverse=True
    )

    # Format the output as a list of dictionaries (name and score)
    # We are not including 'last_motivation' in the ranking list by default,
    # but you could add it here if needed:
    # ranking = [{"name": name, "reputation": data["score"], "last_motivation": data["last_motivation"]}
    #            for name, data in sorted_reputations]
    ranking = [{"name": name, "reputation": data["score"]}
               for name, data in sorted_reputations]


    return jsonify(ranking), 200

# Optional: Add a route to clear all data (for testing)
@app.route('/clear', methods=['POST'])
def clear_data():
    """ Clears all reputation data. Use with caution! """
    global reputations
    count = len(reputations)
    reputations = {}
    app.logger.warning("Cleared all reputation data.")
    return jsonify({"message": f"Cleared {count} reputation entries."}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)