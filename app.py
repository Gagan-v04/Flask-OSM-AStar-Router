import os
import webbrowser # Auto-open
import threading  # Auto-open timer
from flask import Flask, render_template, request, jsonify
from path_planning import calculate_shortest_path
import traceback # For detailed error printing

app = Flask(__name__)

# --- Configuration ---
# IMPORTANT: Define the correct path to YOUR PBF file relative to where app.py is run!
PBF_MAP_PATH = "data/raw/map_1.pbf"

# --- Routes ---
@app.route('/')
def index():
    """Serves the main HTML page which initializes Leaflet directly."""
    print("Serving index page (Direct Leaflet Init in Frontend)")
    # No Folium map generation needed here
    return render_template('index.html')

@app.route('/plan_path', methods=['POST'])
def plan_path_endpoint():
    """
    Handles path planning requests. Expects JSON input with start/end coords.
    Returns JSON with path coordinates, time, and distance, or an error.
    """
    print("\nReceived request for /plan_path (JSON expected)")

    if not request.is_json:
        print("Error: Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    print(f"Request JSON data: {data}")

    # Get coordinates from JSON payload
    start_lat = data.get('start_lat')
    start_lng = data.get('start_lng')
    end_lat = data.get('end_lat')
    end_lng = data.get('end_lng')

    if None in [start_lat, start_lng, end_lat, end_lng]:
        print("Error: Missing coordinate data in JSON")
        return jsonify({"error": "Missing start or end coordinates"}), 400

    try:
        # Convert coordinates to float tuples (lat, lon)
        start_coord = (float(start_lat), float(start_lng))
        end_coord = (float(end_lat), float(end_lng))
    except (ValueError, TypeError):
         print("Error: Invalid coordinate format (must be numbers)")
         return jsonify({"error": "Invalid coordinate format"}), 400

    # Check if the hardcoded PBF file exists before proceeding
    if not os.path.exists(PBF_MAP_PATH):
        abs_path = os.path.abspath(PBF_MAP_PATH)
        print(f"Error: PBF file not found at configured path: {PBF_MAP_PATH}")
        print(f"Absolute path checked: {abs_path}")
        return jsonify({"error": "Server configuration error: PBF map data file not found."}), 500

    # Call the path planning function using the hardcoded PBF path
    try:
        # Expects a dictionary: {"path": [[lat,lon],...], "time_sec": float, "dist_m": float} or None
        result_data = calculate_shortest_path(start_coord, end_coord, PBF_MAP_PATH)

        if result_data and result_data.get("path"):
            print(f"Path calculation successful. Time: {result_data.get('time_sec')}, Dist: {result_data.get('dist_m')}")
            # Return the whole dictionary (path, time_sec, dist_m)
            return jsonify(result_data)
        else:
            # Handles both None return and cases where path might be missing from dict
            print("Path calculation returned None or result missing 'path' key.")
            return jsonify({"error": "No path found or calculation error occurred."}), 404

    except Exception as e:
        print(f"Error during path calculation call: {e}")
        traceback.print_exc() # Print full traceback to server console
        return jsonify({"error": f"An internal server error occurred during path planning: {e}"}), 500

# --- Function to Open Browser 
def open_browser(host='127.0.0.1', port=5000):
    """Opens the default web browser to the specified Flask server address."""
    url = f"http://{host}:{port}"
    print(f"Attempting to open browser at {url}...")
    try:
        success = webbrowser.open(url, new=2) # new=2 typically opens a new tab
        print(f"Browser open command issued. Success flag: {success}")
        if not success: # Try getting default explicitly if open fails
             print("webbrowser.open reported failure. Trying get().")
             browser = webbrowser.get()
             browser.open(url, new=2)
    except Exception as e:
        print(f"Failed to automatically open browser: {e}")


# --- Main Execution Block ---
if __name__ == '__main__':
    host = '127.0.0.1'
    port = 5000

    # Auto-open browser ---
    print("Server starting... will attempt to open browser shortly.")
    threading.Timer(1.0, lambda: open_browser(host=host, port=port)).start()
    print(f"Flask server starting on http://{host}:{port}")
    abs_pbf_path = os.path.abspath(PBF_MAP_PATH)
    print(f"Using PBF map for path planning: {abs_pbf_path}")
    if not os.path.exists(PBF_MAP_PATH):
        print(f"⚠️ WARNING: PBF file not found at the specified path! Path planning will fail.")

    # use_reloader=False is important if using the auto-open timer
    app.run(debug=True, host=host, port=port, use_reloader=False)