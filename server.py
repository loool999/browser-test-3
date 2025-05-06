import json
import asyncio
import logging
import os
import time
import base64
import secrets
from typing import List, Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import uvicorn

from browser import HeadlessBrowser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get configuration from environment variables
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
ENABLE_CORS = os.environ.get("ENABLE_CORS", "false").lower() == "true"
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").split(",")
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "false").lower() == "true"
AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "changeme")
FPS_LIMIT = int(os.environ.get("FPS_LIMIT", "10"))
SCREENSHOT_QUALITY = os.environ.get("SCREENSHOT_QUALITY", "medium")
MAX_CONNECTIONS = int(os.environ.get("MAX_CONNECTIONS", "10"))

# Initialize FastAPI app with optional docs
app = FastAPI(
    title="Interactive Headless Browser",
    description="A web-based interface for interacting with a headless browser",
    version="1.0.0",
    docs_url="/api/docs" if DEBUG else None,
    redoc_url="/api/redoc" if DEBUG else None
)

# Security setup for basic auth
security = HTTPBasic()

# Add CORS middleware if enabled
if ENABLE_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS[0] else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com;"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    return response

# Rate limiting setup
rate_limit_data = {}

def check_rate_limit(client_id: str, limit: int = 100, window: int = 60):
    """Basic rate limiting implementation"""
    now = time.time()
    # Clean up old entries
    for cid in list(rate_limit_data.keys()):
        if now - rate_limit_data[cid]["timestamp"] > window:
            del rate_limit_data[cid]
    
    # Check if client is rate limited
    if client_id in rate_limit_data:
        if rate_limit_data[client_id]["count"] >= limit:
            return False
        rate_limit_data[client_id]["count"] += 1
    else:
        rate_limit_data[client_id] = {"count": 1, "timestamp": now}
    
    return True

# Authentication function
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    if not REQUIRE_AUTH:
        return "anonymous"
        
    is_correct_username = secrets.compare_digest(credentials.username, AUTH_USERNAME)
    is_correct_password = secrets.compare_digest(credentials.password, AUTH_PASSWORD)
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Create a headless browser instance
user_data_dir = os.path.join(os.getcwd(), "browser_data")
os.makedirs(user_data_dir, exist_ok=True)
browser = HeadlessBrowser(user_data_dir=user_data_dir)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.screenshot_task = None
        self.running = False
        self.frame_rate = FPS_LIMIT
        self.screenshot_interval = 1.0 / self.frame_rate
        self.max_connections = MAX_CONNECTIONS
        self.quality = SCREENSHOT_QUALITY

    async def connect(self, websocket: WebSocket):
        # Check if we have too many connections
        if len(self.active_connections) >= self.max_connections:
            await websocket.close(code=1008, reason="Too many connections")
            return
            
        await websocket.accept()
        self.active_connections.append(websocket)
        if not self.running and not self.screenshot_task:
            self.running = True
            self.screenshot_task = asyncio.create_task(self.send_screenshots())

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if not self.active_connections and self.running:
            self.running = False
            if self.screenshot_task:
                self.screenshot_task.cancel()
                self.screenshot_task = None

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {str(e)}")
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        disconnected_ws = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {str(e)}")
                disconnected_ws.append(connection)
        
        # Clean up disconnected websockets
        for ws in disconnected_ws:
            self.disconnect(ws)
    
    async def send_screenshots(self):
        """Continuously send screenshots to all connected clients."""
        try:
            while self.running:
                if not self.active_connections:
                    await asyncio.sleep(0.1)
                    continue
                
                # Get new screenshot
                try:
                    screenshot = browser.get_screenshot()
                    if screenshot:
                        page_info = browser.get_page_info()
                        message = {
                            "type": "screenshot",
                            "data": screenshot,
                            "page_info": page_info
                        }
                        await self.broadcast(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error getting screenshot: {str(e)}")
                
                # Sleep for the screenshot interval
                await asyncio.sleep(self.screenshot_interval)
        except asyncio.CancelledError:
            logger.info("Screenshot task cancelled")
        except Exception as e:
            logger.error(f"Error in screenshot task: {str(e)}")
            self.running = False
            self.screenshot_task = None

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request, username: str = Depends(get_current_username)):
    """Serve the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "browser_running": browser.is_running}

# API endpoints
@app.get("/api/status")
async def get_status(username: str = Depends(get_current_username)):
    """Get the browser status."""
    return {
        "status": "running" if browser.is_running else "fallback",
        "url": browser.current_url
    }

@app.get("/api/page-info")
async def get_page_info(username: str = Depends(get_current_username)):
    """Get information about the currently loaded page."""
    return browser.get_page_info()

@app.get("/api/page-html")
async def get_page_html(username: str = Depends(get_current_username)):
    """Get the HTML source of the current page."""
    return browser.get_page_html()

@app.get("/api/history")
async def get_history(limit: int = None, username: str = Depends(get_current_username)):
    """Get the browsing history."""
    return browser.get_history(limit)

@app.post("/api/history/clear")
async def clear_history(username: str = Depends(get_current_username)):
    """Clear browsing history."""
    return browser.clear_history()

@app.get("/api/bookmarks")
async def get_bookmarks(folder: str = None, username: str = Depends(get_current_username)):
    """Get all bookmarks, optionally filtered by folder."""
    return browser.get_bookmarks(folder)

@app.post("/api/bookmarks/add")
async def add_bookmark(url: str = None, title: str = None, folder: str = None, username: str = Depends(get_current_username)):
    """Add a bookmark."""
    return browser.add_bookmark(url, title, folder)

@app.post("/api/bookmarks/remove")
async def remove_bookmark(url: str, username: str = Depends(get_current_username)):
    """Remove a bookmark."""
    return browser.remove_bookmark(url)

@app.get("/api/cookies")
async def get_cookies(domain: str = None, username: str = Depends(get_current_username)):
    """Get cookies for a domain or all domains."""
    return browser.get_cookies(domain)

@app.post("/api/cookies/clear")
async def clear_cookies(domain: str = None, username: str = Depends(get_current_username)):
    """Clear cookies for a domain or all domains."""
    return browser.clear_cookies(domain)

@app.get("/api/form-data")
async def get_form_data(field: str = None, username: str = Depends(get_current_username)):
    """Get stored form data."""
    return browser.get_form_data(field)

@app.post("/api/form-data/add")
async def add_form_data(field: str, value: str, username: str = Depends(get_current_username)):
    """Add form data for autofill."""
    return browser.add_form_data(field, value)

@app.post("/api/form-data/clear")
async def clear_form_data(field: str = None, username: str = Depends(get_current_username)):
    """Clear stored form data."""
    return browser.clear_form_data(field)

@app.post("/api/form/fill")
async def fill_form(form_data: Dict[str, str] = None, submit: bool = False, username: str = Depends(get_current_username)):
    """Fill a form on the current page."""
    return browser.fill_form(form_data, submit)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for browser interaction."""
    client_ip = websocket.client.host
    
    # Check rate limit for this client
    if not check_rate_limit(client_ip, limit=100, window=60):
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return
    
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action_type = message.get("type")
                
                # Process different message types
                if action_type == "navigate":
                    url = message.get("url")
                    result = browser.navigate(url)
                    await websocket.send_text(json.dumps({
                        "type": "navigate_result",
                        "result": result
                    }))
                
                elif action_type == "click":
                    x = message.get("x")
                    y = message.get("y")
                    result = browser.click(x, y)
                    await websocket.send_text(json.dumps({
                        "type": "click_result",
                        "result": result
                    }))
                
                elif action_type == "type":
                    text = message.get("text")
                    result = browser.type_text(text)
                    await websocket.send_text(json.dumps({
                        "type": "type_result",
                        "result": result
                    }))
                
                elif action_type == "key":
                    key = message.get("key")
                    result = browser.press_key(key)
                    await websocket.send_text(json.dumps({
                        "type": "key_result",
                        "result": result
                    }))
                
                elif action_type == "scroll":
                    x = message.get("x", 0)
                    y = message.get("y", 0)
                    result = browser.scroll(x, y)
                    await websocket.send_text(json.dumps({
                        "type": "scroll_result",
                        "result": result
                    }))
                
                elif action_type == "scroll_to_position":
                    x = message.get("x", 0)
                    y = message.get("y", 0)
                    result = browser.scroll_to_position(x, y)
                    await websocket.send_text(json.dumps({
                        "type": "scroll_to_position_result",
                        "result": result
                    }))
                
                elif action_type == "drag":
                    start_x = message.get("startX")
                    start_y = message.get("startY")
                    end_x = message.get("endX")
                    end_y = message.get("endY")
                    result = browser.drag(start_x, start_y, end_x, end_y)
                    await websocket.send_text(json.dumps({
                        "type": "drag_result",
                        "result": result
                    }))
                
                elif action_type == "back":
                    result = browser.go_back()
                    await websocket.send_text(json.dumps({
                        "type": "back_result",
                        "result": result
                    }))
                
                elif action_type == "forward":
                    result = browser.go_forward()
                    await websocket.send_text(json.dumps({
                        "type": "forward_result",
                        "result": result
                    }))
                
                elif action_type == "refresh":
                    result = browser.refresh()
                    await websocket.send_text(json.dumps({
                        "type": "refresh_result",
                        "result": result
                    }))
                
                elif action_type == "execute_script":
                    script = message.get("script")
                    args = message.get("args", [])
                    result = browser.execute_script(script, *args)
                    await websocket.send_text(json.dumps({
                        "type": "execute_script_result",
                        "result": result
                    }))
                
                elif action_type == "get_element_info":
                    x = message.get("x")
                    y = message.get("y")
                    result = browser.get_element_info(x, y)
                    await websocket.send_text(json.dumps({
                        "type": "get_element_info_result",
                        "result": result
                    }))
                
                elif action_type == "get_screenshot":
                    force_new = message.get("forceNew", False)
                    screenshot = browser.get_screenshot(force_new=force_new)
                    if screenshot:
                        await websocket.send_text(json.dumps({
                            "type": "screenshot_result",
                            "data": screenshot
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "screenshot_result",
                            "error": "Failed to get screenshot"
                        }))
                
                elif action_type == "set_frame_rate":
                    fps = message.get("fps", 10)
                    # Limit fps to reasonable range (1-30)
                    fps = max(1, min(30, fps))
                    manager.frame_rate = fps
                    manager.screenshot_interval = 1.0 / fps
                    await websocket.send_text(json.dumps({
                        "type": "set_frame_rate_result",
                        "fps": fps
                    }))
                
                # Advanced capabilities via WebSocket
                elif action_type == "add_bookmark":
                    url = message.get("url")
                    title = message.get("title")
                    folder = message.get("folder")
                    result = browser.add_bookmark(url, title, folder)
                    await websocket.send_text(json.dumps({
                        "type": "add_bookmark_result",
                        "result": result
                    }))
                
                elif action_type == "remove_bookmark":
                    url = message.get("url")
                    result = browser.remove_bookmark(url)
                    await websocket.send_text(json.dumps({
                        "type": "remove_bookmark_result",
                        "result": result
                    }))
                
                elif action_type == "get_bookmarks":
                    folder = message.get("folder")
                    result = browser.get_bookmarks(folder)
                    await websocket.send_text(json.dumps({
                        "type": "get_bookmarks_result",
                        "result": result
                    }))
                
                elif action_type == "get_cookies":
                    domain = message.get("domain")
                    result = browser.get_cookies(domain)
                    await websocket.send_text(json.dumps({
                        "type": "get_cookies_result",
                        "result": result
                    }))
                
                elif action_type == "clear_cookies":
                    domain = message.get("domain")
                    result = browser.clear_cookies(domain)
                    await websocket.send_text(json.dumps({
                        "type": "clear_cookies_result",
                        "result": result
                    }))
                
                elif action_type == "add_form_data":
                    field = message.get("field")
                    value = message.get("value")
                    result = browser.add_form_data(field, value)
                    await websocket.send_text(json.dumps({
                        "type": "add_form_data_result",
                        "result": result
                    }))
                
                elif action_type == "get_form_data":
                    field = message.get("field")
                    result = browser.get_form_data(field)
                    await websocket.send_text(json.dumps({
                        "type": "get_form_data_result",
                        "result": result
                    }))
                
                elif action_type == "clear_form_data":
                    field = message.get("field")
                    result = browser.clear_form_data(field)
                    await websocket.send_text(json.dumps({
                        "type": "clear_form_data_result",
                        "result": result
                    }))
                
                elif action_type == "fill_form":
                    form_data = message.get("form_data")
                    submit = message.get("submit", False)
                    result = browser.fill_form(form_data, submit)
                    await websocket.send_text(json.dumps({
                        "type": "fill_form_result",
                        "result": result
                    }))
                
                elif action_type == "get_history":
                    limit = message.get("limit")
                    result = browser.get_history(limit)
                    await websocket.send_text(json.dumps({
                        "type": "get_history_result",
                        "result": result
                    }))
                
                elif action_type == "clear_history":
                    result = browser.clear_history()
                    await websocket.send_text(json.dumps({
                        "type": "clear_history_result",
                        "result": result
                    }))
                
                else:
                    logger.warning(f"Unknown action type: {action_type}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Unknown action: {action_type}"
                    }))
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON: {data}")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
                try:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))
                except:
                    pass
    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {client_ip}")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        manager.disconnect(websocket)

def start_server(host="0.0.0.0", port=8001):
    """Start the FastAPI server."""
    uvicorn.run(app, host=host, port=port)