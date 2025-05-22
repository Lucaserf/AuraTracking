# Add render_template to the imports
from flask import Flask, request, jsonify, render_template
import logging
import json
import os
from datetime import datetime, timezone

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# --- Data Persistence Setup ---
DATA_FILE = "reputation_data.json"
reputations = {}


def load_data():
    global reputations
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                content = f.read()
                if not content:
                    app.logger.info(
                        f"Data file '{DATA_FILE}' is empty. Starting fresh."
                    )
                    reputations = {}
                    return
                reputations = json.loads(content)
                if not isinstance(reputations, dict):
                    raise ValueError("Loaded data is not a dictionary.")
                app.logger.info(f"Loaded data from {DATA_FILE}")
        except (json.JSONDecodeError, IOError, ValueError, Exception) as e:
            app.logger.error(
                f"Error loading data from {DATA_FILE}: {e}. Starting with empty data."
            )
            reputations = {}  # Reset on error
    else:
        app.logger.info(f"{DATA_FILE} not found. Starting with empty data.")
        reputations = {}


def save_data():
    global reputations
    try:
        # Ensure consistent state before saving
        valid_data = {
            k: v for k, v in reputations.items() if isinstance(v, dict) and "score" in v
        }
        with open(DATA_FILE, "w") as f:
            json.dump(valid_data, f, indent=4)  # Save only valid data
        app.logger.debug(f"Data successfully saved to {DATA_FILE}")
    except (IOError, Exception) as e:
        app.logger.error(f"Error saving data to {DATA_FILE}: {e}")


load_data()
# -----------------------------


# --- Core Reputation Logic (Refactored Helper) ---
def _update_reputation_internal(name, update_value, motivation=None):
    """Internal helper to update reputation for a given name."""
    global reputations
    try:
        # Ensure name is clean and lowercase for consistency
        name = str(name).strip().lower()
        if not name:
            return {"error": "Name cannot be empty"}, 400

        # Validate update_value
        try:
            update_value = int(update_value)
        except (ValueError, TypeError):
            return {"error": "'update' must be a number"}, 400

        # Special handling for 'serf' - always positive update
        # if name == "serf":
        #     update_value = abs(update_value)

        # Validate motivation (allow None or string)
        if motivation is not None and not isinstance(motivation, str):
            return {"error": "'motivation' must be a string (or null)"}, 400
        # Treat empty string motivation as None for storage/history clarity
        if isinstance(motivation, str) and not motivation.strip():
            motivation = None

        # Get current data or initialize if new user
        user_data = reputations.get(name, {"score": 0, "history": []})
        current_score = user_data.get("score", 0)  # Safely get score
        history_list = user_data.get("history", [])  # Safely get history

        # Ensure history is a list (data sanity check)
        if not isinstance(history_list, list):
            app.logger.warning(
                f"Correcting invalid history type for user '{name}'. Found {type(history_list)}, expected list."
            )
            history_list = []

        # Create history entry
        timestamp = datetime.now(timezone.utc).isoformat()
        history_entry = {
            "update": update_value,
            "motivation": motivation,  # Store None if no motivation provided
            "timestamp": timestamp,
        }

        # Calculate new score and update history
        new_score = current_score + update_value
        history_list.append(history_entry)

        # Update the main reputations dictionary
        reputations[name] = {"score": new_score, "history": history_list}

        # Save the changes
        save_data()  # Save after every successful update

        # Log the update
        log_message = f"Updated reputation for '{name}': {current_score} -> {new_score} ({update_value:+})."  # Use :+ for sign
        if motivation:  # Only add motivation part if it exists
            log_message += f" Motivation: '{motivation}'"
        app.logger.info(log_message)

        # Prepare response data
        response_data = {
            "message": f"Reputation updated for '{name}'",
            "name": name,
            "new_reputation": new_score,
        }
        if motivation is not None:
            response_data["motivation_received"] = motivation

        return response_data, 200

    except Exception as e:
        app.logger.error(f"Internal error updating reputation for '{name}': {e}")
        return {"error": "An internal server error occurred during update."}, 500


# --- API Endpoints ---


@app.route("/")
def home():
    return "Reputation Server is running! Access the dashboard at /dashboard"


# Modified to use the helper function
@app.route("/reputation/<string:name>", methods=["POST"])
def update_reputation_api(name):
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    update_value = data.get("update")
    motivation = data.get("motivation")  # Can be None

    if update_value is None:
        return jsonify({"error": "Missing 'update' key"}), 400

    result, status_code = _update_reputation_internal(name, update_value, motivation)
    return jsonify(result), status_code


@app.route("/reputation/<string:name>", methods=["GET"])
def get_reputation(name):
    name = name.strip().lower()
    # Ensure data is valid before returning
    user_data = reputations.get(name)
    if user_data is None or not isinstance(user_data, dict) or "score" not in user_data:
        return jsonify({"error": f"Name '{name}' not found or data invalid"}), 404
    else:
        # Ensure history exists and is a list, provide default if missing/invalid
        history = user_data.get("history", [])
        if not isinstance(history, list):
            app.logger.warning(
                f"Invalid history type for '{name}' during GET. Returning empty list."
            )
            history = []

        return (
            jsonify(
                {
                    "name": name,
                    "reputation": user_data.get(
                        "score", 0
                    ),  # Default to 0 if score somehow missing
                    "history": history,
                }
            ),
            200,
        )


@app.route("/ranking", methods=["GET"])
def get_ranking():
    try:
        # Filter for valid entries before sorting
        valid_items = [
            (name, data)
            for name, data in reputations.items()
            if isinstance(data, dict) and "score" in data
        ]
        # Sort valid items
        sorted_reputations = sorted(
            valid_items,
            key=lambda item: item[1].get("score", 0),  # Safely access score
            reverse=True,
        )
        # Format output
        ranking = [
            {"name": name, "reputation": data["score"]}
            for name, data in sorted_reputations
        ]
        return jsonify(ranking), 200
    except Exception as e:
        app.logger.error(f"Error generating ranking: {e}")
        return jsonify({"error": "Could not generate ranking"}), 500


@app.route("/clear", methods=["POST"])
def clear_data():
    global reputations
    count = len(reputations)
    reputations = {}  # Clear in-memory data
    save_data()  # Save the empty state to file
    app.logger.warning("Cleared all reputation data and saved empty state.")
    return jsonify({"message": f"Cleared {count} reputation entries."}), 200


# --- Dashboard Endpoints ---


# Route to display the dashboard
@app.route("/dashboard", methods=["GET"])
def show_dashboard():
    """Renders the HTML dashboard visualizing scores and last motivation."""
    try:
        # Prepare data for the template, ensuring validity
        users_for_template = []
        valid_items = [
            (name, data)
            for name, data in reputations.items()
            if isinstance(data, dict) and "score" in data
        ]

        sorted_users_list = sorted(
            valid_items, key=lambda item: item[1].get("score", 0), reverse=True
        )

        for name, data in sorted_users_list:
            last_motivation_text = None
            user_history = data.get("history", [])  # Get history list safely
            current_total_score = data.get("score", 0)  # Get current total score

            # Check if history is a list and not empty
            if isinstance(user_history, list) and user_history:
                # Find the most recent entry *with* a motivation
                last_motivation_entry = next(
                    (
                        entry
                        for entry in reversed(user_history)
                        if isinstance(entry, dict) and entry.get("motivation")
                    ),
                    None,
                )
                if last_motivation_entry:
                    last_motivation_text = last_motivation_entry.get("motivation")

            # Prepare data for the chart
            user_chart_history_list = []  # Renamed to avoid confusion

            # Calculate the sum of all updates in the existing history
            sum_of_all_updates_in_history = sum(
                h.get("update", 0) for h in user_history if isinstance(h, dict)
            )
            # Determine the score before any recorded history events
            initial_score_offset = current_total_score - sum_of_all_updates_in_history

            cumulative_score_from_history = 0

            app.logger.debug(
                f"User '{name}': Raw history has {len(user_history)} entries."
            )

            # Ensure history is sorted by timestamp
            sorted_history_for_chart = sorted(
                [
                    h
                    for h in user_history
                    if isinstance(h, dict) and "timestamp" in h and "update" in h
                ],
                key=lambda x: x["timestamp"],
            )

            app.logger.debug(
                f"User '{name}': Filtered to {len(sorted_history_for_chart)} entries for chart."
            )
            if (
                not sorted_history_for_chart and user_history
            ):  # Log if filtering removed all entries but raw history existed
                app.logger.warning(
                    f"User '{name}': All raw history entries were filtered out. Check format. Raw: {user_history[:5]}"
                )

            for hist_entry in sorted_history_for_chart:
                cumulative_score_from_history += hist_entry["update"]
                # The score at this point in time is the initial offset + cumulative updates since history started
                score_at_timestamp = (
                    initial_score_offset + cumulative_score_from_history
                )
                user_chart_history_list.append(
                    {
                        "timestamp": hist_entry["timestamp"],
                        "score": score_at_timestamp,
                        "motivation": hist_entry.get("motivation"),
                        "update": hist_entry[
                            "update"
                        ],  # Add the delta (original update value)
                    }
                )

            user_chart_history_json_string = json.dumps(user_chart_history_list)

            if not user_chart_history_list:  # Check the list before dumping
                app.logger.info(
                    f"User '{name}': No chart history data will be generated (list is empty)."
                )

            users_for_template.append(
                {
                    "name": name,  # Keep lowercase name for IDs/JS
                    "display_name": name.capitalize(),  # Capitalize for display
                    "reputation": current_total_score,  # Use the authoritative current score
                    "last_motivation": last_motivation_text,
                    # Pass the pre-serialized JSON string
                    "chart_history_json": user_chart_history_json_string,
                }
            )

        # Add basic error template rendering capability
        error_template = """
        <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Error</title></head>
        <body><h1>Server Error</h1><p>{{ message }}</p></body></html>
        """
        return render_template("dashboard.html", users=users_for_template)

    except Exception as e:
        app.logger.error(f"Error generating dashboard: {e}")
        # Render a simple error page if template fails or other error occurs
        # You could create a proper templates/error.html file for this
        from flask import make_response

        error_html = (
            f"<h1>Error Generating Dashboard</h1><p>An internal error occurred: {e}</p>"
        )
        return make_response(error_html, 500)


# Route to handle updates from the dashboard UI
@app.route("/dashboard/update", methods=["POST"])
def update_reputation_dashboard():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    name = data.get("name")
    update_value = data.get("update")
    # *** Get motivation from JSON, default to None if not provided ***
    motivation = data.get("motivation", None)

    if name is None or update_value is None:
        return jsonify({"error": "Missing 'name' or 'update' in request"}), 400

    # Use the refactored internal function
    result, status_code = _update_reputation_internal(name, update_value, motivation)

    # Return the result from the internal function
    return jsonify(result), status_code


# --- Main Execution ---
if __name__ == "__main__":
    if not os.path.exists("templates"):
        os.makedirs("templates")
        print("Created 'templates' directory.")
    app.run(host="0.0.0.0", debug=True, port=5000)
