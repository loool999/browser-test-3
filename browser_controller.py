# browser_controller.py
from playwright.sync_api import sync_playwright, Error as PlaywrightError
import io

class BrowserController:
    def __init__(self, headless=True): # Default to headless for server use
        self.playwright = None
        self.browser = None
        self.page = None
        self._headless = headless
        self._initialize_browser()

    def _initialize_browser(self):
        try:
            self.playwright = sync_playwright().start()
            # For debugging on the server, you might temporarily set headless=False
            self.browser = self.playwright.chromium.launch(headless=self._headless)
            context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            self.page = context.new_page()
            print("Browser initialized.")
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
                    f"*[data-testid*='{selector}' i]" # Common for test IDs
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
                try:
                    self.page.get_by_text(selector, exact=False).first.click(timeout=5000)
                    print(f"Clicked element with text matching '{selector}'")
                    return
                except PlaywrightError: pass
                try:
                    self.page.get_by_role("button", name=selector, exact=False).first.click(timeout=5000)
                    print(f"Clicked button role with name/text matching '{selector}'")
                    return
                except PlaywrightError: pass
                try:
                    self.page.get_by_role("link", name=selector, exact=False).first.click(timeout=5000)
                    print(f"Clicked link role with name/text matching '{selector}'")
                    return
                except PlaywrightError: pass
                try: # Test ID click
                    self.page.locator(f"[data-testid*='{selector}' i]").first.click(timeout=5000)
                    print(f"Clicked element with test ID matching '{selector}'")
                    return
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
            try:
                from PIL import Image, ImageDraw
                img = Image.new('RGB', (800, 600), color = 'grey')
                d = ImageDraw.Draw(img)
                d.text((10,10), "Browser not ready", fill=(255,255,0))
                byte_arr = io.BytesIO()
                img.save(byte_arr, format='JPEG')
                return byte_arr.getvalue()
            except ImportError: return b''
        try:
            return self.page.screenshot(type="jpeg", quality=70)
        except PlaywrightError as e:
            print(f"Error taking screenshot: {e}")
            return b''

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("Browser closed.")
