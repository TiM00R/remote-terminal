// Control Main - Initialization and routing
const CATEGORIES = ['commands', 'file-transfer', 'batch', 'servers', 'workflows'];
const CATEGORY_NAMES = {
    'commands': 'Commands',
    'file-transfer': 'File Transfer',
    'batch': 'Batch Scripts',
    'servers': 'Servers',
    'workflows': 'Workflows'
};

let currentCategory = 'commands';
let currentTool = null;
let allToolSchemas = {};
let cachedRecipes = null; // Cache for recipes list
let cachedConversations = null; // Cache for conversations list

// Initialize on page load
async function init() {
    console.log('Initializing MCP Control Panel...');
    
    // Load all tool schemas
    await loadAllSchemas();
    
    // Initialize categories
    initializeCategories();
    
    // Load first category
    await loadCategory('commands');
    
    // Load server list for server selector
    await loadServers();
    
    // Check connection periodically
    checkConnection();
    
    console.log('Initialization complete');
}

// Load all tool schemas from JSON files
async function loadAllSchemas() {
    for (const category of CATEGORIES) {
        try {
            const response = await fetch(`/static/tool-schemas/${category}.json`);
            const data = await response.json();
            allToolSchemas[category] = data;
            console.log(`Loaded schema for ${category}:`, data.tools.length, 'tools');
        } catch (error) {
            console.error(`Failed to load schema for ${category}:`, error);
        }
    }
}

// Initialize category tabs
function initializeCategories() {
    const tabsContainer = document.getElementById('categoryTabs');
    
    CATEGORIES.forEach(category => {
        const tab = document.createElement('button');
        tab.className = 'category-tab';
        tab.dataset.category = category;
        tab.textContent = CATEGORY_NAMES[category];
        
        if (category === currentCategory) {
            tab.classList.add('active');
        }
        
        tab.addEventListener('click', () => switchCategory(category));
        tabsContainer.appendChild(tab);
    });
}

// Switch to different category
async function switchCategory(category) {
    if (category === currentCategory) return;
    
    currentCategory = category;
    
    // Update active tab
    document.querySelectorAll('.category-tab').forEach(tab => {
        if (tab.dataset.category === category) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    // Load category tools
    await loadCategory(category);
}

// Load tools for category
async function loadCategory(category) {
    const schema = allToolSchemas[category];
    if (!schema) {
        console.error('No schema for category:', category);
        return;
    }
    
    // Populate tool dropdown
    const toolSelect = document.getElementById('toolSelect');
    toolSelect.innerHTML = '<option value="">Select a tool...</option>';
    
    schema.tools.forEach(tool => {
        const option = document.createElement('option');
        option.value = tool.name;
        option.textContent = tool.name;
        toolSelect.appendChild(option);
    });
    
    // Clear form
    document.getElementById('toolForm').innerHTML = '';
    document.getElementById('toolDescription').textContent = 'Select a tool to begin';
    
    // Reset current tool
    currentTool = null;
    
    // If switching to workflows, clear caches to force fresh load
    if (category === 'workflows') {
        cachedRecipes = null;
        cachedConversations = null;
        console.log('Switched to workflows - caches cleared');
    }
}

// Load recipes for workflows tab
async function loadRecipes() {
    if (cachedRecipes !== null) {
        console.log('Using cached recipes:', cachedRecipes.length);
        return cachedRecipes; // Return cached data
    }
    
    console.log('Loading recipes from server...');
    try {
        const response = await fetch('http://localhost:8081/execute_mcp_tool', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tool: 'list_recipes',
                arguments: { limit: 200 }
            })
        });
        
        const data = await response.json();
        console.log('API Response:', data);
        
        // The execute_mcp_tool endpoint returns the parsed JSON directly:
        // {count: 1, recipes: [...]}
        // NOT wrapped in {success: true, result: {...}}
        
        if (data.recipes && Array.isArray(data.recipes)) {
            cachedRecipes = data.recipes;
            console.log('Loaded recipes:', cachedRecipes.length, 'recipes');
            return cachedRecipes;
        } else if (data.error) {
            console.error('API returned error:', data.error);
            cachedRecipes = [];
            return [];
        } else {
            console.error('Unexpected API response format:', data);
            cachedRecipes = [];
            return [];
        }
    } catch (error) {
        console.error('Error loading recipes:', error);
        cachedRecipes = []; // Cache empty array to prevent repeated failures
        return [];
    }
}

// Get cached recipes (for use in forms)
function getCachedRecipes() {
    console.log('getCachedRecipes called, cachedRecipes:', cachedRecipes);
    return cachedRecipes || [];
}

// Load conversations for workflows tab
async function loadConversations() {
    if (cachedConversations !== null) {
        console.log('Using cached conversations:', cachedConversations.length);
        return cachedConversations;
    }
    
    console.log('Loading conversations from server...');
    try {
        const response = await fetch('http://localhost:8081/execute_mcp_tool', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tool: 'list_conversations',
                arguments: { limit: 200 }
            })
        });
        
        const data = await response.json();
        console.log('Conversations API Response:', data);
        
        if (data.conversations && Array.isArray(data.conversations)) {
            cachedConversations = data.conversations;
            console.log('Loaded conversations:', cachedConversations.length, 'conversations');
            return cachedConversations;
        } else if (data.error) {
            console.error('API returned error:', data.error);
            cachedConversations = [];
            return [];
        } else {
            console.error('Unexpected API response format:', data);
            cachedConversations = [];
            return [];
        }
    } catch (error) {
        console.error('Error loading conversations:', error);
        cachedConversations = [];
        return [];
    }
}

// Get cached conversations (for use in forms)
function getCachedConversations() {
    console.log('getCachedConversations called, cachedConversations:', cachedConversations);
    return cachedConversations || [];
}

// Load session commands for command_select fields
async function loadSessionCommands() {
    console.log('Loading session commands...');
    try {
        const response = await fetch('http://localhost:8081/execute_mcp_tool', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tool: 'list_session_commands',
                arguments: {}
            })
        });
        
        const data = await response.json();
        console.log('Session Commands API Response:', data);
        
        if (data.commands && Array.isArray(data.commands)) {
            console.log('Loaded session commands:', data.commands.length, 'commands');
            return data.commands;
        } else if (data.error) {
            console.error('API returned error:', data.error);
            return [];
        } else {
            console.error('Unexpected API response format:', data);
            return [];
        }
    } catch (error) {
        console.error('Error loading session commands:', error);
        return [];
    }
}

// Get session commands (non-cached, always fresh)
async function getSessionCommands() {
    return await loadSessionCommands();
}



// Load batch scripts for script_select fields
async function loadBatchScripts() {
    console.log('Loading batch scripts...');
    try {
        const response = await fetch('http://localhost:8081/execute_mcp_tool', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tool: 'list_batch_scripts',
                arguments: { limit: 200 }
            })
        });
        
        const data = await response.json();
        console.log('Batch Scripts API Response:', data);
        
        const scripts = [];
        
        // Extract text from wrapped response
        const text = data.result || data;
        
        if (typeof text === 'string') {
            const lines = text.split('\n');
            let currentScript = null;
            
            for (const line of lines) {
                if (line.startsWith('ID: ')) {
                    if (currentScript) scripts.push(currentScript);
                    currentScript = { id: parseInt(line.substring(4)) };
                } else if (currentScript && line.trim().startsWith('Description: ')) {
                    currentScript.description = line.trim().substring(13);
                }
            }
            if (currentScript) scripts.push(currentScript);
            
            console.log('Parsed batch scripts:', scripts.length, 'scripts');
        }
        // ADD THIS LINE: Sort numerically by ID
        scripts.sort((a, b) => a.id - b.id);
        return scripts;
    } catch (error) {
        console.error('Error loading batch scripts:', error);
        return [];
    }
}


async function getBatchScripts() {
    return await loadBatchScripts();
}


// Handle tool selection
async function handleToolSelection() {
    const toolName = document.getElementById('toolSelect').value;
    
    if (!toolName) {
        document.getElementById('toolForm').innerHTML = '';
        document.getElementById('toolDescription').textContent = 'Select a tool to begin';
        currentTool = null;
        return;
    }
    
    // Find tool in current category
    const schema = allToolSchemas[currentCategory];
    const tool = schema.tools.find(t => t.name === toolName);
    
    if (!tool) {
        console.error('Tool not found:', toolName);
        return;
    }
    
    currentTool = tool;
    
    // Update description
    document.getElementById('toolDescription').textContent = tool.description;
    
    // If in workflows category AND tool uses recipe_select or conversation_select, load them first
    const needsRecipes = tool.arguments && tool.arguments.some(arg => arg.type === 'recipe_select');
    const needsConversations = tool.arguments && tool.arguments.some(arg => arg.type === 'conversation_select');
    const needsCommands = tool.arguments && tool.arguments.some(arg => arg.type === 'command_select');
    
    if (currentCategory === 'workflows' && needsRecipes) {
        console.log('Tool needs recipes, loading...');
        await loadRecipes();
        console.log('Recipes loaded, generating form');
    }
    
    if (currentCategory === 'workflows' && needsConversations) {
        console.log('Tool needs conversations, loading...');
        await loadConversations();
        console.log('Conversations loaded, generating form');
    }
    
    // Commands tab - load session commands if needed
    if (currentCategory === 'commands' && needsCommands) {
        console.log('Tool needs session commands, loading...');
        // Will be loaded fresh in createCommandSelectField
    }
    
    // Batch Scripts tab - load scripts if needed
    const needsScripts = tool.arguments && tool.arguments.some(arg => arg.type === 'script_select');
    if (currentCategory === 'batch' && needsScripts) {
        console.log('Tool needs batch scripts, loading...');
        // Will be loaded fresh in createScriptSelectField
    }

    // Generate form
    generateForm(tool);
}

// Load servers for server selector
async function loadServers() {
    try {
        const response = await fetch('http://localhost:8081/api/list_servers');
        const data = await response.json();
        const servers = data.servers || [];
        
        const select = document.getElementById('serverSelect');
        select.innerHTML = '';
        
        if (servers.length === 0) {
            select.innerHTML = '<option value="">No servers configured</option>';
            return;
        }
        
        servers.forEach(srv => {
            const option = document.createElement('option');
            option.value = srv.name;
            option.textContent = `${srv.name} (${srv.user}@${srv.host}:${srv.port})${srv.is_current ? ' [CURRENT]' : ''}`;
            if (srv.is_current) {
                option.selected = true;
            }
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load servers:', error);
    }
}

// Check connection status
async function checkConnection() {
    try {
        const response = await fetch('http://localhost:8081/api/connection_info');
        const data = await response.json();
        
        // Build info display
        let infoHtml = `<div style="color: #888;">${data.connection}</div>`;
        
        if (data.machine_id) {
            infoHtml += `<div class="info-line"><strong>Machine ID:</strong> ${data.machine_id}</div>`;
        }
        
        if (data.hostname) {
            infoHtml += `<div class="info-line"><strong>Hostname:</strong> ${data.hostname}</div>`;
        }
        
        document.getElementById('serverInfo').innerHTML = infoHtml;
        
        // Update status badge
        const statusEl = document.getElementById('connectionStatus');
        if (data.connection && !data.connection.includes('Not connected') && !data.connection.includes('disconnected')) {
            statusEl.textContent = 'Connected';
            statusEl.className = 'status connected';
        } else {
            statusEl.textContent = 'Disconnected';
            statusEl.className = 'status disconnected';
        }
    } catch (error) {
        console.error('Connection check failed:', error);
    }
}

// Switch server
async function switchServer() {
    const select = document.getElementById('serverSelect');
    const serverName = select.value;
    
    if (!serverName) {
        alert('Please select a server');
        return;
    }
    
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '⏳ Switching...';
    
    try {
        const response = await fetch('http://localhost:8081/api/select_server', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ identifier: serverName })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`Successfully switched to ${serverName}\n\nMachine ID: ${result.server_info.machine_id}\nHostname: ${result.server_info.hostname || 'N/A'}`);
            await loadServers();
            await checkConnection();
        } else {
            alert(`Failed to switch server:\n${result.error}`);
        }
    } catch (error) {
        alert(`Error switching server:\n${error.toString()}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Switch';
    }
}

// Export for global access
window.controlMain = {
    init,
    handleToolSelection,
    switchServer,
    getCachedRecipes,
    getCachedConversations,
    getSessionCommands,
    getBatchScripts
};