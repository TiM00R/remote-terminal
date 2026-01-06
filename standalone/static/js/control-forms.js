// Control Forms - Dynamic form generation from tool schemas
// Split into modules for better organization

// This file now just serves as the entry point that loads all the split modules
// The modules will export their functions to the window object for global access

// Note: The actual imports happen via script tags in the HTML file in this order:
// 1. control-forms-utils.js (utilities used by other modules)
// 2. control-forms-fields.js (field creators)
// 3. control-forms-generation.js (form generators that use fields and utils)
// 4. control-forms.js (this file - just a placeholder now)

// All functions are already exported to window object by the individual modules:
// - window.generateForm (from control-forms-generation.js)
// - window.createFormField (from control-forms-fields.js)
// - window.executeTool (from control-forms-utils.js)
// - window.showToolHelp (from control-forms-utils.js)
// - window.highlightBash (from control-forms-utils.js)
// - window.saveCursorPosition (from control-forms-utils.js)
// - window.restoreCursorPosition (from control-forms-utils.js)
