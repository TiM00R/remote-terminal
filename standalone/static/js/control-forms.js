// Control Forms - Dynamic form generation from tool schemas

function generateForm(tool) {
    const form = document.getElementById('toolForm');
    form.innerHTML = '';
    
    // Remove any existing submit handler by cloning the form element
    const newForm = form.cloneNode(false);
    form.parentNode.replaceChild(newForm, form);
    
    // Re-reference the new form element
    const freshForm = document.getElementById('toolForm');
    
    if (!tool.arguments || tool.arguments.length === 0) {
        // No arguments - just show execute button
        // Add button container (split row 50/50)
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'button-container';
        
        // Execute button (left side)
        const executeBtn = document.createElement('button');
        executeBtn.type = 'submit';
        executeBtn.className = 'btn-execute';
        executeBtn.textContent = `▶️ Execute ${tool.name}`;
        buttonContainer.appendChild(executeBtn);
        
        // Help button (right side)
        const helpBtn = document.createElement('button');
        helpBtn.type = 'button';
        helpBtn.className = 'btn-help';
        helpBtn.textContent = `❓ Help`;
        helpBtn.addEventListener('click', () => showToolHelp(tool));
        buttonContainer.appendChild(helpBtn);
        
        freshForm.appendChild(buttonContainer);
        
        // Add submit handler to fresh form
        freshForm.addEventListener('submit', (e) => {
            e.preventDefault();
            executeTool(tool);
        });
        return;
    }
    
    // Check if this is a special tool requiring dynamic behavior
    if (tool.special === 'dynamic_server_update') {
        generateDynamicServerUpdateForm(freshForm, tool);
        return;
    }
    
    if (tool.special === 'dynamic_server_select') {
        generateDynamicServerSelectForm(freshForm, tool);
        return;
    }
    
    if (tool.special === 'update_recipe_form') {
        generateUpdateRecipeForm(freshForm, tool);
        return;
    }
    
    // Generate fields
    tool.arguments.forEach(arg => {
        const field = createFormField(arg, tool);
        freshForm.appendChild(field);
    });
    
    // Add button container (split row 50/50)
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'button-container';
    
    // Execute button (left side)
    const executeBtn = document.createElement('button');
    executeBtn.type = 'submit';
    executeBtn.className = 'btn-execute';
    executeBtn.textContent = `▶️ Execute ${tool.name}`;
    buttonContainer.appendChild(executeBtn);
    
    // Help button (right side)
    const helpBtn = document.createElement('button');
    helpBtn.type = 'button';
    helpBtn.className = 'btn-help';
    helpBtn.textContent = `❓ Help`;
    helpBtn.addEventListener('click', () => showToolHelp(tool));
    buttonContainer.appendChild(helpBtn);
    
    freshForm.appendChild(buttonContainer);
    
    // Add submit handler to fresh form (only once!)
    freshForm.addEventListener('submit', (e) => {
        e.preventDefault();
        executeTool(tool);
    });
}

async function generateUpdateRecipeForm(form, tool) {
    console.log('[generateUpdateRecipeForm] Starting form generation');
    
    const recipes = window.controlMain.getCachedRecipes();
    console.log('[generateUpdateRecipeForm] Got recipes:', recipes);
    
    if (!recipes || recipes.length === 0) {
        console.error('[generateUpdateRecipeForm] No recipes available!');
        form.innerHTML = '<div class="error">No recipes available. Please create a recipe first.</div>';
        return;
    }
    
    console.log('[generateUpdateRecipeForm] Building form with', recipes.length, 'recipes');
    
    // Create recipe selection dropdown
    const selectGroup = document.createElement('div');
    selectGroup.className = 'form-group';
    
    const selectLabel = document.createElement('label');
    selectLabel.textContent = 'Select Recipe to Update';
    selectLabel.classList.add('required');
    selectLabel.htmlFor = 'recipe_id';
    selectGroup.appendChild(selectLabel);
    
    const select = document.createElement('select');
    select.id = 'recipe_id';
    select.name = 'recipe_id';
    select.required = true;
    
    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = 'Choose a recipe...';
    select.appendChild(placeholderOpt);
    
    recipes.forEach(recipe => {
        const option = document.createElement('option');
        option.value = recipe.id;
        option.textContent = `${recipe.id} - ${recipe.name}`;
        option.dataset.recipeId = recipe.id;
        select.appendChild(option);
    });
    
    selectGroup.appendChild(select);
    form.appendChild(selectGroup);
    
    // Create other fields (initially empty and enabled for editing)
    const formFields = {};
    
    // Name field
    const nameGroup = document.createElement('div');
    nameGroup.className = 'form-group';
    const nameLabel = document.createElement('label');
    nameLabel.textContent = 'Recipe Name';
    nameLabel.htmlFor = 'name';
    nameGroup.appendChild(nameLabel);
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.id = 'name';
    nameInput.name = 'name';
    nameInput.placeholder = 'docker_diagnostics_v2';
    nameGroup.appendChild(nameInput);
    form.appendChild(nameGroup);
    formFields.name = nameInput;
    
    // Description field
    const descGroup = document.createElement('div');
    descGroup.className = 'form-group';
    const descLabel = document.createElement('label');
    descLabel.textContent = 'Description';
    descLabel.htmlFor = 'description';
    descGroup.appendChild(descLabel);
    const descInput = document.createElement('textarea');
    descInput.id = 'description';
    descInput.name = 'description';
    descInput.rows = 3;
    descGroup.appendChild(descInput);
    form.appendChild(descGroup);
    formFields.description = descInput;
    
    // Commands field
    const cmdsGroup = document.createElement('div');
    cmdsGroup.className = 'form-group';
    const cmdsLabel = document.createElement('label');
    cmdsLabel.textContent = 'Commands JSON (replaces all)';
    cmdsLabel.htmlFor = 'commands';
    cmdsGroup.appendChild(cmdsLabel);

    const cmdsInput = document.createElement('pre');
    cmdsInput.id = 'commands';
    cmdsInput.contentEditable = 'true';
    cmdsInput.className = 'json-editor';
    cmdsInput.innerHTML = '<span style="color: #6e7681; font-style: italic;">[{"sequence": 1, "command": "ls -la"}]</span>';
    cmdsGroup.appendChild(cmdsInput);
    form.appendChild(cmdsGroup);
    formFields.commands = cmdsInput;
    
    // Prerequisites field
    const preqGroup = document.createElement('div');
    preqGroup.className = 'form-group';
    const preqLabel = document.createElement('label');
    preqLabel.textContent = 'Prerequisites';
    preqLabel.htmlFor = 'prerequisites';
    preqGroup.appendChild(preqLabel);
    const preqInput = document.createElement('input');
    preqInput.type = 'text';
    preqInput.id = 'prerequisites';
    preqInput.name = 'prerequisites';
    preqGroup.appendChild(preqInput);
    form.appendChild(preqGroup);
    formFields.prerequisites = preqInput;
    
    // Success criteria field
    const succGroup = document.createElement('div');
    succGroup.className = 'form-group';
    const succLabel = document.createElement('label');
    succLabel.textContent = 'Success Criteria';
    succLabel.htmlFor = 'success_criteria';
    succGroup.appendChild(succLabel);
    const succInput = document.createElement('input');
    succInput.type = 'text';
    succInput.id = 'success_criteria';
    succInput.name = 'success_criteria';
    succGroup.appendChild(succInput);
    form.appendChild(succGroup);
    formFields.success_criteria = succInput;
    
    // Add button container (split row 50/50)
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'button-container';
    
    // Execute button (left side)
    const executeBtn = document.createElement('button');
    executeBtn.type = 'submit';
    executeBtn.className = 'btn-execute';
    executeBtn.textContent = `▶️ Execute ${tool.name}`;
    buttonContainer.appendChild(executeBtn);
    
    // Help button (right side)
    const helpBtn = document.createElement('button');
    helpBtn.type = 'button';
    helpBtn.className = 'btn-help';
    helpBtn.textContent = `❓ Help`;
    helpBtn.addEventListener('click', () => showToolHelp(tool));
    buttonContainer.appendChild(helpBtn);
    
    form.appendChild(buttonContainer);
    
    // Handle recipe selection change - auto-populate fields
    select.addEventListener('change', async () => {
        const selectedRecipeId = select.value;
        
        if (!selectedRecipeId) {
            // Clear all fields
            formFields.name.value = '';
            formFields.description.value = '';
            formFields.commands.value = '';
            formFields.prerequisites.value = '';
            formFields.success_criteria.value = '';
            return;
        }
        
        // Fetch full recipe details
        try {
            const response = await fetch('http://localhost:8081/execute_mcp_tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool: 'get_recipe',
                    arguments: { recipe_id: parseInt(selectedRecipeId) }
                })
            });
            
            const recipe = await response.json();
            console.log('[Recipe Selection] API response:', recipe);

            // The execute_mcp_tool endpoint returns the recipe data directly
            if (recipe.error) {
                alert(`Failed to load recipe details: ${recipe.error}`);
                return;
            }

            if (recipe.id) {                
                // Populate all fields
                formFields.name.value = recipe.name || '';
                formFields.description.value = recipe.description || '';
                
                // Format commands as pretty JSON
                

                if (recipe.command_sequence && Array.isArray(recipe.command_sequence)) {
                    const json = JSON.stringify(recipe.command_sequence, null, 2);
                    const highlighted = json
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
                        .replace(/: (\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
                        .replace(/: (true|false)/g, ': <span class="json-boolean">$1</span>')
                        .replace(/: null/g, ': <span class="json-null">null</span>')
                        .replace(/: "([^"]*)"/g, ': <span class="json-string">"$1"</span>');
                    formFields.commands.innerHTML = highlighted;
                } else {
                    formFields.commands.value = '';
                }
                
                formFields.prerequisites.value = recipe.prerequisites || '';
                formFields.success_criteria.value = recipe.success_criteria || '';
                
                console.log('Auto-populated recipe fields:', recipe.name);
            } else {
                alert(`Failed to load recipe details: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            alert(`Error loading recipe: ${error.toString()}`);
        }
    });
    
    // Add submit handler
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        executeTool(tool);
    });
    
    console.log('[generateUpdateRecipeForm] Form generation complete');
}

async function generateDynamicServerSelectForm(form, tool) {
    // Fetch server list
    try {
        const response = await fetch('http://localhost:8081/api/list_servers');
        const data = await response.json();
        const servers = data.servers || [];
        
        // Create server selection dropdown
        const selectGroup = document.createElement('div');
        selectGroup.className = 'form-group';
        
        const selectLabel = document.createElement('label');
        selectLabel.textContent = 'Select Default Server';
        selectLabel.classList.add('required');
        selectLabel.htmlFor = 'identifier';
        selectGroup.appendChild(selectLabel);
        
        const select = document.createElement('select');
        select.id = 'identifier';
        select.name = 'identifier';
        select.required = true;
        
        const placeholderOpt = document.createElement('option');
        placeholderOpt.value = '';
        placeholderOpt.textContent = 'Choose a server...';
        select.appendChild(placeholderOpt);
        
        servers.forEach(srv => {
            const option = document.createElement('option');
            option.value = srv.name;
            option.textContent = `${srv.name} (${srv.user}@${srv.host}:${srv.port})`;
            select.appendChild(option);
        });
        
        selectGroup.appendChild(select);
        form.appendChild(selectGroup);
        
        // Add button container (split row 50/50)
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'button-container';
        
        // Execute button (left side)
        const executeBtn = document.createElement('button');
        executeBtn.type = 'submit';
        executeBtn.className = 'btn-execute';
        executeBtn.textContent = `▶️ Execute ${tool.name}`;
        buttonContainer.appendChild(executeBtn);
        
        // Help button (right side)
        const helpBtn = document.createElement('button');
        helpBtn.type = 'button';
        helpBtn.className = 'btn-help';
        helpBtn.textContent = `❓ Help`;
        helpBtn.addEventListener('click', () => showToolHelp(tool));
        buttonContainer.appendChild(helpBtn);
        
        form.appendChild(buttonContainer);
        
        // Enable execute button when server is selected
        select.addEventListener('change', () => {
            executeBtn.disabled = !select.value;
        });


        
        // Add submit handler
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            executeTool(tool);
        });
        
    } catch (error) {
        form.innerHTML = `<div class="error">Failed to load servers: ${error}</div>`;
    }
}

async function generateDynamicServerUpdateForm(form, tool) {
    // Fetch server list
    try {
        const response = await fetch('http://localhost:8081/api/list_servers');
        const data = await response.json();
        const servers = data.servers || [];
        
        // Create server selection dropdown
        const selectGroup = document.createElement('div');
        selectGroup.className = 'form-group';
        
        const selectLabel = document.createElement('label');
        selectLabel.textContent = 'Select Server to Update';
        selectLabel.classList.add('required');
        selectLabel.htmlFor = 'identifier';
        selectGroup.appendChild(selectLabel);
        
        const select = document.createElement('select');
        select.id = 'identifier';
        select.name = 'identifier';
        select.required = true;
        
        const placeholderOpt = document.createElement('option');
        placeholderOpt.value = '';
        placeholderOpt.textContent = 'Choose a server...';
        select.appendChild(placeholderOpt);
        
        servers.forEach(srv => {
            const option = document.createElement('option');
            option.value = srv.name;
            option.textContent = `${srv.name} (${srv.user}@${srv.host}:${srv.port})`;
            option.dataset.serverData = JSON.stringify(srv);
            select.appendChild(option);
        });
        
        selectGroup.appendChild(select);
        form.appendChild(selectGroup);
        select.addEventListener('change', () => {
            executeBtn.disabled = !select.value; // Enable if value selected
        });
        // Create other fields (initially disabled)
        const fieldConfigs = [
            { name: 'name', label: 'Server Name', type: 'text' },
            { name: 'host', label: 'Host', type: 'text' },
            { name: 'user', label: 'Username', type: 'text' },
            { name: 'password', label: 'Password', type: 'text' },
            { name: 'port', label: 'Port', type: 'number', min: 1, max: 65535 },
            { name: 'description', label: 'Description', type: 'text' },
            { name: 'tags', label: 'Tags (comma-separated)', type: 'text' }
        ];
        
        const formFields = {};
        fieldConfigs.forEach(config => {
            const group = document.createElement('div');
            group.className = 'form-group';
            
            const label = document.createElement('label');
            label.textContent = config.label;
            label.htmlFor = config.name;
            group.appendChild(label);
            
            const input = document.createElement('input');
            input.type = config.type;
            input.id = config.name;
            input.name = config.name;
            input.disabled = true; // Disabled until server selected
            if (config.min) input.min = config.min;
            if (config.max) input.max = config.max;
            
            group.appendChild(input);
            form.appendChild(group);
            
            formFields[config.name] = input;
        });
        
        
        // Add button container (split row 50/50)
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'button-container';

        // Execute button (left side)
        const executeBtn = document.createElement('button');
        executeBtn.type = 'submit';
        executeBtn.className = 'btn-execute';
        executeBtn.textContent = `▶️ Execute ${tool.name}`;
        executeBtn.disabled = true; // Disabled until server selected
        buttonContainer.appendChild(executeBtn);

        // Help button (right side)
        const helpBtn = document.createElement('button');
        helpBtn.type = 'button';
        helpBtn.className = 'btn-help';
        helpBtn.textContent = `❓ Help`;
        helpBtn.addEventListener('click', () => showToolHelp(tool));
        buttonContainer.appendChild(helpBtn);

        form.appendChild(buttonContainer);



        // Handle server selection change
        select.addEventListener('change', () => {
            const selectedOption = select.options[select.selectedIndex];
            
            if (!selectedOption.dataset.serverData) {
                // Placeholder selected - disable fields
                Object.values(formFields).forEach(input => input.disabled = true);
                executeBtn.disabled = true;
                return;
            }
            
            // Parse server data and populate fields
            const serverData = JSON.parse(selectedOption.dataset.serverData);
            
            formFields.name.value = serverData.name;
            formFields.host.value = serverData.host;
            formFields.user.value = serverData.user;
            formFields.password.value = ''; // Don't populate password for security
            formFields.port.value = serverData.port;
            formFields.description.value = serverData.description || '';
            formFields.tags.value = serverData.tags ? serverData.tags.join(', ') : '';
            
            // Enable fields
            Object.values(formFields).forEach(input => input.disabled = false);
            executeBtn.disabled = false;
        });
        
        // Add submit handler
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            executeTool(tool);
        });
        
    } catch (error) {
        form.innerHTML = `<div class="error">Failed to load servers: ${error}</div>`;
    }
}


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
                                contentField.innerHTML = highlightBash(text);
                                
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
                const cursorPos = saveCursorPosition(this);
                this.innerHTML = highlightBash(this.textContent);
                restoreCursorPosition(this, cursorPos);
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
    showLoading();
    
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
        displayResponse(result);
        
    } catch (error) {
        displayError(error.toString());
    } finally {
        executeBtn.disabled = false;
        executeBtn.textContent = `▶️ Execute ${tool.name}`;
    }
}

// Bash syntax highlighting helper
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
window.generateForm = generateForm;
window.executeTool = executeTool;
window.showToolHelp = showToolHelp;
