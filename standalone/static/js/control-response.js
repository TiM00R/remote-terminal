// Control Response - Response formatting and display

function showLoading() {
    const content = document.getElementById('responseContent');
    content.innerHTML = '<div class="loading">Executing MCP tool...</div>';
}

function displayResponse(result) {
    const content = document.getElementById('responseContent');
    
    // Format JSON with syntax highlighting and escape sequence handling
    const formatted = formatJSON(result);
    content.innerHTML = formatted;
}

function displayError(error) {
    const content = document.getElementById('responseContent');
    content.innerHTML = `<div class="error">ERROR: ${escapeHtml(error)}</div>`;
}

function formatJSON(obj) {
    const json = JSON.stringify(obj, null, 2);
    
    // First convert escape sequences in the JSON string itself
    let processedJson = json
        .replace(/\\\\r\\\\n/g, '\n')  // Double-escaped CRLF
        .replace(/\\\\n/g, '\n')        // Double-escaped LF
        .replace(/\\\\r/g, '\n')        // Double-escaped CR
        .replace(/\\r\\n/g, '\n')       // Escaped CRLF
        .replace(/\\n/g, '\n')          // Escaped LF
        .replace(/\\r/g, '\n')          // Escaped CR
        .replace(/\\t/g, '    ');       // Tabs to spaces
    
    // Collapse multiple consecutive newlines into single newlines
    // This removes empty lines while preserving content
    processedJson = processedJson.replace(/\n\n+/g, '\n');
    
    // Then apply syntax highlighting
    const highlighted = processedJson
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
        .replace(/: (\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
        .replace(/: (true|false)/g, ': <span class="json-boolean">$1</span>')
        .replace(/: null/g, ': <span class="json-null">null</span>');
    
    // Wrap remaining string values (must be done last to avoid breaking the patterns above)
    // Also add newline after opening quote for multi-line strings
    const final = highlighted.replace(/: "([^"]*(?:\n[^"]*)*?)"/g, (match, content) => {
        // Check if content contains newlines (multi-line string)
        if (content.includes('\n')) {
            // Add newline after opening quote for better formatting
            return `: <span class="json-string">"\n${content}"</span>`;
        }
        // Single-line string - no extra newline needed
        return `: <span class="json-string">"${content}"</span>`;
    });
    
    return `<pre>${final}</pre>`;
}

function copyResponse() {
    const content = document.getElementById('responseContent');
    const text = content.innerText || content.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('copyBtn');
        const originalText = btn.textContent;
        btn.textContent = '✓ Copied!';
        btn.classList.add('copied');
        
        setTimeout(() => {
            btn.textContent = originalText;
            btn.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        alert('Failed to copy: ' + err);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export for global access
window.displayResponse = displayResponse;
window.displayError = displayError;
window.showLoading = showLoading;
window.copyResponse = copyResponse;
