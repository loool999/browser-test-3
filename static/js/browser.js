// DOM Elements

// Toolbar elements
const browserScreen = document.getElementById('browserScreen');
const urlInput = document.getElementById('urlInput');
const goButton = document.getElementById('goButton');
const backButton = document.getElementById('backButton');
const forwardButton = document.getElementById('forwardButton');
const refreshButton = document.getElementById('refreshButton');
const homeButton = document.getElementById('homeButton');
const securityIndicator = document.getElementById('securityIndicator');
const bookmarkButton = document.getElementById('bookmarkButton');
const bookmarksListButton = document.getElementById('bookmarksListButton');
const settingsButton = document.getElementById('settingsButton');
const fullscreenButton = document.getElementById('fullscreenButton');

// Page info elements
const pageFavicon = document.getElementById('pageFavicon');
const pageTitle = document.getElementById('pageTitle');
const connectionStatus = document.getElementById('connectionStatus');
const fpsCounter = document.getElementById('fpsCounter');

// Overlays
const loadingOverlay = document.getElementById('loadingOverlay');
const errorOverlay = document.getElementById('errorOverlay');
const errorMessage = document.getElementById('errorMessage');
const errorDismiss = document.getElementById('errorDismiss');
const pageLoadingIndicator = document.getElementById('pageLoadingIndicator');
const elementHighlight = document.getElementById('elementHighlight');
const formDataPrompt = document.getElementById('formDataPrompt');
const formDataFields = document.getElementById('formDataFields');
const saveFormData = document.getElementById('saveFormData');
const cancelFormData = document.getElementById('cancelFormData');

// Status bar elements
const elementInfo = document.getElementById('elementInfo');
const elementType = document.getElementById('elementType');
const elementText = document.getElementById('elementText');
const zoomLevel = document.getElementById('zoomLevel');
const zoomInButton = document.getElementById('zoomInButton');
const zoomOutButton = document.getElementById('zoomOutButton');
const fpsSlider = document.getElementById('fpsSlider');

// Bookmarks panel elements
const bookmarksPanel = document.getElementById('bookmarksPanel');
const closeBookmarksButton = document.getElementById('closeBookmarksButton');
const bookmarkSearch = document.getElementById('bookmarkSearch');
const bookmarksList = document.getElementById('bookmarksList');

// History panel elements
const historyPanel = document.getElementById('historyPanel');
const closeHistoryButton = document.getElementById('closeHistoryButton');
const historySearch = document.getElementById('historySearch');
const clearHistoryButton = document.getElementById('clearHistoryButton');
const historyList = document.getElementById('historyList');

// Settings panel elements
const settingsPanel = document.getElementById('settingsPanel');
const closeSettingsButton = document.getElementById('closeSettingsButton');
const qualitySelector = document.getElementById('qualitySelector');
const fpsLimitSelector = document.getElementById('fpsLimitSelector');
const themeSelector = document.getElementById('themeSelector');
const showElementHighlight = document.getElementById('showElementHighlight');
const autoFillForms = document.getElementById('autoFillForms');
const clearCookiesButton = document.getElementById('clearCookiesButton');
const clearFormDataButton = document.getElementById('clearFormDataButton');
const clearHistorySettingsButton = document.getElementById('clearHistorySettingsButton');
const enableDebugMode = document.getElementById('enableDebugMode');
const viewSourceButton = document.getElementById('viewSourceButton');
const showHistoryButton = document.getElementById('showHistoryButton');

// Debug panel elements
const debugPanel = document.getElementById('debugPanel');
const closeDebugButton = document.getElementById('closeDebugButton');
const wsStatus = document.getElementById('wsStatus');
const lastMessage = document.getElementById('lastMessage');
const elementDebugInfo = document.getElementById('elementDebugInfo');
const debugConsole = document.getElementById('debugConsole');

// Source panel elements
const sourcePanel = document.getElementById('sourcePanel');
const closeSourceButton = document.getElementById('closeSourceButton');
const pageSourceCode = document.getElementById('pageSourceCode');

// State variables
let websocket = null;
let isConnected = false;
let isMouseDown = false;
let lastX = 0;
let lastY = 0;
let dragStartX = 0;
let dragStartY = 0;
let isDragging = false;
let currentZoom = 100;
let currentFps = 10;
let isPageLoading = false;
let frameCount = 0;
let lastFpsUpdate = Date.now();
let hoveredElement = null;
let lastMessageTime = 0;
let screenWidth = 0;
let screenHeight = 0;
let isDebugMode = false;
let receivedFrames = 0;
let lastScreenshot = null;
let detectedFormData = null;
let currentUrl = "about:blank";
let isCurrentPageBookmarked = false;
let bookmarks = [];
let historyItems = [];

// Settings
const settings = {
    quality: 'medium',
    fpsLimit: 10,
    theme: 'light',
    highlightElements: true,
    debugMode: false,
    autoFillForms: true
};

// Load settings from localStorage if available
function loadSettings() {
    const savedSettings = localStorage.getItem('browserSettings');
    if (savedSettings) {
        try {
            const parsedSettings = JSON.parse(savedSettings);
            Object.assign(settings, parsedSettings);
            
            // Apply settings to UI elements
            qualitySelector.value = settings.quality;
            fpsLimitSelector.value = settings.fpsLimit;
            themeSelector.value = settings.theme;
            showElementHighlight.checked = settings.highlightElements;
            enableDebugMode.checked = settings.debugMode;
            fpsSlider.value = settings.fpsLimit;
            autoFillForms.checked = settings.autoFillForms !== false;
            
            // Apply theme
            applyTheme(settings.theme);
            
            // Set debug mode
            isDebugMode = settings.debugMode;
            if (isDebugMode) {
                debugPanel.classList.remove('hidden');
            }
            
            // Set FPS
            currentFps = settings.fpsLimit;
            
            console.log('Settings loaded:', settings);
        } catch (e) {
            console.error('Error loading settings:', e);
        }
    }
}

// Save settings to localStorage
function saveSettings() {
    try {
        localStorage.setItem('browserSettings', JSON.stringify(settings));
        console.log('Settings saved:', settings);
    } catch (e) {
        console.error('Error saving settings:', e);
    }
}

// Apply theme to document
function applyTheme(theme) {
    if (theme === 'system') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    } else {
        document.documentElement.setAttribute('data-theme', theme);
    }
}

// WebSocket connection setup
function connectWebSocket() {
    // Show loading overlay
    loadingOverlay.style.display = 'flex';
    
    // Get WebSocket URL from the current page URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    // Create WebSocket connection
    websocket = new WebSocket(wsUrl);
    
    // Update debug panel
    updateDebugPanel('Connecting to ' + wsUrl);
    
    // WebSocket event handlers
    websocket.onopen = function(event) {
        console.log('WebSocket connected');
        isConnected = true;
        connectionStatus.textContent = 'Connected';
        connectionStatus.classList.add('connected');
        loadingOverlay.style.display = 'none';
        
        // Set initial FPS
        sendFrameRateUpdate(currentFps);
        
        // Load initial bookmarks and history
        loadBookmarks();
        loadHistory();
        
        // Update debug panel
        updateDebugPanel('Connected');
    };
    
    websocket.onclose = function(event) {
        console.log('WebSocket disconnected');
        isConnected = false;
        connectionStatus.textContent = 'Disconnected';
        connectionStatus.classList.remove('connected');
        
        // Show loading overlay with reconnection message
        loadingOverlay.style.display = 'flex';
        document.querySelector('.loading-text').textContent = 'Connection lost. Reconnecting...';
        
        // Update debug panel
        updateDebugPanel('Disconnected, reconnecting in 3s');
        
        // Try to reconnect after a delay
        setTimeout(connectWebSocket, 3000);
    };
    
    websocket.onerror = function(error) {
        console.error('WebSocket error:', error);
        showError('Failed to connect to the browser server. Please try refreshing the page.');
        
        // Update debug panel
        updateDebugPanel('Error: ' + JSON.stringify(error));
    };
    
    websocket.onmessage = function(event) {
        try {
            receivedFrames++;
            const message = JSON.parse(event.data);
            
            // Update debug panel with the last message
            if (isDebugMode) {
                const shortData = message.data ? 
                    message.data.substring(0, 50) + '...[truncated]' : 
                    JSON.stringify(message);
                lastMessage.textContent = `${message.type}: ${shortData}`;
            }
            
            // Handle different message types
            switch(message.type) {
                case 'screenshot':
                    updateBrowserScreen(message.data);
                    updatePageInfo(message.page_info);
                    updateFpsCounter();
                    break;
                    
                case 'navigate_result':
                    hidePageLoadingIndicator();
                    if (message.result.status === 'success') {
                        urlInput.value = message.result.url;
                        currentUrl = message.result.url;
                        updateSecurityIndicator(message.result.url);
                        
                        // Check for auto-fill opportunities
                        if (settings.autoFillForms) {
                            setTimeout(attemptAutoFill, 1000);
                        }
                    } else {
                        showError(`Navigation error: ${message.result.message}`);
                    }
                    break;
                    
                case 'back_result':
                case 'forward_result':
                case 'refresh_result':
                    hidePageLoadingIndicator();
                    if (message.result.status === 'success') {
                        urlInput.value = message.result.url;
                        currentUrl = message.result.url;
                        updateSecurityIndicator(message.result.url);
                    } else {
                        showError(`Navigation error: ${message.result.message}`);
                    }
                    break;
                
                case 'get_element_info_result':
                    if (message.result.status === 'success') {
                        updateElementInfo(message.result.element);
                    }
                    break;
                    
                case 'fill_form_result':
                    if (message.result.status === 'success') {
                        console.log('Form filled:', message.result.results);
                    } else {
                        console.error('Form fill error:', message.result.message);
                    }
                    break;
                    
                case 'get_bookmarks_result':
                    if (message.result.status === 'success') {
                        bookmarks = message.result.bookmarks;
                        renderBookmarks();
                    }
                    break;
                    
                case 'add_bookmark_result':
                    if (message.result.status === 'success') {
                        // Update bookmark button state
                        bookmarkButton.innerHTML = '<i class="fas fa-bookmark"></i>';
                        bookmarkButton.classList.add('active');
                        isCurrentPageBookmarked = true;
                        
                        // Update bookmarks list
                        loadBookmarks();
                    }
                    break;
                    
                case 'remove_bookmark_result':
                    if (message.result.status === 'success') {
                        // Update bookmark button state
                        bookmarkButton.innerHTML = '<i class="far fa-bookmark"></i>';
                        bookmarkButton.classList.remove('active');
                        isCurrentPageBookmarked = false;
                        
                        // Update bookmarks list
                        loadBookmarks();
                    }
                    break;
                    
                case 'get_history_result':
                    if (message.result.status === 'success') {
                        historyItems = message.result.history;
                        renderHistory();
                    }
                    break;
                    
                case 'set_frame_rate_result':
                    console.log(`Frame rate set to ${message.fps} FPS`);
                    break;
                    
                case 'error':
                    showError(message.message);
                    break;
                    
                default:
                    console.log('Received message:', message);
            }
            
        } catch (error) {
            console.error('Error parsing message:', error);
            updateDebugPanel('Error parsing message: ' + error.message);
        }
    };
}

// Update the browser screen with the received screenshot
function updateBrowserScreen(base64Image) {
    // Sometimes we receive duplicate frames, so we can skip rendering them
    if (lastScreenshot === base64Image) return;
    
    lastScreenshot = base64Image;
    
    // Apply the new screenshot
    browserScreen.src = `data:image/png;base64,${base64Image}`;
    
    // Hide loading indicator if it's showing
    if (isPageLoading) {
        hidePageLoadingIndicator();
    }
}

// Update security indicator based on URL
function updateSecurityIndicator(url) {
    if (url.startsWith('https://')) {
        securityIndicator.innerHTML = '<i class="fas fa-lock"></i>';
        securityIndicator.classList.remove('insecure');
        securityIndicator.title = 'Secure connection';
    } else {
        securityIndicator.innerHTML = '<i class="fas fa-lock-open"></i>';
        securityIndicator.classList.add('insecure');
        securityIndicator.title = 'Insecure connection';
    }
}

// Update page information (title, URL, favicon, bookmark status)
function updatePageInfo(pageInfo) {
    if (pageInfo && pageInfo.status === 'success') {
        // Update page title
        document.title = `${pageInfo.title || 'Untitled'} - Interactive Browser`;
        pageTitle.textContent = pageInfo.title || 'Untitled';
        
        // Update URL and bookmark status
        currentUrl = pageInfo.url;
        isCurrentPageBookmarked = pageInfo.is_bookmarked;
        
        // Update bookmark button
        if (isCurrentPageBookmarked) {
            bookmarkButton.innerHTML = '<i class="fas fa-bookmark"></i>';
            bookmarkButton.classList.add('active');
        } else {
            bookmarkButton.innerHTML = '<i class="far fa-bookmark"></i>';
            bookmarkButton.classList.remove('active');
        }
        
        // Update favicon if available
        if (pageInfo.favicon) {
            pageFavicon.src = pageInfo.favicon;
            pageFavicon.style.display = 'inline';
        } else {
            pageFavicon.style.display = 'none';
        }
        
        // Update the URL input field if it's not focused
        if (document.activeElement !== urlInput) {
            urlInput.value = pageInfo.url;
            updateSecurityIndicator(pageInfo.url);
        }
        
        // Update navigation buttons state
        backButton.disabled = !pageInfo.can_go_back;
        forwardButton.disabled = !pageInfo.can_go_forward;
    }
}

// Update element info in the status bar
function updateElementInfo(element) {
    if (!element) {
        elementType.textContent = '';
        elementText.textContent = '';
        hideElementHighlight();
        return;
    }
    
    elementType.textContent = element.tagName.toLowerCase();
    elementText.textContent = element.textContent || '';
    
    // Show element highlight if enabled
    if (settings.highlightElements) {
        showElementHighlight(element.rect);
    }
    
    // Update debug panel with detailed element info
    if (isDebugMode) {
        const formattedInfo = JSON.stringify(element, null, 2);
        elementDebugInfo.textContent = formattedInfo;
    }
}

// Show element highlight overlay
function showElementHighlight(rect) {
    if (!settings.highlightElements) return;
    
    elementHighlight.style.left = `${rect.x}px`;
    elementHighlight.style.top = `${rect.y}px`;
    elementHighlight.style.width = `${rect.width}px`;
    elementHighlight.style.height = `${rect.height}px`;
    elementHighlight.style.opacity = '1';
}

// Hide element highlight overlay
function hideElementHighlight() {
    elementHighlight.style.opacity = '0';
}

// Show page loading indicator
function showPageLoadingIndicator() {
    isPageLoading = true;
    pageLoadingIndicator.classList.remove('hidden');
}

// Hide page loading indicator
function hidePageLoadingIndicator() {
    isPageLoading = false;
    pageLoadingIndicator.classList.add('hidden');
}

// Update FPS counter
function updateFpsCounter() {
    frameCount++;
    const now = Date.now();
    const elapsed = now - lastFpsUpdate;
    
    if (elapsed >= 1000) {  // Update every second
        const fps = Math.round((frameCount * 1000) / elapsed);
        fpsCounter.textContent = `${fps} FPS`;
        frameCount = 0;
        lastFpsUpdate = now;
    }
}

// Show error overlay with message
function showError(message) {
    errorMessage.textContent = message;
    errorOverlay.classList.remove('hidden');
    console.error('Error:', message);
    updateDebugPanel('Error: ' + message);
}

// Navigate to a URL
function navigateToUrl(url) {
    if (!isConnected) return;
    
    showPageLoadingIndicator();
    
    websocket.send(JSON.stringify({
        type: 'navigate',
        url: url
    }));
}

// Send frame rate update to server
function sendFrameRateUpdate(fps) {
    if (!isConnected) return;
    
    websocket.send(JSON.stringify({
        type: 'set_frame_rate',
        fps: fps
    }));
}

// Get element info at coordinates
function getElementInfoAtCoordinates(x, y) {
    if (!isConnected) return;
    
    websocket.send(JSON.stringify({
        type: 'get_element_info',
        x: x,
        y: y
    }));
}

// Execute JavaScript in browser context
function executeScript(script, args = []) {
    if (!isConnected) return;
    
    websocket.send(JSON.stringify({
        type: 'execute_script',
        script: script,
        args: args
    }));
}

// Set zoom level
function setZoom(level) {
    currentZoom = Math.max(25, Math.min(200, level));
    zoomLevel.textContent = `${currentZoom}%`;
    
    // Apply zoom using transform scale
    browserScreen.style.transform = `scale(${currentZoom / 100})`;
}

// Update debug panel
function updateDebugPanel(message) {
    if (!isDebugMode) return;
    
    wsStatus.textContent = message;
    
    // Add log to debug console
    const timestamp = new Date().toISOString().substr(11, 8);
    const logEntry = document.createElement('div');
    logEntry.textContent = `[${timestamp}] ${message}`;
    debugConsole.appendChild(logEntry);
    
    // Scroll to bottom
    debugConsole.scrollTop = debugConsole.scrollHeight;
}

// Load bookmarks from server
function loadBookmarks() {
    if (!isConnected) return;
    
    websocket.send(JSON.stringify({
        type: 'get_bookmarks'
    }));
}

// Toggle bookmark for current page
function toggleBookmark() {
    if (!isConnected) return;
    
    if (isCurrentPageBookmarked) {
        // Remove bookmark
        websocket.send(JSON.stringify({
            type: 'remove_bookmark',
            url: currentUrl
        }));
    } else {
        // Add bookmark
        websocket.send(JSON.stringify({
            type: 'add_bookmark',
            url: currentUrl,
            title: pageTitle.textContent || currentUrl
        }));
    }
}

// Render bookmarks list
function renderBookmarks() {
    bookmarksList.innerHTML = '';
    
    if (!bookmarks || bookmarks.length === 0) {
        const emptyMessage = document.createElement('div');
        emptyMessage.className = 'empty-message';
        emptyMessage.textContent = 'No bookmarks yet';
        bookmarksList.appendChild(emptyMessage);
        return;
    }
    
    const searchTerm = bookmarkSearch.value.toLowerCase();
    
    // Sort bookmarks by creation date (newest first)
    const sortedBookmarks = [...bookmarks].sort((a, b) => b.created - a.created);
    
    for (const bookmark of sortedBookmarks) {
        // Filter by search term if provided
        if (searchTerm && 
            !bookmark.title.toLowerCase().includes(searchTerm) && 
            !bookmark.url.toLowerCase().includes(searchTerm)) {
            continue;
        }
        
        const bookmarkItem = document.createElement('div');
        bookmarkItem.className = 'bookmark-item';
        
        const icon = document.createElement('div');
        icon.className = 'bookmark-icon';
        icon.innerHTML = '<i class="fas fa-bookmark"></i>';
        
        const details = document.createElement('div');
        details.className = 'bookmark-details';
        
        const title = document.createElement('div');
        title.className = 'bookmark-title';
        title.textContent = bookmark.title;
        
        const url = document.createElement('div');
        url.className = 'bookmark-url';
        url.textContent = bookmark.url;
        
        const actions = document.createElement('div');
        actions.className = 'bookmark-actions';
        
        const removeButton = document.createElement('button');
        removeButton.className = 'bookmark-action';
        removeButton.title = 'Remove';
        removeButton.innerHTML = '<i class="fas fa-times"></i>';
        removeButton.addEventListener('click', (e) => {
            e.stopPropagation();
            removeBookmark(bookmark.url);
        });
        
        details.appendChild(title);
        details.appendChild(url);
        actions.appendChild(removeButton);
        
        bookmarkItem.appendChild(icon);
        bookmarkItem.appendChild(details);
        bookmarkItem.appendChild(actions);
        
        // Navigate to bookmark when clicked
        bookmarkItem.addEventListener('click', () => {
            navigateToUrl(bookmark.url);
            toggleBookmarksPanel();
        });
        
        bookmarksList.appendChild(bookmarkItem);
    }
}

// Remove a bookmark
function removeBookmark(url) {
    if (!isConnected) return;
    
    websocket.send(JSON.stringify({
        type: 'remove_bookmark',
        url: url
    }));
}

// Load browsing history
function loadHistory() {
    if (!isConnected) return;
    
    websocket.send(JSON.stringify({
        type: 'get_history'
    }));
}

// Clear browsing history
function clearHistory() {
    if (!isConnected) return;
    
    websocket.send(JSON.stringify({
        type: 'clear_history'
    }));
    
    // Reset history list
    historyItems = [];
    renderHistory();
}

// Render history list
function renderHistory() {
    historyList.innerHTML = '';
    
    if (!historyItems || historyItems.length === 0) {
        const emptyMessage = document.createElement('div');
        emptyMessage.className = 'empty-message';
        emptyMessage.textContent = 'No history yet';
        historyList.appendChild(emptyMessage);
        return;
    }
    
    const searchTerm = historySearch.value.toLowerCase();
    
    // Display history in reverse order (newest first)
    for (let i = historyItems.length - 1; i >= 0; i--) {
        const url = historyItems[i];
        
        // Skip about:blank
        if (url === 'about:blank') continue;
        
        // Filter by search term if provided
        if (searchTerm && !url.toLowerCase().includes(searchTerm)) {
            continue;
        }
        
        // Create history item
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        
        const icon = document.createElement('div');
        icon.className = 'history-icon';
        icon.innerHTML = '<i class="fas fa-history"></i>';
        
        const details = document.createElement('div');
        details.className = 'history-details';
        
        // Use domain as title
        let title = url;
        try {
            const urlObj = new URL(url);
            title = urlObj.hostname;
        } catch (e) {
            title = url;
        }
        
        const titleEl = document.createElement('div');
        titleEl.className = 'history-title';
        titleEl.textContent = title;
        
        const urlEl = document.createElement('div');
        urlEl.className = 'history-url';
        urlEl.textContent = url;
        
        details.appendChild(titleEl);
        details.appendChild(urlEl);
        
        historyItem.appendChild(icon);
        historyItem.appendChild(details);
        
        // Navigate to history item when clicked
        historyItem.addEventListener('click', () => {
            navigateToUrl(url);
            toggleHistoryPanel();
        });
        
        historyList.appendChild(historyItem);
    }
}

// Clear cookies
function clearCookies() {
    if (!isConnected) return;
    
    websocket.send(JSON.stringify({
        type: 'clear_cookies'
    }));
    
    alert('Cookies cleared successfully');
}

// Clear form data
function clearFormData() {
    if (!isConnected) return;
    
    websocket.send(JSON.stringify({
        type: 'clear_form_data'
    }));
    
    alert('Form data cleared successfully');
}

// Auto-fill forms on the current page
function attemptAutoFill() {
    if (!isConnected || !settings.autoFillForms) return;
    
    websocket.send(JSON.stringify({
        type: 'fill_form'
    }));
}

// View page source
function viewPageSource() {
    if (!isConnected) return;
    
    // Request page HTML
    fetch('/api/page-html')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                pageSourceCode.textContent = data.html;
                sourcePanel.classList.remove('hidden');
            } else {
                showError('Failed to get page source: ' + (data.message || 'Unknown error'));
            }
        })
        .catch(error => {
            showError('Failed to get page source: ' + error.message);
        });
}

// Toggle panels
function toggleBookmarksPanel() {
    bookmarksPanel.classList.toggle('hidden');
    if (!bookmarksPanel.classList.contains('hidden')) {
        loadBookmarks();
        historyPanel.classList.add('hidden');
        settingsPanel.classList.add('hidden');
        sourcePanel.classList.add('hidden');
    }
}

function toggleHistoryPanel() {
    historyPanel.classList.toggle('hidden');
    if (!historyPanel.classList.contains('hidden')) {
        loadHistory();
        bookmarksPanel.classList.add('hidden');
        settingsPanel.classList.add('hidden');
        sourcePanel.classList.add('hidden');
    }
}

function toggleSettingsPanel() {
    settingsPanel.classList.toggle('hidden');
    if (!settingsPanel.classList.contains('hidden')) {
        bookmarksPanel.classList.add('hidden');
        historyPanel.classList.add('hidden');
        sourcePanel.classList.add('hidden');
    }
}

function toggleDebugPanel() {
    debugPanel.classList.toggle('hidden');
}

function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => {
            showError(`Error attempting to enable fullscreen: ${err.message}`);
        });
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        }
    }
}

// Event listeners

// Navigation and URL input
urlInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
        navigateToUrl(urlInput.value);
    }
});

goButton.addEventListener('click', () => {
    navigateToUrl(urlInput.value);
});

backButton.addEventListener('click', () => {
    if (!isConnected || backButton.disabled) return;
    
    showPageLoadingIndicator();
    websocket.send(JSON.stringify({
        type: 'back'
    }));
});

forwardButton.addEventListener('click', () => {
    if (!isConnected || forwardButton.disabled) return;
    
    showPageLoadingIndicator();
    websocket.send(JSON.stringify({
        type: 'forward'
    }));
});

refreshButton.addEventListener('click', () => {
    if (!isConnected) return;
    
    showPageLoadingIndicator();
    websocket.send(JSON.stringify({
        type: 'refresh'
    }));
});

homeButton.addEventListener('click', () => {
    if (!isConnected) return;
    
    navigateToUrl('about:blank');
});

// Bookmark actions
bookmarkButton.addEventListener('click', toggleBookmark);
bookmarksListButton.addEventListener('click', toggleBookmarksPanel);
closeBookmarksButton.addEventListener('click', toggleBookmarksPanel);
bookmarkSearch.addEventListener('input', renderBookmarks);

// History actions
clearHistoryButton.addEventListener('click', clearHistory);
closeHistoryButton.addEventListener('click', toggleHistoryPanel);
historySearch.addEventListener('input', renderHistory);
showHistoryButton.addEventListener('click', toggleHistoryPanel);

// Settings and panels
settingsButton.addEventListener('click', toggleSettingsPanel);
closeSettingsButton.addEventListener('click', toggleSettingsPanel);
closeDebugButton.addEventListener('click', toggleDebugPanel);
fullscreenButton.addEventListener('click', toggleFullscreen);
closeSourceButton.addEventListener('click', () => {
    sourcePanel.classList.add('hidden');
});

clearCookiesButton.addEventListener('click', clearCookies);
clearFormDataButton.addEventListener('click', clearFormData);
clearHistorySettingsButton.addEventListener('click', clearHistory);
viewSourceButton.addEventListener('click', viewPageSource);

// Settings changes
themeSelector.addEventListener('change', (e) => {
    settings.theme = e.target.value;
    applyTheme(settings.theme);
    saveSettings();
});

showElementHighlight.addEventListener('change', (e) => {
    settings.highlightElements = e.target.checked;
    saveSettings();
});

autoFillForms.addEventListener('change', (e) => {
    settings.autoFillForms = e.target.checked;
    saveSettings();
});

enableDebugMode.addEventListener('change', (e) => {
    settings.debugMode = e.target.checked;
    isDebugMode = e.target.checked;
    saveSettings();
    
    if (isDebugMode) {
        debugPanel.classList.remove('hidden');
    } else {
        debugPanel.classList.add('hidden');
    }
});

qualitySelector.addEventListener('change', (e) => {
    settings.quality = e.target.value;
    saveSettings();
});

fpsLimitSelector.addEventListener('change', (e) => {
    const fps = parseInt(e.target.value);
    settings.fpsLimit = fps;
    currentFps = fps;
    fpsSlider.value = fps;
    saveSettings();
    sendFrameRateUpdate(fps);
});

// Error handling
errorDismiss.addEventListener('click', () => {
    errorOverlay.classList.add('hidden');
});

// Form data prompt
saveFormData.addEventListener('click', () => {
    if (!detectedFormData) return;
    
    // Save each field
    for (const field in detectedFormData) {
        websocket.send(JSON.stringify({
            type: 'add_form_data',
            field: field,
            value: detectedFormData[field]
        }));
    }
    
    formDataPrompt.classList.add('hidden');
    detectedFormData = null;
});

cancelFormData.addEventListener('click', () => {
    formDataPrompt.classList.add('hidden');
    detectedFormData = null;
});

// Zoom controls
zoomInButton.addEventListener('click', () => {
    setZoom(currentZoom + 10);
});

zoomOutButton.addEventListener('click', () => {
    setZoom(currentZoom - 10);
});

// FPS slider control
fpsSlider.addEventListener('input', (e) => {
    const fps = parseInt(e.target.value);
    currentFps = fps;
    settings.fpsLimit = fps;
    fpsLimitSelector.value = fps.toString();
    saveSettings();
    sendFrameRateUpdate(fps);
});

// Mouse events for browser interaction
browserScreen.addEventListener('mousedown', (event) => {
    if (!isConnected) return;
    
    isMouseDown = true;
    dragStartX = event.offsetX;
    dragStartY = event.offsetY;
    lastX = event.offsetX;
    lastY = event.offsetY;
    
    // Wait a bit to determine if this is a click or drag start
    setTimeout(() => {
        if (isMouseDown && !isDragging) {
            websocket.send(JSON.stringify({
                type: 'click',
                x: event.offsetX,
                y: event.offsetY
            }));
        }
    }, 150); // Short delay to distinguish between click and drag
});

browserScreen.addEventListener('mousemove', (event) => {
    if (!isConnected) return;
    
    // Update hovered element info on mousemove
    if (Date.now() - lastMessageTime > 200) {  // Throttle to avoid too many requests
        getElementInfoAtCoordinates(event.offsetX, event.offsetY);
        lastMessageTime = Date.now();
    }
    
    if (isMouseDown) {
        const moveDistance = Math.sqrt(
            Math.pow(event.offsetX - dragStartX, 2) + 
            Math.pow(event.offsetY - dragStartY, 2)
        );
        
        // If moved more than 5px, consider it a drag
        if (moveDistance > 5) {
            isDragging = true;
        }
    }
    
    lastX = event.offsetX;
    lastY = event.offsetY;
});

browserScreen.addEventListener('mouseup', (event) => {
    if (!isConnected) return;
    
    if (isDragging) {
        websocket.send(JSON.stringify({
            type: 'drag',
            startX: dragStartX,
            startY: dragStartY,
            endX: event.offsetX,
            endY: event.offsetY
        }));
    }
    
    isMouseDown = false;
    isDragging = false;
});

// Handle mouse leaving the browser viewport
browserScreen.addEventListener('mouseleave', () => {
    if (isMouseDown) {
        isMouseDown = false;
        isDragging = false;
    }
    hideElementHighlight();
});

// Keyboard events for typing
document.addEventListener('keydown', (event) => {
    // Only capture key events when browser viewport is active and not in an input field
    if (!isConnected || event.target === urlInput || 
        event.target.tagName === 'INPUT' || 
        event.target.tagName === 'TEXTAREA' ||
        event.target.tagName === 'SELECT') {
        return;
    }
    
    // Handle special keys
    const specialKeys = [
        'Enter', 'Backspace', 'Tab', 'Escape', 
        'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
        'Delete', 'Home', 'End', 'PageUp', 'PageDown'
    ];
    
    if (specialKeys.includes(event.key)) {
        websocket.send(JSON.stringify({
            type: 'key',
            key: event.key
        }));
        
        // Prevent default for these keys to avoid browser actions
        event.preventDefault();
    } else if (event.key.length === 1) {
        // Regular character key
        websocket.send(JSON.stringify({
            type: 'type',
            text: event.key
        }));
    }
});

// Mouse wheel for scrolling
browserScreen.addEventListener('wheel', (event) => {
    if (!isConnected) return;
    
    // Normalize scroll delta
    const deltaX = event.deltaX;
    const deltaY = event.deltaY;
    
    websocket.send(JSON.stringify({
        type: 'scroll',
        x: deltaX,
        y: deltaY
    }));
    
    // Prevent default to avoid browser scrolling
    event.preventDefault();
});

// Window resize event
window.addEventListener('resize', () => {
    // Get screen dimensions
    screenWidth = browserScreen.clientWidth;
    screenHeight = browserScreen.clientHeight;
});

// Document visibility change (tab switch)
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        // Refresh the page if we come back to the tab
        if (isConnected) {
            // Force a new screenshot
            websocket.send(JSON.stringify({
                type: 'get_screenshot',
                forceNew: true
            }));
        }
    }
});

// Initialize
window.addEventListener('load', () => {
    // Load settings
    loadSettings();
    
    // Set initial screen dimensions
    screenWidth = browserScreen.clientWidth;
    screenHeight = browserScreen.clientHeight;
    
    // Connect to WebSocket
    connectWebSocket();
    
    // Set initial zoom
    setZoom(currentZoom);
    
    // Check for system color scheme changes
    if (settings.theme === 'system') {
        const darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        darkModeMediaQuery.addEventListener('change', (e) => {
            applyTheme('system');
        });
    }
});
