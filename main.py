# app.py
from flask import Flask, render_template, request, jsonify, send_file, Response
from browser_controller import BrowserController
import io
import time
import threading
import os
import uuid # For unique task IDs

# --- Global Variables & Configuration ---
browser_controller = None
app_ready = False

browser_lock = threading.Lock() # Still useful for shared Python data structures if any
command_queue = []
command_event = threading.Event()

# Store results of asynchronous tasks (like screenshots)
# Key: task_id, Value: {'result': data, 'status': 'pending'/'done'/'error'}
async_task_results = {}
async_task_lock = threading.Lock() # To protect access to async_task_results

# --- Command Parsing (remains the same) ---
def parse_simple_command(command_str: str):
    # ... (same as before) ...
    if not command_str or not command_str.strip():
        return {"action": "error", "message": "Command cannot be empty."}
    parts = command_str.strip().split(" ", 2)
    action_type = parts[0].lower()
    action_item = {"action": action_type}
    if not parts: return None
    if action_type == "navigate":
        if len(parts) > 1: action_item["url"] = parts[1]
        else: return {"action": "error", "message": "Navigate command needs a URL."}
    elif action_type == "type":
        if len(parts) > 2:
            action_item["selector"] = parts[1]
            action_item["text_to_type"] = parts[2]
        else: return {"action": "error", "message": "Type command needs selector and text."}
    elif action_type == "click":
        if len(parts) > 1: action_item["selector"] = parts[1]
        else: return {"action": "error", "message": "Click command needs a selector."}
    elif action_type == "press_key":
        if len(parts) > 1: action_item["key"] = parts[1]
        else: return {"action": "error", "message": "Press_key command needs a key."}
    else: return {"action": "error", "message": f"Unknown command: {action_type}"}
    return action_item

# --- Browser Worker Thread ---
def browser_thread_worker():
    global browser_controller, app_ready, async_task_results
    print("Browser worker thread started.")
    try:
        browser_controller = BrowserController(headless=True)
        app_ready = True
        print("Browser and Playwright initialized successfully in worker thread.")
    except Exception as e:
        print(f"FATAL ERROR: Could not initialize BrowserController in worker thread: {e}")
        app_ready = False
        return

    while True:
        command_event.wait()
        command_event.clear()

        if not command_queue:
            continue

        task = command_queue.pop(0) # task is a dict
        task_type = task.get('type', 'user_command') # 'user_command', 'get_screenshot', 'get_url'
        task_id = task.get('id') # For async tasks like screenshot

        current_logs = []

        # No need for browser_lock here as this *is* the browser thread
        # All browser_controller calls happen here.

        try:
            if not browser_controller or not browser_controller.page:
                raise RuntimeError("Browser page is not available or controller not initialized.")

            if task_type == 'user_command':
                raw_command_str = task['command_string']
                current_logs.append(f"Processing raw command: '{raw_command_str}'")
                action_item = parse_simple_command(raw_command_str)

                if not action_item or action_item.get("action") == "error":
                    error_message = action_item.get("message") if action_item else "Invalid command format."
                    current_logs.append(f"COMMAND PARSE ERROR: {error_message}")
                    task['result_data'] = {"status": "error", "message": error_message, "logs": current_logs}
                else:
                    action_type_parsed = action_item.get("action")
                    current_logs.append(f"Parsed action: {action_type_parsed}, Params: {action_item}")
                    if action_type_parsed == "navigate":
                        browser_controller.navigate(action_item.get("url"))
                    elif action_type_parsed == "type":
                        browser_controller.type_text(action_item.get("selector"), action_item.get("text_to_type"))
                    elif action_type_parsed == "click":
                        browser_controller.click_element(action_item.get("selector"))
                    elif action_type_parsed == "press_key":
                        browser_controller.press_key(action_item.get("key"))

                    time.sleep(0.2)
                    browser_controller.page.wait_for_load_state("domcontentloaded", timeout=5000)
                    current_logs.append(f"Action '{action_type_parsed}' executed successfully.")
                    task['result_data'] = {"status": "success", "message": f"Action '{action_type_parsed}' processed.", "logs": current_logs}

            elif task_type == 'get_screenshot':
                img_bytes = browser_controller.take_screenshot_bytes()
                with async_task_lock:
                    async_task_results[task_id] = {'status': 'done', 'result': img_bytes}
                # This task type doesn't need to set task['result_data'] for the main command loop

            elif task_type == 'get_url':
                url = browser_controller.get_current_url()
                with async_task_lock:
                    async_task_results[task_id] = {'status': 'done', 'result': url}
                # This task type doesn't need to set task['result_data'] for the main command loop

        except Exception as e:
            error_msg = f"WORKER THREAD ERROR during '{task_type}': {str(e)}"
            print(error_msg)
            current_logs.append(error_msg)
            if task_type == 'user_command':
                task['result_data'] = {"status": "error", "message": error_msg, "logs": current_logs}
            elif task_id: # For async tasks like screenshot/url
                with async_task_lock:
                    async_task_results[task_id] = {'status': 'error', 'result': str(e)}
        # End of try-except block

# --- Flask Application Setup (remains the same) ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

def _queue_and_wait_for_task_result(task_type, timeout=5):
    """Helper to queue a task for the worker and wait for its result via async_task_results."""
    if not app_ready:
        return None, "App not ready"

    task_id = str(uuid.uuid4())
    with async_task_lock:
        async_task_results[task_id] = {'status': 'pending', 'result': None}

    command_queue.append({'type': task_type, 'id': task_id})
    command_event.set()

    start_time = time.time()
    while (time.time() - start_time) < timeout:
        with async_task_lock:
            task_data = async_task_results.get(task_id)
            if task_data and task_data['status'] != 'pending':
                # Clean up the result once fetched
                result_to_return = task_data['result']
                del async_task_results[task_id]
                if task_data['status'] == 'error':
                    return None, str(result_to_return) # Error message
                return result_to_return, None # Data, no error
        time.sleep(0.05) # Poll frequently

    # Timeout
    with async_task_lock: # Cleanup if timed out
        if task_id in async_task_results:
            del async_task_results[task_id]
    return None, f"{task_type} task timed out after {timeout}s"


@app.route('/screenshot')
def screenshot_route():
    if not app_ready:
        try: # Placeholder logic
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (800, 600), color = 'darkgrey')
            d = ImageDraw.Draw(img); d.text((30,30), "Browser services not ready.", fill=(255,255,0))
            byte_arr = io.BytesIO(); img.save(byte_arr, format='JPEG'); byte_arr.seek(0)
            return send_file(byte_arr, mimetype='image/jpeg')
        except ImportError: return "Pillow not installed.", 500
        except Exception as e: return f"Error placeholder: {e}", 500

    img_bytes, error_msg = _queue_and_wait_for_task_result('get_screenshot', timeout=10) # Increased timeout for screenshot

    if error_msg:
        print(f"Error in screenshot_route: {error_msg}")
        # Optionally return a placeholder error image here too
        return f"Server error generating screenshot: {error_msg}", 500

    if not img_bytes:
        return "Failed to capture screenshot (empty bytes returned from worker).", 500

    return send_file(io.BytesIO(img_bytes), mimetype='image/jpeg')

@app.route('/current_url')
def current_url_route():
    if not app_ready:
        return jsonify({"url": "Browser services not ready."})

    url_data, error_msg = _queue_and_wait_for_task_result('get_url', timeout=3)

    if error_msg:
        print(f"Error in current_url_route: {error_msg}")
        return jsonify({"url": f"Error fetching URL: {error_msg}"})

    return jsonify({"url": url_data})


@app.route('/command', methods=['POST'])
def command_route():
    if not app_ready:
        return jsonify({"status": "error", "message": "Backend browser services not ready."}), 503

    data = request.get_json()
    if not data or 'command_string' not in data:
        return jsonify({"status": "error", "message": "Invalid request: 'command_string' not found."}), 400

    raw_command_str = data.get('command_string')
    if not raw_command_str or not raw_command_str.strip():
         return jsonify({"status": "error", "message": "Command string cannot be empty."}), 400

    # 'result_data' will be populated by the worker thread for user commands
    task_info = {'type': 'user_command', 'command_string': raw_command_str, 'result_data': None}

    command_queue.append(task_info)
    command_event.set()

    processing_timeout_seconds = 60
    start_time = time.time()
    while task_info['result_data'] is None and (time.time() - start_time) < processing_timeout_seconds:
        time.sleep(0.1)

    if task_info['result_data']:
        return jsonify(task_info['result_data'])
    else:
        try:
            if task_info in command_queue: command_queue.remove(task_info)
        except ValueError: pass
        return jsonify({
            "status": "error", "message": "Command processing timed out on the server.",
            "logs": [f"Server timeout for command: '{raw_command_str}'"]
        }), 504

# --- Main Execution (remains the same) ---
if __name__ == '__main__':
    print("Starting application...")
    print("Initializing browser worker thread...")
    worker_thread = threading.Thread(target=browser_thread_worker, daemon=True)
    worker_thread.start()

    print("Waiting for browser initialization to complete in worker thread...")
    initialization_timeout = 45
    wait_start_time = time.time()
    while not app_ready and (time.time() - wait_start_time) < initialization_timeout:
        time.sleep(0.5); print(".", end="", flush=True)
    print("")

    if not app_ready:
        print("FATAL ERROR: Browser worker thread did not initialize. Exiting.")
        exit(1)

    print("Browser initialization complete. Flask application is ready.")
    print("Access the application at http://0.0.0.0:3000 (or http://localhost:3000)")
    app.run(host='0.0.0.0', port=3000, debug=False, use_reloader=False) # Important: use_reloader=False

    print("Application shutting down...")
    if browser_controller: # No lock needed here, main thread exit
        try: browser_controller.close(); print("Browser controller closed.")
        except Exception as e: print(f"Error during browser cleanup: {e}")
