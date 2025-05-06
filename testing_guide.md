# Testing Guide for Interactive Headless Browser

This document provides instructions for testing the Interactive Headless Browser application to ensure its functionality and stability.

## Testing Environments

### 1. Local Testing Environment

For development and unit testing:
- Development machine with Python 3.8+ and Chrome/Chromium installed
- Required Python packages from requirements.txt
- Running with DEBUG=true

### 2. Staging Environment

For integration and performance testing:
- Similar to production environment
- Isolated from production data
- Configuration matches production but with DEBUG=true

### 3. Production Environment 

For final validation:
- Live environment with production configuration
- Limited testing to avoid disruption
- Monitoring enabled

## Test Types

### 1. Unit Tests

Test individual components with pytest:

```bash
# Run all unit tests
pytest test_app.py

# Run specific test cases
pytest test_app.py::test_websocket_connection

# Run with verbosity for debugging
pytest -v test_app.py

# Run with code coverage
pytest --cov=. test_app.py
```

### 2. Integration Tests

Test the interaction between components:

```bash
# Set environment variable to start server during tests
# (Alternative to having server running separately)
export START_SERVER=true
pytest test_app.py

# Or run with server already running
pytest test_app.py
```

### 3. End-to-End Tests

Test complete user flows:

```bash
# Run the full browser workflow test
pytest test_app.py::test_full_workflow -v
```

### 4. Performance Tests

Test under load to ensure stability:

```bash
# Install locust for load testing
pip install locust

# Run locust test (create locustfile.py first)
locust -f locustfile.py
```

## Testing Checklist

### Functionality Testing

- [ ] Browser initialization and setup
- [ ] Navigation to websites
- [ ] Screenshot capture
- [ ] Mouse interactions (click, drag)
- [ ] Keyboard interactions (typing, key presses)
- [ ] Form filling and submission
- [ ] Scrolling behavior
- [ ] Browser history navigation
- [ ] Bookmark management
- [ ] Cookie handling
- [ ] Error handling for edge cases

### Security Testing

- [ ] Authentication mechanisms
- [ ] Rate limiting effectiveness
- [ ] Input validation and sanitization
- [ ] Content Security Policy implementation
- [ ] Session management
- [ ] Secure cookie handling
- [ ] CORS configuration

### Performance Testing

- [ ] Response time under normal load
- [ ] Memory usage over time
- [ ] CPU utilization
- [ ] WebSocket frame rate consistency
- [ ] Browser resource consumption
- [ ] Connection limit handling
- [ ] Recovery from high load

### Cross-Browser Testing

Test the client interface on:
- [ ] Chrome
- [ ] Firefox
- [ ] Safari
- [ ] Edge
- [ ] Mobile browsers (responsive design)

## Automated Testing Setup

### 1. CI/CD Integration

Example GitHub Actions workflow (.github/workflows/test.yml):

```yaml
name: Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install Chrome
      run: |
        wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
        echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google.list
        sudo apt-get update
        sudo apt-get install -y google-chrome-stable
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest pytest-cov
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
    - name: Test with pytest
      run: |
        pytest --cov=. test_app.py
```

### 2. Local Test Automation

Shell script for running all tests locally:

```bash
#!/bin/bash
# test_all.sh

echo "Running Unit Tests..."
pytest test_app.py -v

echo "Running with Coverage..."
pytest --cov=. test_app.py

echo "Generating Coverage Report..."
coverage html

echo "Testing Complete!"
```

Make it executable:
```bash
chmod +x test_all.sh
```

## Manual Testing Procedures

### 1. Core Browser Functionality

1. Start the application
2. Navigate to http://localhost:8001
3. Enter a URL (e.g., https://example.com) and verify navigation
4. Test interactions:
   - Click on various page elements
   - Type text into forms
   - Press special keys (Enter, Tab, etc.)
   - Scroll the page
   - Test back/forward navigation
5. Verify screenshot updates are smooth

### 2. Advanced Features

1. Test bookmark management:
   - Add a bookmark
   - View bookmarks list
   - Navigate to a bookmarked site
   - Remove a bookmark
2. Test form handling:
   - Add form data for autofill
   - Visit a site with forms
   - Verify form autofill works
   - Submit a form and verify navigation
3. Test cookie management:
   - View cookies for a site
   - Clear cookies
   - Verify site behavior changes appropriately

### 3. Error Handling

1. Test with invalid URLs
2. Test with unresponsive sites
3. Test with sites that use complex JavaScript
4. Test behavior when Chrome crashes
5. Test recovery from connection interruptions

## Regression Testing

After any significant changes, run the following regression tests:

1. Run all unit tests
2. Perform manual testing of core functionality
3. Verify all features from previous releases still work
4. Check for performance regressions
5. Ensure error handling behaves as expected

## Test Data Management

- Create and maintain a set of test URLs representing different types of websites
- Document expected behavior for each test case
- Reset browser data between test runs when testing sensitive features
- Use mock server responses for consistent testing of complex scenarios

## Reporting Issues

When reporting bugs:

1. Provide clear steps to reproduce
2. Include the URL where the issue occurs
3. Describe expected vs. actual behavior
4. Include screenshots or video if applicable
5. Provide browser logs (available in debug mode)
6. Note the environment where the issue occurs

## Testing Tools

- **pytest**: Primary testing framework
- **coverage.py**: Code coverage reporting
- **locust**: Load testing
- **selenium**: Browser automation for client-side testing
- **flake8**: Code quality checks
- **mypy**: Type checking