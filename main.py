import os
import logging
import signal
import sys
import time
from dotenv import load_dotenv
from server import start_server, browser

# Load environment variables from .env file
load_dotenv()

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
log_file = os.environ.get("LOG_FILE", None)

logging_config = {
    'level': getattr(logging, log_level),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
}

if log_file:
    logging_config['filename'] = log_file
    logging_config['filemode'] = 'a'

logging.basicConfig(**logging_config)
logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutting down...")
    try:
        browser.close()
        logger.info("Browser closed successfully")
    except Exception as e:
        logger.error(f"Error closing browser: {str(e)}")
    
    logger.info("Shutdown complete")
    sys.exit(0)

def main():
    """Main entry point for the application."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Display startup banner
    print("""
    =========================================
    Interactive Headless Browser
    =========================================
    """)
    
    try:
        # Get configuration from environment variables
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", 8001))
        debug = os.environ.get("DEBUG", "false").lower() == "true"
        
        # Log startup information
        logger.info(f"Starting server on {host}:{port}")
        logger.info(f"Debug mode: {debug}")
        logger.info(f"Log level: {log_level}")
        logger.info(f"Browser data directory: {browser.user_data_dir}")
        
        # Start the server
        start_server(host=host, port=port)
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        browser.close()
        sys.exit(1)

if __name__ == "__main__":
    # Add exception handling for entire application
    try:
        main()
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        try:
            browser.close()
        except:
            pass
        sys.exit(1)