from flask import Flask, render_template, request, jsonify, send_file, Response
import io
import time
import threading
import os
import uuid
from playwright.sync_api import sync_playwright, Error as PlaywrightError
# Pillow (PIL) is used for placeholder images.
# Make sure it's installed: pip install Pillow
try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None
    print("WARNING: Pillow (PIL) not installed. Placeholder images will be basic or unavailable.")


# --- Global Variables & Configuration ---
browser_controller = None
app_ready = False # Flag to indicate if backend components are ready

DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 720

# For user commands and interaction commands
command_queue = []
command_event = threading.Event() # Signals worker that a new command/interaction or frame request is pending

# For MJPEG stream - a way to get the latest frame from the worker
latest_frame_bytes = None
latest_frame_lock = threading.Lock() # Protects access to latest_frame_bytes
# This event is set by gen_frames() to tell the worker to prioritize a frame capture
request_new_frame_event = threading.Event()

# --- Browser Controller Class ---
class BrowserController:
    def __init__(self, headless=True, viewport_width=DEFAULT_VIEWPORT_WIDTH, viewport_height=DEFAULT_VIEWPORT_HEIGHT):
        self.playwright = None
        self.browser = None
        self.page = None
        self._headless = headless
        self._viewport_width = viewport_width
        self._viewport_height = viewport_height
        self._initialize_browser()

    def _initialize_browser(self):
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self._headless)
            context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                viewport={"width": self._viewport_width, "height": self._viewport_height} # Explicit viewport
            )
            self.page = context.new_page()
            print(f"Browser initialized with viewport: {self._viewport_width}x{self._viewport_height}.")
        except Exception as e:
            print(f"Error initializing browser: {e}")
            if self.playwright:
                self.playwright.stop()
            raise

    def navigate(self, url):
        if not self.page:
            print("Page not initialized.")
            return
        print(f"Navigating to: {url}")
        try:
            self.page.goto(url, timeout=60000, wait_until="domcontentloaded")
        except PlaywrightError as e:
            print(f"Navigation error: {e}")
            raise

    def type_text(self, selector, text, attempt_descriptive=True):
        if not self.page: return
        print(f"Attempting to type '{text}' into '{selector}'")
        try:
            element = self.page.locator(selector).first
            element.fill(text)
            print(f"Typed '{text}' into '{selector}'")
        except PlaywrightError:
            if attempt_descriptive:
                print(f"CSS selector '{selector}' failed. Trying descriptive search (e.g., placeholder, aria-label).")
                common_input_selectors = [
                    f"input[placeholder*='{selector}' i]", f"textarea[placeholder*='{selector}' i]",
                    f"input[aria-label*='{selector}' i]", f"textarea[aria-label*='{selector}' i]",
                    f"input[name*='{selector}' i]",
                    f"*[data-testid*='{selector}' i]"
                ]
                for desc_selector in common_input_selectors:
                    try:
                        element = self.page.locator(desc_selector).first
                        element.scroll_into_view_if_needed(timeout=2000)
                        element.fill(text)
                        print(f"Typed '{text}' into descriptively found element for '{selector}' using '{desc_selector}'")
                        return
                    except PlaywrightError:
                        continue
            print(f"Could not find element '{selector}' to type into.")
            raise

    def click_element(self, selector, attempt_descriptive=True):
        if not self.page: return
        print(f"Attempting to click '{selector}'")
        try:
            element = self.page.locator(selector).first
            element.click(timeout=10000)
            print(f"Clicked '{selector}'")
        except PlaywrightError:
            if attempt_descriptive:
                print(f"CSS selector '{selector}' failed for click. Trying descriptive search (text, role, label).")
                try: self.page.get_by_text(selector, exact=False).first.click(timeout=5000); print(f"Clicked element with text matching '{selector}'"); return
                except PlaywrightError: pass
                try: self.page.get_by_role("button", name=selector, exact=False).first.click(timeout=5000); print(f"Clicked button role with name/text matching '{selector}'"); return
                except PlaywrightError: pass
                try: self.page.get_by_role("link", name=selector, exact=False).first.click(timeout=5000); print(f"Clicked link role with name/text matching '{selector}'"); return
                except PlaywrightError: pass
                try: self.page.locator(f"[data-testid*='{selector}' i]").first.click(timeout=5000); print(f"Clicked element with test ID matching '{selector}'"); return
                except PlaywrightError: pass
            print(f"Could not find element '{selector}' to click.")
            raise

    def press_key(self, key):
        if not self.page: return
        print(f"Pressing key: {key}")
        self.page.keyboard.press(key)

    def get_current_url(self):
        if not self.page: return "Page not available"
        return self.page.url

    def take_screenshot_bytes(self):
        if not self.page:
            if Image and ImageDraw:
                try:
                    img = Image.new('RGB', (self._viewport_width, self._viewport_height), color = 'grey')
                    d = ImageDraw.Draw(img)
                    d.text((10,10), "Browser not ready", fill=(255,255,0))
                    byte_arr = io.BytesIO()
                    img.save(byte_arr, format='JPEG')
                    return byte_arr.getvalue()
                except Exception as e_pil_ss:
                    print(f"Error creating placeholder screenshot: {e_pil_ss}")
                    return b'' # Fallback to empty bytes
            return b'' # If PIL not available
        try:
            return self.page.screenshot(type="jpeg", quality=70)
        except PlaywrightError as e:
            print(f"Error taking screenshot: {e}")
            return b'' # Fallback to empty bytes on error

    def get_viewport_size(self):
        if not self.page:
            print("Warning: get_viewport_size called but page not available. Returning configured size.")
            return {"width": self._viewport_width, "height": self._viewport_height}
        current_viewport = self.page.viewport_size
        if not current_viewport:
             print("Warning: page.viewport_size returned None. Returning configured size.")
             return {"width": self._viewport_width, "height": self._viewport_height}
        return current_viewport

    def mouse_click_at_coordinates(self, x, y):
        if not self.page:
            print("Page not initialized for mouse click.")
            raise RuntimeError("Page not available for mouse click.")
        print(f"Attempting to click at coordinates: X={x}, Y={y}")
        self.page.mouse.click(float(x), float(y))
        print(f"Clicked at coordinates: X={x}, Y={y}")

    def type_into_focused(self, text_to_type):
        if not self.page:
            print("Page not initialized for typing.")
            raise RuntimeError("Page not available for typing.")
        print(f"Attempting to type into focused element: '{text_to_type}'")
        self.page.keyboard.type(text_to_type) # Playwright handles if nothing is focused gracefully (usually no-op)
        print(f"Typed into focused element: '{text_to_type}'")

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("Browser closed.")

# --- Flask Application Setup ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Command Parsing Utility ---
def parse_simple_command(command_str: str):
    if not command_str or not command_str.strip():
        return {"action": "error", "message": "Command cannot be empty."}
    parts = command_str.strip().split(" ", 2)
    action_type = parts[0].lower()
    action_item = {"action": action_type}
    if not parts: return {"action": "error", "message": "Command parsing failed (empty parts)."}

    if action_type == "navigate":
        if len(parts) > 1: action_item["url"] = parts[1]
        else: return {"action": "error", "message": "Navigate command needs a URL. Usage: navigate <url>"}
    elif action_type == "type":
        if len(parts) > 2:
            action_item["selector"] = parts[1]
            action_item["text_to_type"] = parts[2]
        else: return {"action": "error", "message": "Type command needs a selector and text. Usage: type <selector> <text_to_type>"}
    elif action_type == "click":
        if len(parts) > 1: action_item["selector"] = parts[1]
        else: return {"action": "error", "message": "Click command needs a selector. Usage: click <selector>"}
    elif action_type == "press_key":
        if len(parts) > 1: action_item["key"] = parts[1]
        else: return {"action": "error", "message": "Press_key command needs a key. Usage: press_key <key_name>"}
    else: return {"action": "error", "message": f"Unknown command action: '{action_type}'. Supported: navigate, type, click, press_key"}
    return action_item

# --- Browser Worker Thread ---
def browser_thread_worker():
    global browser_controller, app_ready, latest_frame_bytes, latest_frame_lock, request_new_frame_event
    print("Browser worker thread started.")
    try:
        browser_controller = BrowserController(headless=True, viewport_width=DEFAULT_VIEWPORT_WIDTH, viewport_height=DEFAULT_VIEWPORT_HEIGHT)
        app_ready = True
        print("Browser and Playwright initialized successfully in worker thread.")
    except Exception as e:
        print(f"FATAL ERROR: Could not initialize BrowserController in worker thread: {e}")
        app_ready = False # Ensure this is set if initialization fails
        return

    # Initial placeholder frame
    if Image and ImageDraw:
        try:
            img = Image.new('RGB', (DEFAULT_VIEWPORT_WIDTH, DEFAULT_VIEWPORT_HEIGHT), color='darkgrey')
            d = ImageDraw.Draw(img); d.text((30, 30), "Initializing Stream...", fill=(255, 255, 0))
            byte_arr = io.BytesIO(); img.save(byte_arr, format='JPEG')
            with latest_frame_lock:
                latest_frame_bytes = byte_arr.getvalue()
        except Exception as e_pil_init:
            print(f"Error creating initial placeholder frame with PIL: {e_pil_init}")
            with latest_frame_lock: latest_frame_bytes = b''
    else:
        print("Pillow not installed, cannot create detailed placeholder images.")
        with latest_frame_lock: latest_frame_bytes = b''

    last_frame_capture_time = 0
    worker_frame_capture_interval = 0.2 # Target ~5 FPS for background capture

    while True:
        if request_new_frame_event.is_set():
            request_new_frame_event.clear()
            command_event.set()

        signaled_by_event = command_event.wait(timeout=worker_frame_capture_interval)

        if signaled_by_event:
            command_event.clear()

        if command_queue:
            task = command_queue.pop(0)
            task_type = task.get('type')
            current_logs = []
            if 'result_data' not in task: task['result_data'] = None

            try:
                if not browser_controller or not browser_controller.page:
                    # This check is crucial before any browser operation
                    raise RuntimeError("Browser page is not available or controller not initialized.")

                if task_type == 'user_command':
                    raw_command_str = task.get('command_string', '')
                    print(f"Worker: Dequeued user command: '{raw_command_str}'")
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
                            current_logs.append(f"Navigation to {action_item.get('url')} attempted.")
                        elif action_type_parsed == "type":
                            browser_controller.type_text(action_item.get("selector"), action_item.get("text_to_type"))
                        elif action_type_parsed == "click":
                            browser_controller.click_element(action_item.get("selector"))
                        elif action_type_parsed == "press_key":
                            browser_controller.press_key(action_item.get("key"))
                        # Common post-action steps
                        time.sleep(0.3) # Allow page to react/load
                        if browser_controller.page:
                           browser_controller.page.wait_for_load_state("domcontentloaded", timeout=7000)
                        current_logs.append(f"Action '{action_type_parsed}' executed.")
                        task['result_data'] = {"status": "success", "message": f"Action '{action_type_parsed}' processed.", "logs": current_logs}
                        command_event.set() # Signal to update frame immediately

                elif task_type == 'interaction_command':
                    interaction_details = task.get('interaction_details', {})
                    interaction_action = interaction_details.get('action')
                    print(f"Worker: Dequeued interaction command: {interaction_action}")
                    current_logs.append(f"Processing interaction: {interaction_action}, Details: {interaction_details}")

                    if interaction_action == "click_at_coords":
                        x = interaction_details.get("x")
                        y = interaction_details.get("y")
                        browser_controller.mouse_click_at_coordinates(x, y)
                        current_logs.append(f"Interaction: Clicked at ({float(x):.0f}, {float(y):.0f}).")
                    elif interaction_action == "type_direct":
                        text = interaction_details.get("text")
                        browser_controller.type_into_focused(text)
                        current_logs.append(f"Interaction: Typed directly '{text}'.")
                    else:
                        raise ValueError(f"Unknown interaction action: {interaction_action}")
                    # Common post-interaction steps
                    time.sleep(0.2)
                    if browser_controller.page:
                        browser_controller.page.wait_for_load_state("domcontentloaded", timeout=5000)
                    current_logs.append(f"Interaction action '{interaction_action}' executed.")
                    task['result_data'] = {"status": "success", "message": f"Interaction '{interaction_action}' processed.", "logs": current_logs}
                    command_event.set() # Signal for frame update

            except Exception as e:
                command_details = task.get('command_string', task.get('interaction_details', 'N/A'))
                error_msg = f"WORKER THREAD ERROR processing {task_type}: {str(e)}"
                print(f"{error_msg} (Details: {command_details})")
                current_logs.append(error_msg)
                task['result_data'] = {"status": "error", "message": error_msg, "logs": current_logs}
        # End of command/interaction processing

        # Capture and Update Screenshot Frame
        current_time = time.time()
        should_capture_frame = signaled_by_event or (current_time - last_frame_capture_time > worker_frame_capture_interval)

        if should_capture_frame:
            if app_ready and browser_controller and browser_controller.page:
                try:
                    frame = browser_controller.take_screenshot_bytes()
                    if frame:
                        with latest_frame_lock:
                            latest_frame_bytes = frame
                        last_frame_capture_time = current_time
                    else:
                        print("Worker: take_screenshot_bytes returned empty/None.")
                except Exception as e_frame:
                    print(f"WORKER THREAD: Error taking screenshot for MJPEG: {e_frame}")
            elif not app_ready:
                if Image and ImageDraw: # Try to update "Not Ready" placeholder
                    try:
                        img = Image.new('RGB', (DEFAULT_VIEWPORT_WIDTH, DEFAULT_VIEWPORT_HEIGHT), color='black')
                        d = ImageDraw.Draw(img); d.text((30, 30), "Browser Not Ready...", fill=(255, 0, 0))
                        byte_arr = io.BytesIO(); img.save(byte_arr, format='JPEG')
                        with latest_frame_lock: latest_frame_bytes = byte_arr.getvalue()
                    except Exception: pass # Ignore if PIL fails for placeholder here
# --- End of browser_thread_worker ---

# --- MJPEG Frame Generator ---
def gen_frames():
    global latest_frame_bytes, latest_frame_lock, request_new_frame_event, app_ready
    client_addr = "unknown_client"
    try: client_addr = request.remote_addr
    except RuntimeError: pass # Not in request context (e.g. if called directly, though unlikely for a generator)
    # print(f"DEBUG: MJPEG stream requested by client: {client_addr}")

    frame_error_count = 0
    MAX_FRAME_ERRORS_BEFORE_SLEEP = 5

    while True:
        if not app_ready:
            if Image and ImageDraw:
                try:
                    img = Image.new('RGB', (DEFAULT_VIEWPORT_WIDTH, DEFAULT_VIEWPORT_HEIGHT), color='black')
                    d = ImageDraw.Draw(img); d.text((10,10), "SERVER NOT READY", fill=(255,0,0))
                    byte_arr = io.BytesIO(); img.save(byte_arr, format='JPEG')
                    frame_to_send_error = byte_arr.getvalue()
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_to_send_error + b'\r\n')
                except Exception: yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n') # Empty frame
            else: yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n') # Empty frame if PIL fails
            time.sleep(1)
            continue

        request_new_frame_event.set() # Signal worker to prioritize a new frame
        frame_to_send = None
        timeout_get_frame = 0.15 # Max time to wait for a new frame from worker
        start_get_frame = time.time()

        # Try to get the latest frame from the worker
        while time.time() - start_get_frame < timeout_get_frame:
            with latest_frame_lock:
                if latest_frame_bytes: # Check if there's any frame
                    frame_to_send = latest_frame_bytes # Use the latest available
                    break # Got a frame
            time.sleep(0.01) # Small pause to not busy-wait too hard

        if not frame_to_send: # If timeout and still no frame (or it was empty)
            # This can happen if worker is very busy or screenshot failed silently
            # print(f"gen_frames: Timeout or no frame from worker for {client_addr}. Using last known or placeholder.")
            with latest_frame_lock: # Get whatever is there, even if old
                frame_to_send = latest_frame_bytes
            if not frame_to_send: # Still nothing
                if Image and ImageDraw:
                    try:
                        img = Image.new('RGB', (DEFAULT_VIEWPORT_WIDTH, DEFAULT_VIEWPORT_HEIGHT), color='gray')
                        d = ImageDraw.Draw(img); d.text((10,10), "No Frame Available", fill=(255,255,0))
                        byte_arr = io.BytesIO(); img.save(byte_arr, format='JPEG')
                        frame_to_send = byte_arr.getvalue()
                    except Exception: frame_to_send = b'' # Empty on error
                else: frame_to_send = b'' # Empty if no PIL
                # Avoid busy-looping if frames are consistently unavailable
                frame_error_count += 1
                if frame_error_count > MAX_FRAME_ERRORS_BEFORE_SLEEP:
                    time.sleep(0.5) # Longer sleep if frames are failing
                    frame_error_count = 0 # Reset counter
                else:
                    time.sleep(0.1)
                # Fall through to yield whatever frame_to_send is now
        else:
            frame_error_count = 0 # Reset error count on successful frame

        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
        time.sleep(0.05) # Target ~20 FPS from gen_frames, worker provides actual frames
    # except GeneratorExit: print(f"DEBUG: MJPEG stream for client {client_addr} ended.")
    # except Exception as e_gen: print(f"Error in gen_frames for client {client_addr}: {e_gen}")
# --- End of gen_frames ---

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    if not app_ready:
        # This will likely not be hit if gen_frames itself handles app_ready for initial stream
        return "Browser services not ready for video feed.", 503
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/current_url')
def current_url_route():
    if not app_ready or not browser_controller:
        return jsonify({"url": "Browser not ready..."})
    current_page_url = "N/A"
    try:
        if browser_controller.page:
            current_page_url = browser_controller.get_current_url()
    except Exception as e:
        print(f"Error in current_url_route: {e}")
        current_page_url = "Error fetching URL"
    return jsonify({"url": current_page_url})

@app.route('/command', methods=['POST'])
def command_route():
    # print(f"DEBUG: Flask: Received POST to /command")
    if not app_ready:
        # print("DEBUG: Flask: /command call but app not ready.")
        return jsonify({"status": "error", "message": "Backend browser services not ready."}), 503

    data = request.get_json()
    # print(f"DEBUG: Flask: /command payload: {data}")
    if not data or 'command_string' not in data:
        return jsonify({"status": "error", "message": "Invalid request: 'command_string' not found."}), 400

    raw_command_str = data.get('command_string')
    if not raw_command_str or not raw_command_str.strip():
         return jsonify({"status": "error", "message": "Command string cannot be empty."}), 400

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
        # Try to remove from queue to prevent eventual processing if it's still there
        try: command_queue.remove(task_info)
        except ValueError: pass # Already processed or removed
        return jsonify({
            "status": "error", "message": "Command processing timed out on the server.",
            "logs": [f"Server timeout for command: '{raw_command_str}'"]
        }), 504

@app.route('/viewport_size')
def viewport_size_route():
    if not app_ready or not browser_controller:
        return jsonify({
            "width": DEFAULT_VIEWPORT_WIDTH,
            "height": DEFAULT_VIEWPORT_HEIGHT,
            "source": "fallback_not_ready"
        })
    try:
        size = browser_controller.get_viewport_size()
        size["source"] = "live"
        return jsonify(size)
    except Exception as e:
        print(f"Error in /viewport_size: {e}")
        return jsonify({
            "error": str(e),
            "width": DEFAULT_VIEWPORT_WIDTH, # Fallback to configured defaults
            "height": DEFAULT_VIEWPORT_HEIGHT,
            "source": "error_fallback"
        }), 500

@app.route('/interact', methods=['POST'])
def interact_route():
    # print(f"DEBUG: Flask: Received POST to /interact")
    if not app_ready:
        # print("DEBUG: Flask: /interact call but app not ready.")
        return jsonify({"status": "error", "message": "Backend browser services not ready."}), 503

    data = request.get_json()
    # print(f"DEBUG: Flask: /interact payload: {data}")
    if not data or 'action' not in data:
        return jsonify({"status": "error", "message": "Invalid request: 'action' not found."}), 400

    interaction_action = data.get('action')
    task_info = {'type': 'interaction_command', 'interaction_details': data, 'result_data': None}

    if interaction_action == "click_at_coords":
        if 'x' not in data or 'y' not in data:
            return jsonify({"status": "error", "message": "Click action needs 'x' and 'y' coordinates."}), 400
    elif interaction_action == "type_direct":
        if 'text' not in data: # 'text' can be empty string, so check for key existence
            return jsonify({"status": "error", "message": "Type_direct action needs 'text' field."}), 400
    else:
        return jsonify({"status": "error", "message": f"Unknown interaction action: {interaction_action}"}), 400

    command_queue.append(task_info)
    command_event.set()

    processing_timeout_seconds = 30 # Interactions should be quicker
    start_time = time.time()
    while task_info['result_data'] is None and (time.time() - start_time) < processing_timeout_seconds:
        time.sleep(0.05)

    if task_info['result_data']:
        return jsonify(task_info['result_data'])
    else:
        try: command_queue.remove(task_info)
        except ValueError: pass
        return jsonify({
            "status": "error", "message": "Interaction processing timed out on the server.",
            "logs": [f"Server timeout for interaction: '{interaction_action}' with details: {data}"]
        }), 504
# --- End of Flask Routes ---

# --- Main Execution ---
if __name__ == '__main__':
    print("Starting application...")
    if not Image or not ImageDraw:
        print("WARNING: Pillow (PIL) is not installed. Placeholder images for the stream will be basic or unavailable.")
        print("         Consider installing it: pip install Pillow")


    print("Initializing browser worker thread...")
    worker_thread = threading.Thread(target=browser_thread_worker, daemon=True)
    worker_thread.start()

    print("Waiting for browser initialization to complete in worker thread...")
    initialization_timeout = 45
    wait_start_time = time.time()
    while not app_ready and (time.time() - wait_start_time) < initialization_timeout:
        time.sleep(0.5)
        print(".", end="", flush=True)
    print("")

    if not app_ready:
        print("FATAL ERROR: Browser worker thread did not initialize within the timeout period.")
        print("The application cannot start. Check server logs for errors (Playwright, browser_controller).")
        exit(1)

    print("Browser initialization complete. Flask application is ready.")
    print(f"Access the application at http://0.0.0.0:3000 (or http://localhost:3000)")
    print(f"Playwright browser viewport configured to: {DEFAULT_VIEWPORT_WIDTH}x{DEFAULT_VIEWPORT_HEIGHT}")

    app.run(host='0.0.0.0', port=3000, debug=False, use_reloader=False)

    print("Application shutting down...")
    if browser_controller:
        try:
            browser_controller.close()
            print("Browser controller closed.")
        except Exception as e:
            print(f"Error during browser controller cleanup: {e}")