/**
 * Remote Terminal - WebSocket Edition
 * FIXED: Properly closes WebSocket on page unload to prevent zombie connections
 */

(async function() {
    // Wait for Terminal and FitAddon to load
    while (typeof Terminal === 'undefined' || typeof FitAddon === 'undefined') {
        await new Promise(r => setTimeout(r, 100));
    }
    
    // ========== TERMINAL INITIALIZATION ==========
    
    const term = new Terminal({
        cursorBlink: true, 
        fontSize: 14,
        fontFamily: 'Consolas, "Courier New", monospace',
        theme: { 
            background: '#1e1e1e', 
            foreground: '#cccccc', 
            cursor: '#00ff00' 
        },
        scrollback: 10000,
        convertEol: true
    });
    
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(document.getElementById('terminal'));
    
    await new Promise(r => setTimeout(r, 100));
    fitAddon.fit();
    
    // Welcome message
    term.writeln('Terminal initialized. Connecting via WebSocket...');
    term.writeln('Multi-terminal sync: Type in ANY terminal, see in ALL terminals!');
    term.writeln('Tip: Right-click for Copy/Paste menu, or use Ctrl+Shift+C/V');
    
    // ========== WEBSOCKET CONNECTION ==========
    
    let ws = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    let intentionalClose = false;
    
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/terminal`;
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log('WebSocket connected');
            reconnectAttempts = 0;
            term.writeln('\r\n✓ WebSocket connected - terminals synchronized');
        };
        
        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                
                if (message.type === 'terminal_output') {
                    term.write(message.data);
                }
                else if (message.type === 'connection') {
                    console.log('Connection status:', message.status);
                }
                else if (message.type === 'transfer_progress') {
                    console.log('Transfer progress:', message.transfer_id);
                }
                
            } catch (e) {
                console.error('Error processing WebSocket message:', e);
            }
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        ws.onclose = () => {
            console.log('WebSocket closed');
            
            // Don't reconnect if this was intentional (page unload)
            if (intentionalClose) {
                console.log('WebSocket closed intentionally (page unload)');
                return;
            }
            
            term.writeln('\r\n✗ WebSocket disconnected');
            
            // Attempt reconnection
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
                term.writeln(`  Reconnecting in ${delay/1000}s... (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);
                
                setTimeout(connectWebSocket, delay);
            } else {
                term.writeln('  Max reconnection attempts reached. Please refresh the page.');
            }
        };
    }
    
    // FIXED: Close WebSocket when page unloads
    window.addEventListener('beforeunload', () => {
        intentionalClose = true;
        if (ws && ws.readyState === WebSocket.OPEN) {
            console.log('Closing WebSocket due to page unload');
            ws.close();
        }
    });
    
    // Initial connection
    connectWebSocket();
    
    // ========== USER INPUT HANDLING ==========
    
    term.onData(data => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'terminal_input',
                data: data
            }));
        }
    });
    
    // ========== TERMINAL RESIZE ==========
    
    term.onResize(({cols, rows}) => {
        console.log('Terminal resized to:', cols, 'x', rows);
        
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'terminal_resize',
                cols: cols,
                rows: rows
            }));
        }
    });
    
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            fitAddon.fit();
        }, 100);
    });
    
    // ========== COPY/PASTE FUNCTIONALITY ==========
    
    const terminalElement = document.getElementById('terminal');
    let contextMenu = null;
    
    function copySelection() {
        const selection = term.getSelection();
        if (selection) {
            navigator.clipboard.writeText(selection)
                .then(() => console.log('Copied to clipboard'))
                .catch(err => console.warn('Copy failed:', err));
        }
    }
    
    function pasteFromClipboard() {
        navigator.clipboard.readText()
            .then(text => {
                if (text) {
                    term.paste(text);
                }
            })
            .catch(err => console.warn('Paste failed:', err));
    }
    
    terminalElement.addEventListener('paste', (e) => {
        e.preventDefault();
        const text = e.clipboardData?.getData('text');
        if (text) {
            term.paste(text);
        }
    });
    
    term.attachCustomKeyEventHandler((event) => {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const modKey = isMac ? event.metaKey : event.ctrlKey;
        
        if (event.type !== 'keydown') return true;
        
        if (modKey && event.key.toLowerCase() === 'c') {
            const hasSelection = term.hasSelection();
            
            if (event.shiftKey || hasSelection) {
                copySelection();
                return false;
            } else if (!hasSelection) {
                return true;
            }
        }
        
        if (modKey && event.shiftKey && event.key.toLowerCase() === 'v') {
            pasteFromClipboard();
            return false;
        }
        
        return true;
    });
    
    // ========== CONTEXT MENU ==========
    
    function removeContextMenu() {
        if (contextMenu) {
            contextMenu.remove();
            contextMenu = null;
        }
    }
    
    function showContextMenu(x, y) {
        removeContextMenu();
        
        const hasSelection = term.hasSelection();
        
        contextMenu = document.createElement('div');
        contextMenu.className = 'context-menu';
        contextMenu.style.left = x + 'px';
        contextMenu.style.top = y + 'px';
        
        const copyItem = document.createElement('div');
        copyItem.className = 'context-menu-item' + (hasSelection ? '' : ' disabled');
        copyItem.textContent = 'Copy';
        if (hasSelection) {
            copyItem.onclick = () => {
                copySelection();
                removeContextMenu();
            };
        }
        contextMenu.appendChild(copyItem);
        
        const pasteItem = document.createElement('div');
        pasteItem.className = 'context-menu-item';
        pasteItem.textContent = 'Paste';
        pasteItem.onclick = () => {
            pasteFromClipboard();
            removeContextMenu();
        };
        contextMenu.appendChild(pasteItem);
        
        const separator = document.createElement('div');
        separator.className = 'context-menu-separator';
        contextMenu.appendChild(separator);
        
        const selectAllItem = document.createElement('div');
        selectAllItem.className = 'context-menu-item';
        selectAllItem.textContent = 'Select All';
        selectAllItem.onclick = () => {
            term.selectAll();
            removeContextMenu();
        };
        contextMenu.appendChild(selectAllItem);
        
        const clearItem = document.createElement('div');
        clearItem.className = 'context-menu-item';
        clearItem.textContent = 'Clear Terminal';
        clearItem.onclick = () => {
            term.clear();
            removeContextMenu();
        };
        contextMenu.appendChild(clearItem);
        
        document.body.appendChild(contextMenu);
        
        const rect = contextMenu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            contextMenu.style.left = (x - rect.width) + 'px';
        }
        if (rect.bottom > window.innerHeight) {
            contextMenu.style.top = (y - rect.height) + 'px';
        }
    }
    
    terminalElement.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        showContextMenu(e.pageX, e.pageY);
    });
    
    document.addEventListener('click', removeContextMenu);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            removeContextMenu();
        }
    });
    
    term.focus();
    
})();
