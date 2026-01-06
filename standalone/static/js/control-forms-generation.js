// Control Forms Generation - Main form generators for different tool types

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
        helpBtn.addEventListener('click', () => window.showToolHelp(tool));
        buttonContainer.appendChild(helpBtn);

        freshForm.appendChild(buttonContainer);

        // Add submit handler to fresh form
        freshForm.addEventListener('submit', (e) => {
            e.preventDefault();
            window.executeTool(tool);
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
        const field = window.createFormField(arg, tool);
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
    helpBtn.addEventListener('click', () => window.showToolHelp(tool));
    buttonContainer.appendChild(helpBtn);

    freshForm.appendChild(buttonContainer);

    // Add submit handler to fresh form (only once!)
    freshForm.addEventListener('submit', (e) => {
        e.preventDefault();
        window.executeTool(tool);
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
    helpBtn.addEventListener('click', () => window.showToolHelp(tool));
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
        window.executeTool(tool);
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
        helpBtn.addEventListener('click', () => window.showToolHelp(tool));
        buttonContainer.appendChild(helpBtn);

        form.appendChild(buttonContainer);

        // Enable execute button when server is selected
        select.addEventListener('change', () => {
            executeBtn.disabled = !select.value;
        });



        // Add submit handler
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            window.executeTool(tool);
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
        helpBtn.addEventListener('click', () => window.showToolHelp(tool));
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
            window.executeTool(tool);
        });

    } catch (error) {
        form.innerHTML = `<div class="error">Failed to load servers: ${error}</div>`;
    }
}

// Export for global access
window.generateForm = generateForm;
