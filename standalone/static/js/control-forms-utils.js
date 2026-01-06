// Control Forms Utils - Form utilities, serialization, execution, and helpers

function serializeForm(form, tool) {
    const data = {};

    tool.arguments.forEach(arg => {
        if (arg.type === 'checkbox') {
            const input = form.querySelector(`#${arg.name}`);
            data[arg.name] = input ? input.checked : false;
        } else if (arg.type === 'array') {
            const arrayField = form.querySelector(`.array-field[data-name="${arg.name}"]`);
            const items = arrayField.querySelectorAll('.array-item');
            data[arg.name] = Array.from(items).map(item => {
                const obj = {};
                arg.item_fields.forEach(field => {
                    const input = item.querySelector(`input[name="${field.name}"]`);
                    obj[field.name] = input ? input.value : '';
                });
                return obj;
            });

        } else if (arg.type === 'recipe_select') {
            // Handle recipe_select specially - convert to number
            const input = form.querySelector(`#${arg.name}`);
            if (input && input.value) {
                data[arg.name] = parseInt(input.value);
            }
        } else if (arg.type === 'conversation_select') {
            // Handle conversation_select specially - convert to number
            const input = form.querySelector(`#${arg.name}`);
            if (input && input.value) {
                data[arg.name] = parseInt(input.value);
            }
        } else {
            const input = form.querySelector(`#${arg.name}`);
            if (input) {
                let value;

                // Special handling for contentEditable elements (bash-editor)
                if (input.contentEditable === 'true') {
                    value = input.textContent;
                } else {
                    value = input.value;
                }

                // CRITICAL: Convert Windows backslashes to forward slashes for file paths
                // This prevents escape sequence interpretation (e.g., \t becomes tab, \r becomes carriage return)
                // Python accepts forward slashes on Windows
                if ((arg.type === 'file_picker' || arg.type === 'folder_picker') && value) {
                    value = value.replace(/\\/g, '/');
                }

                // Convert to appropriate type
                if (arg.type === 'number') {
                    value = value ? parseFloat(value) : undefined;
                }

                // // Special handling for commands field - parse JSON if present
                // if (arg.name === 'commands') {
                //     const cmdElement = form.querySelector(`#${arg.name}`);
                //     value = cmdElement ? cmdElement.textContent : '';
                //     if (value) {
                //         try {
                //             value = JSON.parse(value);
                //         } catch (e) {
                //             console.warn('Failed to parse commands JSON');
                //         }
                //     }
                // }

                // Special handling for commands field - parse JSON if present
                if (arg.name === 'commands') {
                    const cmdElement = form.querySelector(`#${arg.name}`);
                    // Check if it's a contentEditable element (like <pre>) or a regular input (like <textarea>)
                    if (cmdElement.contentEditable === 'true') {
                        value = cmdElement.textContent;
                    } else {
                        value = cmdElement.value;  // Regular textarea or input
                    }

                    if (value) {
                        try {
                            value = JSON.parse(value);
                        } catch (e) {
                            console.warn('Failed to parse commands JSON:', e);
                        }
                    }
                }



                // FIXED: Always include required fields, skip only empty optional fields
                // This allows browser validation to catch missing required fields
                if (arg.required) {
                    // Always include required fields even if empty
                    data[arg.name] = value;
                } else {
                    // For optional fields, only include if not empty
                    if (value !== '' && value !== undefined && value !== null) {
                        // Handle comma-separated values (like exclude_patterns)
                        if (arg.name === 'exclude_patterns' && value) {
                            value = value.split(',').map(s => s.trim()).filter(s => s);
                        }
                        data[arg.name] = value;
                    }
                }
            }
        }
    });

    return data;
}

async function executeTool(tool) {
    const form = document.getElementById('toolForm');
    const executeBtn = form.querySelector('.btn-execute');

    // Validate form before execution
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    // Disable button
    executeBtn.disabled = true;
    executeBtn.textContent = '⏳ Executing...';

    // Show loading in response
    window.showLoading();

    try {
        // Serialize form data
        const toolArgs = serializeForm(form, tool);

        console.log('Executing tool:', tool.name, 'with arguments:', toolArgs);

        // Call API
        const response = await fetch('http://localhost:8081/execute_mcp_tool', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tool: tool.name,
                arguments: toolArgs
            })
        });

        const result = await response.json();
        result.tool = tool.name;
        // Display result
        window.displayResponse(result);

    } catch (error) {
        window.displayError(error.toString());
    } finally {
        executeBtn.disabled = false;
        executeBtn.textContent = `▶️ Execute ${tool.name}`;
    }
}

// Bash syntax highlighting helper
function highlightBash(code) {
    // First escape HTML entities
    let highlighted = code
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Then apply syntax highlighting (working on escaped text)
    highlighted = highlighted
        // Comments (# to end of line)
        .replace(/(#[^\n]*)/g, '<span style="color: #6A9955;">$1</span>')
        // Strings (double quotes)
        .replace(/(&quot;(?:[^&]|&(?!quot;))*&quot;)/g, '<span style="color: #CE9178;">$1</span>')
        // Variables ($VAR or ${VAR})
        .replace(/(\$\w+|\$\{[^}]+\})/g, '<span style="color: #9CDCFE;">$1</span>')
        // Keywords
        .replace(/\b(if|then|else|elif|fi|for|while|do|done|case|esac|function|return|source|export|local|readonly)\b/g, '<span style="color: #C586C0;">$1</span>')
        // echo command (special - very common)
        .replace(/\b(echo)\b/g, '<span style="color: #DCDCAA;">$1</span>')
        // Built-in commands
        .replace(/\b(ls|cd|pwd|cat|grep|awk|sed|find|chmod|chown|mkdir|rm|cp|mv|exit)\b/g, '<span style="color: #4EC9B0;">$1</span>')
        // Numbers
        .replace(/\b(\d+)\b/g, '<span style="color: #B5CEA8;">$1</span>');

    return highlighted;
}

// Cursor position helpers
function saveCursorPosition(element) {
    const selection = window.getSelection();
    if (!selection.rangeCount) return 0;

    const range = selection.getRangeAt(0);
    const preRange = range.cloneRange();
    preRange.selectNodeContents(element);
    preRange.setEnd(range.endContainer, range.endOffset);
    return preRange.toString().length;
}

function restoreCursorPosition(element, position) {
    const selection = window.getSelection();
    const range = document.createRange();

    let charCount = 0;
    let nodeStack = [element];
    let node, foundStart = false;

    while (!foundStart && (node = nodeStack.pop())) {
        if (node.nodeType === Node.TEXT_NODE) {
            const nextCharCount = charCount + node.length;
            if (position <= nextCharCount) {
                range.setStart(node, position - charCount);
                range.collapse(true);
                foundStart = true;
            }
            charCount = nextCharCount;
        } else {
            for (let i = node.childNodes.length - 1; i >= 0; i--) {
                nodeStack.push(node.childNodes[i]);
            }
        }
    }

    selection.removeAllRanges();
    selection.addRange(range);
}

function showToolHelp(tool) {
    const responseCardTitle = document.getElementById('responseCardTitle');
    const responseTitle = document.querySelector('.response-title');
    const responseContent = document.getElementById('responseContent');

    // Change card title to "MCP Tool Help"
    if (responseCardTitle) {
        responseCardTitle.textContent = '📤 MCP Tool Help';
    }

    // Change response title to show tool name
    if (responseTitle) {
        responseTitle.innerHTML = `MCP Tool <span class="tool-name-highlight">${tool.name}</span> Help`;
    }

    // Show FULL tool description directly (no wrapper, no nested box)

    const description = tool.description_full || tool.description || 'No description available';
    responseContent.innerHTML = '<pre class="help-description">' + description + '</pre>';
}

// Export for global access
window.executeTool = executeTool;
window.showToolHelp = showToolHelp;
window.highlightBash = highlightBash;
window.saveCursorPosition = saveCursorPosition;
window.restoreCursorPosition = restoreCursorPosition;
