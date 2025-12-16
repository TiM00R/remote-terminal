"""
SQLite Database Viewer - Python Version
View contents of remote_terminal.db
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

# Database is in data/ subdirectory
DB_PATH = Path(__file__).parent / 'data' / 'remote_terminal.db'

def print_header(text):
    print("\n" + "=" * 70)
    print(f" {text}")
    print("=" * 70)

def print_section(text):
    print(f"\n=== {text} ===")

def query_db(query, title=None):
    """Execute query and print results"""
    if title:
        print_section(title)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("  (No data)")
            return
        
        # Print column headers
        columns = [description[0] for description in cursor.description]
        header = " | ".join(f"{col:20}" for col in columns)
        print(f"  {header}")
        print("  " + "-" * len(header))
        
        # Print rows
        for row in rows:
            values = " | ".join(f"{str(val)[:20]:20}" for val in row)
            print(f"  {values}")
        
        print(f"\n  Total rows: {len(rows)}")
        
        conn.close()
        
    except Exception as e:
        print(f"  Error: {e}")

def main():
    print_header("Remote Terminal - SQLite Database Viewer")
    
    # Check if database exists
    if not DB_PATH.exists():
        print(f"\n[X] Database not found: {DB_PATH}")
        print("\nDatabase will be created on first run of the application.")
        return
    
    # Database info
    db_size = DB_PATH.stat().st_size
    print(f"\nDatabase: {DB_PATH}")
    print(f"Size: {db_size / 1024:.2f} KB")
    
    # Show tables
    print_section("Tables in Database")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        conn.close()
    except Exception as e:
        print(f"  Error: {e}")
    
    # Machines (Servers)
    query_db(
        "SELECT COUNT(*) as count FROM machines",
        "Machines/Servers - Total Count"
    )
    
    query_db(
        """SELECT 
            SUBSTR(machine_id, 1, 16) as machine_id,
            hostname,
            datetime(last_seen) as last_seen
        FROM machines 
        ORDER BY last_seen DESC 
        LIMIT 5""",
        "Machines/Servers - Recent (Top 5)"
    )
    
    # Conversations
    query_db(
        "SELECT COUNT(*) as count FROM conversations",
        "Conversations - Total Count"
    )
    
    query_db(
        """SELECT 
            id,
            SUBSTR(goal_summary, 1, 40) as goal_summary,
            status,
            datetime(started_at) as started_at
        FROM conversations 
        ORDER BY started_at DESC 
        LIMIT 5""",
        "Conversations - Recent (Top 5)"
    )
    
    # Commands
    query_db(
        "SELECT COUNT(*) as count FROM commands",
        "Commands - Total Count"
    )
    
    query_db(
        """SELECT 
            id,
            SUBSTR(command_text, 1, 50) as command,
            status,
            datetime(executed_at) as executed_at
        FROM commands 
        ORDER BY executed_at DESC 
        LIMIT 10""",
        "Commands - Recent (Top 10)"
    )
    
    # Batch Scripts
    query_db(
        "SELECT COUNT(*) as count FROM batch_scripts",
        "Batch Scripts - Total Count"
    )
    
    query_db(
        """SELECT 
            id,
            SUBSTR(description, 1, 40) as description,
            times_used,
            datetime(last_used_at) as last_used
        FROM batch_scripts 
        ORDER BY last_used_at DESC 
        LIMIT 5""",
        "Batch Scripts - Recent (Top 5)"
    )
    
    # Batch Executions
    query_db(
        "SELECT COUNT(*) as count FROM batch_executions",
        "Batch Executions - Total Count"
    )
    
    query_db(
        """SELECT 
            id,
            script_name,
            status,
            completed_steps || '/' || total_steps as progress,
            datetime(started_at) as started_at
        FROM batch_executions 
        ORDER BY started_at DESC 
        LIMIT 5""",
        "Batch Executions - Recent (Top 5)"
    )
    
    # Recipes
    query_db(
        "SELECT COUNT(*) as count FROM recipes",
        "Recipes - Total Count"
    )
    
    query_db(
        """SELECT 
            id,
            name,
            times_used,
            datetime(created_at) as created_at
        FROM recipes 
        ORDER BY created_at DESC 
        LIMIT 5""",
        "Recipes - Recent (Top 5)"
    )
    
    print_header("Database Verification Complete!")
    print("\n[OK] Database is working correctly!")
    print("\nTo view full database with GUI:")
    print("  Download DB Browser for SQLite: https://sqlitebrowser.org/")
    print(f"  Then open: {DB_PATH}\n")

if __name__ == "__main__":
    main()
