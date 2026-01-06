// Control Forms Fields - Field creation functions for different input types

function createScriptSelectField(arg) {
    const select = document.createElement('select');
    select.id = arg.name;
    select.name = arg.name;
    if (!arg.required) select.required = false;

    select.innerHTML = '<option value="">Loading scripts...</option>';
    select.disabled = true;

    window.controlMain.getBatchScripts().then(scripts => {
        select.disabled = false;

        if (!scripts || scripts.length === 0) {
            select.innerHTML = '<option value="">No scripts available</option>';
            return;
        }

        select.innerHTML = arg.required ? '' : '<option value="">-- Select Script --</option>';

        scripts.forEach(script => {
            const option = document.createElement('option');
            option.value = script.id;
            let desc = script.description || 'No description';
            if (desc.length > 60) {
                desc = desc.substring(0, 60).trim() + '...';
            }
            option.textContent = `${script.id} - ${desc}`;
            select.appendChild(option);
        });

        // ADD THIS: Auto-load script content for save_batch_script tool
        if (arg.name === 'script_id') {
            select.addEventListener('change', async () => {
                const scriptId = select.value;
                if (!scriptId) return;

                // Fetch script content
                try {
                    const response = await fetch('http://localhost:8081/execute_mcp_tool', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            tool: 'get_batch_script',
                            arguments: { script_id: parseInt(scriptId) }
                        })
                    });

                    const result = await response.json();
                    console.log('Script fetch result:', result);

                    // Extract content from response
                    if (result.result && typeof result.result === 'string') {
                        // Parse the text response to extract script content
                        const lines = result.result.split('\n');
                        let inScript = false;
                        let scriptContent = [];

                        for (const line of lines) {
                            if (line === '```bash') {
                                inScript = true;
                                continue;
                            }
                            if (line === '```') {
                                inScript = false;
                                break;
                            }
                            if (inScript) {
                                scriptContent.push(line);
                            }
                        }

                        // Populate the content textarea
                        const contentField = document.getElementById('content');

                        // Populate the content textarea
                        if (contentField) {
                            const text = scriptContent.join('\n');

                            // Check if it's a contentEditable element or regular textarea
                            if (contentField.contentEditable === 'true') {
                                // Temporarily remove input handler to prevent double-highlighting
                                if (contentField._inputHandler) {
                                    contentField.removeEventListener('input', contentField._inputHandler);
                                }

                                // Set the content with highlighting
                                contentField.textContent = text;
                                contentField.innerHTML = window.highlightBash(text);

                                // Re-attach the input handler
                                if (contentField._inputHandler) {
                                    contentField.addEventListener('input', contentField._inputHandler);
                                }
                            } else {
                                contentField.value = text;
                            }
                        }

                        // ALSO populate description field
                        const descriptionField = document.getElementById('description');
                        if (descriptionField) {
                            // Extract description from response
                            for (const line of lines) {
                                if (line.trim().startsWith('Description: ')) {
                                    const desc = line.trim().substring(13); // Remove "Description: " prefix
                                    descriptionField.value = desc;
                                    break;
                                }
                            }
                        }
                    }

                } catch (error) {
                    console.error('Error fetching script:', error);
                    alert('Failed to load script content');
                }
            });
        }

    }).catch(error => {
        console.error('Error loading batch scripts:', error);
        select.disabled = false;
        select.innerHTML = '<option value="">Error loading scripts</option>';
    });

    return select;
}


function createFormField(arg, tool) {
    const group = document.createElement('div');
    group.className = 'form-group';

    if (arg.type === 'checkbox') {
        return createCheckboxField(arg);
    } else if (arg.type === 'array') {
        return createArrayField(arg);
    } else if (arg.type === 'server_select' || arg.type === 'server_select_simple') {
        return createServerSelectField(arg);
    } else if (arg.type === 'file_picker' || arg.type === 'folder_picker') {
        return createFilePickerField(arg);
    } else if (arg.type === 'recipe_select') {
        return createRecipeSelectField(arg);
    } else if (arg.type === 'conversation_select') {
        return createConversationSelectField(arg);
    } else if (arg.type === 'command_select') {
        return createCommandSelectField(arg);
    } else if (arg.type === 'script_select') {
        return createScriptSelectField(arg);
    }

    // Label
    const label = document.createElement('label');
    label.textContent = arg.label;
    label.htmlFor = arg.name;
    if (arg.required) {
        label.classList.add('required');
    }
    group.appendChild(label);

    // Input based on type
    let input;

    if (arg.type === 'text') {
        input = document.createElement('input');
        input.type = 'text';
        input.id = arg.name;
        input.name = arg.name;
        input.placeholder = arg.placeholder || '';
        if (arg.default) input.value = arg.default;
    } else if (arg.type === 'number') {
        input = document.createElement('input');
        input.type = 'number';
        input.id = arg.name;
        input.name = arg.name;
        if (arg.default !== undefined) input.value = arg.default;
        if (arg.min !== undefined) input.min = arg.min;
        if (arg.max !== undefined) input.max = arg.max;
        input.placeholder = arg.placeholder || '';
    } else if (arg.type === 'select') {
        input = document.createElement('select');
        input.id = arg.name;
        input.name = arg.name;

        arg.options.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt === 'all' ? '' : opt;
            option.textContent = opt;
            if (arg.default === opt) option.selected = true;
            input.appendChild(option);
        });
    }  else if (arg.type === 'textarea') {
        // Special handling for script content fields - use syntax highlighting
        if (arg.name === 'content' || arg.name === 'script_content') {
            input = document.createElement('pre');
            input.id = arg.name;
            input.contentEditable = 'true';
            input.className = 'bash-editor';
            input.style.minHeight = (arg.rows || 15) * 1.5 + 'em';
            input.innerHTML = arg.placeholder ? `<span style="color: #666; font-style: italic;">${arg.placeholder}</span>` : '';

            // Clear placeholder on focus
            input.addEventListener('focus', function() {
                if (this.innerHTML.includes('font-style: italic')) {
                    this.innerHTML = '';
                }
            });

            // Apply syntax highlighting on input
            const inputHandler = function() {
                const cursorPos = window.saveCursorPosition(this);
                this.innerHTML = window.highlightBash(this.textContent);
                window.restoreCursorPosition(this, cursorPos);
            };
            input._inputHandler = inputHandler;
            input.addEventListener('input', inputHandler);


        } else {
            input = document.createElement('textarea');
            input.id = arg.name;
            input.name = arg.name;
            input.rows = arg.rows || 5;
            input.placeholder = arg.placeholder || '';
            if (arg.default) input.value = arg.default;
        }
    }

    if (arg.required) {
        input.required = true;
    }

    group.appendChild(input);
    return group;
}

function createFilePickerField(arg) {
    const group = document.createElement('div');
    group.className = 'form-group';

    // Label
    const label = document.createElement('label');
    label.textContent = arg.label;
    label.htmlFor = arg.name;
    if (arg.required) {
        label.classList.add('required');
    }
    group.appendChild(label);

    // Container for input + button
    const inputContainer = document.createElement('div');
    inputContainer.style.display = 'flex';
    inputContainer.style.gap = '8px';

    // Text input for the full path
    const input = document.createElement('input');
    input.type = 'text';
    input.id = arg.name;
    input.name = arg.name;
    input.placeholder = arg.placeholder || '';
    input.style.flex = '1';
    if (arg.required) input.required = true;

    // Hidden file/folder input for picker
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.style.display = 'none';

    if (arg.type === 'folder_picker') {
        fileInput.setAttribute('webkitdirectory', '');
        fileInput.setAttribute('directory', '');
    }

    // Browse button
    const browseBtn = document.createElement('button');
    browseBtn.type = 'button';
    browseBtn.textContent = '📁 Browse';
    browseBtn.className = 'btn-browse';
    browseBtn.style.padding = '8px 16px';
    browseBtn.style.cursor = 'pointer';
    browseBtn.style.whiteSpace = 'nowrap';

    // Handle browse button click
    browseBtn.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle file/folder selection - JUST GET THE FILENAME
    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            const file = e.target.files[0];

            // Just put the filename in the input
            if (arg.type === 'folder_picker') {
                // For folders, extract folder name
                const path = file.webkitRelativePath || file.name;
                const parts = path.split('/');
                input.value = parts.length > 1 ? parts[0] : path;
            } else {
                // For files, just the filename
                input.value = file.name;
            }

            // Focus the input so user can add the full path
            input.focus();
            input.select();
        }
    });

    inputContainer.appendChild(input);
    inputContainer.appendChild(browseBtn);
    inputContainer.appendChild(fileInput);
    group.appendChild(inputContainer);

    return group;
}

function createServerSelectField(arg) {
    // This is handled by dynamic form generators
    // But included here for completeness
    const group = document.createElement('div');
    group.className = 'form-group';
    group.innerHTML = '<p>Loading servers...</p>';
    return group;
}

function createRecipeSelectField(arg) {
    const group = document.createElement('div');
    group.className = 'form-group';

    const label = document.createElement('label');
    label.textContent = arg.label;
    label.htmlFor = arg.name;
    if (arg.required) {
        label.classList.add('required');
    }
    group.appendChild(label);

    const recipes = window.controlMain.getCachedRecipes();

    const select = document.createElement('select');
    select.id = arg.name;
    select.name = arg.name;
    if (arg.required) select.required = true;

    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = 'Choose a recipe...';
    select.appendChild(placeholderOpt);

    if (recipes && recipes.length > 0) {
        recipes.forEach(recipe => {
            const option = document.createElement('option');
            option.value = recipe.id;
            option.textContent = `${recipe.id} - ${recipe.name}`;
            select.appendChild(option);
        });
    } else {
        const noRecipesOpt = document.createElement('option');
        noRecipesOpt.value = '';
        noRecipesOpt.textContent = 'No recipes available';
        noRecipesOpt.disabled = true;
        select.appendChild(noRecipesOpt);
    }

    group.appendChild(select);
    return group;
}

function createConversationSelectField(arg) {
    const group = document.createElement('div');
    group.className = 'form-group';

    const label = document.createElement('label');
    label.textContent = arg.label;
    label.htmlFor = arg.name;
    if (arg.required) {
        label.classList.add('required');
    }
    group.appendChild(label);

    const conversations = window.controlMain.getCachedConversations();

    const select = document.createElement('select');
    select.id = arg.name;
    select.name = arg.name;
    if (arg.required) select.required = true;

    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = 'Choose a conversation...';
    select.appendChild(placeholderOpt);

    if (conversations && conversations.length > 0) {
        conversations.forEach(conv => {
            const option = document.createElement('option');
            option.value = conv.id;
            const statusIcon = conv.status === 'in_progress' ? '🔄' :
                              conv.status === 'success' ? '✓' :
                              conv.status === 'failed' ? '✗' : '';
            option.textContent = `${conv.id} - ${conv.goal_summary} ${statusIcon}`;
            select.appendChild(option);
        });
    } else {
        const noConvOpt = document.createElement('option');
        noConvOpt.value = '';
        noConvOpt.textContent = 'No conversations available';
        noConvOpt.disabled = true;
        select.appendChild(noConvOpt);
    }

    group.appendChild(select);
    return group;
}


function createCommandSelectField(arg) {
    const group = document.createElement('div');
    group.className = 'form-group';

    const label = document.createElement('label');
    label.textContent = arg.label;
    label.htmlFor = arg.name;
    if (arg.required) {
        label.classList.add('required');
    }
    group.appendChild(label);

    // Create select with loading message
    const select = document.createElement('select');
    select.id = arg.name;
    select.name = arg.name;
    if (arg.required) select.required = true;
    select.disabled = true; // Disabled while loading

    const loadingOpt = document.createElement('option');
    loadingOpt.value = '';
    loadingOpt.textContent = 'Loading commands...';
    select.appendChild(loadingOpt);

    group.appendChild(select);

    // Load session commands asynchronously
    window.controlMain.getSessionCommands().then(commands => {
        select.innerHTML = ''; // Clear loading message

        const placeholderOpt = document.createElement('option');
        placeholderOpt.value = '';
        placeholderOpt.textContent = 'Choose a command...';
        select.appendChild(placeholderOpt);

        if (commands && commands.length > 0) {
            commands.forEach(cmd => {
                const option = document.createElement('option');
                option.value = cmd.command_id;
                const statusIcon = cmd.status === 'running' ? '🔄' :
                                  cmd.status === 'completed' ? '✓' :
                                  cmd.status === 'killed' ? '✗' : '';
                // Truncate command at 60 chars, trim whitespace
                const cmdText = cmd.command.trim().substring(0, 60);
                const truncated = cmd.command.length > 60 ? '...' : '';
                option.textContent = `${statusIcon} ${cmd.command_id} - ${cmdText}${truncated}`;
                select.appendChild(option);
            });
        } else {
            const noCommandsOpt = document.createElement('option');
            noCommandsOpt.value = '';
            noCommandsOpt.textContent = 'No commands in session';
            noCommandsOpt.disabled = true;
            select.appendChild(noCommandsOpt);
        }

        select.disabled = false; // Enable after loading
    }).catch(error => {
        console.error('Failed to load session commands:', error);
        select.innerHTML = '';
        const errorOpt = document.createElement('option');
        errorOpt.value = '';
        errorOpt.textContent = 'Error loading commands';
        errorOpt.disabled = true;
        select.appendChild(errorOpt);
        select.disabled = true;
    });

    return group;
}


function createCheckboxField(arg) {
    const group = document.createElement('div');
    group.className = 'checkbox-group';

    const input = document.createElement('input');
    input.type = 'checkbox';
    input.id = arg.name;
    input.name = arg.name;
    if (arg.default) input.checked = true;

    const label = document.createElement('label');
    label.htmlFor = arg.name;
    label.textContent = arg.label;

    group.appendChild(input);
    group.appendChild(label);

    return group;
}

function createArrayField(arg) {
    const group = document.createElement('div');
    group.className = 'form-group';

    const label = document.createElement('label');
    label.textContent = arg.label;
    if (arg.required) label.classList.add('required');
    group.appendChild(label);

    const arrayContainer = document.createElement('div');
    arrayContainer.className = 'array-field';
    arrayContainer.dataset.name = arg.name;

    const itemsContainer = document.createElement('div');
    itemsContainer.className = 'array-items';
    arrayContainer.appendChild(itemsContainer);

    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'btn-add-item';
    addBtn.textContent = '+ Add Item';
    addBtn.addEventListener('click', () => addArrayItem(itemsContainer, arg.item_fields));
    arrayContainer.appendChild(addBtn);

    group.appendChild(arrayContainer);

    // Add one initial item
    if (arg.required) {
        addArrayItem(itemsContainer, arg.item_fields);
    }

    return group;
}

function addArrayItem(container, itemFields) {
    const item = document.createElement('div');
    item.className = 'array-item';

    itemFields.forEach(field => {
        const fieldGroup = document.createElement('div');
        fieldGroup.className = 'array-item-field';

        const label = document.createElement('label');
        label.textContent = field.label;
        fieldGroup.appendChild(label);

        const input = document.createElement('input');
        input.type = 'text';
        input.name = field.name;
        input.placeholder = field.placeholder || '';
        fieldGroup.appendChild(input);

        item.appendChild(fieldGroup);
    });

    // Remove button
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn-remove-item';
    removeBtn.textContent = '✕';
    removeBtn.addEventListener('click', () => item.remove());
    item.appendChild(removeBtn);

    container.appendChild(item);
}

// Export for global access
window.createFormField = createFormField;
