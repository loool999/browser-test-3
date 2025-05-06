import base64
import io
import time
import threading
import logging
import os
import json
import tempfile
from typing import Dict, Optional, Any, List, Tuple
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import the BrowserPageElement class
from browser_element import BrowserPageElement

logger = logging.getLogger(__name__)

class HeadlessBrowser:
    def __init__(self, user_data_dir=None):
        self.driver = None
        self.is_running = False
        self.current_url = "about:blank"
        self.lock = threading.Lock()
        self.last_screenshot_time = 0
        self.last_screenshot = None  # Cache the last screenshot
        self.history = []  # Navigation history
        self.history_position = -1  # Current position in history
        self.bookmarks = []  # List of bookmarks
        self.cookies = {}  # Dictionary to store cookies
        self.form_data = {}  # Dictionary to store common form data
        self.page = None  # BrowserPageElement instance
        self.user_data_dir = user_data_dir
        
        # Load stored data
        self.load_persistent_data()
        
        # Initialize browser
        self.setup_driver()

    def setup_driver(self):
        """Initialize the Selenium WebDriver with Chrome in headless mode."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-extensions")
            
            # Set user agent to a modern browser to avoid detection
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
            
            # Set user data directory if provided
            if self.user_data_dir:
                chrome_options.add_argument(f"--user-data-dir={self.user_data_dir}")
            
            # Use webdriver manager to handle driver version compatibility
            from selenium.webdriver.chrome.service import Service
            
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
            except Exception as e:
                logger.warning(f"Could not use webdriver_manager: {str(e)}")
                service = Service()  # Use default service if webdriver_manager fails
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(30)  # Set page load timeout
            self.is_running = True
            self.driver.get("about:blank")
            
            # Initialize the page element handler
            self.page = BrowserPageElement(self.driver)
            
            # Add about:blank to history
            self.history.append("about:blank")
            self.history_position = 0
            
            logger.info("Headless browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize headless browser: {str(e)}")
            
            # Fallback to a simple placeholder if browser cannot be initialized
            self.is_running = False
            logger.info("Using fallback mode (screenshot-only)")

    def load_persistent_data(self):
        """Load bookmarks, cookies, and form data from disk."""
        try:
            # Load bookmarks
            if os.path.exists("bookmarks.json"):
                with open("bookmarks.json", "r") as f:
                    self.bookmarks = json.load(f)
            
            # Load form data
            if os.path.exists("form_data.json"):
                with open("form_data.json", "r") as f:
                    self.form_data = json.load(f)
                    
            logger.info("Loaded persistent data successfully")
        except Exception as e:
            logger.error(f"Error loading persistent data: {str(e)}")

    def save_persistent_data(self):
        """Save bookmarks, cookies, and form data to disk."""
        try:
            # Save bookmarks
            with open("bookmarks.json", "w") as f:
                json.dump(self.bookmarks, f)
            
            # Save form data (with optional encryption in the future)
            with open("form_data.json", "w") as f:
                json.dump(self.form_data, f)
                
            logger.info("Saved persistent data successfully")
        except Exception as e:
            logger.error(f"Error saving persistent data: {str(e)}")

    def navigate(self, url):
        """Navigate to a specific URL."""
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                # Handle special URLs like 'about:blank'
                if url == 'about:blank':
                    self.driver.get('about:blank')
                    self.current_url = 'about:blank'
                    
                    # Update history
                    self._update_history('about:blank')
                    
                    return {'status': 'success', 'url': self.current_url}
                
                # Add protocol if missing
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                
                # Attempt to navigate with timeout handling
                try:
                    self.driver.get(url)
                    
                    # Wait for page to load (with timeout protection)
                    self.page.wait_for_page_load(timeout=30)
                    
                    # Get the current URL (might be different after redirects)
                    self.current_url = self.driver.current_url
                    
                    # Update history
                    self._update_history(self.current_url)
                    
                    # Store cookies for this domain
                    self._store_cookies()
                    
                    return {'status': 'success', 'url': self.current_url}
                except TimeoutException:
                    logger.warning(f"Page load timeout for URL: {url}")
                    return {'status': 'error', 'message': 'Page load timed out'}
                    
            except WebDriverException as e:
                logger.error(f"Navigation error: {str(e)}")
                return {'status': 'error', 'message': str(e)}
    
    def _update_history(self, url):
        """Update the browser history when navigating."""
        # If we're not at the end of history, truncate it
        if self.history_position < len(self.history) - 1:
            self.history = self.history[:self.history_position + 1]
        
        # Add the new URL to history
        self.history.append(url)
        self.history_position = len(self.history) - 1

    def go_back(self):
        """Navigate back in browser history."""
        with self.lock:
            if not self.is_running:
                return {'status': 'error', 'message': 'Browser not available'}
            
            # Check if we can go back in our history
            if self.history_position > 0:
                self.history_position -= 1
                url = self.history[self.history_position]
                
                try:
                    self.driver.get(url)
                    self.current_url = self.driver.current_url
                    return {'status': 'success', 'url': self.current_url}
                except Exception as e:
                    logger.error(f"Error going back to {url}: {str(e)}")
                    return {'status': 'error', 'message': str(e)}
            else:
                return {'status': 'error', 'message': 'No previous page in history'}

    def go_forward(self):
        """Navigate forward in browser history."""
        with self.lock:
            if not self.is_running:
                return {'status': 'error', 'message': 'Browser not available'}
            
            # Check if we can go forward in our history
            if self.history_position < len(self.history) - 1:
                self.history_position += 1
                url = self.history[self.history_position]
                
                try:
                    self.driver.get(url)
                    self.current_url = self.driver.current_url
                    return {'status': 'success', 'url': self.current_url}
                except Exception as e:
                    logger.error(f"Error going forward to {url}: {str(e)}")
                    return {'status': 'error', 'message': str(e)}
            else:
                return {'status': 'error', 'message': 'No next page in history'}

    def refresh(self):
        """Refresh the current page."""
        with self.lock:
            if not self.is_running:
                return {'status': 'error', 'message': 'Browser not available'}
            
            try:
                self.driver.refresh()
                # Wait for page to load
                self.page.wait_for_page_load(timeout=30)
                return {'status': 'success', 'url': self.current_url}
            except TimeoutException:
                logger.warning(f"Page refresh timeout for URL: {self.current_url}")
                return {'status': 'error', 'message': 'Page refresh timed out'}
            except Exception as e:
                logger.error(f"Error refreshing page: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def get_screenshot(self, force_new=False):
        """
        Take a screenshot of the current page and return as base64 encoded string.
        
        Args:
            force_new: Force a new screenshot even if we have a recent one
        """
        with self.lock:
            try:
                current_time = time.time()
                
                # Return cached screenshot if it's recent (within 100ms)
                if not force_new and self.last_screenshot and current_time - self.last_screenshot_time < 0.1:
                    return self.last_screenshot
                
                if not self.is_running:
                    # Return a placeholder image if browser is not available
                    from PIL import Image, ImageDraw, ImageFont
                    
                    # Create a blank image for the placeholder
                    img = Image.new('RGB', (1024, 768), color = (240, 240, 240))
                    d = ImageDraw.Draw(img)
                    
                    # Draw some text on the image
                    text_lines = [
                        "Browser Demo Mode",
                        "Unable to initialize Chrome browser",
                        "This is a placeholder interface",
                        f"URL: {self.current_url or 'about:blank'}"
                    ]
                    
                    y_position = 300
                    for line in text_lines:
                        d.text((512, y_position), line, fill=(68, 68, 68), anchor="mm")
                        y_position += 40
                    
                    # Save to a BytesIO object
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    encoded = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
                    
                    # Cache this screenshot
                    self.last_screenshot = encoded
                    self.last_screenshot_time = current_time
                    
                    return encoded
                
                # Take a real screenshot
                screenshot = self.driver.get_screenshot_as_png()
                encoded = base64.b64encode(screenshot).decode('utf-8')
                
                # Cache this screenshot
                self.last_screenshot = encoded
                self.last_screenshot_time = current_time
                
                return encoded
            except Exception as e:
                logger.error(f"Screenshot error: {str(e)}")
                
                # If we have a cached screenshot, return it
                if self.last_screenshot:
                    return self.last_screenshot
                
                # Otherwise return a simple error placeholder
                try:
                    from PIL import Image, ImageDraw
                    
                    img = Image.new('RGB', (1024, 768), color = (240, 240, 240))
                    d = ImageDraw.Draw(img)
                    d.text((512, 384), "Screenshot Error", fill=(255, 0, 0), anchor="mm")
                    
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    return base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
                except Exception:
                    return None

    def click(self, x, y):
        """Simulate a mouse click at the given coordinates."""
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                # First, find any element at these coordinates
                element_js = f"""
                return document.elementFromPoint({x}, {y});
                """
                element = self.driver.execute_script(element_js)
                
                if element:
                    # If the element is a link, log what we're clicking
                    tag_name = element.tag_name.lower() if hasattr(element, 'tag_name') else ''
                    if tag_name == 'a':
                        href = element.get_attribute('href')
                        logger.info(f"Clicking link: {href}")
                
                # Move to the coordinates and click
                actions = ActionChains(self.driver)
                actions.move_by_offset(x, y).click().perform()
                
                # Reset the mouse position after clicking
                actions.move_by_offset(-x, -y).perform()
                
                # Wait a moment for any page changes
                time.sleep(0.5)
                
                # Check if the URL changed after clicking
                new_url = self.driver.current_url
                if new_url != self.current_url:
                    self.current_url = new_url
                    self._update_history(new_url)
                
                return {'status': 'success'}
            except Exception as e:
                logger.error(f"Click error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def type_text(self, text):
        """Type text at the current focus position."""
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                actions = ActionChains(self.driver)
                actions.send_keys(text).perform()
                return {'status': 'success'}
            except Exception as e:
                logger.error(f"Type text error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def press_key(self, key):
        """Press a specific keyboard key."""
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                key_mapping = {
                    'Enter': Keys.ENTER,
                    'Backspace': Keys.BACKSPACE,
                    'Tab': Keys.TAB,
                    'Escape': Keys.ESCAPE,
                    'ArrowUp': Keys.ARROW_UP,
                    'ArrowDown': Keys.ARROW_DOWN,
                    'ArrowLeft': Keys.ARROW_LEFT,
                    'ArrowRight': Keys.ARROW_RIGHT,
                    'Delete': Keys.DELETE,
                    'Home': Keys.HOME,
                    'End': Keys.END,
                    'PageUp': Keys.PAGE_UP,
                    'PageDown': Keys.PAGE_DOWN,
                    'F5': Keys.F5,
                }
                
                key_to_press = key_mapping.get(key)
                if key_to_press:
                    actions = ActionChains(self.driver)
                    actions.send_keys(key_to_press).perform()
                    
                    # Check if Enter was pressed and URL changed (form submission)
                    if key == 'Enter':
                        time.sleep(0.5)  # Short delay to let page load if form was submitted
                        new_url = self.driver.current_url
                        if new_url != self.current_url:
                            self.current_url = new_url
                            self._update_history(new_url)
                    
                    return {'status': 'success'}
                else:
                    return {'status': 'error', 'message': f'Unsupported key: {key}'}
            except Exception as e:
                logger.error(f"Key press error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def scroll(self, x, y):
        """Scroll the page by the given amount."""
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                self.driver.execute_script(f"window.scrollBy({x}, {y});")
                return {'status': 'success'}
            except Exception as e:
                logger.error(f"Scroll error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def scroll_to_position(self, x, y):
        """Scroll to an absolute position on the page."""
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                self.driver.execute_script(f"window.scrollTo({x}, {y});")
                return {'status': 'success'}
            except Exception as e:
                logger.error(f"Scroll to position error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def drag(self, start_x, start_y, end_x, end_y):
        """Simulate a drag operation from start to end coordinates."""
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                actions = ActionChains(self.driver)
                actions.move_by_offset(start_x, start_y)
                actions.click_and_hold()
                actions.move_by_offset(end_x - start_x, end_y - start_y)
                actions.release()
                actions.perform()
                # Reset mouse position
                actions.move_by_offset(-(end_x), -(end_y)).perform()
                return {'status': 'success'}
            except Exception as e:
                logger.error(f"Drag error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def get_page_info(self):
        """Get information about the current page."""
        with self.lock:
            try:
                if not self.is_running:
                    return {
                        'status': 'success',
                        'title': 'Browser Demo Mode',
                        'url': self.current_url or 'about:blank',
                        'can_go_back': self.history_position > 0,
                        'can_go_forward': self.history_position < len(self.history) - 1
                    }
                
                title = self.driver.title
                url = self.driver.current_url
                
                # Get favicon if available
                favicon = None
                try:
                    favicon_element = self.page.find_element('css', 'link[rel*="icon"]', timeout=0.5)
                    if favicon_element:
                        favicon = favicon_element.get_attribute('href')
                except:
                    pass
                
                # Check if this page is bookmarked
                is_bookmarked = any(bookmark['url'] == url for bookmark in self.bookmarks)
                
                return {
                    'status': 'success',
                    'title': title,
                    'url': url,
                    'favicon': favicon,
                    'can_go_back': self.history_position > 0,
                    'can_go_forward': self.history_position < len(self.history) - 1,
                    'is_bookmarked': is_bookmarked
                }
            except Exception as e:
                logger.error(f"Get page info error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def get_page_html(self):
        """Get the HTML source of the current page."""
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                html = self.driver.page_source
                return {'status': 'success', 'html': html}
            except Exception as e:
                logger.error(f"Get page HTML error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def execute_script(self, script, *args):
        """Execute JavaScript in the page context."""
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                result = self.driver.execute_script(script, *args)
                return {'status': 'success', 'result': result}
            except Exception as e:
                logger.error(f"Script execution error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def get_element_info(self, x, y):
        """Get information about the element at the specified coordinates."""
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                # Use JavaScript to get the element at the coordinates
                js = f"""
                var el = document.elementFromPoint({x}, {y});
                if (!el) return null;
                
                return {{
                    tagName: el.tagName,
                    id: el.id,
                    className: el.className,
                    textContent: el.textContent ? el.textContent.trim().substring(0, 100) : '',
                    attributes: (function() {{
                        var attrs = {{}};
                        for (var i = 0; i < el.attributes.length; i++) {{
                            var attr = el.attributes[i];
                            attrs[attr.name] = attr.value;
                        }}
                        return attrs;
                    }})(),
                    rect: el.getBoundingClientRect().toJSON()
                }};
                """
                
                element_info = self.driver.execute_script(js)
                
                if element_info:
                    return {'status': 'success', 'element': element_info}
                else:
                    return {'status': 'error', 'message': 'No element at coordinates'}
            except Exception as e:
                logger.error(f"Get element info error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    # Advanced capabilities

    def add_bookmark(self, url=None, title=None, folder=None):
        """
        Add the current page (or specified URL) to bookmarks.
        
        Args:
            url: URL to bookmark (defaults to current page)
            title: Title for the bookmark (defaults to page title)
            folder: Optional folder to organize bookmarks
            
        Returns:
            Dictionary with status and bookmark info
        """
        with self.lock:
            try:
                if not self.is_running and not url:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                # Use current page if no URL specified
                bookmark_url = url or self.driver.current_url
                bookmark_title = title
                
                # If no title provided, use page title
                if not bookmark_title and self.is_running:
                    try:
                        bookmark_title = self.driver.title
                    except:
                        bookmark_title = bookmark_url
                elif not bookmark_title:
                    bookmark_title = bookmark_url
                
                # Create the bookmark object
                bookmark = {
                    'url': bookmark_url,
                    'title': bookmark_title,
                    'created': time.time(),
                    'folder': folder
                }
                
                # Add to bookmarks if not already there
                if not any(b['url'] == bookmark_url for b in self.bookmarks):
                    self.bookmarks.append(bookmark)
                    self.save_persistent_data()
                    return {'status': 'success', 'bookmark': bookmark}
                else:
                    return {'status': 'info', 'message': 'Bookmark already exists'}
                
            except Exception as e:
                logger.error(f"Add bookmark error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def remove_bookmark(self, url=None):
        """
        Remove a bookmark for the given URL or current page.
        
        Args:
            url: URL to remove from bookmarks (defaults to current page)
            
        Returns:
            Dictionary with status and message
        """
        with self.lock:
            try:
                # Use current page if no URL specified
                bookmark_url = url
                if not bookmark_url and self.is_running:
                    bookmark_url = self.driver.current_url
                
                if not bookmark_url:
                    return {'status': 'error', 'message': 'No URL specified'}
                
                # Find and remove the bookmark
                initial_length = len(self.bookmarks)
                self.bookmarks = [b for b in self.bookmarks if b['url'] != bookmark_url]
                
                if len(self.bookmarks) < initial_length:
                    self.save_persistent_data()
                    return {'status': 'success', 'message': 'Bookmark removed'}
                else:
                    return {'status': 'info', 'message': 'Bookmark not found'}
                
            except Exception as e:
                logger.error(f"Remove bookmark error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def get_bookmarks(self, folder=None):
        """
        Get all bookmarks, optionally filtered by folder.
        
        Args:
            folder: Optional folder to filter bookmarks
            
        Returns:
            Dictionary with status and bookmarks list
        """
        with self.lock:
            try:
                if folder:
                    filtered_bookmarks = [b for b in self.bookmarks if b.get('folder') == folder]
                    return {'status': 'success', 'bookmarks': filtered_bookmarks}
                else:
                    return {'status': 'success', 'bookmarks': self.bookmarks}
                
            except Exception as e:
                logger.error(f"Get bookmarks error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def _store_cookies(self):
        """Store cookies for the current domain."""
        if not self.is_running:
            return
        
        try:
            current_domain = self._extract_domain(self.current_url)
            if not current_domain:
                return
            
            selenium_cookies = self.driver.get_cookies()
            self.cookies[current_domain] = selenium_cookies
            
        except Exception as e:
            logger.error(f"Store cookies error: {str(e)}")

    def _extract_domain(self, url):
        """Extract domain from URL."""
        try:
            if not url or url == 'about:blank':
                return None
                
            # Simple domain extraction
            if url.startswith('http'):
                parts = url.split('://', 1)[1].split('/', 1)[0].split('?')[0]
                return parts
            return None
        except Exception:
            return None

    def get_cookies(self, domain=None):
        """
        Get cookies for a domain or all domains.
        
        Args:
            domain: Optional domain to filter cookies
            
        Returns:
            Dictionary with status and cookies
        """
        with self.lock:
            try:
                if domain:
                    domain_cookies = self.cookies.get(domain, [])
                    return {'status': 'success', 'cookies': domain_cookies}
                else:
                    return {'status': 'success', 'cookies': self.cookies}
                
            except Exception as e:
                logger.error(f"Get cookies error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def clear_cookies(self, domain=None):
        """
        Clear cookies for a domain or all domains.
        
        Args:
            domain: Optional domain to clear cookies for
            
        Returns:
            Dictionary with status and message
        """
        with self.lock:
            try:
                if not self.is_running:
                    if domain:
                        if domain in self.cookies:
                            del self.cookies[domain]
                    else:
                        self.cookies = {}
                    return {'status': 'success', 'message': 'Cookies cleared'}
                
                if domain:
                    # Clear cookies for specific domain
                    if domain in self.cookies:
                        del self.cookies[domain]
                    
                    # If it's the current domain, also clear in the browser
                    current_domain = self._extract_domain(self.current_url)
                    if domain == current_domain:
                        self.driver.delete_all_cookies()
                else:
                    # Clear all cookies
                    self.cookies = {}
                    self.driver.delete_all_cookies()
                
                return {'status': 'success', 'message': 'Cookies cleared'}
                
            except Exception as e:
                logger.error(f"Clear cookies error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def add_form_data(self, field_name, value):
        """
        Store form data for autofill.
        
        Args:
            field_name: Field identifier (e.g., 'email', 'name', 'address')
            value: Value to store for the field
            
        Returns:
            Dictionary with status and message
        """
        with self.lock:
            try:
                self.form_data[field_name] = value
                self.save_persistent_data()
                return {'status': 'success', 'message': f'Form data saved for {field_name}'}
                
            except Exception as e:
                logger.error(f"Add form data error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def get_form_data(self, field_name=None):
        """
        Get stored form data for autofill.
        
        Args:
            field_name: Optional field to get data for
            
        Returns:
            Dictionary with status and form data
        """
        with self.lock:
            try:
                if field_name:
                    value = self.form_data.get(field_name)
                    if value:
                        return {'status': 'success', 'field': field_name, 'value': value}
                    else:
                        return {'status': 'error', 'message': f'No data found for {field_name}'}
                else:
                    return {'status': 'success', 'form_data': self.form_data}
                
            except Exception as e:
                logger.error(f"Get form data error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def clear_form_data(self, field_name=None):
        """
        Clear stored form data.
        
        Args:
            field_name: Optional field to clear
            
        Returns:
            Dictionary with status and message
        """
        with self.lock:
            try:
                if field_name:
                    if field_name in self.form_data:
                        del self.form_data[field_name]
                        self.save_persistent_data()
                        return {'status': 'success', 'message': f'Form data cleared for {field_name}'}
                    else:
                        return {'status': 'info', 'message': f'No data found for {field_name}'}
                else:
                    self.form_data = {}
                    self.save_persistent_data()
                    return {'status': 'success', 'message': 'All form data cleared'}
                
            except Exception as e:
                logger.error(f"Clear form data error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def fill_form(self, form_data=None, submit=False):
        """
        Fill a form on the current page with stored or provided data.
        
        Args:
            form_data: Dictionary of field selectors and values 
                      (e.g., {'#email': 'user@example.com'})
            submit: Whether to submit the form after filling
            
        Returns:
            Dictionary with status and results
        """
        with self.lock:
            try:
                if not self.is_running:
                    return {'status': 'error', 'message': 'Browser not available'}
                
                # If no form data provided, try to auto-detect form fields and use stored data
                if not form_data:
                    # Auto-detect common form fields
                    form_data = {}
                    
                    # Check for common input types
                    input_types = {
                        'email': ['email', 'e-mail', 'mail'],
                        'name': ['name', 'username', 'user', 'fullname', 'full-name', 'first-name', 'firstname', 'last-name', 'lastname'],
                        'password': ['password', 'pass', 'pwd'],
                        'address': ['address', 'street', 'addr'],
                        'city': ['city', 'town'],
                        'zip': ['zip', 'zipcode', 'postal', 'postal-code'],
                        'phone': ['phone', 'telephone', 'tel', 'mobile'],
                    }
                    
                    # Find input elements
                    for input_type, selectors in input_types.items():
                        for selector in selectors:
                            # Try find by ID
                            element = self.page.find_element('id', selector, timeout=0.2)
                            if element:
                                if input_type in self.form_data:
                                    form_data[f'#{selector}'] = self.form_data[input_type]
                                continue
                                
                            # Try find by name
                            element = self.page.find_element('name', selector, timeout=0.2)
                            if element:
                                if input_type in self.form_data:
                                    form_data[f'[name="{selector}"]'] = self.form_data[input_type]
                                continue
                                
                            # Try find by placeholder
                            elements = self.page.find_elements('css', f'input[placeholder*="{selector}" i]', timeout=0.2)
                            if elements:
                                if input_type in self.form_data:
                                    form_data[f'input[placeholder*="{selector}" i]'] = self.form_data[input_type]
                
                # Track which fields were successfully filled
                results = {}
                
                # Fill the form fields
                for selector, value in form_data.items():
                    try:
                        # Determine selector type (CSS is the default)
                        selector_type = 'css'
                        if selector.startswith('//'):
                            selector_type = 'xpath'
                        
                        # Try to find and fill the element
                        element = self.page.find_element(selector_type, selector, timeout=1)
                        if element:
                            # Clear the field first
                            element.clear()
                            # Enter the value
                            element.send_keys(value)
                            results[selector] = 'filled'
                        else:
                            results[selector] = 'not found'
                    except Exception as e:
                        results[selector] = f'error: {str(e)}'
                
                # Submit the form if requested
                if submit and results:
                    try:
                        # Try to find the form element
                        form = None
                        for selector in form_data:
                            try:
                                selector_type = 'css'
                                if selector.startswith('//'):
                                    selector_type = 'xpath'
                                
                                element = self.page.find_element(selector_type, selector, timeout=0.2)
                                if element:
                                    # Try to get parent form
                                    form = self.driver.execute_script("return arguments[0].closest('form')", element)
                                    if form:
                                        break
                            except:
                                pass
                        
                        if form:
                            # Submit the form
                            form.submit()
                            results['form_submission'] = 'submitted'
                            
                            # Wait for page to load
                            self.page.wait_for_page_load(timeout=10)
                            
                            # Check if URL changed
                            new_url = self.driver.current_url
                            if new_url != self.current_url:
                                self.current_url = new_url
                                self._update_history(new_url)
                        else:
                            # Try pressing Enter on the last field
                            for selector in reversed(list(form_data.keys())):
                                try:
                                    selector_type = 'css'
                                    if selector.startswith('//'):
                                        selector_type = 'xpath'
                                    
                                    element = self.page.find_element(selector_type, selector, timeout=0.2)
                                    if element:
                                        element.send_keys(Keys.ENTER)
                                        results['form_submission'] = 'enter key pressed'
                                        
                                        # Wait for page load
                                        time.sleep(1)
                                        self.page.wait_for_page_load(timeout=10)
                                        
                                        # Check if URL changed
                                        new_url = self.driver.current_url
                                        if new_url != self.current_url:
                                            self.current_url = new_url
                                            self._update_history(new_url)
                                        
                                        break
                                except:
                                    pass
                            
                            if 'form_submission' not in results:
                                results['form_submission'] = 'no form found to submit'
                    except Exception as e:
                        results['form_submission'] = f'error: {str(e)}'
                
                return {'status': 'success', 'results': results}
                
            except Exception as e:
                logger.error(f"Fill form error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def get_history(self, limit=None):
        """
        Get browser navigation history.
        
        Args:
            limit: Optional limit on number of history items to return
            
        Returns:
            Dictionary with status and history list
        """
        with self.lock:
            try:
                history = self.history
                if limit and limit > 0:
                    history = history[-limit:]
                
                return {
                    'status': 'success', 
                    'history': history,
                    'current_position': self.history_position
                }
                
            except Exception as e:
                logger.error(f"Get history error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def clear_history(self):
        """
        Clear browser navigation history except for current page.
        
        Returns:
            Dictionary with status and message
        """
        with self.lock:
            try:
                current_url = "about:blank"
                if self.is_running:
                    current_url = self.driver.current_url
                
                self.history = [current_url]
                self.history_position = 0
                
                return {'status': 'success', 'message': 'History cleared'}
                
            except Exception as e:
                logger.error(f"Clear history error: {str(e)}")
                return {'status': 'error', 'message': str(e)}

    def close(self):
        """Close the browser and clean up resources."""
        with self.lock:
            # Save any persistent data before closing
            self.save_persistent_data()
            
            if self.driver and self.is_running:
                self.driver.quit()
                self.is_running = False
                logger.info("Browser closed")