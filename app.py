# Add render_template to the imports
from flask import Flask, request, jsonify, render_template
import logging
import json
import os
from datetime import datetime, timezone

app = Flask(__name__)

# ... (keep logging, DATA_FILE, reputations, load_data, save_data) ...
# Configure logging
logging.basicConfig(level=logging.INFO)

# --- Data Persistence Setup ---
DATA_FILE = "reputation_data.json"
reputations = {}

def load_data():
    # ... (keep existing load_data function) ...
    global reputations
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                content = f.read()
                if not content:
                    app.logger.info(f"Data file '{DATA_FILE}' is empty. Starting fresh.")
                    reputations = {}
                    return
                reputations = json.loads(content)
                if not isinstance(reputations, dict):
                     raise ValueError("Loaded data is not a dictionary.")
                app.logger.info(f"Loaded data from {DATA_FILE}")
        except (json.JSONDecodeError, IOError, ValueError, Exception) as e:
            app.logger.error(f"Error loading data from {DATA_FILE}: {e}. Starting with empty data.")
            reputations = {}
    else:
        app.logger.info(f"{DATA_FILE} not found. Starting with empty data.")
        reputations = {}

def save_data():
    # ... (keep existing save_data function) ...
    global reputations
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(reputations, f, indent=4)
        app.logger.debug(f"Data successfully saved to {DATA_FILE}")
    except (IOError, Exception) as e:
        app.logger.error(f"Error saving data to {DATA_FILE}: {e}")

load_data()
# -----------------------------

# --- Existing API Endpoints ---
# ... (keep /, /reputation POST, /reputation GET, /ranking, /clear routes unchanged) ...

@app.route('/')
def home():
    return "Reputation Server is running! Access the dashboard at /dashboard"

@app.route('/reputation/<string:name>', methods=['POST'])
def update_reputation(name):
    global reputations
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    update_value = data.get('update')
    if name == "serf":
        update_value = abs(update_value)
    motivation = data.get('motivation')
    if update_value is None: return jsonify({"error": "Missing 'update' key"}), 400
    try: update_value = int(update_value)
    except (ValueError, TypeError): return jsonify({"error": "'update' must be a number"}), 400
    if motivation is not None and not isinstance(motivation, str): return jsonify({"error": "'motivation' must be a string"}), 400
    name = name.strip().lower()
    if not name: return jsonify({"error": "Name cannot be empty"}), 400
    user_data = reputations.get(name, {"score": 0, "history": []})
    current_score = user_data.get("score", 0)
    history_list = user_data.get("history", [])
    timestamp = datetime.now(timezone.utc).isoformat()
    history_entry = {"update": update_value,"motivation": motivation,"timestamp": timestamp}
    new_score = current_score + update_value
    history_list.append(history_entry)
    reputations[name] = {"score": new_score, "history": history_list}
    save_data()
    log_message = f"Updated reputation for '{name}': {current_score} -> {new_score} (+{update_value})."
    if motivation: log_message += f" Motivation: '{motivation}'"
    app.logger.info(log_message)
    response_data = {"message": f"Reputation updated for '{name}'","name": name,"new_reputation": new_score,}
    if motivation is not None: response_data["motivation_received"] = motivation
    return jsonify(response_data), 200

@app.route('/reputation/<string:name>', methods=['GET'])
def get_reputation(name):
    name = name.strip().lower()
    user_data = reputations.get(name)
    if user_data is None: return jsonify({"error": f"Name '{name}' not found"}), 404
    else: return jsonify({"name": name,"reputation": user_data.get("score", 0),"history": user_data.get("history", [])}), 200

@app.route('/ranking', methods=['GET'])
def get_ranking():
    try:
        valid_items = [(name, data) for name, data in reputations.items() if isinstance(data, dict) and 'score' in data]
        sorted_reputations = sorted(valid_items, key=lambda item: item[1].get('score', 0), reverse=True)
        ranking = [{"name": name, "reputation": data["score"]} for name, data in sorted_reputations]
        return jsonify(ranking), 200
    except Exception as e:
        app.logger.error(f"Error generating ranking: {e}")
        return jsonify({"error": "Could not generate ranking"}), 500

@app.route('/clear', methods=['POST'])
def clear_data():
    global reputations
    count = len(reputations)
    reputations = {}
    save_data()
    app.logger.warning("Cleared all reputation data and saved empty state.")
    return jsonify({"message": f"Cleared {count} reputation entries."}), 200


# --- UPDATED VISUALIZATION ENDPOINT ---
@app.route('/dashboard', methods=['GET'])
def show_dashboard():
    """Renders the HTML dashboard visualizing scores and last motivation."""
    try:
        valid_items = [
            (name, data) for name, data in reputations.items()
            if isinstance(data, dict) and 'score' in data
        ]

        sorted_users_list = sorted(
            valid_items,
            key=lambda item: item[1].get('score', 0),
            reverse=True
        )

        # Prepare data for template, now including last motivation
        users_for_template = []
        for name, data in sorted_users_list:
            last_motivation_text = None # Default if no history
            user_history = data.get("history", []) # Get history list safely
            if user_history: # Check if the history list is not empty
                # Get the motivation from the *last* entry in the history list
                last_motivation_text = user_history[-1].get("motivation")

            users_for_template.append({
                "name": name,
                "reputation": data["score"],
                "last_motivation": last_motivation_text # Add it to the dict
            })

        return render_template('dashboard.html', users=users_for_template)

    except Exception as e:
        app.logger.error(f"Error generating dashboard: {e}")
        return "Error generating dashboard.", 500

# --- Main Execution ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)