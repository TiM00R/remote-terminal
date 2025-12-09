/**
 * Remote Terminal - JavaScript Module
 * Handles xterm.js terminal initialization, I/O, copy/paste, and SFTP transfer progress
 */

(async function() {
    // Wait for Terminal and FitAddon to load
    while (typeof Terminal === 'undefined' || typeof FitAddon === 'undefined') {
        await new Promise(r => setTimeout(r, 100));
    }
    
    // ========== TERMINAL INITIALIZATION ==========
    
    // Create terminal with configuration
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
    
    // Add fit addon for automatic resizing
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(document.getElementById('terminal'));
    
    // Initial fit and resize notification
    await new Promise(r => setTimeout(r, 100));
    fitAddon.fit();
    
    // Send initial size to backend
    fetch('/api/terminal_resize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            cols: term.cols,
            rows: term.rows
        })
    }).catch(err => console.error('Initial resize failed:', err));
    
    // Welcome message
    term.writeln('Terminal initialized. Waiting for SSH output...');
    term.writeln('Tip: Right-click for Copy/Paste menu, or use Ctrl+Shift+C/V');
    
    // ========== USER INPUT HANDLING ==========
    
    // Send user input to backend
    term.onData(data => {
        fetch('/api/terminal_input', {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({data})
        }).catch(() => {});
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
    
    // Handle paste events
    terminalElement.addEventListener('paste', (e) => {
        e.preventDefault();
        const text = e.clipboardData?.getData('text');
        if (text) {
            term.paste(text);
        }
    });
    
    // Custom keyboard shortcuts (Ctrl+Shift+C/V)
    term.attachCustomKeyEventHandler((event) => {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const modKey = isMac ? event.metaKey : event.ctrlKey;
        
        if (event.type !== 'keydown') return true;
        
        // Ctrl+C or Ctrl+Shift+C for copy
        if (modKey && event.key.toLowerCase() === 'c') {
            const hasSelection = term.hasSelection();
            
            if (event.shiftKey || hasSelection) {
                copySelection();
                return false;
            } else if (!hasSelection) {
                return true; // Allow Ctrl+C through to terminal
            }
        }
        
        // Ctrl+Shift+V for paste
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
        
        // Copy option
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
        
        // Paste option
        const pasteItem = document.createElement('div');
        pasteItem.className = 'context-menu-item';
        pasteItem.textContent = 'Paste';
        pasteItem.onclick = () => {
            pasteFromClipboard();
            removeContextMenu();
        };
        contextMenu.appendChild(pasteItem);
        
        // Separator
        const separator = document.createElement('div');
        separator.className = 'context-menu-separator';
        contextMenu.appendChild(separator);
        
        // Select All option
        const selectAllItem = document.createElement('div');
        selectAllItem.className = 'context-menu-item';
        selectAllItem.textContent = 'Select All';
        selectAllItem.onclick = () => {
            term.selectAll();
            removeContextMenu();
        };
        contextMenu.appendChild(selectAllItem);
        
        // Clear Terminal option
        const clearItem = document.createElement('div');
        clearItem.className = 'context-menu-item';
        clearItem.textContent = 'Clear Terminal';
        clearItem.onclick = () => {
            term.clear();
            removeContextMenu();
        };
        contextMenu.appendChild(clearItem);
        
        document.body.appendChild(contextMenu);
        
        // Adjust position if menu goes off-screen
        const rect = contextMenu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            contextMenu.style.left = (x - rect.width) + 'px';
        }
        if (rect.bottom > window.innerHeight) {
            contextMenu.style.top = (y - rect.height) + 'px';
        }
    }
    
    // Right-click to show context menu
    terminalElement.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        showContextMenu(e.pageX, e.pageY);
    });
    
    // Close context menu on click or escape
    document.addEventListener('click', removeContextMenu);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            removeContextMenu();
        }
    });
    
    // ========== TERMINAL RESIZE ==========
    
    term.onResize(({cols, rows}) => {
        console.log('Terminal resized to:', cols, 'x', rows);
        fetch('/api/terminal_resize', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cols, rows})
        }).catch(err => console.error('Resize failed:', err));
    });
    
    // Handle window resize
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            fitAddon.fit();
        }, 100);
    });
    
    // ========== OUTPUT POLLING ==========
    
    async function pollOutput() {
        while(true) {
            try {
                const res = await fetch('/api/terminal_output');
                const data = await res.json();
                if (data.output) term.write(data.output);
            } catch(e) {}
            await new Promise(r => setTimeout(r, 50));
        }
    }
    pollOutput();
    
    // Focus terminal
    term.focus();
    
})();
