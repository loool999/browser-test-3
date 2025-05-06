import unittest
import requests
import json
import websocket
import time
import threading
import os
import sys
import signal
import subprocess
from urllib.parse import urljoin

# Test configuration
TEST_HOST = os.environ.get("TEST_HOST", "http://localhost:8001")
TEST_WS = os.environ.get("TEST_WS", "ws://localhost:8001/ws")
START_SERVER = os.environ.get("START_SERVER", "false").lower() == "true"
SERVER_PROCESS = None

def start_test_server():
    global SERVER_PROCESS
    print("Starting test server...")
    SERVER_PROCESS = subprocess.Popen([sys.executable, "main.py"], 
                                      env={**os.environ, "DEBUG": "true", "PORT": "8001"})
    # Wait for server to start
    time.sleep(2)
    
def stop_test_server():
    global SERVER_PROCESS
    if SERVER_PROCESS:
        print("Stopping test server...")
        SERVER_PROCESS.send_signal(signal.SIGTERM)
        SERVER_PROCESS.wait()

class HeadlessBrowserTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if START_SERVER:
            start_test_server()
        # Wait for server to be fully up
        max_retries = 10
        for i in range(max_retries):
            try:
                response = requests.get(urljoin(TEST_HOST, "/health"))
                if response.status_code == 200:
                    break
            except Exception:
                pass
            
            if i == max_retries - 1:
                raise Exception("Server did not start properly")
            time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        if START_SERVER:
            stop_test_server()

    def test_server_health(self):
        """Test server health endpoint."""
        response = requests.get(urljoin(TEST_HOST, "/health"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        # The browser might be in fallback mode, so we don't assert on browser_running

    def test_index_page(self):
        """Test index page loads."""
        response = requests.get(TEST_HOST)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Interactive Headless Browser", response.text)

    def test_api_status(self):
        """Test API status endpoint."""
        response = requests.get(urljoin(TEST_HOST, "/api/status"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("url", data)

    def test_websocket_connection(self):
        """Test WebSocket connection."""
        messages = []
        
        def on_message(ws, message):
            messages.append(json.loads(message))
            if len(messages) >= 2:  # Wait for at least two messages
                ws.close()
                
        def on_error(ws, error):
            self.fail(f"WebSocket error: {error}")
            
        def on_close(ws, close_status_code, close_msg):
            print(f"WebSocket closed: {close_status_code}, {close_msg}")
            
        def on_open(ws):
            print("WebSocket connected")
            
        # Create and start WebSocket connection
        ws = websocket.WebSocketApp(
            TEST_WS,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        # Wait for messages
        timeout = 10
        start_time = time.time()
        while len(messages) < 2 and time.time() - start_time < timeout:
            time.sleep(0.5)
            
        self.assertGreaterEqual(len(messages), 1, "Did not receive any messages from WebSocket")
        
        # Check if the first message contains screenshot data
        self.assertIn("type", messages[0])
        self.assertEqual(messages[0]["type"], "screenshot")
        self.assertIn("data", messages[0])
        self.assertIn("page_info", messages[0])

    def test_bookmarks_api(self):
        """Test bookmarks API endpoints."""
        # Get bookmarks
        response = requests.get(urljoin(TEST_HOST, "/api/bookmarks"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "success")
        
        # Add a bookmark
        response = requests.post(
            urljoin(TEST_HOST, "/api/bookmarks/add"),
            params={"url": "https://example.com", "title": "Example"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        
        # Get bookmarks again to verify addition
        response = requests.get(urljoin(TEST_HOST, "/api/bookmarks"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "success")
        
        # Check if our bookmark is in the list
        bookmark_urls = [b["url"] for b in data["bookmarks"]]
        self.assertIn("https://example.com", bookmark_urls)
        
        # Remove the bookmark
        response = requests.post(
            urljoin(TEST_HOST, "/api/bookmarks/remove"),
            params={"url": "https://example.com"}
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify removal
        response = requests.get(urljoin(TEST_HOST, "/api/bookmarks"))
        data = response.json()
        bookmark_urls = [b["url"] for b in data["bookmarks"]]
        self.assertNotIn("https://example.com", bookmark_urls)

    def test_form_data_api(self):
        """Test form data API endpoints."""
        # Add form data
        response = requests.post(
            urljoin(TEST_HOST, "/api/form-data/add"),
            params={"field": "test_field", "value": "test_value"}
        )
        self.assertEqual(response.status_code, 200)
        
        # Get form data
        response = requests.get(
            urljoin(TEST_HOST, "/api/form-data"),
            params={"field": "test_field"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["value"], "test_value")
        
        # Clear specific form data
        response = requests.post(
            urljoin(TEST_HOST, "/api/form-data/clear"),
            params={"field": "test_field"}
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify it's cleared
        response = requests.get(
            urljoin(TEST_HOST, "/api/form-data"),
            params={"field": "test_field"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "error")

    def test_history_api(self):
        """Test history API endpoints."""
        # Get history
        response = requests.get(urljoin(TEST_HOST, "/api/history"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "success")
        
        # Clear history
        response = requests.post(urljoin(TEST_HOST, "/api/history/clear"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "success")
        
        # Get history again to verify it's cleared
        response = requests.get(urljoin(TEST_HOST, "/api/history"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["history"]), 1)  # Should only have one item (current page)

if __name__ == "__main__":
    unittest.main()