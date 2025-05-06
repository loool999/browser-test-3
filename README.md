# Interactive Headless Browser

A web-based interface for a headless browser that allows for real-time interaction with web pages. Users can view, click, type, scroll, and navigate websites directly through a streaming interface.

## Features

### Core Functionality
- **Live Browser Streaming**: Real-time view of browser content with adjustable frame rate
- **Interactive Controls**: Click, type, scroll, and drag directly on the streamed page
- **Navigation**: Full browsing capabilities with address bar and navigation controls
- **Responsive Design**: Works on various screen sizes and devices
- **WebSocket Communication**: Low-latency bidirectional communication for real-time interactions

### Advanced Features
- **Bookmarks Management**: Save, organize, and quickly access your favorite websites
- **Navigation History**: Track and browse your navigation history
- **Form Auto-filling**: Securely store and auto-fill form data
- **Cookie Management**: Control cookies across different domains
- **Element Inspection**: View and interact with page elements
- **Dark Mode**: Support for light, dark, and system themes
- **Performance Controls**: Adjust frame rate and quality for optimal performance

## Technology Stack

- **Backend**: Python with FastAPI
- **Browser Automation**: Selenium WebDriver
- **Real-time Communication**: WebSockets
- **Frontend**: HTML, CSS, JavaScript
- **Containerization**: Docker support for easy deployment

## Getting Started

### Prerequisites

- Python 3.8+
- Chrome or Chromium browser
- pip (Python package manager)

### Installation

1. Clone the repository
   ```
   git clone https://github.com/your-org/headless-browser.git
   cd headless-browser
   ```

2. Set up a virtual environment (recommended)
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Configure the application (optional)
   ```
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

5. Run the application
   ```
   python main.py
   ```

6. Open your browser and navigate to `http://localhost:8001`

### Docker Installation

1. Build the Docker image
   ```
   docker build -t headless-browser .
   ```

2. Run the container
   ```
   docker run -p 8001:8001 headless-browser
   ```

3. Access the application at `http://localhost:8001`

## Usage

### Basic Navigation

1. Enter a URL in the address bar and press Enter or click Go
2. Use the navigation buttons (back, forward, refresh, home) to navigate
3. Click the bookmark icon to save the current page
4. Click on elements in the page to interact with them

### Keyboard and Mouse Controls

- **Click**: Click elements on the page
- **Type**: Type text into form fields
- **Scroll**: Use the mouse wheel to scroll the page
- **Drag**: Click and drag to select text or move elements

### Managing Bookmarks

1. Click the bookmark icon (☆) to save the current page
2. Click the bookmarks list icon (☰) to view all bookmarks
3. Use the search box to find specific bookmarks
4. Click on a bookmark to navigate to that page
5. Click the remove icon (×) to delete a bookmark

### Form Auto-filling

1. Enable auto-fill in settings
2. When you enter information in a form, you'll be prompted to save it
3. Next time you encounter a similar form, it will be filled automatically

### Settings and Preferences

1. Click the settings icon (⚙) to open settings
2. Adjust performance settings (quality, FPS)
3. Choose your preferred theme
4. Configure privacy options
5. Access advanced features

## API Documentation

The application provides a comprehensive REST API and WebSocket interface for programmatic control.

### REST API Endpoints

- **GET /api/status**: Get browser status
- **GET /api/page-info**: Get information about current page
- **GET /api/page-html**: Get HTML source of current page
- **GET /api/bookmarks**: Get all bookmarks
- **POST /api/bookmarks/add**: Add a bookmark
- **POST /api/bookmarks/remove**: Remove a bookmark
- **GET /api/history**: Get browsing history
- **POST /api/history/clear**: Clear history
- **GET /api/cookies**: Get cookies
- **POST /api/cookies/clear**: Clear cookies
- **GET /api/form-data**: Get stored form data
- **POST /api/form-data/add**: Add form data
- **POST /api/form-data/clear**: Clear form data
- **POST /api/form/fill**: Fill a form on the current page

### WebSocket API

Connect to `/ws` for real-time browser control. Messages use JSON format:

```json
{
  "type": "action_type",
  "parameter1": "value1",
  "parameter2": "value2"
}
```

Available action types:
- navigate, click, type, key, scroll, drag
- back, forward, refresh
- get_element_info, execute_script
- get_screenshot, set_frame_rate
- add_bookmark, get_bookmarks, remove_bookmark
- get_history, clear_history
- add_form_data, get_form_data, clear_form_data
- fill_form

## Security Considerations

- Browser sessions are isolated per user
- Authentication can be enabled via environment variables
- Rate limiting prevents abuse
- Security headers protect against common web vulnerabilities
- Data is stored locally on the server
- Secure defaults for cross-origin requests

## Testing

Run the test suite with:

```
python test_app.py
```

## Deployment

See [deployment.md](deployment.md) for detailed deployment instructions for various environments.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Acknowledgements

- [Selenium](https://www.selenium.dev/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Uvicorn](https://www.uvicorn.org/)
- [WebSockets](https://websockets.readthedocs.io/)