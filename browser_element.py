import logging
from typing import List, Dict, Any, Optional, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

logger = logging.getLogger(__name__)

class BrowserPageElement:
    """
    Class to manage elements on a web page, providing more specific element-based interactions.
    This enhances the HeadlessBrowser class by adding the ability to find and interact with 
    specific elements rather than just coordinates.
    """
    
    def __init__(self, driver):
        """Initialize with the WebDriver instance."""
        self.driver = driver
    
    def find_element(self, by: str, value: str, timeout: int = 5) -> Optional[WebElement]:
        """
        Find an element on the page using various selector strategies.
        
        Args:
            by: Locator strategy (e.g., 'id', 'xpath', 'css', 'name', 'tag', 'class', 'link_text')
            value: The value to search for
            timeout: Time to wait for element in seconds
            
        Returns:
            WebElement if found, None otherwise
        """
        try:
            locator_map = {
                'id': By.ID,
                'xpath': By.XPATH,
                'css': By.CSS_SELECTOR,
                'name': By.NAME,
                'tag': By.TAG_NAME,
                'class': By.CLASS_NAME,
                'link_text': By.LINK_TEXT,
                'partial_link_text': By.PARTIAL_LINK_TEXT
            }
            
            locator = locator_map.get(by.lower(), By.CSS_SELECTOR)
            
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((locator, value))
            )
            return element
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"Element not found: {by}={value}, error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error finding element: {str(e)}")
            return None
    
    def find_elements(self, by: str, value: str, timeout: int = 5) -> List[WebElement]:
        """
        Find all elements matching the criteria.
        
        Args:
            by: Locator strategy
            value: The value to search for
            timeout: Time to wait for elements in seconds
            
        Returns:
            List of WebElements, empty list if none found
        """
        try:
            locator_map = {
                'id': By.ID,
                'xpath': By.XPATH,
                'css': By.CSS_SELECTOR,
                'name': By.NAME,
                'tag': By.TAG_NAME,
                'class': By.CLASS_NAME,
                'link_text': By.LINK_TEXT,
                'partial_link_text': By.PARTIAL_LINK_TEXT
            }
            
            locator = locator_map.get(by.lower(), By.CSS_SELECTOR)
            
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((locator, value))
            )
            return self.driver.find_elements(locator, value)
        except TimeoutException:
            logger.warning(f"No elements found: {by}={value} after {timeout} seconds")
            return []
        except Exception as e:
            logger.error(f"Error finding elements: {str(e)}")
            return []
    
    def click_element(self, by: str, value: str, timeout: int = 5) -> bool:
        """
        Find and click an element.
        
        Args:
            by: Locator strategy
            value: The value to search for
            timeout: Time to wait for element in seconds
            
        Returns:
            True if successful, False otherwise
        """
        element = self.find_element(by, value, timeout)
        if element:
            try:
                element.click()
                return True
            except Exception as e:
                logger.error(f"Error clicking element: {str(e)}")
                return False
        return False
    
    def input_text(self, by: str, value: str, text: str, timeout: int = 5, clear_first: bool = True) -> bool:
        """
        Find an input element and enter text.
        
        Args:
            by: Locator strategy
            value: The value to search for
            text: Text to enter
            timeout: Time to wait for element in seconds
            clear_first: Whether to clear the field before entering text
            
        Returns:
            True if successful, False otherwise
        """
        element = self.find_element(by, value, timeout)
        if element:
            try:
                if clear_first:
                    element.clear()
                element.send_keys(text)
                return True
            except Exception as e:
                logger.error(f"Error entering text: {str(e)}")
                return False
        return False
    
    def get_element_text(self, by: str, value: str, timeout: int = 5) -> Optional[str]:
        """
        Get the text content of an element.
        
        Args:
            by: Locator strategy
            value: The value to search for
            timeout: Time to wait for element in seconds
            
        Returns:
            Text content if found, None otherwise
        """
        element = self.find_element(by, value, timeout)
        if element:
            try:
                return element.text
            except Exception as e:
                logger.error(f"Error getting element text: {str(e)}")
                return None
        return None
    
    def get_element_attribute(self, by: str, value: str, attribute: str, timeout: int = 5) -> Optional[str]:
        """
        Get an attribute value of an element.
        
        Args:
            by: Locator strategy
            value: The value to search for
            attribute: Attribute name to retrieve
            timeout: Time to wait for element in seconds
            
        Returns:
            Attribute value if found, None otherwise
        """
        element = self.find_element(by, value, timeout)
        if element:
            try:
                return element.get_attribute(attribute)
            except Exception as e:
                logger.error(f"Error getting element attribute: {str(e)}")
                return None
        return None
    
    def is_element_visible(self, by: str, value: str, timeout: int = 5) -> bool:
        """
        Check if an element is visible on the page.
        
        Args:
            by: Locator strategy
            value: The value to search for
            timeout: Time to wait for element in seconds
            
        Returns:
            True if element is visible, False otherwise
        """
        try:
            locator_map = {
                'id': By.ID,
                'xpath': By.XPATH,
                'css': By.CSS_SELECTOR,
                'name': By.NAME,
                'tag': By.TAG_NAME,
                'class': By.CLASS_NAME,
                'link_text': By.LINK_TEXT,
                'partial_link_text': By.PARTIAL_LINK_TEXT
            }
            
            locator = locator_map.get(by.lower(), By.CSS_SELECTOR)
            
            element = WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((locator, value))
            )
            return True
        except TimeoutException:
            return False
        except Exception as e:
            logger.error(f"Error checking element visibility: {str(e)}")
            return False
    
    def execute_script(self, script: str, *args) -> Any:
        """
        Execute JavaScript in the context of the page.
        
        Args:
            script: JavaScript code to execute
            *args: Arguments to pass to the script
            
        Returns:
            Result of the JavaScript execution
        """
        try:
            return self.driver.execute_script(script, *args)
        except Exception as e:
            logger.error(f"Error executing script: {str(e)}")
            return None
    
    def get_element_dimensions(self, by: str, value: str, timeout: int = 5) -> Optional[Dict[str, int]]:
        """
        Get the dimensions and position of an element.
        
        Args:
            by: Locator strategy
            value: The value to search for
            timeout: Time to wait for element in seconds
            
        Returns:
            Dictionary with x, y, width, height if found, None otherwise
        """
        element = self.find_element(by, value, timeout)
        if element:
            try:
                rect = element.rect
                return {
                    'x': rect['x'],
                    'y': rect['y'],
                    'width': rect['width'],
                    'height': rect['height']
                }
            except Exception as e:
                logger.error(f"Error getting element dimensions: {str(e)}")
                return None
        return None
    
    def wait_for_page_load(self, timeout: int = 30) -> bool:
        """
        Wait for the page to finish loading.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if page loaded successfully, False on timeout
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            return True
        except TimeoutException:
            logger.warning(f"Page load timeout after {timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Error waiting for page load: {str(e)}")
            return False