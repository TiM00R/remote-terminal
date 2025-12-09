"""
Recipe Export Tool
Exports recipes from database to bash scripts and README files in recipes/ folder
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime

def export_recipe(recipe_id: int, db_path: str = 'data/remote_terminal.db', output_dir: str = 'recipes'):
    """
    Export a recipe to bash script and README
    
    Args:
        recipe_id: Recipe ID to export
        db_path: Path to database
        output_dir: Output directory for exported files
    """
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get recipe details
    cursor.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
    recipe = cursor.fetchone()
    
    if not recipe:
        print(f"❌ Recipe {recipe_id} not found")
        conn.close()
        return False
    
    recipe_dict = dict(recipe)
    recipe_name = recipe_dict['name']
    description = recipe_dict['description']
    command_sequence = json.loads(recipe_dict['command_sequence'])
    prerequisites = recipe_dict.get('prerequisites') or 'None specified'
    success_criteria = recipe_dict.get('success_criteria') or 'None specified'
    source_conv_id = recipe_dict.get('source_conversation_id')
    created_at = recipe_dict.get('created_at')
    times_used = recipe_dict.get('times_used', 0)
    
    # Get source conversation info if available
    conv_info = {}
    if source_conv_id:
        cursor.execute("SELECT * FROM conversations WHERE id = ?", (source_conv_id,))
        conv = cursor.fetchone()
        if conv:
            conv_info = dict(conv)
    
    conn.close()
    
    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate bash script
    script_filename = f"{recipe_name}.sh"
    script_path = os.path.join(output_dir, script_filename)
    
    # Check if file exists
    if os.path.exists(script_path):
        print(f"⚠️  File already exists: {script_path}")
        overwrite = input("Overwrite? (y/n): ").lower().strip()
        if overwrite != 'y':
            print("❌ Export cancelled")
            return False
    
    # Build bash script
    script_lines = [
        "#!/bin/bash",
        f"# Recipe: {recipe_name}",
        f"# Description: {description}",
        f"# Created: {created_at}",
        f"# Times used: {times_used}",
        ""
    ]
    
    if source_conv_id and conv_info:
        script_lines.extend([
            f"# Source: Conversation #{source_conv_id}",
            f"# Goal: {conv_info.get('goal_summary', 'N/A')}",
            f"# Status: {conv_info.get('status', 'N/A')}",
            ""
        ])
    
    script_lines.extend([
        f'echo "=== {recipe_name} ==="',
        f'echo "Started: $(date)"',
        'echo ""',
        ""
    ])
    
    # Add commands
    for cmd in command_sequence:
        seq = cmd['sequence']
        total = len(command_sequence)
        
        if cmd.get('type') == 'mcp_tool' and cmd.get('tool') == 'execute_batch_script':
            # Batch script - embed the script content
            params = cmd.get('params', {})
            batch_description = params.get('description', f'Batch step {seq}')
            script_content = params.get('script_content', '')
            
            script_lines.extend([
                f'echo "=== [{seq}/{total}] {batch_description} ==="',
                "",
                "# Batch script embedded below:",
                script_content,
                "",
                f'echo "[STEP_{seq}_COMPLETE]"',
                'echo ""',
                ""
            ])
        else:
            # Regular command
            cmd_text = cmd['command']
            cmd_desc = cmd.get('description', f'Step {seq}')
            
            script_lines.extend([
                f'echo "=== [{seq}/{total}] {cmd_desc} ==="',
                cmd_text,
                f'echo "[STEP_{seq}_COMPLETE]"',
                'echo ""',
                ""
            ])
    
    script_lines.extend([
        'echo "[ALL_STEPS_COMPLETE]"',
        f'echo "Completed: $(date)"'
    ])
    
    # Write bash script
    with open(script_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(script_lines))
    
    print(f"✅ Exported script: {script_path}")
    
    # Generate README
    readme_filename = f"{recipe_name}_README.md"
    readme_path = os.path.join(output_dir, readme_filename)
    
    readme_lines = [
        f"# {recipe_name} Recipe",
        ""
    ]
    
    if source_conv_id and conv_info:
        readme_lines.extend([
            f"**Created from:** Conversation #{source_conv_id}",
            f"**Goal:** {conv_info.get('goal_summary', 'N/A')}",
            f"**Status:** {conv_info.get('status', 'N/A')}",
            f"**Created:** {created_at}",
            ""
        ])
    
    readme_lines.extend([
        "## Overview",
        "",
        description,
        "",
        "## Prerequisites",
        "",
        prerequisites,
        "",
        "## Usage",
        "",
        "### Basic Usage",
        "```bash",
        f"bash {script_filename}",
        "```",
        "",
        "### With Output Logging",
        "```bash",
        f"bash {script_filename} | tee {recipe_name}_output.txt",
        "```",
        "",
        "### With Sudo (if needed)",
        "```bash",
        f"sudo bash {script_filename}",
        "```",
        "",
        "## Steps",
        "",
        f"This recipe executes {len(command_sequence)} steps:",
        ""
    ])
    
    # List steps
    for i, cmd in enumerate(command_sequence, 1):
        if cmd.get('type') == 'mcp_tool':
            params = cmd.get('params', {})
            step_desc = params.get('description', f'Batch script step {i}')
            readme_lines.append(f"{i}. **{step_desc}** (batch script)")
        else:
            step_desc = cmd.get('description', f'Step {i}')
            readme_lines.append(f"{i}. **{step_desc}**: `{cmd['command']}`")
    
    readme_lines.extend([
        "",
        "## Success Criteria",
        "",
        success_criteria,
        "",
        "## Statistics",
        "",
        f"- **Times executed:** {times_used}",
        f"- **Last updated:** {created_at}",
        ""
    ])
    
    # Write README
    with open(readme_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(readme_lines))
    
    print(f"✅ Exported README: {readme_path}")
    
    return True


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python export_recipe.py <recipe_id>")
        print("\nAvailable recipes:")
        
        conn = sqlite3.connect('data/remote_terminal.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description FROM recipes ORDER BY id")
        recipes = cursor.fetchall()
        conn.close()
        
        if recipes:
            for r in recipes:
                print(f"  {r[0]:2d}: {r[1]} - {r[2][:60]}")
        else:
            print("  No recipes found")
        
        sys.exit(1)
    
    recipe_id = int(sys.argv[1])
    export_recipe(recipe_id)
